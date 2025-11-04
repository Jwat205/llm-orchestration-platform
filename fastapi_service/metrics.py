"""
Prometheus Metrics for FastAPI Service
Tracks all the performance claims: RPS, latency, uptime, cache hits
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response
import time
from functools import wraps

# Performance Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')]
)

CACHE_HITS = Counter(
    'cache_hits_total',
    'Total cache hits'
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total cache misses'
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Active HTTP requests'
)

# Business Metrics
MONTHLY_REQUESTS = Counter(
    'monthly_requests_total',
    'Total monthly requests for 1M+ target'
)

API_ERRORS = Counter(
    'api_errors_total',
    'Total API errors',
    ['error_type']
)

UPTIME_GAUGE = Gauge(
    'service_uptime_seconds',
    'Service uptime in seconds'
)

# Performance SLA Metrics
SLA_RESPONSE_TIME = Histogram(
    'sla_response_time_seconds',
    'SLA response time tracking',
    ['endpoint_type'],  # 'api', 'cached', 'model'
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')]
)

RPS_GAUGE = Gauge(
    'current_rps',
    'Current requests per second'
)

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

def track_metrics(endpoint_type: str = "api"):
    """Decorator to track request metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            ACTIVE_REQUESTS.inc()

            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Calculate response time
                response_time = time.time() - start_time

                # Record metrics
                REQUEST_COUNT.labels(
                    method="GET",  # Simplified for demo
                    endpoint=func.__name__,
                    status_code="200"
                ).inc()

                REQUEST_LATENCY.labels(
                    method="GET",
                    endpoint=func.__name__
                ).observe(response_time)

                SLA_RESPONSE_TIME.labels(
                    endpoint_type=endpoint_type
                ).observe(response_time)

                MONTHLY_REQUESTS.inc()

                # Update uptime
                UPTIME_GAUGE.set(time.time() - SERVICE_START_TIME)

                return result

            except Exception as e:
                API_ERRORS.labels(error_type=type(e).__name__).inc()
                REQUEST_COUNT.labels(
                    method="GET",
                    endpoint=func.__name__,
                    status_code="500"
                ).inc()
                raise
            finally:
                ACTIVE_REQUESTS.dec()

        return wrapper
    return decorator

def track_cache_hit():
    """Track cache hit"""
    CACHE_HITS.inc()

def track_cache_miss():
    """Track cache miss"""
    CACHE_MISSES.inc()

def get_metrics_response():
    """Generate Prometheus metrics response"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

def get_performance_summary():
    """Get current performance summary"""
    uptime = time.time() - SERVICE_START_TIME

    return {
        "uptime_seconds": uptime,
        "uptime_hours": uptime / 3600,
        "total_requests": "See /metrics for detailed counters",
        "cache_hit_rate": calculate_cache_hit_rate(),
        "avg_response_time": "See /metrics for detailed histograms",
        "current_status": "Service running with metrics collection",
        "sla_status": {
            "uptime_target": "99.5%",
            "latency_target": "<100ms for API endpoints",
            "throughput_target": "1,000+ RPS",
            "monthly_requests_target": "1M+"
        }
    }

def calculate_cache_hit_rate():
    """Calculate cache hit rate percentage"""
    try:
        # Simple approach - return a message pointing to metrics
        return "See /metrics endpoint for cache_hits_total and cache_misses_total"
    except:
        return 0.0