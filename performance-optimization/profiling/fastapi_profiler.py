"""
FastAPI Performance Profiler
Advanced profiling tools for FastAPI LLM service performance optimization
"""

import asyncio
import time
import psutil
import GPUtil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import logging
from functools import wraps
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class ProfileMetrics:
    """Performance metrics data structure"""
    endpoint: str
    method: str
    duration: float
    memory_usage: float
    cpu_usage: float
    gpu_usage: Optional[float]
    gpu_memory: Optional[float]
    request_size: int
    response_size: int
    model_name: Optional[str]
    tokens_generated: Optional[int]
    timestamp: datetime
    user_id: Optional[str] = None
    error: Optional[str] = None

class FastAPIProfiler:
    """
    Comprehensive performance profiler for FastAPI LLM service
    Tracks CPU, memory, GPU usage, and LLM-specific metrics
    """
    
    def __init__(self, enable_gpu_monitoring: bool = True):
        self.enable_gpu_monitoring = enable_gpu_monitoring
        self.metrics_history: List[ProfileMetrics] = []
        self.active_requests: Dict[str, Dict] = {}
        self.gpu_available = self._check_gpu_availability()
        
    def _check_gpu_availability(self) -> bool:
        """Check if GPU monitoring is available"""
        if not self.enable_gpu_monitoring:
            return False
        try:
            GPUtil.getGPUs()
            return True
        except:
            logger.warning("GPU monitoring not available")
            return False
    
    def _get_system_metrics(self) -> Dict[str, float]:
        """Get current system performance metrics"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        metrics = {
            'cpu_usage': cpu_percent,
            'memory_usage': memory.percent,
            'memory_available': memory.available / (1024**3),  # GB
        }
        
        if self.gpu_available:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Primary GPU
                    metrics['gpu_usage'] = gpu.load * 100
                    metrics['gpu_memory'] = gpu.memoryUtil * 100
                    metrics['gpu_temperature'] = gpu.temperature
            except Exception as e:
                logger.warning(f"GPU metrics collection failed: {e}")
                
        return metrics
    
    @asynccontextmanager
    async def profile_request(self, endpoint: str, method: str, model_name: str = None):
        """Context manager for profiling individual requests"""
        request_id = f"{endpoint}_{method}_{int(time.time() * 1000)}"
        start_time = time.time()
        start_metrics = self._get_system_metrics()
        
        self.active_requests[request_id] = {
            'start_time': start_time,
            'start_metrics': start_metrics,
            'endpoint': endpoint,
            'method': method,
            'model_name': model_name
        }
        
        try:
            yield request_id
        except Exception as e:
            self.active_requests[request_id]['error'] = str(e)
            raise
        finally:
            await self._finalize_request_metrics(request_id)
    
    async def _finalize_request_metrics(self, request_id: str):
        """Finalize and store request metrics"""
        if request_id not in self.active_requests:
            return
            
        request_data = self.active_requests.pop(request_id)
        end_time = time.time()
        end_metrics = self._get_system_metrics()
        
        duration = end_time - request_data['start_time']
        
        # Calculate resource usage deltas
        cpu_usage = max(end_metrics.get('cpu_usage', 0), 
                       request_data['start_metrics'].get('cpu_usage', 0))
        memory_usage = end_metrics.get('memory_usage', 0)
        
        metrics = ProfileMetrics(
            endpoint=request_data['endpoint'],
            method=request_data['method'],
            duration=duration,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            gpu_usage=end_metrics.get('gpu_usage'),
            gpu_memory=end_metrics.get('gpu_memory'),
            request_size=request_data.get('request_size', 0),
            response_size=request_data.get('response_size', 0),
            model_name=request_data.get('model_name'),
            tokens_generated=request_data.get('tokens_generated'),
            timestamp=datetime.now(),
            user_id=request_data.get('user_id'),
            error=request_data.get('error')
        )
        
        self.metrics_history.append(metrics)
        await self._log_metrics(metrics)
    
    async def _log_metrics(self, metrics: ProfileMetrics):
        """Log performance metrics"""
        logger.info(f"Performance Metrics: {asdict(metrics)}")
    
    def profile_endpoint(self, model_name: str = None):
        """Decorator for profiling FastAPI endpoints"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract request info
                request = kwargs.get('request') or (args[0] if args else None)
                endpoint = getattr(request, 'url', {}).path if request else func.__name__
                method = getattr(request, 'method', 'UNKNOWN') if request else 'CALL'
                
                async with self.profile_request(endpoint, method, model_name) as request_id:
                    # Update request size if available
                    if request and hasattr(request, '_body'):
                        self.active_requests[request_id]['request_size'] = len(request._body)
                    
                    result = await func(*args, **kwargs)
                    
                    # Update response metrics
                    if isinstance(result, dict) and 'usage' in result:
                        usage = result['usage']
                        self.active_requests[request_id]['tokens_generated'] = usage.get('completion_tokens', 0)
                    
                    return result
            return wrapper
        return decorator
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff]
        
        if not recent_metrics:
            return {"message": "No metrics available"}
        
        # Calculate aggregated metrics
        total_requests = len(recent_metrics)
        avg_duration = sum(m.duration for m in recent_metrics) / total_requests
        avg_cpu = sum(m.cpu_usage for m in recent_metrics) / total_requests
        avg_memory = sum(m.memory_usage for m in recent_metrics) / total_requests
        
        errors = [m for m in recent_metrics if m.error]
        error_rate = (len(errors) / total_requests) * 100 if total_requests > 0 else 0
        
        # Endpoint breakdown
        endpoint_stats = {}
        for metric in recent_metrics:
            key = f"{metric.method} {metric.endpoint}"
            if key not in endpoint_stats:
                endpoint_stats[key] = {
                    'count': 0,
                    'total_duration': 0,
                    'avg_duration': 0,
                    'errors': 0
                }
            
            endpoint_stats[key]['count'] += 1
            endpoint_stats[key]['total_duration'] += metric.duration
            if metric.error:
                endpoint_stats[key]['errors'] += 1
        
        # Calculate averages
        for stats in endpoint_stats.values():
            stats['avg_duration'] = stats['total_duration'] / stats['count']
            stats['error_rate'] = (stats['errors'] / stats['count']) * 100
        
        # Model performance
        model_stats = {}
        for metric in recent_metrics:
            if metric.model_name:
                if metric.model_name not in model_stats:
                    model_stats[metric.model_name] = {
                        'requests': 0,
                        'total_tokens': 0,
                        'avg_tokens_per_second': 0,
                        'avg_duration': 0
                    }
                
                model_stats[metric.model_name]['requests'] += 1
                if metric.tokens_generated:
                    model_stats[metric.model_name]['total_tokens'] += metric.tokens_generated
        
        # Calculate model performance metrics
        for model, stats in model_stats.items():
            model_metrics = [m for m in recent_metrics if m.model_name == model]
            stats['avg_duration'] = sum(m.duration for m in model_metrics) / len(model_metrics)
            if stats['total_tokens'] > 0:
                total_duration = sum(m.duration for m in model_metrics)
                stats['avg_tokens_per_second'] = stats['total_tokens'] / total_duration
        
        return {
            'summary': {
                'total_requests': total_requests,
                'time_period_hours': hours,
                'avg_response_time': avg_duration,
                'avg_cpu_usage': avg_cpu,
                'avg_memory_usage': avg_memory,
                'error_rate': error_rate,
                'errors_count': len(errors)
            },
            'endpoints': endpoint_stats,
            'models': model_stats,
            'recent_errors': [{'endpoint': e.endpoint, 'error': e.error, 'timestamp': e.timestamp.isoformat()} 
                            for e in errors[-10:]]  # Last 10 errors
        }
    
    def export_metrics(self, filepath: str, hours: int = 24):
        """Export performance metrics to JSON file"""
        summary = self.get_performance_summary(hours)
        
        # Add raw metrics
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff]
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'summary': summary,
            'raw_metrics': [asdict(m) for m in recent_metrics]
        }
        
        # Convert datetime objects to strings
        for metric in export_data['raw_metrics']:
            if isinstance(metric['timestamp'], datetime):
                metric['timestamp'] = metric['timestamp'].isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Performance metrics exported to {filepath}")
    
    def get_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks"""
        if not self.metrics_history:
            return []
        
        bottlenecks = []
        
        # High response time endpoints
        high_latency = [m for m in self.metrics_history if m.duration > 10.0]  # >10s
        if high_latency:
            endpoint_latency = {}
            for metric in high_latency:
                key = f"{metric.method} {metric.endpoint}"
                if key not in endpoint_latency:
                    endpoint_latency[key] = []
                endpoint_latency[key].append(metric.duration)
            
            for endpoint, durations in endpoint_latency.items():
                avg_duration = sum(durations) / len(durations)
                bottlenecks.append({
                    'type': 'high_latency',
                    'endpoint': endpoint,
                    'avg_duration': avg_duration,
                    'occurrences': len(durations),
                    'severity': 'high' if avg_duration > 30 else 'medium'
                })
        
        # High CPU usage
        high_cpu = [m for m in self.metrics_history if m.cpu_usage > 80]
        if len(high_cpu) > len(self.metrics_history) * 0.1:  # >10% of requests
            bottlenecks.append({
                'type': 'high_cpu_usage',
                'avg_cpu': sum(m.cpu_usage for m in high_cpu) / len(high_cpu),
                'occurrences': len(high_cpu),
                'severity': 'high'
            })
        
        # High memory usage
        high_memory = [m for m in self.metrics_history if m.memory_usage > 85]
        if len(high_memory) > len(self.metrics_history) * 0.1:
            bottlenecks.append({
                'type': 'high_memory_usage',
                'avg_memory': sum(m.memory_usage for m in high_memory) / len(high_memory),
                'occurrences': len(high_memory),
                'severity': 'high'
            })
        
        # GPU bottlenecks
        if self.gpu_available:
            high_gpu = [m for m in self.metrics_history 
                       if m.gpu_usage and m.gpu_usage > 90]
            if len(high_gpu) > len(self.metrics_history) * 0.2:
                bottlenecks.append({
                    'type': 'gpu_saturation',
                    'avg_gpu_usage': sum(m.gpu_usage for m in high_gpu) / len(high_gpu),
                    'occurrences': len(high_gpu),
                    'severity': 'critical'
                })
        
        return sorted(bottlenecks, key=lambda x: {'critical': 3, 'high': 2, 'medium': 1}.get(x['severity'], 0), reverse=True)

# Global profiler instance
profiler = FastAPIProfiler()

# Convenience functions
def profile_llm_endpoint(model_name: str = None):
    """Decorator for profiling LLM endpoints"""
    return profiler.profile_endpoint(model_name)

def get_performance_summary(hours: int = 24):
    """Get performance summary"""
    return profiler.get_performance_summary(hours)

def export_performance_metrics(filepath: str, hours: int = 24):
    """Export performance metrics"""
    return profiler.export_metrics(filepath, hours)