import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import plotly.utils

class WasteAnalyticsAI:
    def __init__(self):
        self.waste_prediction_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.revenue_prediction_model = LinearRegression()
        self.customer_segmentation_model = KMeans(n_clusters=4, random_state=42)
        self.scaler = StandardScaler()
        self.models_trained = False
        
    def prepare_waste_data(self, waste_entries):
        """Prepare waste data for AI analysis"""
        if not waste_entries:
            return pd.DataFrame()
            
        data = []
        for entry in waste_entries:
            data.append({
                'user_id': entry.user_id,
                'date': entry.collection_date,
                'waste_type': entry.waste_type,
                'weight': entry.weight,
                'recycled': entry.recycled,
                'location': entry.location,
                'day_of_week': entry.collection_date.weekday(),
                'month': entry.collection_date.month,
                'year': entry.collection_date.year,
                'is_weekend': entry.collection_date.weekday() >= 5
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
        return df
    
    def prepare_payment_data(self, payments, pickup_requests):
        """Prepare payment and request data for revenue analysis"""
        if not payments or not pickup_requests:
            return pd.DataFrame()
            
        data = []
        for payment in payments:
            request = next((r for r in pickup_requests if r.id == payment.pickup_request_id), None)
            if request:
                data.append({
                    'user_id': payment.user_id,
                    'date': payment.payment_date,
                    'amount': payment.amount,
                    'payment_method': payment.payment_method,
                    'waste_type': request.waste_type,
                    'weight': request.estimated_weight,
                    'status': request.status,
                    'payment_status': payment.payment_status,
                    'day_of_week': payment.payment_date.weekday(),
                    'month': payment.payment_date.month,
                    'year': payment.payment_date.year
                })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
        return df
    
    def train_waste_prediction_model(self, waste_data):
        """Train AI model to predict future waste generation"""
        if waste_data.empty:
            return False
            
        # Create features for prediction
        waste_data['days_since_start'] = (waste_data['date'] - waste_data['date'].min()).dt.days
        
        # Aggregate by date
        daily_waste = waste_data.groupby('date').agg({
            'weight': 'sum',
            'recycled': lambda x: (x == True).sum(),
            'waste_type': 'count'
        }).reset_index()
        
        daily_waste['days_since_start'] = (daily_waste['date'] - daily_waste['date'].min()).dt.days
        daily_waste['day_of_week'] = daily_waste['date'].dt.weekday
        daily_waste['month'] = daily_waste['date'].dt.month
        
        if len(daily_waste) < 7:  # Need at least a week of data
            return False
        
        # Prepare features and target
        X = daily_waste[['days_since_start', 'day_of_week', 'month']].values
        y = daily_waste['weight'].values
        
        # Train model
        self.waste_prediction_model.fit(X, y)
        return True
    
    def predict_waste_generation(self, days_ahead=30):
        """Predict waste generation for the next N days"""
        if not hasattr(self.waste_prediction_model, 'feature_importances_'):
            return []
        
        # Generate future dates
        future_dates = pd.date_range(
            start=datetime.now().date(),
            periods=days_ahead,
            freq='D'
        )
        
        predictions = []
        start_date = pd.Timestamp(datetime.now().date())
        
        for i, date in enumerate(future_dates):
            days_since_start = (date - start_date).days
            features = np.array([[days_since_start, date.weekday(), date.month]])
            prediction = self.waste_prediction_model.predict(features)[0]
            
            predictions.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_weight': max(0, prediction),
                'day_of_week': date.strftime('%A')
            })
        
        return predictions
    
    def analyze_waste_trends(self, waste_data):
        """Analyze waste generation trends using AI"""
        if waste_data.empty:
            return {}
        
        analysis = {}
        
        # Trend analysis
        daily_waste = waste_data.groupby('date')['weight'].sum().reset_index()
        daily_waste['date'] = pd.to_datetime(daily_waste['date'])
        
        # Calculate moving averages
        daily_waste['7_day_avg'] = daily_waste['weight'].rolling(window=7).mean()
        daily_waste['30_day_avg'] = daily_waste['weight'].rolling(window=30).mean()
        
        # Trend direction
        if len(daily_waste) >= 2:
            recent_trend = daily_waste['weight'].iloc[-7:].mean() - daily_waste['weight'].iloc[-14:-7].mean()
            analysis['trend_direction'] = 'increasing' if recent_trend > 0 else 'decreasing'
            analysis['trend_strength'] = abs(recent_trend)
        
        # Waste type analysis
        waste_by_type = waste_data.groupby('waste_type')['weight'].sum().sort_values(ascending=False)
        analysis['top_waste_types'] = waste_by_type.head(3).to_dict()
        
        # Recycling analysis
        recycling_rate = (waste_data['recycled'].sum() / len(waste_data)) * 100
        analysis['recycling_rate'] = recycling_rate
        
        # Seasonal patterns
        monthly_waste = waste_data.groupby('month')['weight'].sum()
        analysis['seasonal_patterns'] = monthly_waste.to_dict()
        
        return analysis
    
    def customer_segmentation(self, users, waste_data, payment_data):
        """Segment customers using AI clustering"""
        if not users or waste_data.empty:
            return []
        
        # Create customer features
        customer_features = []
        for user in users:
            user_waste = waste_data[waste_data['user_id'] == user.id]
            user_payments = payment_data[payment_data['user_id'] == user.id] if not payment_data.empty else pd.DataFrame()
            
            # Only consider completed payments for spending analysis
            completed_payments = user_payments[user_payments['payment_status'] == 'completed'] if not user_payments.empty else pd.DataFrame()
            
            # Calculate days since user creation, handling different date types
            user_created = pd.Timestamp(user.created_at)
            days_since_creation = (pd.Timestamp.now() - user_created).days
            
            features = {
                'user_id': user.id,
                'username': user.username,
                'total_waste': user_waste['weight'].sum() if not user_waste.empty else 0,
                'avg_waste_per_entry': user_waste['weight'].mean() if not user_waste.empty else 0,
                'recycling_rate': (user_waste['recycled'].sum() / len(user_waste) * 100) if not user_waste.empty else 0,
                'total_spent': completed_payments['amount'].sum() if not completed_payments.empty else 0,
                'request_frequency': len(user_waste) / max(1, days_since_creation) * 30,  # per month
                'waste_type_diversity': user_waste['waste_type'].nunique() if not user_waste.empty else 0
            }
            customer_features.append(features)
        
        if not customer_features:
            return []
        
        df = pd.DataFrame(customer_features)
        
        # Prepare features for clustering
        feature_columns = ['total_waste', 'avg_waste_per_entry', 'recycling_rate', 
                          'total_spent', 'request_frequency', 'waste_type_diversity']
        
        X = df[feature_columns].fillna(0)
        X_scaled = self.scaler.fit_transform(X)
        
        # Perform clustering
        clusters = self.customer_segmentation_model.fit_predict(X_scaled)
        df['segment'] = clusters
        
        # Define segment names based on characteristics
        segment_names = {
            0: 'Low-Volume Users',
            1: 'High-Value Customers', 
            2: 'Regular Recyclers',
            3: 'Occasional Users'
        }
        
        df['segment_name'] = df['segment'].map(segment_names)
        
        return df.to_dict('records')
    
    def revenue_forecasting(self, payment_data, days_ahead=30):
        """Forecast future revenue using AI"""
        if payment_data.empty:
            return []
        
        # Filter only completed payments for revenue analysis
        completed_payments = payment_data[payment_data['payment_status'] == 'completed']
        
        if completed_payments.empty:
            return []
        
        # Aggregate daily revenue
        daily_revenue = completed_payments.groupby('date')['amount'].sum().reset_index()
        daily_revenue['date'] = pd.to_datetime(daily_revenue['date'])
        daily_revenue['days_since_start'] = (daily_revenue['date'] - daily_revenue['date'].min()).dt.days
        
        if len(daily_revenue) < 7:
            return []
        
        # Prepare features
        X = daily_revenue[['days_since_start']].values
        y = daily_revenue['amount'].values
        
        # Train model
        self.revenue_prediction_model.fit(X, y)
        
        # Generate predictions
        start_date = pd.Timestamp(datetime.now().date())
        predictions = []
        
        for i in range(days_ahead):
            future_date = start_date + pd.Timedelta(days=i)
            days_since_start = (future_date - daily_revenue['date'].min()).days
            features = np.array([[days_since_start]])
            prediction = self.revenue_prediction_model.predict(features)[0]
            
            predictions.append({
                'date': future_date.strftime('%Y-%m-%d'),
                'predicted_revenue': max(0, prediction),
                'day_of_week': future_date.strftime('%A')
            })
        
        return predictions
    
    def generate_ai_insights(self, waste_data, payment_data, users):
        """Generate comprehensive AI insights"""
        insights = {
            'waste_prediction': [],
            'revenue_forecast': [],
            'customer_segments': [],
            'trend_analysis': {},
            'recommendations': []
        }
        
        try:
            # Waste prediction
            if self.train_waste_prediction_model(waste_data):
                insights['waste_prediction'] = self.predict_waste_generation(30)
        except Exception as e:
            print(f"Error in waste prediction: {e}")
            insights['waste_prediction'] = []
        
        try:
            # Revenue forecasting
            if not payment_data.empty:
                insights['revenue_forecast'] = self.revenue_forecasting(payment_data, 30)
        except Exception as e:
            print(f"Error in revenue forecasting: {e}")
            insights['revenue_forecast'] = []
        
        try:
            # Customer segmentation
            insights['customer_segments'] = self.customer_segmentation(users, waste_data, payment_data)
        except Exception as e:
            print(f"Error in customer segmentation: {e}")
            insights['customer_segments'] = []
        
        try:
            # Trend analysis
            insights['trend_analysis'] = self.analyze_waste_trends(waste_data)
        except Exception as e:
            print(f"Error in trend analysis: {e}")
            insights['trend_analysis'] = {}
        
        try:
            # Generate recommendations
            insights['recommendations'] = self.generate_recommendations(insights)
        except Exception as e:
            print(f"Error in generating recommendations: {e}")
            insights['recommendations'] = []
        
        return insights
    
    def generate_recommendations(self, insights):
        """Generate AI-powered recommendations"""
        recommendations = []
        
        # Waste reduction recommendations
        if insights['trend_analysis']:
            trend = insights['trend_analysis'].get('trend_direction', 'stable')
            if trend == 'increasing':
                recommendations.append({
                    'type': 'waste_reduction',
                    'title': 'Waste Generation Increasing',
                    'description': 'Consider implementing waste reduction strategies and recycling programs.',
                    'priority': 'high'
                })
        
        # Revenue optimization
        if insights['revenue_forecast']:
            avg_revenue = np.mean([r['predicted_revenue'] for r in insights['revenue_forecast']])
            if avg_revenue < 100:  # Threshold for low revenue
                recommendations.append({
                    'type': 'revenue_optimization',
                    'title': 'Revenue Optimization Opportunity',
                    'description': 'Consider promotional campaigns or service improvements to increase revenue.',
                    'priority': 'medium'
                })
        
        # Customer engagement
        if insights['customer_segments']:
            low_volume_users = [s for s in insights['customer_segments'] if s['segment_name'] == 'Low-Volume Users']
            if len(low_volume_users) > len(insights['customer_segments']) * 0.5:
                recommendations.append({
                    'type': 'customer_engagement',
                    'title': 'Customer Engagement Opportunity',
                    'description': 'High number of low-volume users. Consider engagement campaigns.',
                    'priority': 'medium'
                })
        
        return recommendations
    
    def create_ai_dashboard_charts(self, insights):
        """Create interactive charts for AI insights"""
        charts = {}
        
        try:
            # Waste prediction chart
            if insights['waste_prediction']:
                df_pred = pd.DataFrame(insights['waste_prediction'])
                fig_pred = px.line(df_pred, x='date', y='predicted_weight', 
                                  title='AI-Powered Waste Generation Forecast',
                                  labels={'predicted_weight': 'Predicted Weight (kg)', 'date': 'Date'})
                charts['waste_prediction'] = json.dumps(fig_pred, cls=plotly.utils.PlotlyJSONEncoder)
        except Exception as e:
            print(f"Error creating waste prediction chart: {e}")
        
        try:
            # Revenue forecast chart
            if insights['revenue_forecast']:
                df_rev = pd.DataFrame(insights['revenue_forecast'])
                fig_rev = px.line(df_rev, x='date', y='predicted_revenue',
                                 title='AI-Powered Revenue Forecast',
                                 labels={'predicted_revenue': 'Predicted Revenue ($)', 'date': 'Date'})
                charts['revenue_forecast'] = json.dumps(fig_rev, cls=plotly.utils.PlotlyJSONEncoder)
        except Exception as e:
            print(f"Error creating revenue forecast chart: {e}")
        
        try:
            # Customer segmentation chart
            if insights['customer_segments']:
                df_seg = pd.DataFrame(insights['customer_segments'])
                segment_counts = df_seg['segment_name'].value_counts()
                fig_seg = px.pie(values=segment_counts.values, names=segment_counts.index,
                                title='Customer Segmentation Analysis')
                charts['customer_segments'] = json.dumps(fig_seg, cls=plotly.utils.PlotlyJSONEncoder)
        except Exception as e:
            print(f"Error creating customer segmentation chart: {e}")
        
        return charts 