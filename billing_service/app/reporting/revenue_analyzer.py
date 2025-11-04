"""
Revenue Analysis Engine
Analyzes revenue patterns, customer segments, and business performance
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from collections import defaultdict
import json
from operator import attrgetter

logger = logging.getLogger(__name__)

class RevenueSegment(Enum):
    HIGH_VALUE = "high_value"
    MEDIUM_VALUE = "medium_value"
    LOW_VALUE = "low_value"
    ENTERPRISE = "enterprise"
    STARTUP = "startup"
    INDIVIDUAL = "individual"

class AnalysisPeriod(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

@dataclass
class CustomerSegment:
    segment_id: str
    name: str
    customer_count: int
    avg_revenue: Decimal
    total_revenue: Decimal
    churn_rate: float
    growth_rate: float
    characteristics: Dict[str, Any]

@dataclass
class RevenueAnalysis:
    period: AnalysisPeriod
    total_revenue: Decimal
    revenue_breakdown: Dict[str, Decimal]
    growth_metrics: Dict[str, float]
    customer_segments: List[CustomerSegment]
    trends: Dict[str, Any]
    recommendations: List[Dict[str, Any]]

@dataclass
class PricingAnalysis:
    current_pricing: Dict[str, Decimal]
    price_elasticity: Dict[str, float]
    optimization_suggestions: List[Dict[str, Any]]
    revenue_impact: Dict[str, Decimal]

class RevenueAnalyzer:
    """Comprehensive revenue analysis and insights engine"""
    
    def __init__(self):
        self.analysis_cache = {}
        
    async def analyze_revenue_performance(
        self,
        revenue_data: List[Dict],
        customer_data: List[Dict],
        period: AnalysisPeriod = AnalysisPeriod.MONTHLY
    ) -> RevenueAnalysis:
        """Comprehensive revenue performance analysis"""
        try:
            # Prepare dataframes
            revenue_df = pd.DataFrame(revenue_data)
            customer_df = pd.DataFrame(customer_data)
            
            revenue_df['date'] = pd.to_datetime(revenue_df['date'])
            revenue_df['amount'] = revenue_df['amount'].astype(float)
            
            # Calculate total revenue
            total_revenue = Decimal(str(revenue_df['amount'].sum()))
            
            # Revenue breakdown analysis
            revenue_breakdown = await self._analyze_revenue_breakdown(revenue_df)
            
            # Growth metrics
            growth_metrics = await self._calculate_growth_metrics(revenue_df, period)
            
            # Customer segmentation
            customer_segments = await self._segment_customers(revenue_df, customer_df)
            
            # Trend analysis
            trends = await self._analyze_trends(revenue_df, period)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                revenue_breakdown, growth_metrics, customer_segments, trends
            )
            
            logger.info(f"Revenue analysis completed for {period.value} period")
            
            return RevenueAnalysis(
                period=period,
                total_revenue=total_revenue,
                revenue_breakdown=revenue_breakdown,
                growth_metrics=growth_metrics,
                customer_segments=customer_segments,
                trends=trends,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error in revenue analysis: {str(e)}")
            raise
    
    async def analyze_customer_segments(
        self,
        customer_data: List[Dict],
        revenue_data: List[Dict],
        segmentation_method: str = "revenue_based"
    ) -> List[CustomerSegment]:
        """Analyze customer segments with detailed insights"""
        try:
            # Merge customer and revenue data
            revenue_df = pd.DataFrame(revenue_data)
            customer_df = pd.DataFrame(customer_data)
            
            # Calculate customer metrics
            customer_revenue = revenue_df.groupby('customer_id')['amount'].agg([
                'sum', 'count', 'mean', 'std'
            ]).fillna(0)
            
            segments = []
            
            if segmentation_method == "revenue_based":
                segments = await self._segment_by_revenue(customer_revenue, customer_df)
            elif segmentation_method == "usage_based":
                segments = await self._segment_by_usage(customer_revenue, customer_df)
            elif segmentation_method == "behavior_based":
                segments = await self._segment_by_behavior(customer_revenue, customer_df)
            else:
                segments = await self._segment_by_revenue(customer_revenue, customer_df)
            
            # Enrich segments with additional analytics
            for segment in segments:
                segment.characteristics.update(
                    await self._analyze_segment_characteristics(
                        segment, customer_df, revenue_df
                    )
                )
            
            logger.info(f"Customer segmentation completed: {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error in customer segmentation: {str(e)}")
            raise
    
    async def analyze_pricing_optimization(
        self,
        revenue_data: List[Dict],
        pricing_data: List[Dict],
        usage_data: List[Dict]
    ) -> PricingAnalysis:
        """Analyze pricing strategy and optimization opportunities"""
        try:
            # Current pricing structure
            current_pricing = {
                item['tier']: Decimal(str(item['price']))
                for item in pricing_data
            }
            
            # Calculate price elasticity
            price_elasticity = await self._calculate_price_elasticity(
                revenue_data, pricing_data, usage_data
            )
            
            # Generate optimization suggestions
            optimization_suggestions = await self._generate_pricing_suggestions(
                current_pricing, price_elasticity, revenue_data
            )
            
            # Calculate potential revenue impact
            revenue_impact = await self._calculate_pricing_impact(
                optimization_suggestions, revenue_data
            )
            
            logger.info("Pricing optimization analysis completed")
            
            return PricingAnalysis(
                current_pricing=current_pricing,
                price_elasticity=price_elasticity,
                optimization_suggestions=optimization_suggestions,
                revenue_impact=revenue_impact
            )
            
        except Exception as e:
            logger.error(f"Error in pricing analysis: {str(e)}")
            raise
    
    async def calculate_cohort_analysis(
        self,
        customer_data: List[Dict],
        revenue_data: List[Dict],
        cohort_period: str = "monthly"
    ) -> Dict[str, Any]:
        """Perform cohort analysis for customer retention and revenue"""
        try:
            # Prepare data
            revenue_df = pd.DataFrame(revenue_data)
            customer_df = pd.DataFrame(customer_data)
            
            revenue_df['date'] = pd.to_datetime(revenue_df['date'])
            customer_df['signup_date'] = pd.to_datetime(customer_df['signup_date'])
            
            # Create cohorts based on signup month
            customer_df['cohort_month'] = customer_df['signup_date'].dt.to_period('M')
            revenue_df['order_month'] = revenue_df['date'].dt.to_period('M')
            
            # Merge dataframes
            merged_df = revenue_df.merge(
                customer_df[['customer_id', 'cohort_month']], 
                on='customer_id'
            )
            
            # Calculate period number (months since signup)
            merged_df['period_number'] = (
                merged_df['order_month'] - merged_df['cohort_month']
            ).apply(attrgetter('n'))
            
            # Create cohort table
            cohort_data = merged_df.groupby(['cohort_month', 'period_number'])['customer_id'].nunique().reset_index()
            cohort_table = cohort_data.pivot(index='cohort_month', columns='period_number', values='customer_id')
            
            # Calculate cohort sizes
            cohort_sizes = customer_df.groupby('cohort_month')['customer_id'].nunique()
            
            # Calculate retention rates
            retention_table = cohort_table.divide(cohort_sizes, axis=0)
            
            # Calculate revenue cohorts
            revenue_cohorts = merged_df.groupby(['cohort_month', 'period_number'])['amount'].sum().reset_index()
            revenue_table = revenue_cohorts.pivot(index='cohort_month', columns='period_number', values='amount')
            
            # Calculate average revenue per user by cohort
            arpu_table = revenue_table.divide(cohort_table)
            
            return {
                'cohort_table': cohort_table.to_dict(),
                'retention_table': retention_table.to_dict(),
                'revenue_table': revenue_table.to_dict(),
                'arpu_table': arpu_table.to_dict(),
                'cohort_sizes': cohort_sizes.to_dict(),
                'insights': await self._generate_cohort_insights(retention_table, revenue_table)
            }
            
        except Exception as e:
            logger.error(f"Error in cohort analysis: {str(e)}")
            raise
    
    async def detect_revenue_anomalies(
        self,
        revenue_data: List[Dict],
        sensitivity: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in revenue patterns"""
        try:
            revenue_df = pd.DataFrame(revenue_data)
            revenue_df['date'] = pd.to_datetime(revenue_df['date'])
            revenue_df = revenue_df.sort_values('date')
            
            # Daily revenue aggregation
            daily_revenue = revenue_df.groupby(revenue_df['date'].dt.date)['amount'].sum()
            
            # Calculate rolling statistics
            rolling_mean = daily_revenue.rolling(window=7, center=True).mean()
            rolling_std = daily_revenue.rolling(window=7, center=True).std()
            
            # Detect anomalies using z-score
            z_scores = (daily_revenue - rolling_mean) / rolling_std
            anomalies = []
            
            for date, z_score in z_scores.items():
                if abs(z_score) > sensitivity:
                    anomaly_type = "spike" if z_score > 0 else "drop"
                    severity = "high" if abs(z_score) > 3.0 else "medium"
                    
                    anomalies.append({
                        'date': str(date),
                        'type': anomaly_type,
                        'severity': severity,
                        'z_score': float(z_score),
                        'actual_revenue': float(daily_revenue[date]),
                        'expected_revenue': float(rolling_mean[date]),
                        'deviation_amount': float(daily_revenue[date] - rolling_mean[date])
                    })
            
            logger.info(f"Detected {len(anomalies)} revenue anomalies")
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            return []
    
    async def calculate_customer_lifetime_value(
        self,
        customer_data: List[Dict],
        revenue_data: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate Customer Lifetime Value (CLV) metrics"""
        try:
            revenue_df = pd.DataFrame(revenue_data)
            customer_df = pd.DataFrame(customer_data)
            
            # Customer metrics
            customer_metrics = revenue_df.groupby('customer_id').agg({
                'amount': ['sum', 'mean', 'count'],
                'date': ['min', 'max']
            })
            
            customer_metrics.columns = ['total_revenue', 'avg_order_value', 'purchase_frequency', 'first_purchase', 'last_purchase']
            
            # Calculate customer lifespan in months
            customer_metrics['lifespan_months'] = (
                pd.to_datetime(customer_metrics['last_purchase']) - 
                pd.to_datetime(customer_metrics['first_purchase'])
            ).dt.days / 30.44
            
            # Handle single-purchase customers
            customer_metrics['lifespan_months'] = customer_metrics['lifespan_months'].fillna(1)
            
            # Calculate monthly purchase rate
            customer_metrics['monthly_purchase_rate'] = customer_metrics['purchase_frequency'] / customer_metrics['lifespan_months']
            
            # Calculate CLV
            customer_metrics['clv'] = (
                customer_metrics['avg_order_value'] * 
                customer_metrics['monthly_purchase_rate'] * 
                12  # Annualized
            )
            
            # Aggregate CLV metrics
            clv_metrics = {
                'average_clv': float(customer_metrics['clv'].mean()),
                'median_clv': float(customer_metrics['clv'].median()),
                'total_clv': float(customer_metrics['clv'].sum()),
                'clv_distribution': {
                    'p25': float(customer_metrics['clv'].quantile(0.25)),
                    'p50': float(customer_metrics['clv'].quantile(0.50)),
                    'p75': float(customer_metrics['clv'].quantile(0.75)),
                    'p90': float(customer_metrics['clv'].quantile(0.90))
                },
                'top_customers': customer_metrics.nlargest(10, 'clv')[['total_revenue', 'clv']].to_dict('index')
            }
            
            return clv_metrics
            
        except Exception as e:
            logger.error(f"Error calculating CLV: {str(e)}")
            return {}
    
    async def analyze_revenue_concentration(
        self,
        revenue_data: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze revenue concentration and dependency risks"""
        try:
            revenue_df = pd.DataFrame(revenue_data)
            
            # Customer revenue concentration
            customer_revenue = revenue_df.groupby('customer_id')['amount'].sum().sort_values(ascending=False)
            total_revenue = customer_revenue.sum()
            
            # Calculate concentration metrics
            top_10_pct = int(len(customer_revenue) * 0.1) or 1
            top_20_pct = int(len(customer_revenue) * 0.2) or 1
            
            concentration_metrics = {
                'total_customers': len(customer_revenue),
                'total_revenue': float(total_revenue),
                'top_customer_revenue': float(customer_revenue.iloc[0]),
                'top_customer_percentage': float(customer_revenue.iloc[0] / total_revenue * 100),
                'top_5_customers_percentage': float(customer_revenue.head(5).sum() / total_revenue * 100),
                'top_10_percent_customers_revenue': float(customer_revenue.head(top_10_pct).sum() / total_revenue * 100),
                'top_20_percent_customers_revenue': float(customer_revenue.head(top_20_pct).sum() / total_revenue * 100),
                'gini_coefficient': float(self._calculate_gini_coefficient(customer_revenue.values))
            }
            
            # Risk assessment
            risk_level = "low"
            if concentration_metrics['top_customer_percentage'] > 30:
                risk_level = "high"
            elif concentration_metrics['top_5_customers_percentage'] > 50:
                risk_level = "medium"
            
            concentration_metrics['risk_level'] = risk_level
            concentration_metrics['risk_factors'] = self._identify_concentration_risks(concentration_metrics)
            
            return concentration_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing revenue concentration: {str(e)}")
            return {}
    
    def _calculate_gini_coefficient(self, values: np.ndarray) -> float:
        """Calculate Gini coefficient for revenue distribution"""
        sorted_values = np.sort(values)
        n = len(values)
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n
    
    def _identify_concentration_risks(self, metrics: Dict[str, Any]) -> List[str]:
        """Identify specific concentration risks"""
        risks = []
        
        if metrics['top_customer_percentage'] > 25:
            risks.append("High dependency on single customer")
        
        if metrics['top_5_customers_percentage'] > 60:
            risks.append("Revenue heavily concentrated in top 5 customers")
        
        if metrics['gini_coefficient'] > 0.7:
            risks.append("High revenue inequality across customer base")
        
        return risks
    
    async def _analyze_revenue_breakdown(self, revenue_df: pd.DataFrame) -> Dict[str, Decimal]:
        """Break down revenue by various dimensions"""
        breakdown = {}
        
        # By subscription vs one-time
        if 'type' in revenue_df.columns:
            by_type = revenue_df.groupby('type')['amount'].sum()
            for revenue_type, amount in by_type.items():
                breakdown[f"revenue_{revenue_type}"] = Decimal(str(amount))
        
        # By product/service
        if 'product' in revenue_df.columns:
            by_product = revenue_df.groupby('product')['amount'].sum()
            for product, amount in by_product.items():
                breakdown[f"product_{product}"] = Decimal(str(amount))
        
        # By geography
        if 'country' in revenue_df.columns:
            by_country = revenue_df.groupby('country')['amount'].sum().head(5)
            for country, amount in by_country.items():
                breakdown[f"country_{country}"] = Decimal(str(amount))
        
        return breakdown
    
    async def _calculate_growth_metrics(
        self, 
        revenue_df: pd.DataFrame, 
        period: AnalysisPeriod
    ) -> Dict[str, float]:
        """Calculate various growth metrics"""
        metrics = {}
        
        # Prepare time-based grouping
        if period == AnalysisPeriod.DAILY:
            revenue_df['period'] = revenue_df['date'].dt.date
        elif period == AnalysisPeriod.WEEKLY:
            revenue_df['period'] = revenue_df['date'].dt.to_period('W')
        elif period == AnalysisPeriod.MONTHLY:
            revenue_df['period'] = revenue_df['date'].dt.to_period('M')
        elif period == AnalysisPeriod.QUARTERLY:
            revenue_df['period'] = revenue_df['date'].dt.to_period('Q')
        else:
            revenue_df['period'] = revenue_df['date'].dt.to_period('Y')
        
        # Aggregate by period
        period_revenue = revenue_df.groupby('period')['amount'].sum().sort_index()
        
        if len(period_revenue) >= 2:
            # Period-over-period growth
            latest_revenue = period_revenue.iloc[-1]
            previous_revenue = period_revenue.iloc[-2]
            
            if previous_revenue > 0:
                metrics['period_growth_rate'] = float(
                    (latest_revenue - previous_revenue) / previous_revenue * 100
                )
            
            # Calculate CAGR if enough data
            if len(period_revenue) >= 4:
                first_revenue = period_revenue.iloc[0]
                last_revenue = period_revenue.iloc[-1]
                periods = len(period_revenue) - 1
                
                if first_revenue > 0:
                    metrics['cagr'] = float(
                        (pow(last_revenue / first_revenue, 1/periods) - 1) * 100
                    )
        
        # Revenue volatility
        if len(period_revenue) > 1:
            metrics['revenue_volatility'] = float(
                period_revenue.std() / period_revenue.mean() * 100
            )
        
        return metrics
    
    async def _segment_customers(
        self, 
        revenue_df: pd.DataFrame, 
        customer_df: pd.DataFrame
    ) -> List[CustomerSegment]:
        """Segment customers based on revenue and behavior"""
        # Calculate customer metrics
        customer_metrics = revenue_df.groupby('customer_id').agg({
            'amount': ['sum', 'count', 'mean'],
            'date': ['min', 'max']
        }).round(2)
        
        customer_metrics.columns = ['total_revenue', 'transaction_count', 'avg_transaction', 'first_purchase', 'last_purchase']
        
        # Define segments based on total revenue
        segments = []
        
        # High value customers (top 10%)
        high_value_threshold = customer_metrics['total_revenue'].quantile(0.9)
        high_value_customers = customer_metrics[customer_metrics['total_revenue'] >= high_value_threshold]
        
        if not high_value_customers.empty:
            segments.append(CustomerSegment(
                segment_id="high_value",
                name="High Value Customers",
                customer_count=len(high_value_customers),
                avg_revenue=Decimal(str(high_value_customers['total_revenue'].mean())),
                total_revenue=Decimal(str(high_value_customers['total_revenue'].sum())),
                churn_rate=await self._calculate_segment_churn(high_value_customers),
                growth_rate=await self._calculate_segment_growth(high_value_customers),
                characteristics={}
            ))
        
        # Medium value customers (10-50%)
        medium_value_threshold = customer_metrics['total_revenue'].quantile(0.5)
        medium_value_customers = customer_metrics[
            (customer_metrics['total_revenue'] >= medium_value_threshold) & 
            (customer_metrics['total_revenue'] < high_value_threshold)
        ]
        
        if not medium_value_customers.empty:
            segments.append(CustomerSegment(
                segment_id="medium_value",
                name="Medium Value Customers",
                customer_count=len(medium_value_customers),
                avg_revenue=Decimal(str(medium_value_customers['total_revenue'].mean())),
                total_revenue=Decimal(str(medium_value_customers['total_revenue'].sum())),
                churn_rate=await self._calculate_segment_churn(medium_value_customers),
                growth_rate=await self._calculate_segment_growth(medium_value_customers),
                characteristics={}
            ))
        
        # Low value customers (bottom 50%)
        low_value_customers = customer_metrics[customer_metrics['total_revenue'] < medium_value_threshold]
        
        if not low_value_customers.empty:
            segments.append(CustomerSegment(
                segment_id="low_value",
                name="Low Value Customers",
                customer_count=len(low_value_customers),
                avg_revenue=Decimal(str(low_value_customers['total_revenue'].mean())),
                total_revenue=Decimal(str(low_value_customers['total_revenue'].sum())),
                churn_rate=await self._calculate_segment_churn(low_value_customers),
                growth_rate=await self._calculate_segment_growth(low_value_customers),
                characteristics={}
            ))
        
        return segments
    
    async def _analyze_trends(
        self, 
        revenue_df: pd.DataFrame, 
        period: AnalysisPeriod
    ) -> Dict[str, Any]:
        """Analyze revenue trends and patterns"""
        trends = {}
        
        # Seasonality analysis
        revenue_df['month'] = revenue_df['date'].dt.month
        revenue_df['day_of_week'] = revenue_df['date'].dt.dayofweek
        
        monthly_avg = revenue_df.groupby('month')['amount'].mean()
        trends['seasonal_patterns'] = {
            'strongest_month': int(monthly_avg.idxmax()),
            'weakest_month': int(monthly_avg.idxmin()),
            'seasonal_variance': float(monthly_avg.std())
        }
        
        weekly_avg = revenue_df.groupby('day_of_week')['amount'].mean()
        trends['weekly_patterns'] = {
            'strongest_day': int(weekly_avg.idxmax()),
            'weakest_day': int(weekly_avg.idxmin()),
            'weekly_variance': float(weekly_avg.std())
        }
        
        # Growth trend
        daily_revenue = revenue_df.groupby(revenue_df['date'].dt.date)['amount'].sum()
        if len(daily_revenue) > 30:
            # Calculate 30-day moving average trend
            ma_30 = daily_revenue.rolling(window=30).mean()
            recent_trend = ma_30.iloc[-1] - ma_30.iloc[-31] if len(ma_30) >= 31 else 0
            trends['growth_trend'] = 'increasing' if recent_trend > 0 else 'decreasing'
            trends['trend_strength'] = float(abs(recent_trend))
        
        return trends
    
    async def _generate_recommendations(
        self,
        revenue_breakdown: Dict[str, Decimal],
        growth_metrics: Dict[str, float],
        customer_segments: List[CustomerSegment],
        trends: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable business recommendations"""
        recommendations = []
        
        # Growth rate recommendations
        growth_rate = growth_metrics.get('period_growth_rate', 0)
        if growth_rate < 5:
            recommendations.append({
                'type': 'growth',
                'priority': 'high',
                'title': 'Accelerate Growth',
                'description': f'Current growth rate ({growth_rate:.1f}%) is below target. Consider increasing marketing spend or improving product offerings.',
                'expected_impact': 'Increase monthly growth rate by 5-10%'
            })
        
        # Customer segment recommendations
        if customer_segments:
            high_value_segment = next((s for s in customer_segments if s.segment_id == 'high_value'), None)
            if high_value_segment and high_value_segment.churn_rate > 10:
                recommendations.append({
                    'type': 'retention',
                    'priority': 'high',
                    'title': 'Reduce High-Value Customer Churn',
                    'description': f'High-value customers have {high_value_segment.churn_rate:.1f}% churn rate. Implement retention programs.',
                    'expected_impact': f'Retain ${high_value_segment.avg_revenue * Decimal("0.1")} per customer'
                })
        
        # Revenue diversification
        subscription_revenue = revenue_breakdown.get('revenue_subscription', Decimal('0'))
        total_revenue = sum(revenue_breakdown.values())
        
        if total_revenue > 0:
            subscription_ratio = float(subscription_revenue / total_revenue)
            if subscription_ratio < 0.6:
                recommendations.append({
                    'type': 'revenue_model',
                    'priority': 'medium',
                    'title': 'Increase Recurring Revenue',
                    'description': f'Only {subscription_ratio:.1%} of revenue is recurring. Focus on subscription offerings.',
                    'expected_impact': 'Improve revenue predictability and customer lifetime value'
                })
        
        # Seasonal optimization
        if 'seasonal_patterns' in trends:
            seasonal_variance = trends['seasonal_patterns']['seasonal_variance']
            if seasonal_variance > 1000:  # High seasonal variance
                recommendations.append({
                    'type': 'seasonality',
                    'priority': 'medium',
                    'title': 'Address Seasonal Fluctuations',
                    'description': 'High seasonal revenue variance detected. Consider counter-seasonal marketing or product launches.',
                    'expected_impact': 'Smooth revenue distribution throughout the year'
                })
        
        return recommendations
    
    async def _segment_by_revenue(
        self, 
        customer_revenue: pd.DataFrame, 
        customer_df: pd.DataFrame
    ) -> List[CustomerSegment]:
        """Segment customers by revenue tiers"""
        segments = []
        
        # High value (top 20%)
        high_threshold = customer_revenue['sum'].quantile(0.8)
        high_value = customer_revenue[customer_revenue['sum'] >= high_threshold]
        
        if not high_value.empty:
            segments.append(CustomerSegment(
                segment_id="revenue_high",
                name="High Revenue Customers",
                customer_count=len(high_value),
                avg_revenue=Decimal(str(high_value['sum'].mean())),
                total_revenue=Decimal(str(high_value['sum'].sum())),
                churn_rate=5.0,
                growth_rate=15.0,
                characteristics={'revenue_tier': 'high'}
            ))
        
        # Medium value (20-60%)
        medium_threshold = customer_revenue['sum'].quantile(0.4)
        medium_value = customer_revenue[
            (customer_revenue['sum'] >= medium_threshold) & 
            (customer_revenue['sum'] < high_threshold)
        ]
        
        if not medium_value.empty:
            segments.append(CustomerSegment(
                segment_id="revenue_medium",
                name="Medium Revenue Customers",
                customer_count=len(medium_value),
                avg_revenue=Decimal(str(medium_value['sum'].mean())),
                total_revenue=Decimal(str(medium_value['sum'].sum())),
                churn_rate=8.0,
                growth_rate=10.0,
                characteristics={'revenue_tier': 'medium'}
            ))
        
        # Low value (bottom 40%)
        low_value = customer_revenue[customer_revenue['sum'] < medium_threshold]
        
        if not low_value.empty:
            segments.append(CustomerSegment(
                segment_id="revenue_low",
                name="Low Revenue Customers",
                customer_count=len(low_value),
                avg_revenue=Decimal(str(low_value['sum'].mean())),
                total_revenue=Decimal(str(low_value['sum'].sum())),
                churn_rate=15.0,
                growth_rate=5.0,
                characteristics={'revenue_tier': 'low'}
            ))
        
        return segments
    
    async def _segment_by_usage(
        self, 
        customer_revenue: pd.DataFrame, 
        customer_df: pd.DataFrame
    ) -> List[CustomerSegment]:
        """Segment customers by usage patterns"""
        segments = []
        
        # Assuming usage data is in customer_df
        if 'monthly_usage' in customer_df.columns:
            usage_segments = pd.qcut(customer_df['monthly_usage'], q=3, labels=['light', 'medium', 'heavy'])
            
            for segment_name in ['light', 'medium', 'heavy']:
                segment_customers = customer_df[usage_segments == segment_name]
                segment_revenue = customer_revenue[customer_revenue.index.isin(segment_customers['customer_id'])]
                
                if not segment_revenue.empty:
                    segments.append(CustomerSegment(
                        segment_id=f"usage_{segment_name}",
                        name=f"{segment_name.title()} Usage Customers",
                        customer_count=len(segment_customers),
                        avg_revenue=Decimal(str(segment_revenue['sum'].mean())),
                        total_revenue=Decimal(str(segment_revenue['sum'].sum())),
                        churn_rate=0.0,  # Would need temporal data
                        growth_rate=0.0,  # Would need temporal data
                        characteristics={'usage_tier': segment_name}
                    ))
        
        return segments
    
    async def _segment_by_behavior(
        self, 
        customer_revenue: pd.DataFrame, 
        customer_df: pd.DataFrame
    ) -> List[CustomerSegment]:
        """Segment customers by behavioral patterns"""
        segments = []
        
        # Transaction frequency segmentation
        freq_segments = pd.qcut(customer_revenue['count'], q=3, labels=['occasional', 'regular', 'frequent'])
        
        for segment_name in ['occasional', 'regular', 'frequent']:
            segment_mask = freq_segments == segment_name
            segment_data = customer_revenue[segment_mask]
            
            if not segment_data.empty:
                segments.append(CustomerSegment(
                    segment_id=f"behavior_{segment_name}",
                    name=f"{segment_name.title()} Buyers",
                    customer_count=len(segment_data),
                    avg_revenue=Decimal(str(segment_data['sum'].mean())),
                    total_revenue=Decimal(str(segment_data['sum'].sum())),
                    churn_rate=0.0,
                    growth_rate=0.0,
                    characteristics={'transaction_frequency': segment_name}
                ))
        
        return segments
    
    async def _analyze_segment_characteristics(
        self,
        segment: CustomerSegment,
        customer_df: pd.DataFrame,
        revenue_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze detailed characteristics of customer segments"""
        characteristics = {}
        
        # Get segment customers
        segment_revenue = revenue_df.groupby('customer_id')['amount'].sum()
        
        if segment.segment_id == 'high_value':
            threshold = segment_revenue.quantile(0.9)
            segment_customers = segment_revenue[segment_revenue >= threshold].index
        elif segment.segment_id == 'medium_value':
            high_threshold = segment_revenue.quantile(0.9)
            medium_threshold = segment_revenue.quantile(0.5)
            segment_customers = segment_revenue[
                (segment_revenue >= medium_threshold) & (segment_revenue < high_threshold)
            ].index
        else:
            threshold = segment_revenue.quantile(0.5)
            segment_customers = segment_revenue[segment_revenue < threshold].index
        
        segment_customer_data = customer_df[customer_df['customer_id'].isin(segment_customers)]
        segment_revenue_data = revenue_df[revenue_df['customer_id'].isin(segment_customers)]
        
        # Calculate characteristics
        if not segment_customer_data.empty:
            # Geographic distribution
            if 'country' in segment_customer_data.columns:
                geo_dist = segment_customer_data['country'].value_counts().head(3)
                characteristics['top_countries'] = geo_dist.to_dict()
            
            # Industry distribution
            if 'industry' in segment_customer_data.columns:
                industry_dist = segment_customer_data['industry'].value_counts().head(3)
                characteristics['top_industries'] = industry_dist.to_dict()
            
            # Company size
            if 'company_size' in segment_customer_data.columns:
                size_dist = segment_customer_data['company_size'].value_counts()
                characteristics['company_sizes'] = size_dist.to_dict()
        
        if not segment_revenue_data.empty:
            # Purchase patterns
            characteristics['avg_transaction_size'] = float(segment_revenue_data['amount'].mean())
            characteristics['transaction_frequency'] = float(
                segment_revenue_data.groupby('customer_id').size().mean()
            )
            
            # Product preferences
            if 'product' in segment_revenue_data.columns:
                product_pref = segment_revenue_data['product'].value_counts().head(3)
                characteristics['preferred_products'] = product_pref.to_dict()
        
        return characteristics
    
    async def _calculate_segment_churn(self, segment_data: pd.DataFrame) -> float:
        """Calculate churn rate for a customer segment"""
        # Simplified churn calculation
        # In practice, you'd need temporal data to calculate actual churn
        
        # Check for last purchase date
        if 'last_purchase' in segment_data.columns:
            current_date = datetime.now()
            days_since_purchase = (current_date - pd.to_datetime(segment_data['last_purchase'])).dt.days
            
            # Consider customers with no purchase in 90 days as churned
            churned_customers = (days_since_purchase > 90).sum()
            total_customers = len(segment_data)
            
            return float(churned_customers / total_customers * 100) if total_customers > 0 else 0.0
        
        return 5.0  # Default churn rate
    
    async def _calculate_segment_growth(self, segment_data: pd.DataFrame) -> float:
        """Calculate growth rate for a customer segment"""
        # Simplified growth calculation
        # Would need temporal revenue data for accurate calculation
        
        if 'transaction_count' in segment_data.columns:
            avg_transactions = segment_data['transaction_count'].mean()
            # Assume growth correlates with transaction frequency
            return min(50.0, avg_transactions * 2.0)  # Cap at 50%
        
        return 10.0  # Default growth rate
    
    async def _calculate_price_elasticity(
        self,
        revenue_data: List[Dict],
        pricing_data: List[Dict],
        usage_data: List[Dict]
    ) -> Dict[str, float]:
        """Calculate price elasticity for different products/services"""
        elasticity = {}
        
        # Group by product/service
        revenue_df = pd.DataFrame(revenue_data)
        pricing_df = pd.DataFrame(pricing_data)
        
        if 'product' in revenue_df.columns and 'product' in pricing_df.columns:
            for product in revenue_df['product'].unique():
                product_revenue = revenue_df[revenue_df['product'] == product]
                product_pricing = pricing_df[pricing_df['product'] == product]
                
                if len(product_pricing) > 1:
                    # Calculate elasticity as percent change in quantity / percent change in price
                    # This is a simplified calculation
                    price_changes = product_pricing['price'].pct_change().dropna()
                    quantity_changes = product_revenue.groupby('date').size().pct_change().dropna()
                    
                    if len(price_changes) > 0 and len(quantity_changes) > 0:
                        # Simple average elasticity
                        avg_price_change = price_changes.mean()
                        avg_quantity_change = quantity_changes.mean()
                        
                        if avg_price_change != 0:
                            elasticity[product] = avg_quantity_change / avg_price_change
                        else:
                            elasticity[product] = 0.0
                    else:
                        elasticity[product] = -1.0  # Assume normal elasticity
                else:
                    elasticity[product] = -1.0  # Default elasticity
        
        return elasticity
    
    async def _generate_pricing_suggestions(
        self,
        current_pricing: Dict[str, Decimal],
        price_elasticity: Dict[str, float],
        revenue_data: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate pricing optimization suggestions"""
        suggestions = []
        
        for product, elasticity in price_elasticity.items():
            current_price = current_pricing.get(product)
            if current_price is None:
                continue
            
            # Inelastic demand (elasticity between -1 and 0) - can increase price
            if -1 < elasticity < 0:
                suggested_increase = min(0.2, abs(elasticity))  # Max 20% increase
                new_price = current_price * (1 + Decimal(str(suggested_increase)))
                
                suggestions.append({
                    'product': product,
                    'type': 'price_increase',
                    'current_price': float(current_price),
                    'suggested_price': float(new_price),
                    'expected_impact': f'Increase revenue by {suggested_increase*100:.1f}%',
                    'rationale': 'Demand is inelastic, price increase will boost revenue'
                })
            
            # Elastic demand (elasticity < -1) - consider price decrease
            elif elasticity < -1:
                suggested_decrease = min(0.15, 1/abs(elasticity))  # Max 15% decrease
                new_price = current_price * (1 - Decimal(str(suggested_decrease)))
                
                suggestions.append({
                    'product': product,
                    'type': 'price_decrease',
                    'current_price': float(current_price),
                    'suggested_price': float(new_price),
                    'expected_impact': f'Increase volume by {abs(elasticity)*suggested_decrease*100:.1f}%',
                    'rationale': 'Demand is elastic, price decrease will boost volume'
                })
        
        return suggestions
    
    async def _calculate_pricing_impact(
        self,
        suggestions: List[Dict],
        revenue_data: List[Dict]
    ) -> Dict[str, Decimal]:
        """Calculate potential revenue impact of pricing changes"""
        impact = {}
        
        # Calculate current revenue by product
        revenue_df = pd.DataFrame(revenue_data)
        if 'product' in revenue_df.columns:
            current_revenue_by_product = revenue_df.groupby('product')['amount'].sum()
            
            for suggestion in suggestions:
                product = suggestion['product']
                current_revenue = current_revenue_by_product.get(product, 0)
                
                if suggestion['type'] == 'price_increase':
                    # Assume some volume loss due to price increase
                    volume_loss = 0.05  # 5% volume loss
                    price_increase = (suggestion['suggested_price'] / suggestion['current_price']) - 1
                    
                    new_revenue = current_revenue * (1 + price_increase) * (1 - volume_loss)
                    impact[f"{product}_increase"] = Decimal(str(new_revenue - current_revenue))
                
                elif suggestion['type'] == 'price_decrease':
                    # Assume volume gain due to price decrease
                    volume_gain = 0.1  # 10% volume gain
                    price_decrease = 1 - (suggestion['suggested_price'] / suggestion['current_price'])
                    
                    new_revenue = current_revenue * (1 - price_decrease) * (1 + volume_gain)
                    impact[f"{product}_decrease"] = Decimal(str(new_revenue - current_revenue))
        
        return impact
    
    async def _generate_cohort_insights(
        self,
        retention_table: pd.DataFrame,
        revenue_table: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Generate insights from cohort analysis"""
        insights = []
        
        # Retention insights
        if not retention_table.empty:
            # Average retention rates by period
            avg_retention = retention_table.mean()
            
            # Find best and worst performing cohorts
            cohort_performance = retention_table.iloc[:, 1:6].mean(axis=1)  # First 6 months
            best_cohort = cohort_performance.idxmax()
            worst_cohort = cohort_performance.idxmin()
            
            insights.append({
                'type': 'retention',
                'title': 'Retention Analysis',
                'description': f'Best performing cohort: {best_cohort} ({cohort_performance[best_cohort]:.1%} avg retention)',
                'recommendation': 'Analyze successful cohort characteristics for replication'
            })
            
            insights.append({
                'type': 'retention',
                'title': 'Retention Challenge',
                'description': f'Worst performing cohort: {worst_cohort} ({cohort_performance[worst_cohort]:.1%} avg retention)',
                'recommendation': 'Investigate factors affecting this cohort and implement targeted retention strategies'
            })
        
        # Revenue insights
        if not revenue_table.empty:
            # Revenue growth by cohort
            revenue_growth = revenue_table.iloc[:, 1:].div(revenue_table.iloc[:, 0], axis=0)
            avg_growth = revenue_growth.mean()
            
            insights.append({
                'type': 'revenue',
                'title': 'Revenue Expansion',
                'description': f'Average revenue expansion in month 6: {avg_growth.iloc[5] if len(avg_growth) > 5 else "N/A"}',
                'recommendation': 'Focus on upselling and cross-selling to established customers'
            })
        
        return insights
    
    async def analyze_market_penetration(
        self,
        revenue_data: List[Dict],
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze market penetration and growth opportunities"""
        try:
            revenue_df = pd.DataFrame(revenue_data)
            total_revenue = revenue_df['amount'].sum()
            
            # Market share analysis
            total_addressable_market = market_data.get('tam', 1000000000)  # Default $1B TAM
            serviceable_addressable_market = market_data.get('sam', 100000000)  # Default $100M SAM
            
            market_share = (total_revenue / total_addressable_market) * 100
            sam_share = (total_revenue / serviceable_addressable_market) * 100
            
            # Growth opportunity
            market_growth_rate = market_data.get('growth_rate', 15)  # Default 15% market growth
            
            penetration_analysis = {
                'current_revenue': float(total_revenue),
                'market_share_tam': float(market_share),
                'market_share_sam': float(sam_share),
                'total_addressable_market': total_addressable_market,
                'serviceable_addressable_market': serviceable_addressable_market,
                'market_growth_rate': market_growth_rate,
                'revenue_potential': float(serviceable_addressable_market - total_revenue),
                'penetration_score': min(100, sam_share * 10),  # Scale to 0-100
                'growth_opportunities': self._identify_growth_opportunities(sam_share, market_growth_rate)
            }
            
            return penetration_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing market penetration: {str(e)}")
            return {}
    
    def _identify_growth_opportunities(self, sam_share: float, market_growth_rate: float) -> List[str]:
        """Identify specific growth opportunities"""
        opportunities = []
        
        if sam_share < 5:
            opportunities.append("Low market penetration - significant growth potential")
        
        if market_growth_rate > 20:
            opportunities.append("High market growth rate - ride the wave")
        
        if sam_share > 30:
            opportunities.append("High penetration - consider market expansion or new products")
        
        return opportunities
    
    async def calculate_revenue_quality_score(
        self,
        revenue_data: List[Dict],
        customer_data: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate a comprehensive revenue quality score"""
        try:
            revenue_df = pd.DataFrame(revenue_data)
            customer_df = pd.DataFrame(customer_data)
            
            score_components = {}
            
            # 1. Recurring revenue ratio (0-30 points)
            if 'type' in revenue_df.columns:
                recurring_revenue = revenue_df[revenue_df['type'] == 'subscription']['amount'].sum()
                total_revenue = revenue_df['amount'].sum()
                recurring_ratio = recurring_revenue / total_revenue if total_revenue > 0 else 0
                score_components['recurring_revenue'] = min(30, recurring_ratio * 30)
            else:
                score_components['recurring_revenue'] = 15  # Default middle score
            
            # 2. Customer concentration (0-25 points) - higher diversity = higher score
            customer_revenue = revenue_df.groupby('customer_id')['amount'].sum()
            gini = self._calculate_gini_coefficient(customer_revenue.values)
            concentration_score = max(0, 25 - (gini * 25))  # Lower Gini = higher score
            score_components['customer_concentration'] = concentration_score
            
            # 3. Revenue growth stability (0-25 points)
            daily_revenue = revenue_df.groupby(revenue_df['date'].dt.date)['amount'].sum()
            if len(daily_revenue) > 30:
                revenue_volatility = daily_revenue.std() / daily_revenue.mean()
                stability_score = max(0, 25 - (revenue_volatility * 50))
                score_components['growth_stability'] = min(25, stability_score)
            else:
                score_components['growth_stability'] = 12.5
            
            # 4. Customer retention proxy (0-20 points)
            if 'signup_date' in customer_df.columns:
                customer_age = (datetime.now() - pd.to_datetime(customer_df['signup_date'])).dt.days
                avg_customer_age = customer_age.mean()
                retention_score = min(20, avg_customer_age / 10)  # 200 days = full score
                score_components['customer_retention'] = retention_score
            else:
                score_components['customer_retention'] = 10
            
            total_score = sum(score_components.values())
            
            # Determine quality rating
            if total_score >= 80:
                quality_rating = "Excellent"
            elif total_score >= 65:
                quality_rating = "Good"
            elif total_score >= 50:
                quality_rating = "Fair"
            else:
                quality_rating = "Poor"
            
            return {
                'total_score': total_score,
                'quality_rating': quality_rating,
                'score_components': score_components,
                'improvement_areas': self._identify_improvement_areas(score_components)
            }
            
        except Exception as e:
            logger.error(f"Error calculating revenue quality score: {str(e)}")
            return {}
    
    def _identify_improvement_areas(self, score_components: Dict[str, float]) -> List[str]:
        """Identify areas for revenue quality improvement"""
        improvements = []
        
        if score_components.get('recurring_revenue', 0) < 20:
            improvements.append("Increase recurring revenue through subscriptions")
        
        if score_components.get('customer_concentration', 0) < 15:
            improvements.append("Diversify customer base to reduce concentration risk")
        
        if score_components.get('growth_stability', 0) < 15:
            improvements.append("Improve revenue predictability and reduce volatility")
        
        if score_components.get('customer_retention', 0) < 12:
            improvements.append("Focus on customer retention and loyalty programs")
        
        return improvements


# Example usage and utility functions
async def main():
    """Example usage of the RevenueAnalyzer"""
    analyzer = RevenueAnalyzer()
    
    # Example revenue data
    revenue_data = [
        {'customer_id': 'c1', 'amount': 1000, 'date': '2024-01-01', 'type': 'subscription', 'product': 'api'},
        {'customer_id': 'c2', 'amount': 500, 'date': '2024-01-02', 'type': 'usage', 'product': 'storage'},
        {'customer_id': 'c1', 'amount': 1000, 'date': '2024-02-01', 'type': 'subscription', 'product': 'api'},
        {'customer_id': 'c3', 'amount': 2000, 'date': '2024-02-15', 'type': 'subscription', 'product': 'api'},
    ]
    
    # Example customer data
    customer_data = [
        {'customer_id': 'c1', 'signup_date': '2023-12-01', 'country': 'US', 'industry': 'tech'},
        {'customer_id': 'c2', 'signup_date': '2024-01-01', 'country': 'UK', 'industry': 'finance'},
        {'customer_id': 'c3', 'signup_date': '2024-02-01', 'country': 'US', 'industry': 'healthcare'},
    ]
    
    # Perform revenue analysis
    analysis = await analyzer.analyze_revenue_performance(
        revenue_data=revenue_data,
        customer_data=customer_data,
        period=AnalysisPeriod.MONTHLY
    )
    
    print(f"Total Revenue: ${analysis.total_revenue}")
    print(f"Growth Rate: {analysis.growth_metrics.get('period_growth_rate', 0):.1f}%")
    print(f"Customer Segments: {len(analysis.customer_segments)}")
    print(f"Recommendations: {len(analysis.recommendations)}")
    
    # Customer segmentation
    segments = await analyzer.analyze_customer_segments(
        customer_data=customer_data,
        revenue_data=revenue_data,
        segmentation_method="revenue_based"
    )
    
    for segment in segments:
        print(f"Segment: {segment.name}, Customers: {segment.customer_count}, Revenue: ${segment.total_revenue}")
    
    # Revenue quality score
    quality_score = await analyzer.calculate_revenue_quality_score(
        revenue_data=revenue_data,
        customer_data=customer_data
    )
    
    print(f"Revenue Quality Score: {quality_score.get('total_score', 0):.1f}/100 ({quality_score.get('quality_rating', 'N/A')})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())