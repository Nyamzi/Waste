from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import os
from dotenv import load_dotenv
from ai_analytics import WasteAnalyticsAI
import googlemaps
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///waste_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Google Maps configuration
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'your-google-maps-api-key')
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY) if GOOGLE_MAPS_API_KEY != 'your-google-maps-api-key' else None

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize AI Analytics
ai_analytics = WasteAnalyticsAI()

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # user, company, admin
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.now)
    waste_entries = db.relationship('WasteEntry', backref='user', lazy=True)
    pickup_requests = db.relationship('PickupRequest', foreign_keys='PickupRequest.user_id', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)
    assigned_requests = db.relationship('PickupRequest', foreign_keys='PickupRequest.company_id', backref='company', lazy=True)

class WasteEntry(db.Model):
    __tablename__ = 'waste_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    waste_type = db.Column(db.String(50), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    collection_date = db.Column(db.DateTime, default=datetime.now)
    location = db.Column(db.String(100))
    notes = db.Column(db.Text)
    recycled = db.Column(db.Boolean, default=False)

class PickupRequest(db.Model):
    __tablename__ = 'pickup_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Reference users table for companies
    waste_type = db.Column(db.String(50), nullable=False)
    estimated_weight = db.Column(db.Float, nullable=False)
    pickup_date = db.Column(db.Date, nullable=False)
    pickup_time = db.Column(db.String(10), nullable=False)  # HH:MM
    address = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed, cancelled
    price = db.Column(db.Float, default=0.0)  # Price for the pickup service
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime, nullable=True)
    payment = db.relationship('Payment', backref='pickup_request', uselist=False)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pickup_request_id = db.Column(db.Integer, db.ForeignKey('pickup_requests.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # visa, mobile_money
    payment_status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    transaction_id = db.Column(db.String(100), unique=True)
    payment_date = db.Column(db.DateTime, default=datetime.now)
    
    # Visa card fields
    card_last4 = db.Column(db.String(4))  # Last 4 digits of card
    card_holder = db.Column(db.String(100))  # Cardholder name
    billing_address = db.Column(db.String(200))
    
    # Mobile money fields
    mobile_provider = db.Column(db.String(50))  # mpesa, airtel_money, mtn_momo, etc.
    phone_number = db.Column(db.String(20))
    account_name = db.Column(db.String(100))

class CollectionSchedule(db.Model):
    __tablename__ = 'collection_schedules'
    id = db.Column(db.Integer, primary_key=True)
    waste_type = db.Column(db.String(50), nullable=False)
    collection_day = db.Column(db.String(20), nullable=False)
    collection_time = db.Column(db.String(10), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'company':
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('customer_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.role == 'company':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# User Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'company':
        # Company dashboard - use the current dashboard template with company data
        # Get company's pickup requests
        pickup_requests = PickupRequest.query.filter_by(company_id=current_user.id).order_by(PickupRequest.created_at.desc()).all()
        
        # Calculate statistics
        total_requests = len(pickup_requests)
        pending_requests = len([r for r in pickup_requests if r.status == 'pending'])
        completed_requests = len([r for r in pickup_requests if r.status == 'completed'])
        
        # Calculate total revenue from completed requests with payments
        total_revenue = sum(
            request.price for request in pickup_requests 
            if request.status == 'completed' and request.payment and request.payment.payment_status == 'completed'
        )
        
        # Calculate additional analytics for companies
        avg_request_value = total_revenue / completed_requests if completed_requests > 0 else 0
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Get unique customers
        unique_customers = set(request.user_id for request in pickup_requests)
        total_customers = len(unique_customers)
        
        # Calculate average response time (time from request creation to acceptance)
        response_times = []
        for request in pickup_requests:
            if request.status in ['accepted', 'completed'] and request.created_at:
                # For demo purposes, assume 2-8 hours response time
                import random
                response_time = random.uniform(2, 8)
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 4.5
        
        # Get waste by type for company's requests
        waste_by_type = {}
        for request in pickup_requests:
            if request.waste_type not in waste_by_type:
                waste_by_type[request.waste_type] = 0
            waste_by_type[request.waste_type] += request.estimated_weight
        
        # Get requests by status
        requests_by_status = {
            'pending': len([r for r in pickup_requests if r.status == 'pending']),
            'accepted': len([r for r in pickup_requests if r.status == 'accepted']),
            'completed': len([r for r in pickup_requests if r.status == 'completed']),
            'cancelled': len([r for r in pickup_requests if r.status == 'cancelled'])
        }
        
        return render_template('dashboard.html',
                             pickup_requests=pickup_requests,
                             total_requests=total_requests,
                             pending_requests=pending_requests,
                             completed_requests=completed_requests,
                             total_revenue=total_revenue,
                             avg_request_value=avg_request_value,
                             completion_rate=completion_rate,
                             total_customers=total_customers,
                             avg_response_time=avg_response_time,
                             waste_by_type=waste_by_type,
                             requests_by_status=requests_by_status,
                             is_company=True)
    else:
        # Customer dashboard - redirect to new customer dashboard
        return redirect(url_for('customer_dashboard'))

@app.route('/customer_dashboard')
@login_required
def customer_dashboard():
    if current_user.role == 'company':
        return redirect(url_for('dashboard'))
    
    # Get user's waste data
    user_waste = WasteEntry.query.filter_by(user_id=current_user.id).all()
    
    # Calculate statistics
    total_waste = sum(entry.weight for entry in user_waste)
    recycled_waste = sum(entry.weight for entry in user_waste if entry.recycled)
    recycling_rate = (recycled_waste / total_waste * 100) if total_waste > 0 else 0
    
    # Get waste by type
    waste_by_type = {}
    for entry in user_waste:
        if entry.waste_type not in waste_by_type:
            waste_by_type[entry.waste_type] = 0
        waste_by_type[entry.waste_type] += entry.weight
    
    # Get recent entries
    recent_entries = WasteEntry.query.filter_by(user_id=current_user.id).order_by(WasteEntry.collection_date.desc()).limit(5).all()
    
    # Get user's pickup requests
    pickup_requests = PickupRequest.query.filter_by(user_id=current_user.id).order_by(PickupRequest.created_at.desc()).limit(5).all()
    
    # Calculate total payments
    total_payments = sum(request.price for request in pickup_requests if request.payment and request.payment.payment_status == 'completed')
    
    return render_template('customer_dashboard.html',
                         total_waste=total_waste,
                         recycled_waste=recycled_waste,
                         recycling_rate=recycling_rate,
                         waste_by_type=waste_by_type,
                         recent_entries=recent_entries,
                         pickup_requests=pickup_requests,
                         total_payments=total_payments,
                         user=current_user)

# Company Dashboard
@app.route('/company_dashboard')
@login_required
def company_dashboard():
    # Redirect to main dashboard which now handles both user and company views
    return redirect(url_for('dashboard'))

@app.route('/add_waste', methods=['GET', 'POST'])
@login_required
def add_waste():
    if current_user.role == 'company':
        return redirect(url_for('company_dashboard'))
        
    if request.method == 'POST':
        waste_type = request.form.get('waste_type')
        weight = float(request.form.get('weight'))
        location = request.form.get('location')
        notes = request.form.get('notes')
        recycled = 'recycled' in request.form
        
        entry = WasteEntry(
            user_id=current_user.id,
            waste_type=waste_type,
            weight=weight,
            location=location,
            notes=notes,
            recycled=recycled
        )
        db.session.add(entry)
        db.session.commit()
        
        flash('Waste entry added successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('add_waste.html', now=datetime.now())

# Pickup Request Routes
@app.route('/request_pickup', methods=['GET', 'POST'])
@login_required
def request_pickup():
    if current_user.role == 'company':
        return redirect(url_for('company_dashboard'))
        
    if request.method == 'POST':
        waste_type = request.form.get('waste_type')
        estimated_weight = float(request.form.get('estimated_weight'))
        pickup_date = datetime.strptime(request.form.get('pickup_date'), '%Y-%m-%d').date()
        pickup_time = request.form.get('pickup_time')
        address = request.form.get('address')
        notes = request.form.get('notes')
        
        # Calculate price based on waste type and weight
        base_prices = {
            'plastic': 5.0,
            'paper': 3.0,
            'glass': 4.0,
            'metal': 6.0,
            'organic': 2.0,
            'electronics': 15.0,
            'textiles': 4.0,
            'hazardous': 25.0,
            'construction': 20.0,
            'furniture': 30.0,
            'other': 5.0
        }
        
        base_price = base_prices.get(waste_type, 5.0)
        price = base_price + (estimated_weight * 0.5)  # $0.50 per kg
        
        # Find available companies (in real app, you'd match by location/service area)
        available_companies = User.query.filter_by(role='company').all()
        assigned_company = None
        
        if available_companies:
            # For demo purposes, assign to the first available company
            # In a real app, you'd match by location, service area, availability, etc.
            assigned_company = available_companies[0]
        
        request_obj = PickupRequest(
            user_id=current_user.id,
            company_id=assigned_company.id if assigned_company else None,
            waste_type=waste_type,
            estimated_weight=estimated_weight,
            pickup_date=pickup_date,
            pickup_time=pickup_time,
            address=address,
            notes=notes,
            price=price
        )
        db.session.add(request_obj)
        db.session.commit()
        
        flash(f'Pickup request submitted successfully! Estimated cost: ${price:.2f}')
        return redirect(url_for('payment', request_id=request_obj.id))
    
    return render_template('request_pickup.html', now=datetime.now())

@app.route('/payment/<int:request_id>', methods=['GET', 'POST'])
@login_required
def payment(request_id):
    if current_user.role == 'company':
        return redirect(url_for('company_dashboard'))
    
    pickup_request = PickupRequest.query.get_or_404(request_id)
    
    # Ensure the request belongs to the current user
    if pickup_request.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        
        # Generate a simple transaction ID (in real app, use proper payment gateway)
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{pickup_request.id}"
        
        # Initialize payment object
        payment = Payment(
            user_id=current_user.id,
            pickup_request_id=pickup_request.id,
            amount=pickup_request.price,
            payment_method=payment_method,
            payment_status='completed',  # In real app, verify with payment gateway
            transaction_id=transaction_id
        )
        
        # Handle Visa card payment
        if payment_method == 'visa':
            card_number = request.form.get('card_number')
            card_holder = request.form.get('card_holder')
            billing_address = request.form.get('billing_address')
            
            payment.card_last4 = card_number[-4:] if card_number else None
            payment.card_holder = card_holder
            payment.billing_address = billing_address
            
            flash('Visa payment completed successfully! Your pickup request has been confirmed.')
        
        # Handle mobile money payment
        elif payment_method == 'mobile_money':
            mobile_provider = request.form.get('mobile_provider')
            phone_number = request.form.get('phone_number')
            account_name = request.form.get('account_name')
            
            payment.mobile_provider = mobile_provider
            payment.phone_number = phone_number
            payment.account_name = account_name
            
            # Simulate mobile money payment process
            provider_names = {
                'mpesa': 'M-Pesa',
                'airtel_money': 'Airtel Money',
                'mtn_momo': 'MTN Mobile Money',
                'vodafone_cash': 'Vodafone Cash',
                'orange_money': 'Orange Money',
                'other': 'Mobile Money'
            }
            
            provider_name = provider_names.get(mobile_provider, 'Mobile Money')
            flash(f'{provider_name} payment completed successfully! Your pickup request has been confirmed.')
        
        db.session.add(payment)
        db.session.commit()
        
        return redirect(url_for('dashboard'))
    
    return render_template('payment.html', pickup_request=pickup_request)

@app.route('/pickup_requests')
@login_required
def pickup_requests():
    if current_user.role == 'company':
        requests = PickupRequest.query.filter_by(company_id=current_user.id).order_by(PickupRequest.created_at.desc()).all()
    else:
        requests = PickupRequest.query.filter_by(user_id=current_user.id).order_by(PickupRequest.created_at.desc()).all()
    
    return render_template('pickup_requests.html', requests=requests)

@app.route('/update_request_status/<int:request_id>', methods=['POST'])
@login_required
def update_request_status(request_id):
    if current_user.role != 'company':
        flash('Access denied')
        return redirect(url_for('dashboard'))
    
    pickup_request = PickupRequest.query.get_or_404(request_id)
    new_status = request.form.get('status')
    
    if new_status in ['accepted', 'completed', 'cancelled']:
        pickup_request.status = new_status
        if new_status == 'completed':
            pickup_request.completed_at = datetime.now()
        db.session.commit()
        flash(f'Request status updated to {new_status}')
    
    return redirect(url_for('company_dashboard'))

@app.route('/analytics')
@login_required
def analytics():
    """Redirect all users to company dashboard - analytics are company-only"""
    return redirect(url_for('dashboard'))

@app.route('/schedule')
@login_required
def schedule():
    schedules = CollectionSchedule.query.filter_by(active=True).all()
    return render_template('schedule.html', schedules=schedules)

@app.route('/api/waste_stats')
@login_required
def waste_stats():
    if current_user.role == 'company':
        return jsonify({'error': 'Not available for companies'})
        
    # Get user's waste statistics
    user_waste = WasteEntry.query.filter_by(user_id=current_user.id).all()
    
    total_waste = sum(entry.weight for entry in user_waste)
    recycled_waste = sum(entry.weight for entry in user_waste if entry.recycled)
    recycling_rate = (recycled_waste / total_waste * 100) if total_waste > 0 else 0
    
    return jsonify({
        'total_waste': total_waste,
        'recycled_waste': recycled_waste,
        'recycling_rate': recycling_rate
    })

@app.route('/ai_analytics')
@login_required
def ai_analytics_dashboard():
    """Redirect all users to company AI analytics - AI analytics are company-only"""
    return redirect(url_for('company_ai_analytics'))

@app.route('/company_ai_analytics')
@login_required
def company_ai_analytics():
    """Advanced AI-powered analytics dashboard for companies only"""
    if current_user.role != 'company':
        flash('Access denied. This feature is only available for companies.')
        return redirect(url_for('dashboard'))
    
    # Get all data for comprehensive company analysis
    all_waste = WasteEntry.query.all()
    all_payments = Payment.query.all()
    all_requests = PickupRequest.query.all()
    all_users = User.query.filter_by(role='user').all()
    
    # Get company's assigned requests
    company_requests = PickupRequest.query.filter_by(company_id=current_user.id).all()
    company_payments = []
    
    for request in company_requests:
        if request.payment:
            company_payments.append(request.payment)
    
    # Prepare data for AI analysis
    waste_data = ai_analytics.prepare_waste_data(all_waste)
    payment_data = ai_analytics.prepare_payment_data(company_payments, company_requests)
    
    # Generate comprehensive AI insights
    insights = ai_analytics.generate_ai_insights(waste_data, payment_data, all_users)
    charts = ai_analytics.create_ai_dashboard_charts(insights)
    
    return render_template('company_ai_analytics.html',
                         insights=insights,
                         charts=charts,
                         company=current_user)

@app.route('/api/ai_insights')
@login_required
def api_ai_insights():
    """API endpoint for AI insights - companies only"""
    if current_user.role != 'company':
        return jsonify({'error': 'Access denied. This feature is only available for companies.'}), 403
    
    # Company insights only
    all_waste = WasteEntry.query.all()
    all_payments = Payment.query.all()
    all_requests = PickupRequest.query.all()
    all_users = User.query.filter_by(role='user').all()
    
    company_requests = PickupRequest.query.filter_by(company_id=current_user.id).all()
    company_payments = [req.payment for req in company_requests if req.payment]
    
    waste_data = ai_analytics.prepare_waste_data(all_waste)
    payment_data = ai_analytics.prepare_payment_data(company_payments, company_requests)
    insights = ai_analytics.generate_ai_insights(waste_data, payment_data, all_users)
    
    return jsonify(insights)

# Google Maps Routes
@app.route('/maps')
@login_required
def maps_dashboard():
    """Google Maps dashboard for location-based services"""
    return render_template('maps_dashboard.html', api_key=GOOGLE_MAPS_API_KEY)

@app.route('/api/geocode')
@login_required
def geocode_address():
    """Geocode an address to get coordinates"""
    if not gmaps:
        return jsonify({'error': 'Google Maps API not configured'}), 400
    
    address = request.args.get('address')
    if not address:
        return jsonify({'error': 'Address parameter required'}), 400
    
    try:
        # Geocode the address
        geocode_result = gmaps.geocode(address)
        
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            return jsonify({
                'lat': location['lat'],
                'lng': location['lng'],
                'formatted_address': geocode_result[0]['formatted_address']
            })
        else:
            return jsonify({'error': 'Address not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/distance')
@login_required
def calculate_distance():
    """Calculate distance between two locations"""
    if not gmaps:
        return jsonify({'error': 'Google Maps API not configured'}), 400
    
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    
    if not origin or not destination:
        return jsonify({'error': 'Origin and destination parameters required'}), 400
    
    try:
        # Calculate distance and duration
        distance_result = gmaps.distance_matrix(origin, destination, mode="driving")
        
        if distance_result['rows'][0]['elements'][0]['status'] == 'OK':
            element = distance_result['rows'][0]['elements'][0]
            return jsonify({
                'distance': element['distance']['text'],
                'duration': element['duration']['text'],
                'distance_meters': element['distance']['value'],
                'duration_seconds': element['duration']['value']
            })
        else:
            return jsonify({'error': 'Could not calculate route'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/nearby_companies')
@login_required
def find_nearby_companies():
    """Find waste management companies near a location"""
    if not gmaps:
        return jsonify({'error': 'Google Maps API not configured'}), 400
    
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    radius = request.args.get('radius', 5000)  # Default 5km radius
    
    if not lat or not lng:
        return jsonify({'error': 'Latitude and longitude parameters required'}), 400
    
    try:
        # Search for waste management companies
        location = f"{lat},{lng}"
        places_result = gmaps.places_nearby(
            location=location,
            radius=radius,
            type='business',
            keyword='waste management'
        )
        
        companies = []
        for place in places_result.get('results', []):
            companies.append({
                'name': place['name'],
                'address': place.get('vicinity', ''),
                'rating': place.get('rating', 0),
                'lat': place['geometry']['location']['lat'],
                'lng': place['geometry']['location']['lng'],
                'place_id': place['place_id']
            })
        
        return jsonify({'companies': companies})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/route_optimization')
@login_required
def optimize_route():
    """Optimize pickup route for multiple locations"""
    if not gmaps:
        return jsonify({'error': 'Google Maps API not configured'}), 400
    
    if current_user.role != 'company':
        return jsonify({'error': 'Access denied'}), 403
    
    # Get company's pending pickup requests
    pickup_requests = PickupRequest.query.filter_by(
        company_id=current_user.id, 
        status='accepted'
    ).all()
    
    if not pickup_requests:
        return jsonify({'error': 'No pickup requests to optimize'}), 400
    
    try:
        # Prepare waypoints for route optimization
        waypoints = []
        for request in pickup_requests:
            # Geocode the address
            geocode_result = gmaps.geocode(request.address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                waypoints.append(f"{location['lat']},{location['lng']}")
        
        if len(waypoints) < 2:
            return jsonify({'error': 'Need at least 2 locations for route optimization'}), 400
        
        # Get company's location (you might want to store this in the database)
        company_location = "0,0"  # Default, should be company's actual location
        
        # Calculate optimized route
        directions_result = gmaps.directions(
            origin=company_location,
            destination=waypoints[-1],
            waypoints=waypoints[:-1],
            optimize_waypoints=True,
            mode="driving"
        )
        
        if directions_result:
            route = directions_result[0]
            optimized_waypoints = route['waypoint_order']
            
            # Reorder pickup requests according to optimized route
            optimized_requests = []
            for i in optimized_waypoints:
                optimized_requests.append({
                    'request_id': pickup_requests[i].id,
                    'address': pickup_requests[i].address,
                    'waste_type': pickup_requests[i].waste_type,
                    'estimated_weight': pickup_requests[i].estimated_weight,
                    'customer': pickup_requests[i].user.username
                })
            
            return jsonify({
                'optimized_route': optimized_requests,
                'total_distance': route['legs'][0]['distance']['text'],
                'total_duration': route['legs'][0]['duration']['text']
            })
        else:
            return jsonify({'error': 'Could not optimize route'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        # Check if database exists and create tables if needed
        try:
            db.create_all()
        except Exception as e:
            print(f"Database initialization note: {e}")
            # Continue anyway, tables might already exist
        
        # Create admin user if it doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@wastemanagement.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
        
        # Create demo company if it doesn't exist
        demo_company = User.query.filter_by(username='demo_company').first()
        if not demo_company:
            demo_company = User(
                username='demo_company',
                email='company@demo.com',
                password_hash=generate_password_hash('company123'),
                role='company',
                phone='555-0123'
            )
            db.session.add(demo_company)
            db.session.commit()
            print("Demo company created successfully!")
        
        # Create sample waste entries for AI demonstration
        import random
        
        # Sample waste types and weights for realistic data
        waste_types = ['Plastic', 'Paper', 'Glass', 'Metal', 'Organic', 'Electronics']
        locations = ['Kitchen', 'Office', 'Garage', 'Garden', 'Living Room']
        
        # Create sample data for the last 30 days
        for i in range(30):
            date = datetime.now() - timedelta(days=29-i)
            # Create 2-5 entries per day for realistic patterns
            for j in range(random.randint(2, 5)):
                waste_entry = WasteEntry(
                    user_id=1,  # demo user
                    waste_type=random.choice(waste_types),
                    weight=random.uniform(0.5, 5.0),
                    recycled=random.choice([True, False]),
                    location=random.choice(locations),
                    collection_date=date,
                    notes=f"Sample entry {i+1}-{j+1}"
                )
                db.session.add(waste_entry)
        
        # Create sample pickup requests and payments
        for i in range(15):
            request_date = datetime.now() - timedelta(days=random.randint(1, 28))
            pickup_request = PickupRequest(
                user_id=1,
                waste_type=random.choice(waste_types),
                estimated_weight=random.uniform(2.0, 10.0),
                pickup_date=request_date + timedelta(days=1),
                pickup_time='09:00',
                address=random.choice(locations),
                status=random.choice(['pending', 'assigned', 'completed']),
                company_id=2 if random.choice([True, False]) else None
            )
            db.session.add(pickup_request)
            db.session.flush()  # Get the ID
            
            # Create payment for some requests
            if random.choice([True, False]):
                payment = Payment(
                    user_id=1,
                    pickup_request_id=pickup_request.id,
                    amount=random.uniform(15.0, 50.0),
                    payment_method=random.choice(['Visa', 'Mobile Money']),
                    payment_date=request_date + timedelta(hours=random.randint(1, 6)),
                    payment_status='completed'
                )
                db.session.add(payment)
        
        db.session.commit()
        print("Sample AI demonstration data created successfully!")
    
    app.run(debug=True) 