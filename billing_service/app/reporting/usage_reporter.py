"""
Usage Reporting Service
Generates comprehensive usage reports, analytics, and insights
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from decimal import Decimal
import json
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

class ReportType(Enum):
    USAGE_SUMMARY = "usage_summary"
    CUSTOMER_ACTIVITY = "customer_activity"
    API_ANALYTICS = "api_analytics"
    BILLING_REPORT = "billing_report"
    PERFORMANCE_METRICS = "performance_metrics"
    CUSTOM_REPORT = "custom_report"

class ReportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "xlsx"

class AggregationPeriod(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

@dataclass
class UsageMetric:
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class CustomerUsageReport:
    customer_id: str
    customer_name: str
    period_start: datetime
    period_end: datetime
    total_requests: int
    total_tokens: int
    total_cost: Decimal
    avg_response_time: float
    error_rate: float
    top_endpoints: List[Dict[str, Any]]
    usage_trends: Dict[str, List[float]]

@dataclass
class SystemReport:
    report_id: str
    report_type: ReportType
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    summary_metrics: Dict[str, Any]
    detailed_data: Dict[str, Any]
    insights: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]

class UsageReporter:
    """Comprehensive usage reporting and analytics service"""
    
    def __init__(self):
        self.report_cache = {}
        self.custom_metrics = {}
        
    async def generate_usage_summary_report(
        self,
        start_date: datetime,
        end_date: datetime,
        aggregation: AggregationPeriod = AggregationPeriod.DAILY,
        include_predictions: bool = False
    ) -> SystemReport:
        """Generate comprehensive usage summary report"""
        try:
            report_id = f"usage_summary_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            
            # Collect usage data
            usage_data = await self._collect_usage_data(start_date, end_date)
            
            # Calculate summary metrics
            summary_metrics = await self._calculate_summary_metrics(usage_data, aggregation)
            
            # Generate detailed analysis
            detailed_data = await self._generate_detailed_analysis(usage_data, aggregation)
            
            # Generate insights
            insights = await self._generate_usage_insights(usage_data, summary_metrics)
            
            # Generate recommendations
            recommendations = await self._generate_usage_recommendations(insights, summary_metrics)
            
            # Add predictions if requested
            if include_predictions:
                predictions = await self._generate_usage_predictions(usage_data)
                detailed_data['predictions'] = predictions
            
            logger.info(f"Usage summary report generated: {report_id}")
            
            return SystemReport(
                report_id=report_id,
                report_type=ReportType.USAGE_SUMMARY,
                generated_at=datetime.now(),
                period_start=start_date,
                period_end=end_date,
                summary_metrics=summary_metrics,
                detailed_data=detailed_data,
                insights=insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating usage summary report: {str(e)}")
            raise
    
    async def generate_customer_activity_report(
        self,
        customer_id: Optional[str] = None,
        start_date: datetime = None,
        end_date: datetime = None,
        include_comparisons: bool = True
    ) -> List[CustomerUsageReport]:
        """Generate detailed customer activity reports"""
        try:
            if start_date is None:
                start_date = datetime.now() - timedelta(days=30)
            if end_date is None:
                end_date = datetime.now()
            
            # Get customer list
            if customer_id:
                customers = [customer_id]
            else:
                customers = await self._get_active_customers(start_date, end_date)
            
            reports = []
            
            for cust_id in customers:
                # Collect customer data
                customer_data = await self._collect_customer_data(cust_id, start_date, end_date)
                
                if not customer_data:
                    continue
                
                # Calculate customer metrics
                customer_metrics = await self._calculate_customer_metrics(customer_data)
                
                # Generate usage trends
                usage_trends = await self._calculate_usage_trends(customer_data)
                
                # Get top endpoints
                top_endpoints = await self._get_top_endpoints(customer_data)
                
                # Create customer report
                report = CustomerUsageReport(
                    customer_id=cust_id,
                    customer_name=customer_data.get('customer_name', f'Customer {cust_id}'),
                    period_start=start_date,
                    period_end=end_date,
                    total_requests=customer_metrics['total_requests'],
                    total_tokens=customer_metrics['total_tokens'],
                    total_cost=customer_metrics['total_cost'],
                    avg_response_time=customer_metrics['avg_response_time'],
                    error_rate=customer_metrics['error_rate'],
                    top_endpoints=top_endpoints,
                    usage_trends=usage_trends
                )
                
                reports.append(report)
            
            logger.info(f"Generated customer activity reports for {len(reports)} customers")
            return reports
            
        except Exception as e:
            logger.error(f"Error generating customer activity reports: {str(e)}")
            raise
    
    async def generate_api_analytics_report(
        self,
        start_date: datetime,
        end_date: datetime,
        endpoint_filter: Optional[List[str]] = None
    ) -> SystemReport:
        """Generate detailed API analytics report"""
        try:
            report_id = f"api_analytics_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            
            # Collect API usage data
            api_data = await self._collect_api_data(start_date, end_date, endpoint_filter)
            
            # Calculate API metrics
            summary_metrics = {
                'total_requests': sum(req['count'] for req in api_data),
                'unique_endpoints': len(set(req['endpoint'] for req in api_data)),
                'avg_response_time': np.mean([req['response_time'] for req in api_data]),
                'error_rate': np.mean([req['error_rate'] for req in api_data]) * 100,
                'peak_rps': max(req['rps'] for req in api_data) if api_data else 0
            }
            
            # Detailed endpoint analysis
            endpoint_analysis = await self._analyze_endpoints(api_data)
            
            # Performance analysis
            performance_analysis = await self._analyze_api_performance(api_data)
            
            # Usage patterns
            usage_patterns = await self._analyze_usage_patterns(api_data)
            
            detailed_data = {
                'endpoint_analysis': endpoint_analysis,
                'performance_analysis': performance_analysis,
                'usage_patterns': usage_patterns,
                'error_analysis': await self._analyze_api_errors(api_data)
            }
            
            # Generate insights
            insights = await self._generate_api_insights(api_data, summary_metrics)
            
            # Generate recommendations
            recommendations = await self._generate_api_recommendations(insights)
            
            logger.info(f"API analytics report generated: {report_id}")
            
            return SystemReport(
                report_id=report_id,
                report_type=ReportType.API_ANALYTICS,
                generated_at=datetime.now(),
                period_start=start_date,
                period_end=end_date,
                summary_metrics=summary_metrics,
                detailed_data=detailed_data,
                insights=insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating API analytics report: {str(e)}")
            raise
    
    async def generate_billing_report(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[str] = None,
        include_forecasts: bool = True
    ) -> SystemReport:
        """Generate comprehensive billing and revenue report"""
        try:
            report_id = f"billing_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            
            # Collect billing data
            billing_data = await self._collect_billing_data(start_date, end_date, customer_id)
            
            # Calculate billing metrics
            summary_metrics = {
                'total_revenue': sum(Decimal(str(bill['amount'])) for bill in billing_data),
                'total_customers': len(set(bill['customer_id'] for bill in billing_data)),
                'avg_revenue_per_customer': 0,
                'subscription_revenue': sum(
                    Decimal(str(bill['amount'])) for bill in billing_data 
                    if bill.get('type') == 'subscription'
                ),
                'usage_revenue': sum(
                    Decimal(str(bill['amount'])) for bill in billing_data 
                    if bill.get('type') == 'usage'
                )
            }
            
            if summary_metrics['total_customers'] > 0:
                summary_metrics['avg_revenue_per_customer'] = (
                    summary_metrics['total_revenue'] / summary_metrics['total_customers']
                )
            
            # Revenue breakdown analysis
            revenue_breakdown = await self._analyze_revenue_breakdown(billing_data)
            
            # Customer tier analysis
            customer_tiers = await self._analyze_customer_tiers(billing_data)
            
            # Billing trends
            billing_trends = await self._analyze_billing_trends(billing_data)
            
            detailed_data = {
                'revenue_breakdown': revenue_breakdown,
                'customer_tiers': customer_tiers,
                'billing_trends': billing_trends
            }
            
            # Add forecasts if requested
            if include_forecasts:
                forecasts = await self._generate_billing_forecasts(billing_data)
                detailed_data['forecasts'] = forecasts
            
            # Generate insights
            insights = await self._generate_billing_insights(billing_data, summary_metrics)
            
            # Generate recommendations
            recommendations = await self._generate_billing_recommendations(insights)
            
            logger.info(f"Billing report generated: {report_id}")
            
            return SystemReport(
                report_id=report_id,
                report_type=ReportType.BILLING_REPORT,
                generated_at=datetime.now(),
                period_start=start_date,
                period_end=end_date,
                summary_metrics=summary_metrics,
                detailed_data=detailed_data,
                insights=insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating billing report: {str(e)}")
            raise
    
    async def generate_performance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        include_sla_analysis: bool = True
    ) -> SystemReport:
        """Generate system performance report"""
        try:
            report_id = f"performance_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            
            # Collect performance data
            performance_data = await self._collect_performance_data(start_date, end_date)
            
            # Calculate performance metrics
            summary_metrics = {
                'avg_response_time': np.mean([p['response_time'] for p in performance_data]),
                'p95_response_time': np.percentile([p['response_time'] for p in performance_data], 95),
                'p99_response_time': np.percentile([p['response_time'] for p in performance_data], 99),
                'uptime_percentage': await self._calculate_uptime(performance_data),
                'error_rate': np.mean([p['error_rate'] for p in performance_data]) * 100,
                'throughput': np.mean([p['requests_per_second'] for p in performance_data])
            }
            
            # Performance trends
            performance_trends = await self._analyze_performance_trends(performance_data)
            
            # Bottleneck analysis
            bottlenecks = await self._identify_bottlenecks(performance_data)
            
            # Resource utilization
            resource_usage = await self._analyze_resource_usage(performance_data)
            
            detailed_data = {
                'performance_trends': performance_trends,
                'bottlenecks': bottlenecks,
                'resource_usage': resource_usage
            }
            
            # SLA analysis if requested
            if include_sla_analysis:
                sla_analysis = await self._analyze_sla_compliance(performance_data)
                detailed_data['sla_analysis'] = sla_analysis
            
            # Generate insights
            insights = await self._generate_performance_insights(performance_data, summary_metrics)
            
            # Generate recommendations
            recommendations = await self._generate_performance_recommendations(insights, bottlenecks)
            
            logger.info(f"Performance report generated: {report_id}")
            
            return SystemReport(
                report_id=report_id,
                report_type=ReportType.PERFORMANCE_METRICS,
                generated_at=datetime.now(),
                period_start=start_date,
                period_end=end_date,
                summary_metrics=summary_metrics,
                detailed_data=detailed_data,
                insights=insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            raise
    
    async def generate_custom_report(
        self,
        report_config: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> SystemReport:
        """Generate custom report based on configuration"""
        try:
            report_id = f"custom_{report_config.get('name', 'report')}_{start_date.strftime('%Y%m%d')}"
            
            # Extract configuration
            metrics = report_config.get('metrics', [])
            filters = report_config.get('filters', {})
            aggregations = report_config.get('aggregations', ['sum', 'avg'])
            
            # Collect data based on configuration
            custom_data = await self._collect_custom_data(
                start_date, end_date, metrics, filters
            )
            
            # Calculate custom metrics
            summary_metrics = await self._calculate_custom_metrics(
                custom_data, aggregations
            )
            
            # Generate visualizations data
            detailed_data = await self._generate_custom_analysis(
                custom_data, report_config
            )
            
            # Generate insights
            insights = await self._generate_custom_insights(
                custom_data, summary_metrics, report_config
            )
            
            recommendations = []  # Custom reports may not have standard recommendations
            
            logger.info(f"Custom report generated: {report_id}")
            
            return SystemReport(
                report_id=report_id,
                report_type=ReportType.CUSTOM_REPORT,
                generated_at=datetime.now(),
                period_start=start_date,
                period_end=end_date,
                summary_metrics=summary_metrics,
                detailed_data=detailed_data,
                insights=insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating custom report: {str(e)}")
            raise
    
    async def export_report(
        self,
        report: SystemReport,
        format_type: ReportFormat,
        include_charts: bool = True
    ) -> bytes:
        """Export report in specified format"""
        try:
            if format_type == ReportFormat.JSON:
                return await self._export_json(report)
            elif format_type == ReportFormat.CSV:
                return await self._export_csv(report)
            elif format_type == ReportFormat.PDF:
                return await self._export_pdf(report, include_charts)
            elif format_type == ReportFormat.EXCEL:
                return await self._export_excel(report, include_charts)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting report: {str(e)}")
            raise
    
    # Data collection methods
    async def _collect_usage_data(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Collect comprehensive usage data"""
        # This would typically query your database
        # Returning mock data structure for demonstration
        return [
            {
                'timestamp': start_date + timedelta(hours=i),
                'requests': np.random.randint(100, 1000),
                'tokens': np.random.randint(10000, 100000),
                'response_time': np.random.uniform(50, 500),
                'errors': np.random.randint(0, 50),
                'endpoint': f'/api/v1/endpoint_{i % 5}',
                'customer_id': f'customer_{i % 10}'
            }
            for i in range(int((end_date - start_date).total_seconds() / 3600))
        ]
    
    async def _collect_customer_data(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Collect data for specific customer"""
        # Mock customer data
        return {
            'customer_id': customer_id,
            'customer_name': f'Customer {customer_id}',
            'requests': [
                {
                    'timestamp': start_date + timedelta(hours=i),
                    'endpoint': f'/api/v1/endpoint_{i % 3}',
                    'tokens': np.random.randint(100, 1000),
                    'response_time': np.random.uniform(50, 300),
                    'status': 200 if np.random.random() > 0.05 else 500
                }
                for i in range(24 * int((end_date - start_date).days))
            ]
        }
    
    async def _collect_api_data(
        self,
        start_date: datetime,
        end_date: datetime,
        endpoint_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Collect API usage data"""
        endpoints = endpoint_filter or ['/api/v1/chat', '/api/v1/embeddings', '/api/v1/completions']
        
        return [
            {
                'endpoint': endpoint,
                'timestamp': start_date + timedelta(hours=i),
                'count': np.random.randint(50, 500),
                'response_time': np.random.uniform(100, 800),
                'error_rate': np.random.uniform(0.01, 0.1),
                'rps': np.random.uniform(10, 100)
            }
            for endpoint in endpoints
            for i in range(int((end_date - start_date).total_seconds() / 3600))
        ]
    
    async def _collect_billing_data(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Collect billing and revenue data"""
        return [
            {
                'customer_id': customer_id or f'customer_{i % 20}',
                'amount': np.random.uniform(10, 1000),
                'type': np.random.choice(['subscription', 'usage']),
                'timestamp': start_date + timedelta(days=i),
                'product': np.random.choice(['api_calls', 'storage', 'compute'])
            }
            for i in range((end_date - start_date).days)
        ]
    
    async def _collect_performance_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Collect system performance data"""
        return [
            {
                'timestamp': start_date + timedelta(minutes=i * 5),
                'response_time': np.random.uniform(50, 500),
                'requests_per_second': np.random.uniform(10, 200),
                'error_rate': np.random.uniform(0.001, 0.05),
                'cpu_usage': np.random.uniform(20, 80),
                'memory_usage': np.random.uniform(30, 90),
                'disk_usage': np.random.uniform(40, 85)
            }
            for i in range(int((end_date - start_date).total_seconds() / 300))
        ]
    
    # Calculation methods
    async def _calculate_summary_metrics(
        self,
        usage_data: List[Dict[str, Any]],
        aggregation: AggregationPeriod
    ) -> Dict[str, Any]:
        """Calculate summary metrics from usage data"""
        if not usage_data:
            return {}
        
        df = pd.DataFrame(usage_data)
        
        return {
            'total_requests': df['requests'].sum(),
            'total_tokens': df['tokens'].sum(),
            'avg_response_time': df['response_time'].mean(),
            'peak_response_time': df['response_time'].max(),
            'total_errors': df['errors'].sum(),
            'error_rate': (df['errors'].sum() / df['requests'].sum()) * 100 if df['requests'].sum() > 0 else 0,
            'unique_customers': df['customer_id'].nunique(),
            'unique_endpoints': df['endpoint'].nunique(),
            'requests_per_hour': df['requests'].sum() / len(df) if len(df) > 0 else 0
        }
    
    async def _calculate_customer_metrics(
        self,
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate metrics for individual customer"""
        requests = customer_data.get('requests', [])
        if not requests:
            return {
                'total_requests': 0,
                'total_tokens': 0,
                'total_cost': Decimal('0'),
                'avg_response_time': 0,
                'error_rate': 0
            }
        
        df = pd.DataFrame(requests)
        error_count = len(df[df['status'] != 200])
        
        return {
            'total_requests': len(requests),
            'total_tokens': df['tokens'].sum(),
            'total_cost': Decimal(str(df['tokens'].sum() * 0.002)),  # Mock pricing
            'avg_response_time': df['response_time'].mean(),
            'error_rate': (error_count / len(requests)) * 100 if requests else 0
        }
    
    async def _generate_detailed_analysis(
        self,
        usage_data: List[Dict[str, Any]],
        aggregation: AggregationPeriod
    ) -> Dict[str, Any]:
        """Generate detailed analysis from usage data"""
        if not usage_data:
            return {}
        
        df = pd.DataFrame(usage_data)
        
        # Time-based analysis
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Endpoint analysis
        endpoint_stats = df.groupby('endpoint').agg({
            'requests': 'sum',
            'tokens': 'sum',
            'response_time': 'mean',
            'errors': 'sum'
        }).to_dict('index')
        
        # Customer analysis
        customer_stats = df.groupby('customer_id').agg({
            'requests': 'sum',
            'tokens': 'sum',
            'response_time': 'mean'
        }).to_dict('index')
        
        # Hourly patterns
        df['hour'] = df['timestamp'].dt.hour
        hourly_patterns = df.groupby('hour')['requests'].sum().to_dict()
        
        return {
            'endpoint_analysis': endpoint_stats,
            'customer_analysis': customer_stats,
            'hourly_patterns': hourly_patterns,
            'peak_usage_hour': max(hourly_patterns, key=hourly_patterns.get) if hourly_patterns else 0
        }
    
    async def _calculate_usage_trends(
        self,
        customer_data: Dict[str, Any]
    ) -> Dict[str, List[float]]:
        """Calculate usage trends for customer"""
        requests = customer_data.get('requests', [])
        if not requests:
            return {}
        
        df = pd.DataFrame(requests)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        daily_usage = df.groupby('date').agg({
            'tokens': 'sum',
            'response_time': 'mean'
        })
        
        return {
            'daily_tokens': daily_usage['tokens'].tolist(),
            'daily_response_time': daily_usage['response_time'].tolist()
        }
    
    async def _get_top_endpoints(
        self,
        customer_data: Dict[str, Any],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top endpoints for customer"""
        requests = customer_data.get('requests', [])
        if not requests:
            return []
        
        df = pd.DataFrame(requests)
        endpoint_stats = df.groupby('endpoint').agg({
            'endpoint': 'count',
            'tokens': 'sum',
            'response_time': 'mean'
        }).rename(columns={'endpoint': 'count'})
        
        top_endpoints = endpoint_stats.nlargest(limit, 'count')
        
        return [
            {
                'endpoint': endpoint,
                'requests': row['count'],
                'tokens': row['tokens'],
                'avg_response_time': row['response_time']
            }
            for endpoint, row in top_endpoints.iterrows()
        ]
    
    # Analysis methods
    async def _analyze_endpoints(
        self,
        api_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze endpoint performance and usage"""
        if not api_data:
            return {}
        
        df = pd.DataFrame(api_data)
        
        endpoint_analysis = df.groupby('endpoint').agg({
            'count': 'sum',
            'response_time': 'mean',
            'error_rate': 'mean',
            'rps': 'max'
        }).to_dict('index')
        
        # Find slowest and fastest endpoints
        slowest_endpoint = df.loc[df['response_time'].idxmax(), 'endpoint']
        fastest_endpoint = df.loc[df['response_time'].idxmin(), 'endpoint']
        
        return {
            'endpoint_stats': endpoint_analysis,
            'slowest_endpoint': slowest_endpoint,
            'fastest_endpoint': fastest_endpoint,
            'total_endpoints': df['endpoint'].nunique()
        }
    
    async def _analyze_api_performance(
        self,
        api_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze API performance metrics"""
        if not api_data:
            return {}
        
        df = pd.DataFrame(api_data)
        
        return {
            'response_time_distribution': {
                'p50': df['response_time'].quantile(0.5),
                'p95': df['response_time'].quantile(0.95),
                'p99': df['response_time'].quantile(0.99)
            },
            'performance_trends': {
                'improving': df['response_time'].diff().mean() < 0,
                'degrading': df['response_time'].diff().mean() > 0
            },
            'peak_performance_time': df.loc[df['rps'].idxmax(), 'timestamp'] if not df.empty else None
        }
    
    async def _analyze_usage_patterns(
        self,
        api_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze usage patterns and seasonality"""
        if not api_data:
            return {}
        
        df = pd.DataFrame(api_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Hourly patterns
        hourly_usage = df.groupby('hour')['count'].sum()
        
        # Weekly patterns
        weekly_usage = df.groupby('day_of_week')['count'].sum()
        
        return {
            'peak_hour': int(hourly_usage.idxmax()),
            'low_usage_hour': int(hourly_usage.idxmin()),
            'peak_day': int(weekly_usage.idxmax()),
            'hourly_distribution': hourly_usage.to_dict(),
            'weekly_distribution': weekly_usage.to_dict()
        }
    
    async def _analyze_api_errors(
        self,
        api_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze API error patterns"""
        if not api_data:
            return {}
        
        df = pd.DataFrame(api_data)
        
        # Error rate by endpoint
        error_by_endpoint = df.groupby('endpoint')['error_rate'].mean().to_dict()
        
        # Overall error trends
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.sort_values('timestamp')
        error_trend = df_sorted['error_rate'].rolling(window=24).mean().iloc[-1] if len(df_sorted) >= 24 else df['error_rate'].mean()
        
        return {
            'error_by_endpoint': error_by_endpoint,
            'avg_error_rate': df['error_rate'].mean(),
            'highest_error_endpoint': max(error_by_endpoint, key=error_by_endpoint.get) if error_by_endpoint else None,
            'error_trend': 'increasing' if error_trend > df['error_rate'].mean() else 'decreasing'
        }
    
    # Insight generation methods
    async def _generate_usage_insights(
        self,
        usage_data: List[Dict[str, Any]],
        summary_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate insights from usage data"""
        insights = []
        
        # High error rate insight
        error_rate = summary_metrics.get('error_rate', 0)
        if error_rate > 5:
            insights.append({
                'type': 'alert',
                'severity': 'high',
                'title': 'High Error Rate Detected',
                'description': f'Error rate of {error_rate:.1f}% exceeds acceptable threshold',
                'impact': 'User experience degradation',
                'action_required': True
            })
        
        # Peak usage insight
        peak_response_time = summary_metrics.get('peak_response_time', 0)
        avg_response_time = summary_metrics.get('avg_response_time', 0)
        
        if peak_response_time > avg_response_time * 3:
            insights.append({
                'type': 'performance',
                'severity': 'medium',
                'title': 'Response Time Spikes',
                'description': f'Peak response time ({peak_response_time:.0f}ms) is significantly higher than average',
                'impact': 'Potential performance bottlenecks',
                'action_required': True
            })
        
        # Growth insight
        total_requests = summary_metrics.get('total_requests', 0)
        if total_requests > 10000:
            insights.append({
                'type': 'growth',
                'severity': 'info',
                'title': 'High API Usage',
                'description': f'Processing {total_requests:,} requests indicates strong platform adoption',
                'impact': 'Consider scaling infrastructure',
                'action_required': False
            })
        
        return insights
    
    async def _generate_usage_recommendations(
        self,
        insights: List[Dict[str, Any]],
        summary_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Error rate recommendations
        for insight in insights:
            if insight['type'] == 'alert' and 'error rate' in insight['description'].lower():
                recommendations.append({
                    'priority': 'high',
                    'category': 'reliability',
                    'title': 'Improve Error Handling',
                    'description': 'Implement better error handling and monitoring',
                    'expected_impact': 'Reduce error rate to < 2%',
                    'effort': 'medium'
                })
        
        # Performance recommendations
        avg_response_time = summary_metrics.get('avg_response_time', 0)
        if avg_response_time > 200:
            recommendations.append({
                'priority': 'medium',
                'category': 'performance',
                'title': 'Optimize Response Times',
                'description': 'Consider caching, database optimization, or CDN implementation',
                'expected_impact': f'Reduce average response time from {avg_response_time:.0f}ms to <200ms',
                'effort': 'high'
            })
        
        return recommendations
    
    async def _generate_api_insights(
        self,
        api_data: List[Dict[str, Any]],
        summary_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate insights from API data"""
        insights = []
        
        # Response time insight
        avg_response_time = summary_metrics.get('avg_response_time', 0)
        if avg_response_time > 500:
            insights.append({
                'type': 'performance',
                'severity': 'high',
                'title': 'Slow API Response Times',
                'description': f'Average response time of {avg_response_time:.0f}ms is above optimal threshold',
                'impact': 'Poor user experience and potential timeouts',
                'action_required': True
            })
        
        # Error rate insight
        error_rate = summary_metrics.get('error_rate', 0)
        if error_rate > 2:
            insights.append({
                'type': 'reliability',
                'severity': 'medium',
                'title': 'Elevated Error Rate',
                'description': f'API error rate of {error_rate:.1f}% requires attention',
                'impact': 'Reduced API reliability',
                'action_required': True
            })
        
        # Throughput insight
        peak_rps = summary_metrics.get('peak_rps', 0)
        if peak_rps > 500:
            insights.append({
                'type': 'capacity',
                'severity': 'info',
                'title': 'High Throughput Detected',
                'description': f'Peak RPS of {peak_rps:.0f} indicates high demand',
                'impact': 'May need capacity planning',
                'action_required': False
            })
        
        return insights
    
    async def _generate_api_recommendations(
        self,
        insights: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate API-specific recommendations"""
        recommendations = []
        
        for insight in insights:
            if insight['type'] == 'performance':
                recommendations.append({
                    'priority': 'high',
                    'category': 'optimization',
                    'title': 'Implement API Caching',
                    'description': 'Add caching layers to reduce response times',
                    'expected_impact': 'Reduce response times by 30-50%',
                    'effort': 'medium'
                })
            elif insight['type'] == 'reliability':
                recommendations.append({
                    'priority': 'high',
                    'category': 'reliability',
                    'title': 'Enhance Error Handling',
                    'description': 'Implement circuit breakers and better retry logic',
                    'expected_impact': 'Reduce error rate to < 1%',
                    'effort': 'high'
                })
            elif insight['type'] == 'capacity':
                recommendations.append({
                    'priority': 'medium',
                    'category': 'scaling',
                    'title': 'Scale Infrastructure',
                    'description': 'Consider horizontal scaling to handle increased load',
                    'expected_impact': 'Support 2x current throughput',
                    'effort': 'high'
                })
        
        return recommendations
    
    async def _generate_billing_insights(
        self,
        billing_data: List[Dict[str, Any]],
        summary_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate billing and revenue insights"""
        insights = []
        
        # Revenue concentration
        if billing_data:
            df = pd.DataFrame(billing_data)
            top_customer_revenue = df.groupby('customer_id')['amount'].sum().max()
            total_revenue = float(summary_metrics.get('total_revenue', 0))
            
            if total_revenue > 0 and (top_customer_revenue / total_revenue) > 0.3:
                insights.append({
                    'type': 'risk',
                    'severity': 'medium',
                    'title': 'Revenue Concentration Risk',
                    'description': f'Top customer represents {(top_customer_revenue/total_revenue)*100:.1f}% of revenue',
                    'impact': 'High dependency on single customer',
                    'action_required': True
                })
        
        # Growth opportunity
        subscription_revenue = float(summary_metrics.get('subscription_revenue', 0))
        usage_revenue = float(summary_metrics.get('usage_revenue', 0))
        
        if usage_revenue > subscription_revenue * 2:
            insights.append({
                'type': 'opportunity',
                'severity': 'info',
                'title': 'Subscription Upsell Opportunity',
                'description': 'High usage revenue suggests customers may benefit from subscription plans',
                'impact': 'Potential for more predictable revenue',
                'action_required': False
            })
        
        return insights
    
    async def _generate_billing_recommendations(
        self,
        insights: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate billing-specific recommendations"""
        recommendations = []
        
        for insight in insights:
            if insight['type'] == 'risk':
                recommendations.append({
                    'priority': 'high',
                    'category': 'diversification',
                    'title': 'Diversify Customer Base',
                    'description': 'Focus on acquiring more customers to reduce concentration risk',
                    'expected_impact': 'Reduce single customer dependency',
                    'effort': 'high'
                })
            elif insight['type'] == 'opportunity':
                recommendations.append({
                    'priority': 'medium',
                    'category': 'monetization',
                    'title': 'Introduce Subscription Tiers',
                    'description': 'Create subscription plans for high-usage customers',
                    'expected_impact': 'Increase predictable recurring revenue',
                    'effort': 'medium'
                })
        
        return recommendations
    
    async def _generate_performance_insights(
        self,
        performance_data: List[Dict[str, Any]],
        summary_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate performance insights"""
        insights = []
        
        # Uptime insight
        uptime = summary_metrics.get('uptime_percentage', 100)
        if uptime < 99.9:
            insights.append({
                'type': 'availability',
                'severity': 'high',
                'title': 'Uptime Below SLA',
                'description': f'System uptime of {uptime:.2f}% is below 99.9% target',
                'impact': 'SLA violations and customer dissatisfaction',
                'action_required': True
            })
        
        # Response time insight
        p99_response_time = summary_metrics.get('p99_response_time', 0)
        if p99_response_time > 1000:
            insights.append({
                'type': 'performance',
                'severity': 'medium',
                'title': 'High P99 Response Time',
                'description': f'99th percentile response time of {p99_response_time:.0f}ms affects user experience',
                'impact': 'Poor experience for some users',
                'action_required': True
            })
        
        return insights
    
    async def _generate_performance_recommendations(
        self,
        insights: List[Dict[str, Any]],
        bottlenecks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate performance recommendations"""
        recommendations = []
        
        # Address bottlenecks
        for bottleneck in bottlenecks:
            if bottleneck['type'] == 'cpu':
                recommendations.append({
                    'priority': 'high',
                    'category': 'infrastructure',
                    'title': 'Scale CPU Resources',
                    'description': 'Increase CPU allocation or add more instances',
                    'expected_impact': 'Reduce CPU utilization to < 70%',
                    'effort': 'medium'
                })
            elif bottleneck['type'] == 'memory':
                recommendations.append({
                    'priority': 'high',
                    'category': 'infrastructure',
                    'title': 'Increase Memory Allocation',
                    'description': 'Add more memory or optimize memory usage',
                    'expected_impact': 'Reduce memory pressure and improve performance',
                    'effort': 'low'
                })
        
        # General performance recommendations
        for insight in insights:
            if insight['type'] == 'availability':
                recommendations.append({
                    'priority': 'critical',
                    'category': 'reliability',
                    'title': 'Implement High Availability',
                    'description': 'Add redundancy and failover mechanisms',
                    'expected_impact': 'Achieve 99.99% uptime',
                    'effort': 'high'
                })
        
        return recommendations
    
    # Additional analysis methods
    async def _analyze_billing_trends(
        self,
        billing_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze billing trends over time"""
        if not billing_data:
            return {}
        
        df = pd.DataFrame(billing_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        daily_revenue = df.groupby('date')['amount'].sum()
        
        # Calculate growth rate
        if len(daily_revenue) > 1:
            recent_avg = daily_revenue.tail(7).mean()
            previous_avg = daily_revenue.head(7).mean()
            growth_rate = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
        else:
            growth_rate = 0
        
        return {
            'daily_revenue': daily_revenue.to_dict(),
            'growth_rate': growth_rate,
            'trend': 'increasing' if growth_rate > 0 else 'decreasing',
            'peak_revenue_day': daily_revenue.idxmax() if not daily_revenue.empty else None
        }
    
    async def _generate_billing_forecasts(
        self,
        billing_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate billing forecasts"""
        if not billing_data:
            return {}
        
        df = pd.DataFrame(billing_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        daily_revenue = df.groupby('date')['amount'].sum()
        
        # Simple trend-based forecast
        if len(daily_revenue) >= 7:
            recent_trend = daily_revenue.tail(7).mean()
            forecast_next_30_days = recent_trend * 30
        else:
            forecast_next_30_days = daily_revenue.sum()
        
        return {
            'next_30_days': forecast_next_30_days,
            'confidence': 0.75,
            'methodology': 'trend_based'
        }
    
    async def _analyze_performance_trends(
        self,
        performance_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze performance trends"""
        if not performance_data:
            return {}
        
        df = pd.DataFrame(performance_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calculate trends
        response_time_trend = df['response_time'].rolling(window=12).mean().iloc[-1] - df['response_time'].rolling(window=12).mean().iloc[0] if len(df) >= 12 else 0
        error_rate_trend = df['error_rate'].rolling(window=12).mean().iloc[-1] - df['error_rate'].rolling(window=12).mean().iloc[0] if len(df) >= 12 else 0
        
        return {
            'response_time_trend': 'improving' if response_time_trend < 0 else 'degrading',
            'error_rate_trend': 'improving' if error_rate_trend < 0 else 'degrading',
            'throughput_trend': 'increasing' if df['requests_per_second'].diff().mean() > 0 else 'decreasing'
        }
    
    async def _analyze_sla_compliance(
        self,
        performance_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze SLA compliance"""
        if not performance_data:
            return {}
        
        df = pd.DataFrame(performance_data)
        
        # Define SLA thresholds
        sla_response_time = 200  # ms
        sla_uptime = 99.9  # %
        sla_error_rate = 0.01  # 1%
        
        # Calculate compliance
        response_time_compliance = (df['response_time'] <= sla_response_time).mean() * 100
        uptime_compliance = await self._calculate_uptime(performance_data.copy())
        error_rate_compliance = (df['error_rate'] <= sla_error_rate).mean() * 100
        
        return {
            'response_time_compliance': response_time_compliance,
            'uptime_compliance': uptime_compliance,
            'error_rate_compliance': error_rate_compliance,
            'overall_compliance': min(response_time_compliance, uptime_compliance, error_rate_compliance),
            'sla_breaches': {
                'response_time': len(df[df['response_time'] > sla_response_time]),
                'errors': len(df[df['error_rate'] > sla_error_rate])
            }
        }
    
    # Export methods
    async def _export_json(self, report: SystemReport) -> bytes:
        """Export report as JSON"""
        report_dict = asdict(report)
        # Convert non-serializable objects
        report_dict = self._serialize_report_data(report_dict)
        return json.dumps(report_dict, indent=2, default=str).encode('utf-8')
    
    async def _export_csv(self, report: SystemReport) -> bytes:
        """Export report as CSV"""
        # Create CSV from summary metrics
        df = pd.DataFrame([report.summary_metrics])
        return df.to_csv(index=False).encode('utf-8')
    
    async def _export_pdf(self, report: SystemReport, include_charts: bool = True) -> bytes:
        """Export report as PDF"""
        # This would require a PDF generation library like reportlab
        # For now, return a placeholder
        pdf_content = f"""
        {report.report_type.value.upper()} REPORT
        Generated: {report.generated_at}
        Period: {report.period_start} to {report.period_end}
        
        SUMMARY METRICS:
        {json.dumps(report.summary_metrics, indent=2, default=str)}
        
        INSIGHTS:
        {json.dumps(report.insights, indent=2, default=str)}
        
        RECOMMENDATIONS:
        {json.dumps(report.recommendations, indent=2, default=str)}
        """
        return pdf_content.encode('utf-8')
    
    async def _export_excel(self, report: SystemReport, include_charts: bool = True) -> bytes:
        """Export report as Excel"""
        # This would require openpyxl or xlsxwriter
        # For now, return CSV format
        return await self._export_csv(report)
    
    def _serialize_report_data(self, data: Any) -> Any:
        """Serialize report data for JSON export"""
        if isinstance(data, dict):
            return {k: self._serialize_report_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_report_data(item) for item in data]
        elif isinstance(data, (datetime, Decimal)):
            return str(data)
        elif isinstance(data, Enum):
            return data.value
        else:
            return data
    
    # Helper methods for additional analysis
    async def _get_active_customers(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """Get list of active customers in period"""
        # Mock implementation
        return [f'customer_{i}' for i in range(1, 11)]
    
    async def _generate_usage_predictions(
        self,
        usage_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate usage predictions"""
        # Simple trend-based prediction
        if not usage_data:
            return {}
        
        df = pd.DataFrame(usage_data)
        recent_trend = df['requests'].tail(10).mean()
        
        return {
            'next_week_requests': recent_trend * 7,
            'confidence': 0.75,
            'trend': 'increasing' if recent_trend > df['requests'].head(10).mean() else 'decreasing'
        }
    
    async def _calculate_uptime(self, performance_data: List[Dict[str, Any]]) -> float:
        """Calculate system uptime percentage"""
        if not performance_data:
            return 100.0
        
        # Consider error rate > 50% as downtime
        uptime_periods = sum(1 for p in performance_data if p['error_rate'] < 0.5)
        total_periods = len(performance_data)
        
        return (uptime_periods / total_periods) * 100 if total_periods > 0 else 100.0
    
    async def _identify_bottlenecks(
        self,
        performance_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify system bottlenecks"""
        if not performance_data:
            return []
        
        bottlenecks = []
        df = pd.DataFrame(performance_data)
        
        # High CPU usage
        if df['cpu_usage'].mean() > 70:
            bottlenecks.append({
                'type': 'cpu',
                'severity': 'high' if df['cpu_usage'].mean() > 85 else 'medium',
                'description': f'Average CPU usage: {df["cpu_usage"].mean():.1f}%'
            })
        
        # High memory usage
        if df['memory_usage'].mean() > 80:
            bottlenecks.append({
                'type': 'memory',
                'severity': 'high' if df['memory_usage'].mean() > 90 else 'medium',
                'description': f'Average memory usage: {df["memory_usage"].mean():.1f}%'
            })
        
        return bottlenecks
    
    async def _analyze_resource_usage(
        self,
        performance_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze resource utilization patterns"""
        if not performance_data:
            return {}
        
        df = pd.DataFrame(performance_data)
        
        return {
            'cpu_stats': {
                'avg': df['cpu_usage'].mean(),
                'max': df['cpu_usage'].max(),
                'min': df['cpu_usage'].min()
            },
            'memory_stats': {
                'avg': df['memory_usage'].mean(),
                'max': df['memory_usage'].max(),
                'min': df['memory_usage'].min()
            },
            'disk_stats': {
                'avg': df['disk_usage'].mean(),
                'max': df['disk_usage'].max(),
                'min': df['disk_usage'].min()
            }
        }
    
    # Additional helper methods for billing, API analysis, etc.
    async def _analyze_revenue_breakdown(self, billing_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze revenue by various dimensions"""
        if not billing_data:
            return {}
        
        df = pd.DataFrame(billing_data)
        
        return {
            'by_type': df.groupby('type')['amount'].sum().to_dict(),
            'by_product': df.groupby('product')['amount'].sum().to_dict(),
            'top_customers': df.groupby('customer_id')['amount'].sum().nlargest(5).to_dict()
        }
    
    async def _analyze_customer_tiers(self, billing_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze customer revenue tiers"""
        if not billing_data:
            return {}
        
        df = pd.DataFrame(billing_data)
        customer_revenue = df.groupby('customer_id')['amount'].sum()
        
        # Define tiers
        enterprise = customer_revenue[customer_revenue >= 1000].count()
        professional = customer_revenue[(customer_revenue >= 100) & (customer_revenue < 1000)].count()
        starter = customer_revenue[customer_revenue < 100].count()
        
        return {
            'enterprise': enterprise,
            'professional': professional,
            'starter': starter,
            'total_customers': len(customer_revenue)
        }
    
    async def _collect_custom_data(
        self,
        start_date: datetime,
        end_date: datetime,
        metrics: List[str],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Collect data for custom reports"""
        # Mock implementation - would query based on metrics and filters
        return [
            {
                'timestamp': start_date + timedelta(hours=i),
                **{metric: np.random.uniform(0, 100) for metric in metrics}
            }
            for i in range(24)
        ]
    
    async def _calculate_custom_metrics(
        self,
        data: List[Dict[str, Any]],
        aggregations: List[str]
    ) -> Dict[str, Any]:
        """Calculate custom metrics based on aggregation functions"""
        if not data:
            return {}
        
        df = pd.DataFrame(data)
        results = {}
        
        for column in df.select_dtypes(include=[np.number]).columns:
            if column != 'timestamp':
                for agg in aggregations:
                    if agg == 'sum':
                        results[f'{column}_sum'] = df[column].sum()
                    elif agg == 'avg':
                        results[f'{column}_avg'] = df[column].mean()
                    elif agg == 'max':
                        results[f'{column}_max'] = df[column].max()
                    elif agg == 'min':
                        results[f'{column}_min'] = df[column].min()
        
        return results
    
    async def _generate_custom_analysis(
        self,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate custom analysis based on configuration"""
        if not data:
            return {}
        
        df = pd.DataFrame(data)
        analysis = {}
        
        # Time-based grouping if configured
        if config.get('group_by_time'):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['timestamp'].dt.hour
            time_groups = df.groupby('hour').mean().to_dict()
            analysis['time_based'] = time_groups
        
        # Correlation analysis
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            correlation_matrix = df[numeric_cols].corr().to_dict()
            analysis['correlations'] = correlation_matrix
        
        return analysis
    
    async def _generate_custom_insights(
        self,
        data: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate insights for custom reports"""
        insights = []
        
        # Check for any metrics that exceed thresholds
        thresholds = config.get('thresholds', {})
        for metric, value in metrics.items():
            if metric in thresholds:
                threshold = thresholds[metric]
                if value > threshold:
                    insights.append({
                        'type': 'threshold',
                        'severity': 'medium',
                        'title': f'{metric} Exceeds Threshold',
                        'description': f'{metric} value of {value:.2f} exceeds threshold of {threshold}',
                        'impact': 'May require attention',
                        'action_required': True
                    })
        
        return insights


# Example usage
async def main():
    """Example usage of the UsageReporter"""
    reporter = UsageReporter()
    
    # Generate usage summary report
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    usage_report = await reporter.generate_usage_summary_report(
        start_date=start_date,
        end_date=end_date,
        aggregation=AggregationPeriod.DAILY,
        include_predictions=True
    )
    
    print(f"Usage Report Generated: {usage_report.report_id}")
    print(f"Total Requests: {usage_report.summary_metrics.get('total_requests', 0):,}")
    print(f"Error Rate: {usage_report.summary_metrics.get('error_rate', 0):.2f}%")
    print(f"Insights: {len(usage_report.insights)}")
    print(f"Recommendations: {len(usage_report.recommendations)}")
    
    # Export report as JSON
    json_export = await reporter.export_report(usage_report, ReportFormat.JSON)
    print(f"JSON Export Size: {len(json_export)} bytes")
    
    # Generate customer activity reports
    customer_reports = await reporter.generate_customer_activity_report(
        start_date=start_date,
        end_date=end_date
    )
    
    print(f"Generated {len(customer_reports)} customer reports")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())