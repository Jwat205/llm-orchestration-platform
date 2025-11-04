# monitoring-service/app/main.py
"""
Dedicated Monitoring Service - The Restaurant's Security & Health Inspector

This is like having a dedicated team that:
- Continuously checks food quality (API health)
- Monitors kitchen temperature (system performance) 
- Tracks customer satisfaction (user experience)
- Alerts management to any issues (automated alerting)

Why separate service: Your resume shows 99.9% uptime target. 
This requires dedicated monitoring that runs independently of your main services.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
import logging
import time
from datetime import datetime, timedelta
import json
import psutil
import redis
from prometheus_client import Counter, Histogram, Gauge, generate_latest

app = FastAPI(title="LLM API Monitoring Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics - like having digital scoreboards
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')
RESPONSE_TIME = Histogram('response_time_milliseconds', 'Response time in milliseconds', ['endpoint', 'model'])
CACHE_HIT_RATE = Gauge('cache_hit_rate', 'Cache hit rate percentage')
ERROR_RATE = Gauge('error_rate', 'Error rate percentage')

# Redis for storing metrics (like a scoreboard that persists)
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class MetricsCollector:
    """
    Metrics collection engine - like a data logger recording everything
    
    This continuously collects performance data from all your services
    to ensure you maintain your performance targets from your resume
    """
    
    def __init__(self):
        self.services = {
            'django': 'http://django-service:8000',
            'fastapi': 'http://fastapi-service:8001',
            'redis': 'redis://redis:6379',
            'postgres': 'postgresql://postgres:5432/llm_db'
        }
        self.collection_interval = 30  # seconds
        self.is_running = False
    
    async def start_collection(self):
        """Start continuous metrics collection - like starting the monitoring shift"""
        self.is_running = True
        while self.is_running:
            try:
                await self.collect_all_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logging.error(f"Metrics collection error: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    async def collect_all_metrics(self):
        """Collect metrics from all services - like doing a full kitchen inspection"""
        
        # Collect API performance metrics
        api_metrics = await self.collect_api_metrics()
        
        # Collect system resource metrics
        system_metrics = self.collect_system_metrics()
        
        # Collect database metrics
        db_metrics = await self.collect_database_metrics()
        
        # Collect cache metrics
        cache_metrics = await self.collect_cache_metrics()
        
        # Store all metrics
        timestamp = datetime.now().isoformat()
        all_metrics = {
            'timestamp': timestamp,
            'api': api_metrics,
            'system': system_metrics,
            'database': db_metrics,
            'cache': cache_metrics
        }
        
        # Store in Redis with TTL (like keeping recent records accessible)
        redis_client.setex(
            f"metrics:{timestamp}", 
            3600,  # 1 hour TTL
            json.dumps(all_metrics)
        )
        
        # Update Prometheus metrics
        self.update_prometheus_metrics(all_metrics)
        
        return all_metrics
    
    async def collect_api_metrics(self) -> Dict[str, Any]:
        """
        Collect API performance metrics - like timing each order
        
        This ensures you maintain your <100ms response time target
        """
        metrics = {}
        
        async with aiohttp.ClientSession() as session:
            for service_name, base_url in self.services.items():
                if service_name in ['redis', 'postgres']:
                    continue
                
                try:
                    # Health check endpoint
                    start_time = time.time()
                    async with session.get(f"{base_url}/health", timeout=5) as response:
                        response_time = (time.time() - start_time) * 1000  # Convert to ms
                        
                        metrics[service_name] = {
                            'status': 'healthy' if response.status == 200 else 'unhealthy',
                            'response_time_ms': response_time,
                            'status_code': response.status,
                            'last_check': datetime.now().isoformat()
                        }
                        
                        # Update Prometheus metrics
                        REQUEST_COUNT.labels(
                            method='GET', 
                            endpoint='/health', 
                            status=response.status
                        ).inc()
                        
                        REQUEST_DURATION.observe(response_time / 1000)
                        RESPONSE_TIME.labels(endpoint='/health', model='none').observe(response_time)
                
                except asyncio.TimeoutError:
                    metrics[service_name] = {
                        'status': 'timeout',
                        'response_time_ms': 5000,  # Timeout threshold
                        'status_code': 408,
                        'last_check': datetime.now().isoformat()
                    }
                except Exception as e:
                    metrics[service_name] = {
                        'status': 'error',
                        'error': str(e),
                        'last_check': datetime.now().isoformat()
                    }
        
        return metrics
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system resource metrics - like monitoring kitchen equipment
        
        This ensures your infrastructure can handle 1000+ concurrent requests
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            metrics = {
                'cpu': {
                    'usage_percent': cpu_percent,
                    'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
                },
                'memory': {
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'usage_percent': memory.percent,
                    'available_gb': memory.available / (1024**3)
                },
                'disk': {
                    'total_gb': disk.total / (1024**3),
                    'used_gb': disk.used / (1024**3),
                    'usage_percent': (disk.used / disk.total) * 100,
                    'free_gb': disk.free / (1024**3)
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_received': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_received': network.packets_recv
                }
            }
            
            return metrics
            
        except Exception as e:
            logging.error(f"System metrics collection error: {e}")
            return {}
    
    async def collect_database_metrics(self) -> Dict[str, Any]:
        """
        Collect database performance metrics - like monitoring ingredient storage
        
        This ensures your database queries stay optimized (contributing to <50ms cached response times)
        """
        try:
            # This would connect to your actual database
            # For now, we'll simulate the key metrics you need to track
            
            metrics = {
                'connections': {
                    'active': 15,  # Would get from actual DB
                    'idle': 5,
                    'max_connections': 100
                },
                'performance': {
                    'avg_query_time_ms': 12.5,  # Your target: fast queries
                    'slow_queries_count': 2,
                    'queries_per_second': 150
                },
                'storage': {
                    'database_size_gb': 2.1,
                    'index_size_gb': 0.3,
                    'free_space_gb': 47.6
                },
                'cache': {
                    'buffer_cache_hit_ratio': 99.2,  # PostgreSQL buffer cache
                    'index_cache_hit_ratio': 98.7
                }
            }
            
            return metrics
            
        except Exception as e:
            logging.error(f"Database metrics collection error: {e}")
            return {}
    
    async def collect_cache_metrics(self) -> Dict[str, Any]:
        """
        Collect Redis cache metrics - like monitoring prep station efficiency
        
        This tracks your cache hit rate (target: 70%+ from your resume)
        """
        try:
            info = redis_client.info()
            
            # Calculate cache hit rate from Redis stats
            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            total_commands = keyspace_hits + keyspace_misses
            hit_rate = (keyspace_hits / max(total_commands, 1)) * 100
            
            metrics = {
                'performance': {
                    'hit_rate_percent': hit_rate,
                    'commands_processed': info.get('total_commands_processed', 0),
                    'keyspace_hits': keyspace_hits,
                    'keyspace_misses': keyspace_misses
                },
                'memory': {
                    'used_memory_mb': info.get('used_memory', 0) / (1024*1024),
                    'max_memory_mb': info.get('maxmemory', 0) / (1024*1024),
                    'memory_usage_percent': (info.get('used_memory', 0) / max(info.get('maxmemory', 1), 1)) * 100
                },
                'connections': {
                    'connected_clients': info.get('connected_clients', 0),
                    'blocked_clients': info.get('blocked_clients', 0),
                    'max_clients': info.get('maxclients', 10000)
                },
                'keys': {
                    'total_keys': sum([info.get(f'db{i}', {}).get('keys', 0) for i in range(16)]),
                    'expired_keys': info.get('expired_keys', 0),
                    'evicted_keys': info.get('evicted_keys', 0)
                }
            }
            
            # Update Prometheus cache hit rate
            CACHE_HIT_RATE.set(hit_rate)
            
            return metrics
            
        except Exception as e:
            logging.error(f"Cache metrics collection error: {e}")
            return {}
    
    def update_prometheus_metrics(self, metrics: Dict[str, Any]):
        """Update Prometheus metrics - like updating the main scoreboard"""
        try:
            # Update system metrics
            if 'system' in metrics:
                system = metrics['system']
                if 'cpu' in system:
                    # Note: You'd create these gauges at module level
                    pass
            
            # Calculate overall error rate
            api_metrics = metrics.get('api', {})
            total_services = len(api_metrics)
            unhealthy_services = sum(1 for service in api_metrics.values() 
                                   if service.get('status') != 'healthy')
            
            if total_services > 0:
                error_rate = (unhealthy_services / total_services) * 100
                ERROR_RATE.set(error_rate)
        
        except Exception as e:
            logging.error(f"Prometheus metrics update error: {e}")

    def stop_collection(self):
        """Stop metrics collection"""
        self.is_running = False


class PerformanceAnalyzer:
    """
    Performance analysis engine - like a kitchen consultant analyzing efficiency
    
    This analyzes collected metrics to identify performance bottlenecks
    and optimization opportunities
    """
    
    def __init__(self):
        self.analysis_window = 3600  # 1 hour
    
    async def analyze_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze performance trends - like reviewing daily kitchen performance
        
        This helps you maintain your performance targets consistently
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Get metrics from Redis
        metrics_keys = redis_client.keys(f"metrics:*")
        
        # Filter keys within time range and sort
        relevant_metrics = []
        for key in metrics_keys:
            timestamp_str = key.split(":")[1]
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if start_time <= timestamp <= end_time:
                    metrics_data = json.loads(redis_client.get(key))
                    relevant_metrics.append(metrics_data)
            except:
                continue
        
        # Sort by timestamp
        relevant_metrics.sort(key=lambda x: x['timestamp'])
        
        if not relevant_metrics:
            return {"error": "No metrics data available"}
        
        # Analyze trends
        analysis = {
            'response_time_trend': self._analyze_response_time_trend(relevant_metrics),
            'error_rate_trend': self._analyze_error_rate_trend(relevant_metrics),
            'cache_performance_trend': self._analyze_cache_trend(relevant_metrics),
            'resource_utilization_trend': self._analyze_resource_trend(relevant_metrics),
            'recommendations': self._generate_recommendations(relevant_metrics)
        }
        
        return analysis
    
    def _analyze_response_time_trend(self, metrics_data: List[Dict]) -> Dict[str, Any]:
        """Analyze response time trends - like tracking order fulfillment speed"""
        response_times = []
        
        for metric in metrics_data:
            api_metrics = metric.get('api', {})
            for service, data in api_metrics.items():
                if 'response_time_ms' in data:
                    response_times.append({
                        'timestamp': metric['timestamp'],
                        'service': service,
                        'response_time': data['response_time_ms']
                    })
        
        if not response_times:
            return {"error": "No response time data"}
        
        # Calculate statistics
        times = [rt['response_time'] for rt in response_times]
        avg_response_time = sum(times) / len(times)
        max_response_time = max(times)
        min_response_time = min(times)
        
        # Check against your performance targets
        target_response_time = 100  # ms, from your resume
        performance_score = "excellent" if avg_response_time < 50 else \
                           "good" if avg_response_time < target_response_time else \
                           "needs_improvement"
        
        return {
            'average_ms': round(avg_response_time, 2),
            'max_ms': max_response_time,
            'min_ms': min_response_time,
            'target_ms': target_response_time,
            'performance_score': performance_score,
            'trend_data': response_times[-50:]  # Last 50 data points for trending
        }
    
    def _analyze_error_rate_trend(self, metrics_data: List[Dict]) -> Dict[str, Any]:
        """Analyze error rate trends - like tracking order mistakes"""
        healthy_count = 0
        total_checks = 0
        
        for metric in metrics_data:
            api_metrics = metric.get('api', {})
            for service, data in api_metrics.items():
                total_checks += 1
                if data.get('status') == 'healthy':
                    healthy_count += 1
        
        if total_checks == 0:
            return {"error": "No health check data"}
        
        success_rate = (healthy_count / total_checks) * 100
        error_rate = 100 - success_rate
        
        # Your target: 99.9% uptime = 0.1% error rate
        target_error_rate = 0.1
        performance_score = "excellent" if error_rate <= target_error_rate else \
                           "good" if error_rate <= 1.0 else \
                           "needs_improvement"
        
        return {
            'error_rate_percent': round(error_rate, 3),
            'success_rate_percent': round(success_rate, 3),
            'target_error_rate_percent': target_error_rate,
            'performance_score': performance_score,
            'total_checks': total_checks
        }
    
    def _analyze_cache_trend(self, metrics_data: List[Dict]) -> Dict[str, Any]:
        """Analyze cache performance trends - like tracking prep efficiency"""
        cache_hit_rates = []
        
        for metric in metrics_data:
            cache_metrics = metric.get('cache', {})
            performance = cache_metrics.get('performance', {})
            if 'hit_rate_percent' in performance:
                cache_hit_rates.append({
                    'timestamp': metric['timestamp'],
                    'hit_rate': performance['hit_rate_percent']
                })
        
        if not cache_hit_rates:
            return {"error": "No cache performance data"}
        
        rates = [chr['hit_rate'] for chr in cache_hit_rates]
        avg_hit_rate = sum(rates) / len(rates)
        
        # Your target: 70%+ cache hit rate
        target_hit_rate = 70
        performance_score = "excellent" if avg_hit_rate >= 85 else \
                           "good" if avg_hit_rate >= target_hit_rate else \
                           "needs_improvement"
        
        return {
            'average_hit_rate_percent': round(avg_hit_rate, 2),
            'target_hit_rate_percent': target_hit_rate,
            'performance_score': performance_score,
            'trend_data': cache_hit_rates[-50:]
        }
    
    def _analyze_resource_trend(self, metrics_data: List[Dict]) -> Dict[str, Any]:
        """Analyze resource utilization trends - like monitoring kitchen capacity"""
        cpu_usage = []
        memory_usage = []
        
        for metric in metrics_data:
            system_metrics = metric.get('system', {})
            
            if 'cpu' in system_metrics:
                cpu_usage.append({
                    'timestamp': metric['timestamp'],
                    'usage': system_metrics['cpu'].get('usage_percent', 0)
                })
            
            if 'memory' in system_metrics:
                memory_usage.append({
                    'timestamp': metric['timestamp'],
                    'usage': system_metrics['memory'].get('usage_percent', 0)
                })
        
        analysis = {}
        
        if cpu_usage:
            cpu_values = [cpu['usage'] for cpu in cpu_usage]
            avg_cpu = sum(cpu_values) / len(cpu_values)
            analysis['cpu'] = {
                'average_percent': round(avg_cpu, 2),
                'max_percent': max(cpu_values),
                'trend_data': cpu_usage[-50:]
            }
        
        if memory_usage:
            mem_values = [mem['usage'] for mem in memory_usage]
            avg_memory = sum(mem_values) / len(mem_values)
            analysis['memory'] = {
                'average_percent': round(avg_memory, 2),
                'max_percent': max(mem_values),
                'trend_data': memory_usage[-50:]
            }
        
        return analysis
    
    def _generate_recommendations(self, metrics_data: List[Dict]) -> List[str]:
        """Generate optimization recommendations - like kitchen efficiency tips"""
        recommendations = []
        
        if not metrics_data:
            return recommendations
        
        latest_metrics = metrics_data[-1]
        
        # Response time recommendations
        api_metrics = latest_metrics.get('api', {})
        avg_response_times = []
        for service, data in api_metrics.items():
            if 'response_time_ms' in data:
                avg_response_times.append(data['response_time_ms'])
        
        if avg_response_times:
            avg_rt = sum(avg_response_times) / len(avg_response_times)
            if avg_rt > 100:
                recommendations.append("Response times are above target (100ms). Consider implementing response caching or optimizing model inference.")
            if avg_rt > 200:
                recommendations.append("Critical: Response times are significantly high. Investigate database queries and model loading times.")
        
        # Cache recommendations
        cache_metrics = latest_metrics.get('cache', {})
        cache_performance = cache_metrics.get('performance', {})
        hit_rate = cache_performance.get('hit_rate_percent', 0)
        
        if hit_rate < 70:
            recommendations.append(f"Cache hit rate ({hit_rate:.1f}%) is below target (70%). Review caching strategy and cache key patterns.")
        if hit_rate < 50:
            recommendations.append("Critical: Very low cache hit rate. Consider increasing cache TTL or improving cache key design.")
        
        # Resource recommendations
        system_metrics = latest_metrics.get('system', {})
        cpu_usage = system_metrics.get('cpu', {}).get('usage_percent', 0)
        memory_usage = system_metrics.get('memory', {}).get('usage_percent', 0)
        
        if cpu_usage > 80:
            recommendations.append(f"High CPU usage ({cpu_usage:.1f}%). Consider horizontal scaling or optimizing compute-intensive operations.")
        if memory_usage > 85:
            recommendations.append(f"High memory usage ({memory_usage:.1f}%). Monitor for memory leaks and consider increasing available memory.")
        
        # Database recommendations
        db_metrics = latest_metrics.get('database', {})
        performance = db_metrics.get('performance', {})
        slow_queries = performance.get('slow_queries_count', 0)
        
        if slow_queries > 5:
            recommendations.append(f"Found {slow_queries} slow queries. Review and optimize database indexes and query patterns.")
        
        return recommendations


class AlertManager:
    """
    Alert management system - like having emergency protocols
    
    This ensures you get notified immediately when performance
    drops below your targets (99.9% uptime, <100ms response time)
    """
    
    def __init__(self):
        self.alert_rules = {
            'response_time_critical': {
                'metric': 'response_time_ms',
                'threshold': 200,
                'comparison': 'greater',
                'severity': 'critical',
                'message': 'Response time exceeded 200ms'
            },
            'response_time_warning': {
                'metric': 'response_time_ms',
                'threshold': 100,
                'comparison': 'greater',
                'severity': 'warning',
                'message': 'Response time exceeded target (100ms)'
            },
            'cache_hit_rate_low': {
                'metric': 'cache_hit_rate_percent',
                'threshold': 70,
                'comparison': 'less',
                'severity': 'warning',
                'message': 'Cache hit rate below target (70%)'
            },
            'error_rate_high': {
                'metric': 'error_rate_percent',
                'threshold': 1.0,
                'comparison': 'greater',
                'severity': 'critical',
                'message': 'Error rate exceeded 1%'
            },
            'cpu_usage_high': {
                'metric': 'cpu_usage_percent',
                'threshold': 80,
                'comparison': 'greater',
                'severity': 'warning',
                'message': 'CPU usage exceeded 80%'
            },
            'memory_usage_high': {
                'metric': 'memory_usage_percent',
                'threshold': 85,
                'comparison': 'greater',
                'severity': 'critical',
                'message': 'Memory usage exceeded 85%'
            }
        }
        self.notification_channels = []
    
    async def check_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check all alert rules against current metrics"""
        triggered_alerts = []
        
        for rule_name, rule in self.alert_rules.items():
            alert = await self._evaluate_rule(rule_name, rule, metrics)
            if alert:
                triggered_alerts.append(alert)
        
        # Send notifications for triggered alerts
        for alert in triggered_alerts:
            await self._send_notification(alert)
        
        return triggered_alerts
    
    async def _evaluate_rule(self, rule_name: str, rule: Dict, metrics: Dict) -> Optional[Dict]:
        """Evaluate a single alert rule"""
        try:
            metric_value = self._extract_metric_value(rule['metric'], metrics)
            if metric_value is None:
                return None
            
            threshold = rule['threshold']
            comparison = rule['comparison']
            
            triggered = False
            if comparison == 'greater' and metric_value > threshold:
                triggered = True
            elif comparison == 'less' and metric_value < threshold:
                triggered = True
            elif comparison == 'equal' and metric_value == threshold:
                triggered = True
            
            if triggered:
                return {
                    'rule_name': rule_name,
                    'severity': rule['severity'],
                    'message': rule['message'],
                    'metric_value': metric_value,
                    'threshold': threshold,
                    'timestamp': datetime.now().isoformat()
                }
        
        except Exception as e:
            logging.error(f"Alert rule evaluation error for {rule_name}: {e}")
        
        return None
    
    def _extract_metric_value(self, metric_name: str, metrics: Dict) -> Optional[float]:
        """Extract metric value from nested metrics structure"""
        
        # Map metric names to their locations in the metrics structure
        metric_paths = {
            'response_time_ms': ['api', '*', 'response_time_ms'],
            'cache_hit_rate_percent': ['cache', 'performance', 'hit_rate_percent'],
            'error_rate_percent': None,  # Calculated separately
            'cpu_usage_percent': ['system', 'cpu', 'usage_percent'],
            'memory_usage_percent': ['system', 'memory', 'usage_percent']
        }
        
        if metric_name == 'error_rate_percent':
            # Calculate error rate from API metrics
            api_metrics = metrics.get('api', {})
            if not api_metrics:
                return None
            
            total_services = len(api_metrics)
            unhealthy_services = sum(1 for service in api_metrics.values() 
                                   if service.get('status') != 'healthy')
            
            return (unhealthy_services / max(total_services, 1)) * 100
        
        elif metric_name == 'response_time_ms':
            # Average response time across all services
            api_metrics = metrics.get('api', {})
            response_times = [
                service.get('response_time_ms', 0) 
                for service in api_metrics.values() 
                if 'response_time_ms' in service
            ]
            
            if response_times:
                return sum(response_times) / len(response_times)
            return None
        
        else:
            # Navigate nested structure
            path = metric_paths.get(metric_name)
            if not path:
                return None
            
            current = metrics
            for key in path:
                if key == '*':
                    # Handle wildcard - take first available
                    if isinstance(current, dict):
                        current = next(iter(current.values()), {})
                else:
                    current = current.get(key, {})
                
                if current is None:
                    return None
            
            return current if isinstance(current, (int, float)) else None
    
    async def _send_notification(self, alert: Dict[str, Any]):
        """Send alert notification - like calling the manager"""
        
        # Log the alert
        logging.warning(f"ALERT TRIGGERED: {alert}")
        
        # Store alert in Redis for dashboard
        alert_key = f"alert:{alert['timestamp']}:{alert['rule_name']}"
        redis_client.setex(alert_key, 86400, json.dumps(alert))  # 24 hour TTL
        
        # Here you would integrate with your notification systems:
        # - Slack webhook
        # - Email
        # - PagerDuty
        # - SMS
        
        # Example Slack notification (you'd implement this)
        # await self._send_slack_notification(alert)
    
    async def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts for dashboard display"""
        alert_keys = redis_client.keys("alert:*")
        
        recent_alerts = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for key in alert_keys:
            try:
                alert_data = json.loads(redis_client.get(key))
                alert_time = datetime.fromisoformat(alert_data['timestamp'])
                
                if alert_time >= cutoff_time:
                    recent_alerts.append(alert_data)
            except:
                continue
        
        # Sort by timestamp, newest first
        recent_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        return recent_alerts


# FastAPI endpoints
metrics_collector = MetricsCollector()
performance_analyzer = PerformanceAnalyzer()
alert_manager = AlertManager()

@app.on_event("startup")
async def startup_event():
    """Start background tasks when the service starts"""
    asyncio.create_task(metrics_collector.start_collection())

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    metrics_collector.stop_collection()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "monitoring", "timestamp": datetime.now().isoformat()}

@app.get("/metrics")
async def get_current_metrics():
    """Get current system metrics"""
    return await metrics_collector.collect_all_metrics()

@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

@app.get("/analysis/performance")
async def get_performance_analysis(hours: int = 24):
    """Get performance trend analysis"""
    return await performance_analyzer.analyze_performance_trends(hours)

@app.get("/alerts")
async def get_alerts(hours: int = 24):
    """Get recent alerts"""
    return await alert_manager.get_recent_alerts(hours)

@app.post("/alerts/check")
async def trigger_alert_check():
    """Manually trigger alert checking"""
    current_metrics = await metrics_collector.collect_all_metrics()
    alerts = await alert_manager.check_alerts(current_metrics)
    return {"triggered_alerts": alerts}

# Usage example in your main application:
"""
This monitoring service runs independently and provides:

1. Real-time metrics collection every 30 seconds
2. Performance trend analysis over time
3. Automated alerting when metrics exceed thresholds
4. Prometheus metrics for Grafana dashboards
5. REST API for dashboard integration

To integrate with your main services:
1. Deploy this as a separate Docker container
2. Configure your services to expose /health endpoints
3. Set up Prometheus to scrape /metrics/prometheus
4. Create Grafana dashboards using the metrics
5. Configure notification channels in AlertManager
"""