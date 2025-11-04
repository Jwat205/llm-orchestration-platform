# django-service/apps/analytics/dashboards.py
from django.db import models
from django.utils import timezone
from django.db.models import Avg, Count, Sum
from django.core.cache import cache
from datetime import datetime, timedelta
import json
from typing import Dict, List, Any

class AnalyticsDashboard:
    """Main dashboard controller - like the head chef monitoring all kitchen screens"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes - fresh data without overwhelming DB
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        cache_key = "real_time_metrics"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Get metrics from last 5 minutes
        five_min_ago = timezone.now() - timedelta(minutes=5)
        
        from ..usage.models import APIRequest  # Import here to avoid circular imports
        
        recent_requests = APIRequest.objects.filter(
            created_at__gte=five_min_ago
        )
        
        metrics = {
            'requests_per_second': recent_requests.count() / 300,  # 5 minutes = 300 seconds
            'avg_response_time': recent_requests.aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0,
            'error_rate': (
                recent_requests.filter(status_code__gte=400).count() / 
                max(recent_requests.count(), 1)
            ) * 100,
            'active_users': recent_requests.values('user').distinct().count(),
            'total_tokens': recent_requests.aggregate(
                total=Sum('tokens_used')
            )['total'] or 0
        }
        
        cache.set(cache_key, metrics, self.cache_timeout)
        return metrics
    
    def get_usage_analytics(self, days: int = 7) -> Dict[str, Any]:
        cache_key = f"usage_analytics_{days}d"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date = timezone.now() - timedelta(days=days)
        
        from ..usage.models import APIRequest
        
        requests = APIRequest.objects.filter(created_at__gte=start_date)
        
        # Daily breakdown - like daily sales reports
        daily_stats = []
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_requests = requests.filter(
                created_at__gte=day_start,
                created_at__lt=day_end
            )
            
            daily_stats.append({
                'date': day_start.date().isoformat(),
                'requests': day_requests.count(),
                'avg_response_time': day_requests.aggregate(
                    avg=Avg('response_time_ms')
                )['avg'] or 0,
                'unique_users': day_requests.values('user').distinct().count(),
                'total_tokens': day_requests.aggregate(
                    total=Sum('tokens_used')
                )['total'] or 0
            })
        
        # Model usage - like tracking which dishes are most popular
        model_stats = list(
            requests.values('model_name')
            .annotate(
                request_count=Count('id'),
                avg_response_time=Avg('response_time_ms'),
                total_tokens=Sum('tokens_used')
            )
            .order_by('-request_count')[:10]
        )
        
        analytics = {
            'daily_stats': daily_stats,
            'model_usage': model_stats,
            'total_requests': requests.count(),
            'avg_response_time': requests.aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
            'total_users': requests.values('user').distinct().count()
        }
        
        cache.set(cache_key, analytics, self.cache_timeout * 4)  # Cache longer for historical data
        return analytics
    
    def get_performance_monitoring(self) -> Dict[str, Any]:
        cache_key = "performance_monitoring"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        ##from  import APIRequest, CacheHit
        from django.db import connection
        
        # Last hour performance
        hour_ago = timezone.now() - timedelta(hours=1)
        
        recent_requests = APIRequest.objects.filter(created_at__gte=hour_ago)
        
        # Response time distribution - like tracking cooking times
        response_time_buckets = {
            'under_50ms': recent_requests.filter(response_time_ms__lt=50).count(),
            'under_100ms': recent_requests.filter(response_time_ms__lt=100).count(),
            'under_200ms': recent_requests.filter(response_time_ms__lt=200).count(),
            'over_200ms': recent_requests.filter(response_time_ms__gte=200).count()
        }
        
        # Cache performance - like tracking prep vs cook-to-order ratio
        try:
            cache_hits = CacheHit.objects.filter(created_at__gte=hour_ago)
            total_requests = recent_requests.count()
            cache_hit_rate = (cache_hits.filter(hit=True).count() / max(total_requests, 1)) * 100
        except:
            cache_hit_rate = 0
        
        # Database performance - like tracking ingredient prep time
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as slow_queries 
                FROM django_admin_log 
                WHERE action_time >= %s
            """, [hour_ago])
            slow_queries = cursor.fetchone()[0]
        
        performance = {
            'response_time_buckets': response_time_buckets,
            'cache_hit_rate': cache_hit_rate,
            'slow_queries': slow_queries,
            'avg_db_query_time': self._get_avg_db_query_time(),
            'memory_usage': self._get_memory_usage(),
            'cpu_usage': self._get_cpu_usage()
        }
        
        cache.set(cache_key, performance, 60)  # 1 minute cache for performance data
        return performance
    
    def get_cost_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Cost analysis - like calculating food costs vs revenue
        
        This helps optimize your infrastructure costs while maintaining performance
        """
        cache_key = f"cost_analysis_{days}d"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date = timezone.now() - timedelta(days=days)
        
        from ..usage.models import APIRequest
        from ..billing.models import Usage
        
        requests = APIRequest.objects.filter(created_at__gte=start_date)
        
        # Calculate costs per model (like different ingredient costs)
        model_costs = {}
        for model in requests.values_list('model_name', flat=True).distinct():
            model_requests = requests.filter(model_name=model)
            total_tokens = model_requests.aggregate(total=Sum('tokens_used'))['total'] or 0
            
            # Estimated costs (you'd replace with actual cost calculations)
            cost_per_token = self._get_model_cost_per_token(model)
            model_costs[model] = {
                'requests': model_requests.count(),
                'tokens': total_tokens,
                'estimated_cost': total_tokens * cost_per_token,
                'avg_tokens_per_request': total_tokens / max(model_requests.count(), 1)
            }
        
        # Infrastructure costs (like rent, utilities, staff)
        infrastructure_costs = {
            'compute': self._estimate_compute_costs(days),
            'storage': self._estimate_storage_costs(days),
            'bandwidth': self._estimate_bandwidth_costs(days)
        }
        
        cost_analysis = {
            'model_costs': model_costs,
            'infrastructure_costs': infrastructure_costs,
            'total_requests': requests.count(),
            'cost_per_request': self._calculate_cost_per_request(model_costs, infrastructure_costs, requests.count()),
            'optimization_suggestions': self._get_cost_optimizations()
        }
        
        cache.set(cache_key, cost_analysis, self.cache_timeout * 12)  # Cache for 1 hour
        return cost_analysis
    
    def _get_avg_db_query_time(self) -> float:
        """Get average database query time - like timing ingredient prep"""
        # This would integrate with your database monitoring
        return 5.2  # Placeholder - integrate with actual DB monitoring
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage percentage"""
        import psutil
        return psutil.virtual_memory().percent
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        import psutil
        return psutil.cpu_percent(interval=1)
    
    def _get_model_cost_per_token(self, model_name: str) -> float:
        """Get cost per token for specific model - like ingredient costs"""
        cost_mapping = {
            'llama-2-7b': 0.0001,
            'llama-2-13b': 0.0002,
            'mistral-7b': 0.00015,
            'codellama': 0.00018
        }
        return cost_mapping.get(model_name, 0.0001)
    
    def _estimate_compute_costs(self, days: int) -> float:
        """Estimate compute costs based on usage"""
        # This would integrate with your cloud provider's billing API
        return days * 50.0  # Placeholder
    
    def _estimate_storage_costs(self, days: int) -> float:
        """Estimate storage costs"""
        return days * 10.0  # Placeholder
    
    def _estimate_bandwidth_costs(self, days: int) -> float:
        """Estimate bandwidth costs"""
        return days * 25.0  # Placeholder
    
    def _calculate_cost_per_request(self, model_costs: Dict, infrastructure_costs: Dict, total_requests: int) -> float:
        """Calculate average cost per request"""
        total_model_cost = sum(cost['estimated_cost'] for cost in model_costs.values())
        total_infrastructure_cost = sum(infrastructure_costs.values())
        total_cost = total_model_cost + total_infrastructure_cost
        
        return total_cost / max(total_requests, 1)
    
    def _get_cost_optimizations(self) -> List[str]:
        """Suggest cost optimizations - like menu engineering"""
        return [
            "Consider using smaller models for simple tasks",
            "Implement request batching for better GPU utilization",
            "Increase cache hit rate to reduce model inference calls",
            "Use spot instances for non-critical workloads"
        ]


class CustomDashboardWidget:
    """
    Custom dashboard widgets - like specialized kitchen displays
    
    This allows creating custom charts and metrics displays
    for specific business needs
    """
    
    def __init__(self, widget_type: str, config: Dict[str, Any]):
        self.widget_type = widget_type
        self.config = config
    
    def render_chart_data(self) -> Dict[str, Any]:
        """Render data for charts - like formatting data for display screens"""
        
        if self.widget_type == "line_chart":
            return self._render_line_chart()
        elif self.widget_type == "bar_chart":
            return self._render_bar_chart()
        elif self.widget_type == "pie_chart":
            return self._render_pie_chart()
        elif self.widget_type == "gauge":
            return self._render_gauge()
        else:
            return {"error": "Unknown widget type"}
    
    def _render_line_chart(self) -> Dict[str, Any]:
        """Render time-series data - like tracking orders over time"""
        from ..usage.models import APIRequest
        
        days = self.config.get('days', 7)
        metric = self.config.get('metric', 'requests')
        
        start_date = timezone.now() - timedelta(days=days)
        requests = APIRequest.objects.filter(created_at__gte=start_date)
        
        # Group by hour for detailed view
        data_points = []
        for i in range(days * 24):  # Hourly data points
            hour_start = start_date + timedelta(hours=i)
            hour_end = hour_start + timedelta(hours=1)
            
            hour_requests = requests.filter(
                created_at__gte=hour_start,
                created_at__lt=hour_end
            )
            
            if metric == 'requests':
                value = hour_requests.count()
            elif metric == 'response_time':
                value = hour_requests.aggregate(avg=Avg('response_time_ms'))['avg'] or 0
            elif metric == 'tokens':
                value = hour_requests.aggregate(total=Sum('tokens_used'))['total'] or 0
            else:
                value = 0
            
            data_points.append({
                'timestamp': hour_start.isoformat(),
                'value': value
            })
        
        return {
            'type': 'line',
            'data': data_points,
            'labels': {
                'x': 'Time',
                'y': metric.replace('_', ' ').title()
            }
        }
    
    def _render_bar_chart(self) -> Dict[str, Any]:
        """Render categorical data - like comparing model usage"""
        from ..usage.models import APIRequest
        
        days = self.config.get('days', 7)
        start_date = timezone.now() - timedelta(days=days)
        
        model_usage = APIRequest.objects.filter(
            created_at__gte=start_date
        ).values('model_name').annotate(
            count=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            total_tokens=Sum('tokens_used')
        ).order_by('-count')[:10]
        
        return {
            'type': 'bar',
            'data': list(model_usage),
            'labels': {
                'x': 'Model',
                'y': 'Usage Count'
            }
        }
    
    def _render_pie_chart(self) -> Dict[str, Any]:
        """Render distribution data - like error type breakdown"""
        from ..usage.models import APIRequest
        
        days = self.config.get('days', 7)
        start_date = timezone.now() - timedelta(days=days)
        
        status_distribution = APIRequest.objects.filter(
            created_at__gte=start_date
        ).extra(
            select={
                'status_category': """
                    CASE 
                        WHEN status_code < 300 THEN 'Success'
                        WHEN status_code < 400 THEN 'Redirect'
                        WHEN status_code < 500 THEN 'Client Error'
                        ELSE 'Server Error'
                    END
                """
            }
        ).values('status_category').annotate(
            count=Count('id')
        )
        
        return {
            'type': 'pie',
            'data': list(status_distribution),
            'labels': {
                'title': 'Response Status Distribution'
            }
        }
    
    def _render_gauge(self) -> Dict[str, Any]:
        """Render gauge metrics - like speedometer for performance"""
        dashboard = AnalyticsDashboard()
        metrics = dashboard.get_real_time_metrics()
        
        metric_name = self.config.get('metric', 'response_time')
        current_value = metrics.get(metric_name, 0)
        
        # Define thresholds based on your performance targets
        thresholds = {
            'response_time': {'good': 50, 'warning': 100, 'critical': 200},
            'error_rate': {'good': 1, 'warning': 5, 'critical': 10},
            'requests_per_second': {'good': 100, 'warning': 50, 'critical': 10}
        }
        
        threshold = thresholds.get(metric_name, {'good': 80, 'warning': 60, 'critical': 40})
        
        if current_value <= threshold['good']:
            status = 'good'
        elif current_value <= threshold['warning']:
            status = 'warning'
        else:
            status = 'critical'
        
        return {
            'type': 'gauge',
            'value': current_value,
            'status': status,
            'thresholds': threshold,
            'label': metric_name.replace('_', ' ').title()
        }

