"""
Django Performance Profiler
Comprehensive profiling tools for Django service performance analysis.
"""

import cProfile
import pstats
import time
import functools
import logging
import threading
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
from collections import defaultdict, deque
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
import psutil
import tracemalloc

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Collect and store performance metrics"""

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.request_times = deque(maxlen=max_samples)
        self.db_query_times = deque(maxlen=max_samples)
        self.cache_stats = defaultdict(int)
        self.memory_usage = deque(maxlen=max_samples)
        self.error_counts = defaultdict(int)
        self.slow_queries = deque(maxlen=100)
        self._lock = threading.Lock()

    def add_request_time(self, duration: float, path: str, status_code: int):
        """Add request timing data"""
        with self._lock:
            self.request_times.append({
                'timestamp': datetime.now(),
                'duration': duration,
                'path': path,
                'status_code': status_code
            })

    def add_db_query(self, query: str, duration: float):
        """Add database query timing"""
        with self._lock:
            self.db_query_times.append({
                'timestamp': datetime.now(),
                'query': query[:200],  # Truncate for storage
                'duration': duration
            })

            # Track slow queries
            if duration > 0.1:  # 100ms threshold
                self.slow_queries.append({
                    'timestamp': datetime.now(),
                    'query': query,
                    'duration': duration
                })

    def update_cache_stats(self, operation: str, hit: bool = None):
        """Update cache operation statistics"""
        with self._lock:
            self.cache_stats[f'{operation}_total'] += 1
            if hit is not None:
                self.cache_stats[f'{operation}_{"hits" if hit else "misses"}'] += 1

    def add_memory_usage(self, usage_mb: float):
        """Add memory usage measurement"""
        with self._lock:
            self.memory_usage.append({
                'timestamp': datetime.now(),
                'usage_mb': usage_mb
            })

    def get_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary"""
        with self._lock:
            if not self.request_times:
                return {}

            request_durations = [r['duration'] for r in self.request_times]
            db_durations = [q['duration'] for q in self.db_query_times]

            return {
                'request_stats': {
                    'total_requests': len(self.request_times),
                    'avg_response_time': sum(request_durations) / len(request_durations),
                    'max_response_time': max(request_durations) if request_durations else 0,
                    'min_response_time': min(request_durations) if request_durations else 0,
                    'p95_response_time': self._percentile(request_durations, 95),
                    'p99_response_time': self._percentile(request_durations, 99),
                },
                'database_stats': {
                    'total_queries': len(self.db_query_times),
                    'avg_query_time': sum(db_durations) / len(db_durations) if db_durations else 0,
                    'slow_queries_count': len(self.slow_queries),
                    'queries_per_request': len(self.db_query_times) / len(self.request_times) if self.request_times else 0,
                },
                'cache_stats': dict(self.cache_stats),
                'memory_stats': {
                    'current_usage_mb': self.memory_usage[-1]['usage_mb'] if self.memory_usage else 0,
                    'avg_usage_mb': sum(m['usage_mb'] for m in self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
                },
                'last_updated': datetime.now().isoformat()
            }

    @staticmethod
    def _percentile(data: list, percentile: int) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = k - f
        if f == len(sorted_data) - 1:
            return sorted_data[f]
        return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c


# Global metrics collector
metrics = PerformanceMetrics()


class DjangoProfilerMiddleware(MiddlewareMixin):
    """Django middleware for performance profiling"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.profiling_enabled = getattr(settings, 'ENABLE_PROFILING', False)
        super().__init__(get_response)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self.profiling_enabled:
            return self.get_response(request)

        # Start profiling
        start_time = time.time()
        memory_before = self._get_memory_usage()
        queries_before = len(connection.queries)

        # Track memory allocations
        tracemalloc.start()

        try:
            response = self.get_response(request)
        finally:
            # Calculate metrics
            duration = time.time() - start_time
            memory_after = self._get_memory_usage()
            queries_after = len(connection.queries)

            # Stop memory tracking
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Record metrics
            metrics.add_request_time(duration, request.path, response.status_code)
            metrics.add_memory_usage(memory_after)

            # Record database queries
            new_queries = connection.queries[queries_before:]
            for query_data in new_queries:
                query_time = float(query_data['time'])
                metrics.add_db_query(query_data['sql'], query_time)

            # Add profiling headers (for development)
            if settings.DEBUG and hasattr(response, '__setitem__'):
                response['X-Response-Time'] = f"{duration:.3f}s"
                response['X-DB-Queries'] = str(queries_after - queries_before)
                response['X-Memory-Usage'] = f"{memory_after:.1f}MB"
                response['X-Memory-Peak'] = f"{peak / 1024 / 1024:.1f}MB"

        return response

    @staticmethod
    def _get_memory_usage() -> float:
        """Get current memory usage in MB"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024


@contextmanager
def profile_function(func_name: str):
    """Context manager for profiling individual functions"""
    start_time = time.time()
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        yield
    finally:
        profiler.disable()
        duration = time.time() - start_time

        # Log performance data
        logger.info(f"Function '{func_name}' took {duration:.3f}s")

        # Save detailed profile if duration is significant
        if duration > 0.1:  # 100ms threshold
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')

            # Save to file for later analysis
            profile_filename = f"/tmp/profile_{func_name}_{int(time.time())}.prof"
            stats.dump_stats(profile_filename)
            logger.info(f"Detailed profile saved to {profile_filename}")


def profile_method(threshold: float = 0.01):
    """Decorator for profiling methods automatically"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            if duration > threshold:
                logger.info(f"Method {func.__name__} took {duration:.3f}s")

                # Log slow method details
                if duration > 1.0:  # 1 second threshold
                    logger.warning(f"SLOW METHOD: {func.__name__} took {duration:.3f}s")

            return result
        return wrapper
    return decorator


# Export key functions and classes
__all__ = [
    'DjangoProfilerMiddleware',
    'profile_function',
    'profile_method',
    'metrics'
]
import io
import pstats
import time
import functools
from typing import Dict, Any, Optional, Callable
from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class DjangoProfiler:
    """Django application profiler"""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.profile_data = {}
    
    def profile_view(self, view_func: Callable) -> Callable:
        """Decorator to profile Django views"""
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not self.enabled:
                return view_func(request, *args, **kwargs)
            
            profiler = cProfile.Profile()
            profiler.enable()
            
            start_time = time.time()
            try:
                response = view_func(request, *args, **kwargs)
            finally:
                end_time = time.time()
                profiler.disable()
            
            # Store profile data
            view_name = f"{view_func.__module__}.{view_func.__name__}"
            execution_time = end_time - start_time
            
            # Convert profile to string
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s)
            ps.sort_stats('cumulative')
            ps.print_stats(20)  # Top 20 functions
            profile_output = s.getvalue()
            
            # Store profile information
            self.profile_data[view_name] = {
                'execution_time': execution_time,
                'timestamp': time.time(),
                'profile_output': profile_output,
                'request_method': request.method,
                'request_path': request.path
            }
            
            # Add timing header to response
            if hasattr(response, '__setitem__'):
                response['X-Execution-Time'] = f"{execution_time:.4f}s"
            
            return response
        
        return wrapper
    
    def get_profile_data(self, view_name: Optional[str] = None) -> Dict[str, Any]:
        """Get profile data for a specific view or all views"""
        if view_name:
            return self.profile_data.get(view_name, {})
        return self.profile_data
    
    def clear_profile_data(self) -> None:
        """Clear all profile data"""
        self.profile_data.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get profiling summary"""
        if not self.profile_data:
            return {"message": "No profile data available"}
        
        total_views = len(self.profile_data)
        total_execution_time = sum(data['execution_time'] for data in self.profile_data.values())
        avg_execution_time = total_execution_time / total_views if total_views > 0 else 0
        
        # Find slowest view
        slowest_view = max(self.profile_data.items(), 
                          key=lambda x: x[1]['execution_time'])
        
        return {
            'total_views_profiled': total_views,
            'total_execution_time': total_execution_time,
            'average_execution_time': avg_execution_time,
            'slowest_view': {
                'name': slowest_view[0],
                'execution_time': slowest_view[1]['execution_time']
            }
        }


class ProfilerMiddleware(MiddlewareMixin):
    """Middleware for automatic profiling"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.profiler = DjangoProfiler(enabled=getattr(settings, 'PROFILING_ENABLED', False))
        super().__init__(get_response)
    
    def process_request(self, request):
        """Start profiling for the request"""
        if not self.profiler.enabled:
            return None
        
        # Skip profiling for certain paths
        skip_paths = getattr(settings, 'PROFILING_SKIP_PATHS', ['/admin/', '/static/', '/media/'])
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        request._profiler = cProfile.Profile()
        request._profiler.enable()
        request._start_time = time.time()
        
        return None
    
    def process_response(self, request, response):
        """Finish profiling and add data to response"""
        if not self.profiler.enabled or not hasattr(request, '_profiler'):
            return response
        
        request._profiler.disable()
        end_time = time.time()
        execution_time = end_time - request._start_time
        
        # Add timing header
        response['X-Execution-Time'] = f"{execution_time:.4f}s"
        
        # Store detailed profile data if requested
        if request.GET.get('profile') == '1':
            s = io.StringIO()
            ps = pstats.Stats(request._profiler, stream=s)
            ps.sort_stats('cumulative')
            ps.print_stats(50)
            profile_output = s.getvalue()
            
            # Store in profiler
            view_name = f"{request.method} {request.path}"
            self.profiler.profile_data[view_name] = {
                'execution_time': execution_time,
                'timestamp': time.time(),
                'profile_output': profile_output,
                'request_method': request.method,
                'request_path': request.path
            }
        
        return response


class DatabaseQueryProfiler:
    """Profile database queries"""
    
    def __init__(self):
        self.queries = []
        self.enabled = False
    
    def enable(self):
        """Enable query profiling"""
        self.enabled = True
        self.queries.clear()
    
    def disable(self):
        """Disable query profiling"""
        self.enabled = False
    
    def add_query(self, query: str, execution_time: float, params: tuple = None):
        """Add a query to the profile"""
        if not self.enabled:
            return
        
        self.queries.append({
            'query': query,
            'execution_time': execution_time,
            'params': params,
            'timestamp': time.time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get query profiling summary"""
        if not self.queries:
            return {"message": "No queries profiled"}
        
        total_queries = len(self.queries)
        total_time = sum(q['execution_time'] for q in self.queries)
        avg_time = total_time / total_queries if total_queries > 0 else 0
        
        # Find slowest query
        slowest_query = max(self.queries, key=lambda x: x['execution_time'])
        
        # Group by similar queries
        query_groups = {}
        for query in self.queries:
            # Normalize query by removing specific values
            normalized = query['query'][:100] + "..." if len(query['query']) > 100 else query['query']
            if normalized not in query_groups:
                query_groups[normalized] = {'count': 0, 'total_time': 0}
            query_groups[normalized]['count'] += 1
            query_groups[normalized]['total_time'] += query['execution_time']
        
        return {
            'total_queries': total_queries,
            'total_execution_time': total_time,
            'average_execution_time': avg_time,
            'slowest_query': {
                'query': slowest_query['query'][:200],
                'execution_time': slowest_query['execution_time']
            },
            'query_groups': query_groups
        }


class MemoryProfiler:
    """Profile memory usage"""
    
    def __init__(self):
        self.enabled = False
        self.snapshots = []
    
    def enable(self):
        """Enable memory profiling"""
        try:
            import psutil
            self.enabled = True
            self.psutil = psutil
            self.process = psutil.Process()
            self.snapshots.clear()
        except ImportError:
            logger.warning("psutil not available, memory profiling disabled")
            self.enabled = False
    
    def take_snapshot(self, label: str = ""):
        """Take a memory snapshot"""
        if not self.enabled:
            return
        
        memory_info = self.process.memory_info()
        self.snapshots.append({
            'label': label,
            'timestamp': time.time(),
            'memory_rss': memory_info.rss,
            'memory_vms': memory_info.vms,
            'memory_percent': self.process.memory_percent()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get memory profiling summary"""
        if not self.snapshots:
            return {"message": "No memory snapshots available"}
        
        snapshots = self.snapshots
        max_memory = max(s['memory_rss'] for s in snapshots)
        min_memory = min(s['memory_rss'] for s in snapshots)
        avg_memory = sum(s['memory_rss'] for s in snapshots) / len(snapshots)
        
        return {
            'total_snapshots': len(snapshots),
            'max_memory_mb': max_memory / (1024 * 1024),
            'min_memory_mb': min_memory / (1024 * 1024),
            'avg_memory_mb': avg_memory / (1024 * 1024),
            'memory_growth_mb': (snapshots[-1]['memory_rss'] - snapshots[0]['memory_rss']) / (1024 * 1024),
            'snapshots': snapshots[-10:]  # Last 10 snapshots
        }


# Global profiler instances
django_profiler = DjangoProfiler()
db_profiler = DatabaseQueryProfiler()
memory_profiler = MemoryProfiler()


def profile_function(func: Callable) -> Callable:
    """Decorator to profile individual functions"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
        finally:
            end_time = time.time()
            profiler.disable()
        
        execution_time = end_time - start_time
        
        # Log profiling info
        if execution_time > 0.1:  # Only log slow functions
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s)
            ps.sort_stats('cumulative')
            ps.print_stats(10)
            
            logger.info(f"Function {func.__name__} took {execution_time:.4f}s")
            logger.debug(f"Profile data:\n{s.getvalue()}")
        
        return result
    
    return wrapper


# Performance analysis utilities
def analyze_slow_queries(threshold_ms: float = 100) -> List[Dict[str, Any]]:
    """Analyze slow database queries"""
    slow_queries = [
        q for q in db_profiler.queries 
        if q['execution_time'] * 1000 > threshold_ms
    ]
    
    return sorted(slow_queries, key=lambda x: x['execution_time'], reverse=True)


def get_performance_report() -> Dict[str, Any]:
    """Get comprehensive performance report"""
    return {
        'django_profiler': django_profiler.get_summary(),
        'database_profiler': db_profiler.get_summary(),
        'memory_profiler': memory_profiler.get_summary(),
        'slow_queries': analyze_slow_queries(),
        'timestamp': time.time()
    }


# Django management command integration
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Django command for performance profiling"""
    help = 'Performance profiling utilities'
    
    def add_arguments(self, parser):
        parser.add_argument('--enable', action='store_true', help='Enable profiling')
        parser.add_argument('--disable', action='store_true', help='Disable profiling')
        parser.add_argument('--report', action='store_true', help='Generate performance report')
        parser.add_argument('--clear', action='store_true', help='Clear profiling data')
    
    def handle(self, *args, **options):
        if options['enable']:
            django_profiler.enabled = True
            db_profiler.enable()
            memory_profiler.enable()
            self.stdout.write(self.style.SUCCESS('Profiling enabled'))
        
        elif options['disable']:
            django_profiler.enabled = False
            db_profiler.disable()
            self.stdout.write(self.style.SUCCESS('Profiling disabled'))
        
        elif options['report']:
            report = get_performance_report()
            self.stdout.write(self.style.SUCCESS('Performance Report:'))
            self.stdout.write(str(report))
        
        elif options['clear']:
            django_profiler.clear_profile_data()
            db_profiler.queries.clear()
            memory_profiler.snapshots.clear()
            self.stdout.write(self.style.SUCCESS('Profiling data cleared'))


if __name__ == "__main__":
    # Example usage
    profiler = DjangoProfiler(enabled=True)
    
    @profiler.profile_view
    def example_view(request):
        # Simulate some work
        time.sleep(0.1)
        return HttpResponse("Hello World")
    
    # Simulate request
    class MockRequest:
        method = "GET"
        path = "/test/"
    
    request = MockRequest()
    response = example_view(request)
    
    print("Profile summary:")
    print(profiler.get_summary())