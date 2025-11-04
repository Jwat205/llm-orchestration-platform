"""
Business Metrics Collection for LLM Platform
Track key business KPIs and user engagement metrics
"""

import time
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

@dataclass
class BusinessMetric:
    """Business metric definition"""
    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None

class BusinessMetricsCollector:
    """
    Comprehensive business metrics collection for LLM platform
    """
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.custom_metrics: Dict[str, Dict] = {}
        self.session_data: Dict[str, Dict] = {}
        
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available, using in-memory storage")
        
        self._setup_core_metrics()
    
    def _setup_core_metrics(self):
        """Initialize core business metrics"""
        
        # Revenue and billing metrics
        self.revenue_total = self._create_metric(
            "llm_platform_revenue_total",
            MetricType.COUNTER,
            "Total revenue generated",
            ["subscription_tier", "billing_period"]
        )
        
        self.active_subscriptions = self._create_metric(
            "llm_platform_active_subscriptions",
            MetricType.GAUGE,
            "Number of active subscriptions",
            ["tier", "status"]
        )
        
        # User engagement metrics
        self.user_sessions = self._create_metric(
            "llm_platform_user_sessions_total",
            MetricType.COUNTER,
            "Total user sessions",
            ["user_type", "session_duration_bucket"]
        )
        
        self.daily_active_users = self._create_metric(
            "llm_platform_daily_active_users",
            MetricType.GAUGE,
            "Daily active users"
        )
        
        self.monthly_active_users = self._create_metric(
            "llm_platform_monthly_active_users",
            MetricType.GAUGE,
            "Monthly active users"
        )
        
        # API usage metrics
        self.api_calls_total = self._create_metric(
            "llm_platform_api_calls_total",
            MetricType.COUNTER,
            "Total API calls",
            ["endpoint", "user_tier", "model", "success"]
        )
        
        self.tokens_processed = self._create_metric(
            "llm_platform_tokens_processed_total",
            MetricType.COUNTER,
            "Total tokens processed",
            ["model", "operation_type", "user_tier"]
        )
        
        self.api_latency = self._create_metric(
            "llm_platform_api_latency_seconds",
            MetricType.HISTOGRAM,
            "API call latency",
            ["endpoint", "model"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        # Model performance metrics
        self.model_inference_time = self._create_metric(
            "llm_platform_model_inference_seconds",
            MetricType.HISTOGRAM,
            "Model inference time",
            ["model_name", "model_size", "user_tier"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.model_accuracy = self._create_metric(
            "llm_platform_model_accuracy_score",
            MetricType.GAUGE,
            "Model accuracy score",
            ["model_name", "evaluation_dataset"]
        )
        
        # Cost and efficiency metrics
        self.compute_costs = self._create_metric(
            "llm_platform_compute_costs_total",
            MetricType.COUNTER,
            "Total compute costs",
            ["resource_type", "provider", "region"]
        )
        
        self.cost_per_token = self._create_metric(
            "llm_platform_cost_per_token",
            MetricType.GAUGE,
            "Cost per token processed",
            ["model", "tier"]
        )
        
        # User satisfaction metrics
        self.user_ratings = self._create_metric(
            "llm_platform_user_ratings_total",
            MetricType.COUNTER,
            "User ratings distribution",
            ["rating", "feature", "model"]
        )
        
        self.support_tickets = self._create_metric(
            "llm_platform_support_tickets_total",
            MetricType.COUNTER,
            "Support tickets created",
            ["category", "priority", "resolution_status"]
        )
        
        # Feature usage metrics
        self.feature_usage = self._create_metric(
            "llm_platform_feature_usage_total",
            MetricType.COUNTER,
            "Feature usage count",
            ["feature_name", "user_tier", "success"]
        )
        
        # Error and failure metrics
        self.business_errors = self._create_metric(
            "llm_platform_business_errors_total",
            MetricType.COUNTER,
            "Business logic errors",
            ["error_type", "severity", "component"]
        )
        
        # Conversion metrics
        self.trial_conversions = self._create_metric(
            "llm_platform_trial_conversions_total",
            MetricType.COUNTER,
            "Trial to paid conversions",
            ["source", "tier"]
        )
        
        self.churn_rate = self._create_metric(
            "llm_platform_churn_rate",
            MetricType.GAUGE,
            "Customer churn rate percentage",
            ["tier", "time_period"]
        )
    
    def _create_metric(self, name: str, metric_type: MetricType, description: str, 
                      labels: List[str] = None, buckets: List[float] = None):
        """Create a Prometheus metric or fallback to in-memory tracking"""
        labels = labels or []
        
        if PROMETHEUS_AVAILABLE:
            if metric_type == MetricType.COUNTER:
                return Counter(name, description, labels)
            elif metric_type == MetricType.GAUGE:
                return Gauge(name, description, labels)
            elif metric_type == MetricType.HISTOGRAM:
                if buckets:
                    return Histogram(name, description, labels, buckets=buckets)
                return Histogram(name, description, labels)
            elif metric_type == MetricType.SUMMARY:
                return Summary(name, description, labels)
        else:
            # Fallback to in-memory storage
            self.custom_metrics[name] = {
                'type': metric_type.value,
                'description': description,
                'labels': labels,
                'values': {},
                'last_updated': datetime.now()
            }
            return MockMetric(name, self.custom_metrics)
    
    # Revenue and billing tracking
    def track_revenue(self, amount: float, subscription_tier: str, billing_period: str):
        """Track revenue generation"""
        if PROMETHEUS_AVAILABLE:
            self.revenue_total.labels(
                subscription_tier=subscription_tier,
                billing_period=billing_period
            ).inc(amount)
        else:
            self._update_custom_metric("llm_platform_revenue_total", amount, {
                'subscription_tier': subscription_tier,
                'billing_period': billing_period
            })
        
        logger.info(f"Revenue tracked: ${amount} from {subscription_tier} ({billing_period})")
    
    def update_active_subscriptions(self, tier: str, status: str, count: int):
        """Update active subscription count"""
        if PROMETHEUS_AVAILABLE:
            self.active_subscriptions.labels(tier=tier, status=status).set(count)
        else:
            self._set_custom_metric("llm_platform_active_subscriptions", count, {
                'tier': tier, 'status': status
            })
    
    # User engagement tracking
    def track_user_session(self, user_type: str, session_duration: float):
        """Track user session"""
        duration_bucket = self._get_duration_bucket(session_duration)
        
        if PROMETHEUS_AVAILABLE:
            self.user_sessions.labels(
                user_type=user_type,
                session_duration_bucket=duration_bucket
            ).inc()
        else:
            self._update_custom_metric("llm_platform_user_sessions_total", 1, {
                'user_type': user_type,
                'session_duration_bucket': duration_bucket
            })
    
    def update_active_users(self, dau_count: int, mau_count: int):
        """Update daily and monthly active user counts"""
        if PROMETHEUS_AVAILABLE:
            self.daily_active_users.set(dau_count)
            self.monthly_active_users.set(mau_count)
        else:
            self._set_custom_metric("llm_platform_daily_active_users", dau_count)
            self._set_custom_metric("llm_platform_monthly_active_users", mau_count)
    
    # API usage tracking
    def track_api_call(self, endpoint: str, user_tier: str, model: str, 
                      success: bool, latency: float, tokens: int = 0):
        """Track API call with comprehensive metrics"""
        success_str = "true" if success else "false"
        
        if PROMETHEUS_AVAILABLE:
            self.api_calls_total.labels(
                endpoint=endpoint,
                user_tier=user_tier,
                model=model,
                success=success_str
            ).inc()
            
            self.api_latency.labels(endpoint=endpoint, model=model).observe(latency)
            
            if tokens > 0:
                self.tokens_processed.labels(
                    model=model,
                    operation_type="inference",
                    user_tier=user_tier
                ).inc(tokens)
        else:
            self._update_custom_metric("llm_platform_api_calls_total", 1, {
                'endpoint': endpoint, 'user_tier': user_tier, 
                'model': model, 'success': success_str
            })
    
    # Model performance tracking
    def track_model_inference(self, model_name: str, model_size: str, 
                            user_tier: str, inference_time: float):
        """Track model inference performance"""
        if PROMETHEUS_AVAILABLE:
            self.model_inference_time.labels(
                model_name=model_name,
                model_size=model_size,
                user_tier=user_tier
            ).observe(inference_time)
        else:
            self._update_custom_metric("llm_platform_model_inference_seconds", 
                                     inference_time, {
                'model_name': model_name,
                'model_size': model_size,
                'user_tier': user_tier
            })
    
    def update_model_accuracy(self, model_name: str, dataset: str, accuracy: float):
        """Update model accuracy score"""
        if PROMETHEUS_AVAILABLE:
            self.model_accuracy.labels(
                model_name=model_name,
                evaluation_dataset=dataset
            ).set(accuracy)
        else:
            self._set_custom_metric("llm_platform_model_accuracy_score", accuracy, {
                'model_name': model_name,
                'evaluation_dataset': dataset
            })
    
    # Cost tracking
    def track_compute_cost(self, amount: float, resource_type: str, 
                          provider: str, region: str):
        """Track compute costs"""
        if PROMETHEUS_AVAILABLE:
            self.compute_costs.labels(
                resource_type=resource_type,
                provider=provider,
                region=region
            ).inc(amount)
        else:
            self._update_custom_metric("llm_platform_compute_costs_total", amount, {
                'resource_type': resource_type,
                'provider': provider,
                'region': region
            })
    
    def update_cost_per_token(self, model: str, tier: str, cost: float):
        """Update cost per token metric"""
        if PROMETHEUS_AVAILABLE:
            self.cost_per_token.labels(model=model, tier=tier).set(cost)
        else:
            self._set_custom_metric("llm_platform_cost_per_token", cost, {
                'model': model, 'tier': tier
            })
    
    # User satisfaction tracking
    def track_user_rating(self, rating: int, feature: str, model: str):
        """Track user rating"""
        if PROMETHEUS_AVAILABLE:
            self.user_ratings.labels(
                rating=str(rating),
                feature=feature,
                model=model
            ).inc()
        else:
            self._update_custom_metric("llm_platform_user_ratings_total", 1, {
                'rating': str(rating),
                'feature': feature,
                'model': model
            })
    
    def track_support_ticket(self, category: str, priority: str, status: str):
        """Track support ticket creation"""
        if PROMETHEUS_AVAILABLE:
            self.support_tickets.labels(
                category=category,
                priority=priority,
                resolution_status=status
            ).inc()
        else:
            self._update_custom_metric("llm_platform_support_tickets_total", 1, {
                'category': category,
                'priority': priority,
                'resolution_status': status
            })
    
    # Feature usage tracking
    def track_feature_usage(self, feature_name: str, user_tier: str, success: bool):
        """Track feature usage"""
        success_str = "true" if success else "false"
        
        if PROMETHEUS_AVAILABLE:
            self.feature_usage.labels(
                feature_name=feature_name,
                user_tier=user_tier,
                success=success_str
            ).inc()
        else:
            self._update_custom_metric("llm_platform_feature_usage_total", 1, {
                'feature_name': feature_name,
                'user_tier': user_tier,
                'success': success_str
            })
    
    # Error tracking
    def track_business_error(self, error_type: str, severity: str, component: str):
        """Track business logic errors"""
        if PROMETHEUS_AVAILABLE:
            self.business_errors.labels(
                error_type=error_type,
                severity=severity,
                component=component
            ).inc()
        else:
            self._update_custom_metric("llm_platform_business_errors_total", 1, {
                'error_type': error_type,
                'severity': severity,
                'component': component
            })
    
    # Conversion tracking
    def track_trial_conversion(self, source: str, tier: str):
        """Track trial to paid conversion"""
        if PROMETHEUS_AVAILABLE:
            self.trial_conversions.labels(source=source, tier=tier).inc()
        else:
            self._update_custom_metric("llm_platform_trial_conversions_total", 1, {
                'source': source, 'tier': tier
            })
    
    def update_churn_rate(self, tier: str, time_period: str, rate: float):
        """Update churn rate percentage"""
        if PROMETHEUS_AVAILABLE:
            self.churn_rate.labels(tier=tier, time_period=time_period).set(rate)
        else:
            self._set_custom_metric("llm_platform_churn_rate", rate, {
                'tier': tier, 'time_period': time_period
            })
    
    # Helper methods
    def _get_duration_bucket(self, duration: float) -> str:
        """Categorize session duration into buckets"""
        if duration < 60:
            return "short"  # < 1 minute
        elif duration < 600:
            return "medium"  # 1-10 minutes
        elif duration < 3600:
            return "long"  # 10-60 minutes
        else:
            return "extended"  # > 1 hour
    
    def _update_custom_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """Update custom metric for non-Prometheus environments"""
        if name not in self.custom_metrics:
            return
        
        labels = labels or {}
        label_key = json.dumps(labels, sort_keys=True)
        
        if label_key not in self.custom_metrics[name]['values']:
            self.custom_metrics[name]['values'][label_key] = 0
        
        self.custom_metrics[name]['values'][label_key] += value
        self.custom_metrics[name]['last_updated'] = datetime.now()
    
    def _set_custom_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set custom metric value for non-Prometheus environments"""
        if name not in self.custom_metrics:
            return
        
        labels = labels or {}
        label_key = json.dumps(labels, sort_keys=True)
        
        self.custom_metrics[name]['values'][label_key] = value
        self.custom_metrics[name]['last_updated'] = datetime.now()
    
    def get_business_summary(self) -> Dict[str, Any]:
        """Get comprehensive business metrics summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'metrics_available': PROMETHEUS_AVAILABLE,
            'custom_metrics_count': len(self.custom_metrics)
        }
        
        if not PROMETHEUS_AVAILABLE:
            summary['custom_metrics'] = {}
            for name, metric in self.custom_metrics.items():
                summary['custom_metrics'][name] = {
                    'type': metric['type'],
                    'description': metric['description'],
                    'value_count': len(metric['values']),
                    'last_updated': metric['last_updated'].isoformat()
                }
        
        return summary

class MockMetric:
    """Mock metric for non-Prometheus environments"""
    
    def __init__(self, name: str, custom_metrics: Dict):
        self.name = name
        self.custom_metrics = custom_metrics
        self._labels = {}
    
    def labels(self, **kwargs):
        self._labels = kwargs
        return self
    
    def inc(self, amount: float = 1):
        # This would be handled by _update_custom_metric
        pass
    
    def set(self, value: float):
        # This would be handled by _set_custom_metric
        pass
    
    def observe(self, value: float):
        # This would be handled by _update_custom_metric
        pass

# Global business metrics instance
business_metrics = BusinessMetricsCollector()

# Convenience functions
def track_api_usage(endpoint: str, user_tier: str, model: str, success: bool, 
                   latency: float, tokens: int = 0):
    """Track API usage metrics"""
    business_metrics.track_api_call(endpoint, user_tier, model, success, latency, tokens)

def track_revenue(amount: float, tier: str, period: str):
    """Track revenue generation"""
    business_metrics.track_revenue(amount, tier, period)

def track_user_engagement(user_type: str, session_duration: float):
    """Track user engagement"""
    business_metrics.track_user_session(user_type, session_duration)

def get_business_metrics_summary():
    """Get business metrics summary"""
    return business_metrics.get_business_summary()