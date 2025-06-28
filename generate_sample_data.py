from app import app, db, User, WasteEntry, PickupRequest, Payment, CollectionSchedule
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, date
import random
import string
from faker import Faker

fake = Faker()

def generate_sample_data():
    """Generate comprehensive sample data for the waste management system"""
    
    with app.app_context():
        # Clear existing data (except admin users)
        print("Clearing existing sample data...")
        Payment.query.delete()
        PickupRequest.query.delete()
        WasteEntry.query.delete()
        CollectionSchedule.query.delete()
        
        # Keep admin users but clear regular users and companies
        admin_users = User.query.filter_by(role='admin').all()
        User.query.filter(User.role != 'admin').delete()
        
        print("Generating sample data...")
        
        # Generate regular users
        users = []
        for i in range(50):  # 50 regular users
            user = User(
                username=f"user{i+1}",
                email=f"user{i+1}@example.com",
                password_hash=generate_password_hash("password123"),
                role="user",
                address=fake.address(),
                phone=fake.phone_number(),
                created_at=fake.date_time_between(start_date='-1y', end_date='now')
            )
            users.append(user)
            db.session.add(user)
        
        # Generate companies
        companies = []
        company_names = [
            "EcoWaste Solutions", "GreenClean Services", "WastePro Management",
            "CleanEarth Co.", "Sustainable Waste", "EcoDisposal Ltd",
            "GreenCollection", "WasteWise Partners", "CleanFuture Inc",
            "EcoManagement Group"
        ]
        
        for i, name in enumerate(company_names):
            company = User(
                username=f"company{i+1}",
                email=f"contact@{name.lower().replace(' ', '').replace('.', '').replace(',', '')}.com",
                password_hash=generate_password_hash("password123"),
                role="company",
                address=fake.address(),
                phone=fake.phone_number(),
                created_at=fake.date_time_between(start_date='-2y', end_date='-6m')
            )
            companies.append(company)
            db.session.add(company)
        
        db.session.commit()
        print(f"Created {len(users)} users and {len(companies)} companies")
        
        # Generate waste entries with realistic patterns
        waste_types = ['Plastic', 'Paper', 'Glass', 'Metal', 'Organic', 'Electronic', 'Textile', 'Construction']
        locations = ['Kitchen', 'Office', 'Garage', 'Garden', 'Workshop', 'Warehouse', 'Restaurant', 'Retail']
        
        waste_entries = []
        for user in users:
            # Each user has 10-50 waste entries over the past year
            num_entries = random.randint(10, 50)
            
            for _ in range(num_entries):
                entry_date = fake.date_time_between(
                    start_date=user.created_at,
                    end_date='now'
                )
                
                # Seasonal patterns - more waste in certain months
                month = entry_date.month
                if month in [6, 7, 8]:  # Summer - more organic waste
                    waste_type_weights = {'Organic': 0.3, 'Plastic': 0.2, 'Paper': 0.15, 'Glass': 0.1, 'Metal': 0.1, 'Electronic': 0.05, 'Textile': 0.05, 'Construction': 0.05}
                elif month in [11, 12, 1]:  # Winter - more paper and construction
                    waste_type_weights = {'Paper': 0.25, 'Construction': 0.2, 'Plastic': 0.15, 'Organic': 0.15, 'Glass': 0.1, 'Metal': 0.1, 'Electronic': 0.03, 'Textile': 0.02}
                else:  # Regular months
                    waste_type_weights = {'Plastic': 0.25, 'Paper': 0.2, 'Organic': 0.15, 'Glass': 0.15, 'Metal': 0.1, 'Electronic': 0.05, 'Textile': 0.05, 'Construction': 0.05}
                
                waste_type = random.choices(list(waste_type_weights.keys()), weights=list(waste_type_weights.values()))[0]
                
                # Weight varies by waste type
                if waste_type == 'Organic':
                    weight = random.uniform(0.5, 5.0)
                elif waste_type == 'Construction':
                    weight = random.uniform(1.0, 20.0)
                elif waste_type == 'Electronic':
                    weight = random.uniform(0.1, 2.0)
                else:
                    weight = random.uniform(0.1, 3.0)
                
                entry = WasteEntry(
                    user_id=user.id,
                    waste_type=waste_type,
                    weight=round(weight, 2),
                    collection_date=entry_date,
                    location=random.choice(locations),
                    notes=fake.sentence(),
                    recycled=random.random() < 0.4  # 40% chance of being recycled
                )
                waste_entries.append(entry)
                db.session.add(entry)
        
        db.session.commit()
        print(f"Created {len(waste_entries)} waste entries")
        
        # Generate pickup requests
        pickup_requests = []
        for user in users:
            # Each user has 2-8 pickup requests
            num_requests = random.randint(2, 8)
            
            for _ in range(num_requests):
                request_date = fake.date_time_between(
                    start_date=user.created_at,
                    end_date='now'
                )
                
                # Pickup date is 1-14 days after request
                pickup_date = request_date.date() + timedelta(days=random.randint(1, 14))
                
                # Status distribution
                status_weights = {'completed': 0.6, 'accepted': 0.2, 'pending': 0.15, 'cancelled': 0.05}
                status = random.choices(list(status_weights.keys()), weights=list(status_weights.values()))[0]
                
                # Assign company for accepted/completed requests
                company_id = None
                if status in ['accepted', 'completed']:
                    company_id = random.choice(companies).id
                
                # Price calculation
                estimated_weight = random.uniform(5.0, 50.0)
                base_price = estimated_weight * random.uniform(2.0, 5.0)  # $2-5 per kg
                price = round(base_price, 2)
                
                request = PickupRequest(
                    user_id=user.id,
                    company_id=company_id,
                    waste_type=random.choice(waste_types),
                    estimated_weight=round(estimated_weight, 2),
                    pickup_date=pickup_date,
                    pickup_time=f"{random.randint(8, 18):02d}:{random.choice(['00', '30'])}",
                    address=user.address,
                    notes=fake.sentence(),
                    status=status,
                    price=price,
                    created_at=request_date,
                    completed_at=request_date + timedelta(days=random.randint(1, 7)) if status == 'completed' else None
                )
                pickup_requests.append(request)
                db.session.add(request)
        
        db.session.commit()
        print(f"Created {len(pickup_requests)} pickup requests")
        
        # Generate payments
        payments = []
        payment_methods = ['visa', 'mobile_money']
        mobile_providers = ['mpesa', 'airtel_money', 'mtn_momo', 'orange_money']
        
        for request in pickup_requests:
            if request.status in ['accepted', 'completed']:
                payment_method = random.choice(payment_methods)
                
                if payment_method == 'visa':
                    payment = Payment(
                        user_id=request.user_id,
                        pickup_request_id=request.id,
                        amount=request.price,
                        payment_method=payment_method,
                        payment_status='completed',
                        transaction_id=f"TXN{random.randint(100000, 999999)}",
                        payment_date=request.created_at + timedelta(hours=random.randint(1, 24)),
                        card_last4=str(random.randint(1000, 9999)),
                        card_holder=fake.name(),
                        billing_address=request.address
                    )
                else:  # mobile_money
                    payment = Payment(
                        user_id=request.user_id,
                        pickup_request_id=request.id,
                        amount=request.price,
                        payment_method=payment_method,
                        payment_status='completed',
                        transaction_id=f"MM{random.randint(100000, 999999)}",
                        payment_date=request.created_at + timedelta(hours=random.randint(1, 24)),
                        mobile_provider=random.choice(mobile_providers),
                        phone_number=fake.phone_number(),
                        account_name=fake.name()
                    )
                
                payments.append(payment)
                db.session.add(payment)
        
        db.session.commit()
        print(f"Created {len(payments)} payments")
        
        # Generate collection schedules
        schedules = []
        for company in companies:
            for waste_type in waste_types[:5]:  # First 5 waste types
                for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                    schedule = CollectionSchedule(
                        waste_type=waste_type,
                        collection_day=day,
                        collection_time=f"{random.randint(8, 16):02d}:00",
                        location=fake.city(),
                        active=random.random() < 0.8  # 80% active
                    )
                    schedules.append(schedule)
                    db.session.add(schedule)
        
        db.session.commit()
        print(f"Created {len(schedules)} collection schedules")
        
        print("\n=== Sample Data Generation Complete ===")
        print(f"Users: {len(users)}")
        print(f"Companies: {len(companies)}")
        print(f"Waste Entries: {len(waste_entries)}")
        print(f"Pickup Requests: {len(pickup_requests)}")
        print(f"Payments: {len(payments)}")
        print(f"Collection Schedules: {len(schedules)}")
        
        # Print some statistics
        total_waste = sum(entry.weight for entry in waste_entries)
        recycled_waste = sum(entry.weight for entry in waste_entries if entry.recycled)
        recycling_rate = (recycled_waste / total_waste * 100) if total_waste > 0 else 0
        
        print(f"\n=== Statistics ===")
        print(f"Total Waste: {total_waste:.2f} kg")
        print(f"Recycled Waste: {recycled_waste:.2f} kg")
        print(f"Recycling Rate: {recycling_rate:.1f}%")
        
        # Waste by type
        waste_by_type = {}
        for entry in waste_entries:
            if entry.waste_type not in waste_by_type:
                waste_by_type[entry.waste_type] = 0
            waste_by_type[entry.waste_type] += entry.weight
        
        print(f"\nWaste by Type:")
        for waste_type, weight in sorted(waste_by_type.items(), key=lambda x: x[1], reverse=True):
            print(f"  {waste_type}: {weight:.2f} kg")
        
        # Request status distribution
        status_counts = {}
        for request in pickup_requests:
            if request.status not in status_counts:
                status_counts[request.status] = 0
            status_counts[request.status] += 1
        
        print(f"\nPickup Request Status:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        
        # Payment method distribution
        payment_method_counts = {}
        for payment in payments:
            if payment.payment_method not in payment_method_counts:
                payment_method_counts[payment.payment_method] = 0
            payment_method_counts[payment.payment_method] += 1
        
        print(f"\nPayment Methods:")
        for method, count in payment_method_counts.items():
            print(f"  {method}: {count}")

if __name__ == "__main__":
    generate_sample_data() 