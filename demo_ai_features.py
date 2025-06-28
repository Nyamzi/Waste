#!/usr/bin/env python3
"""
AI Analytics Demonstration Script
This script demonstrates the AI-powered analytics features of the waste management system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, WasteEntry, PickupRequest, Payment
from ai_analytics import WasteAnalyticsAI
from datetime import datetime, timedelta
import random

def create_demo_data():
    """Create comprehensive demo data for AI analysis"""
    print("🤖 Creating AI demonstration data...")
    
    # Create app context
    with app.app_context():
        # Get or create demo user
        demo_user = User.query.filter_by(username='demo_user').first()
        if not demo_user:
            print("❌ Demo user not found. Please run the main app first to create demo accounts.")
            return False
        
        # Clear existing demo data
        WasteEntry.query.filter_by(user_id=demo_user.id).delete()
        PickupRequest.query.filter_by(user_id=demo_user.id).delete()
        Payment.query.filter_by(user_id=demo_user.id).delete()
        
        # Sample data parameters
        waste_types = ['Plastic', 'Paper', 'Glass', 'Metal', 'Organic', 'Electronics']
        locations = ['Kitchen', 'Office', 'Garage', 'Garden', 'Living Room']
        
        print("📊 Generating 60 days of waste data...")
        
        # Create realistic waste patterns with trends
        for i in range(60):
            date = datetime.now() - timedelta(days=59-i)
            
            # Create seasonal patterns (more waste in certain months)
            seasonal_factor = 1.0
            if date.month in [6, 7, 8]:  # Summer - more waste
                seasonal_factor = 1.3
            elif date.month in [12, 1, 2]:  # Winter - less waste
                seasonal_factor = 0.8
            
            # Create weekly patterns (more waste on weekends)
            weekend_factor = 1.2 if date.weekday() >= 5 else 1.0
            
            # Number of entries per day (2-6)
            num_entries = random.randint(2, 6)
            
            for j in range(num_entries):
                base_weight = random.uniform(0.5, 3.0)
                adjusted_weight = base_weight * seasonal_factor * weekend_factor
                
                waste_entry = WasteEntry(
                    user_id=demo_user.id,
                    waste_type=random.choice(waste_types),
                    weight=adjusted_weight,
                    recycled=random.choice([True, False, True, True]),  # 75% recycling rate
                    location=random.choice(locations),
                    collection_date=date,
                    notes=f"AI Demo Entry {i+1}-{j+1}"
                )
                db.session.add(waste_entry)
        
        print("💰 Generating pickup requests and payments...")
        
        # Create pickup requests with payment patterns
        for i in range(25):
            request_date = datetime.now() - timedelta(days=random.randint(1, 45))
            pickup_request = PickupRequest(
                user_id=demo_user.id,
                waste_type=random.choice(waste_types),
                estimated_weight=random.uniform(2.0, 15.0),
                pickup_date=request_date + timedelta(days=1),
                pickup_time='09:00',
                address=random.choice(locations),
                status=random.choice(['pending', 'assigned', 'completed']),
                company_id=None
            )
            db.session.add(pickup_request)
            db.session.flush()
            
            # Create payment for 80% of requests
            if random.random() < 0.8:
                payment = Payment(
                    user_id=demo_user.id,
                    pickup_request_id=pickup_request.id,
                    amount=random.uniform(20.0, 80.0),
                    payment_method=random.choice(['Visa', 'Mobile Money']),
                    payment_date=request_date + timedelta(hours=random.randint(1, 6)),
                    payment_status='completed'
                )
                db.session.add(payment)
        
        db.session.commit()
        print("✅ Demo data created successfully!")
        return True

def demonstrate_ai_features():
    """Demonstrate AI analytics features"""
    print("\n🧠 Demonstrating AI Analytics Features...")
    
    # Create app context
    with app.app_context():
        # Initialize AI analytics
        ai = WasteAnalyticsAI()
        
        # Get demo user data
        demo_user = User.query.filter_by(username='demo_user').first()
        if not demo_user:
            print("❌ Demo user not found.")
            return
        
        # Get all data
        waste_entries = WasteEntry.query.filter_by(user_id=demo_user.id).all()
        payments = Payment.query.filter_by(user_id=demo_user.id).all()
        requests = PickupRequest.query.filter_by(user_id=demo_user.id).all()
        
        print(f"📈 Analyzing {len(waste_entries)} waste entries, {len(payments)} payments, and {len(requests)} requests...")
        
        # Prepare data for AI analysis
        waste_data = ai.prepare_waste_data(waste_entries)
        payment_data = ai.prepare_payment_data(payments, requests)
        
        # Generate AI insights
        insights = ai.generate_ai_insights(waste_data, payment_data, [demo_user])
        
        # Display insights
        print("\n🎯 AI-Generated Insights:")
        print("=" * 50)
        
        # Trend Analysis
        if insights['trend_analysis']:
            trend = insights['trend_analysis']
            print(f"📊 Trend Direction: {trend.get('trend_direction', 'stable').title()}")
            print(f"♻️  Recycling Rate: {trend.get('recycling_rate', 0):.1f}%")
            print(f"🗑️  Top Waste Types: {len(trend.get('top_waste_types', {}))}")
            print(f"📅 Seasonal Patterns: {len(trend.get('seasonal_patterns', {}))} months")
        
        # Waste Prediction
        if insights['waste_prediction']:
            print(f"\n🔮 Waste Generation Forecast:")
            total_predicted = sum(p['predicted_weight'] for p in insights['waste_prediction'])
            print(f"   📈 Total predicted waste (30 days): {total_predicted:.1f} kg")
            print(f"   📊 Average daily prediction: {total_predicted/30:.1f} kg")
        
        # Revenue Forecast
        if insights['revenue_forecast']:
            print(f"\n💰 Revenue Forecast:")
            total_revenue = sum(r['predicted_revenue'] for r in insights['revenue_forecast'])
            print(f"   💵 Total predicted revenue (30 days): ${total_revenue:.2f}")
            print(f"   📈 Average daily revenue: ${total_revenue/30:.2f}")
        
        # Customer Segmentation
        if insights['customer_segments']:
            print(f"\n👥 Customer Segmentation:")
            for segment in insights['customer_segments']:
                print(f"   🏷️  {segment['segment_name']}: {segment['total_waste']:.1f} kg waste, ${segment['total_spent']:.2f} spent")
        
        # Recommendations
        if insights['recommendations']:
            print(f"\n💡 AI Recommendations:")
            for i, rec in enumerate(insights['recommendations'], 1):
                print(f"   {i}. {rec['title']} ({rec['priority']} priority)")
                print(f"      {rec['description']}")
        
        print("\n" + "=" * 50)
        print("🎉 AI Analytics demonstration completed!")
        print("\n💡 To see interactive visualizations, visit:")
        print("   - User AI Analytics: http://127.0.0.1:5000/ai_analytics")
        print("   - Company AI Analytics: http://127.0.0.1:5000/company_ai_analytics")

def main():
    """Main demonstration function"""
    print("🚀 AI-Powered Waste Management System - Analytics Demo")
    print("=" * 60)
    
    # Create demo data
    if create_demo_data():
        # Demonstrate AI features
        demonstrate_ai_features()
    else:
        print("❌ Failed to create demo data. Please ensure the main app is running first.")

if __name__ == "__main__":
    main() 