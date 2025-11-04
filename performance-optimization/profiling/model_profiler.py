"""
Model Performance Profiler
Specialized profiling for LLM model inference performance
"""

import time
import threading
import GPUtil
import psutil
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import json
import numpy as np
from contextlib import contextmanager
import torch
import gc

logger = logging.getLogger(__name__)

@dataclass
class ModelMetrics:
    """Model-specific performance metrics"""
    model_name: str
    model_size: str
    batch_size: int
    sequence_length: int
    input_tokens: int
    output_tokens: int
    inference_time: float
    tokens_per_second: float
    memory_before: float
    memory_after: float
    memory_peak: float
    gpu_memory_before: Optional[float]
    gpu_memory_after: Optional[float]
    gpu_memory_peak: Optional[float]
    cpu_usage: float
    gpu_usage: Optional[float]
    temperature: Optional[float]
    quantization: Optional[str]
    precision: str
    timestamp: datetime
    error: Optional[str] = None

class ModelProfiler:
    """
    Comprehensive model performance profiler
    Tracks inference performance, memory usage, and throughput
    """
    
    def __init__(self):
        self.metrics_history: List[ModelMetrics] = []
        self.gpu_available = self._check_gpu_availability()
        self.monitoring_active = False
        self.peak_memory = 0
        self.peak_gpu_memory = 0
        
    def _check_gpu_availability(self) -> bool:
        """Check if GPU monitoring is available"""
        try:
            GPUtil.getGPUs()
            return torch.cuda.is_available()
        except:
            return False
    
    def _get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage"""
        memory = psutil.virtual_memory()
        metrics = {
            'cpu_memory': memory.used / (1024**3),  # GB
            'cpu_memory_percent': memory.percent
        }
        
        if self.gpu_available:
            try:
                metrics['gpu_memory'] = torch.cuda.memory_allocated() / (1024**3)  # GB
                metrics['gpu_memory_reserved'] = torch.cuda.memory_reserved() / (1024**3)  # GB
                metrics['gpu_memory_percent'] = (torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated()) * 100
            except:
                metrics['gpu_memory'] = None
                metrics['gpu_memory_reserved'] = None
                metrics['gpu_memory_percent'] = None
        
        return metrics
    
    def _get_gpu_metrics(self) -> Dict[str, Optional[float]]:
        """Get GPU performance metrics"""
        if not self.gpu_available:
            return {'gpu_usage': None, 'gpu_temperature': None}
        
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Primary GPU
                return {
                    'gpu_usage': gpu.load * 100,
                    'gpu_temperature': gpu.temperature
                }
        except:
            pass
        
        return {'gpu_usage': None, 'gpu_temperature': None}
    
    def _memory_monitor(self):
        """Background memory monitoring thread"""
        while self.monitoring_active:
            memory_metrics = self._get_memory_usage()
            self.peak_memory = max(self.peak_memory, memory_metrics['cpu_memory'])
            
            if memory_metrics.get('gpu_memory'):
                self.peak_gpu_memory = max(self.peak_gpu_memory, memory_metrics['gpu_memory'])
            
            time.sleep(0.1)  # Monitor every 100ms
    
    @contextmanager
    def profile_inference(self, 
                         model_name: str,
                         model_size: str = "unknown",
                         batch_size: int = 1,
                         quantization: str = None,
                         precision: str = "fp32"):
        """Context manager for profiling model inference"""
        
        # Reset peak memory tracking
        self.peak_memory = 0
        self.peak_gpu_memory = 0
        
        # Start memory monitoring
        self.monitoring_active = True
        monitor_thread = threading.Thread(target=self._memory_monitor, daemon=True)
        monitor_thread.start()
        
        # Collect initial metrics
        start_time = time.time()
        initial_memory = self._get_memory_usage()
        initial_gpu = self._get_gpu_metrics()
        
        # Clear GPU cache if available
        if self.gpu_available:
            torch.cuda.empty_cache()
            gc.collect()
        
        inference_data = {
            'model_name': model_name,
            'model_size': model_size,
            'batch_size': batch_size,
            'quantization': quantization,
            'precision': precision,
            'start_time': start_time,
            'initial_memory': initial_memory,
            'initial_gpu': initial_gpu,
            'input_tokens': 0,
            'output_tokens': 0,
            'sequence_length': 0
        }
        
        try:
            yield inference_data
        except Exception as e:
            inference_data['error'] = str(e)
            logger.error(f"Model inference error: {e}")
            raise
        finally:
            # Stop monitoring and collect final metrics
            self.monitoring_active = False
            monitor_thread.join(timeout=1)
            
            end_time = time.time()
            final_memory = self._get_memory_usage()
            final_gpu = self._get_gpu_metrics()
            
            # Calculate metrics
            inference_time = end_time - start_time
            tokens_per_second = inference_data['output_tokens'] / inference_time if inference_time > 0 else 0
            
            metrics = ModelMetrics(
                model_name=model_name,
                model_size=model_size,
                batch_size=batch_size,
                sequence_length=inference_data['sequence_length'],
                input_tokens=inference_data['input_tokens'],
                output_tokens=inference_data['output_tokens'],
                inference_time=inference_time,
                tokens_per_second=tokens_per_second,
                memory_before=initial_memory['cpu_memory'],
                memory_after=final_memory['cpu_memory'],
                memory_peak=self.peak_memory,
                gpu_memory_before=initial_memory.get('gpu_memory'),
                gpu_memory_after=final_memory.get('gpu_memory'),
                gpu_memory_peak=self.peak_gpu_memory,
                cpu_usage=psutil.cpu_percent(interval=0.1),
                gpu_usage=final_gpu.get('gpu_usage'),
                temperature=final_gpu.get('gpu_temperature'),
                quantization=quantization,
                precision=precision,
                timestamp=datetime.now(),
                error=inference_data.get('error')
            )
            
            self.metrics_history.append(metrics)
            await self._log_metrics(metrics)
    
    async def _log_metrics(self, metrics: ModelMetrics):
        """Log model performance metrics"""
        logger.info(f"Model Performance: {metrics.model_name} - "
                   f"{metrics.tokens_per_second:.1f} tokens/s - "
                   f"{metrics.inference_time:.3f}s - "
                   f"Memory: {metrics.memory_peak:.1f}GB")
    
    def get_model_summary(self, model_name: str = None, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for specific model or all models"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff]
        
        if model_name:
            recent_metrics = [m for m in recent_metrics if m.model_name == model_name]
        
        if not recent_metrics:
            return {"message": f"No metrics available for {model_name or 'any model'}"}
        
        # Calculate aggregated metrics
        total_inferences = len(recent_metrics)
        avg_inference_time = sum(m.inference_time for m in recent_metrics) / total_inferences
        avg_tokens_per_second = sum(m.tokens_per_second for m in recent_metrics) / total_inferences
        avg_memory_usage = sum(m.memory_peak for m in recent_metrics) / total_inferences
        
        # Token statistics
        total_input_tokens = sum(m.input_tokens for m in recent_metrics)
        total_output_tokens = sum(m.output_tokens for m in recent_metrics)
        
        # Performance by batch size
        batch_performance = {}
        for metric in recent_metrics:
            batch_size = metric.batch_size
            if batch_size not in batch_performance:
                batch_performance[batch_size] = {
                    'count': 0,
                    'avg_tokens_per_second': 0,
                    'avg_inference_time': 0,
                    'total_tokens_per_second': 0,
                    'total_inference_time': 0
                }
            
            batch_performance[batch_size]['count'] += 1
            batch_performance[batch_size]['total_tokens_per_second'] += metric.tokens_per_second
            batch_performance[batch_size]['total_inference_time'] += metric.inference_time
        
        # Calculate batch averages
        for batch_size, stats in batch_performance.items():
            stats['avg_tokens_per_second'] = stats['total_tokens_per_second'] / stats['count']
            stats['avg_inference_time'] = stats['total_inference_time'] / stats['count']
        
        # GPU metrics if available
        gpu_metrics = {}
        if self.gpu_available:
            gpu_data = [m for m in recent_metrics if m.gpu_memory_peak is not None]
            if gpu_data:
                gpu_metrics = {
                    'avg_gpu_memory': sum(m.gpu_memory_peak for m in gpu_data) / len(gpu_data),
                    'max_gpu_memory': max(m.gpu_memory_peak for m in gpu_data),
                    'avg_gpu_usage': sum(m.gpu_usage for m in gpu_data if m.gpu_usage) / len([m for m in gpu_data if m.gpu_usage]),
                    'avg_temperature': sum(m.temperature for m in gpu_data if m.temperature) / len([m for m in gpu_data if m.temperature])
                }
        
        # Error analysis
        errors = [m for m in recent_metrics if m.error]
        error_rate = (len(errors) / total_inferences) * 100 if total_inferences > 0 else 0
        
        return {
            'model_name': model_name or 'all_models',
            'time_period_hours': hours,
            'summary': {
                'total_inferences': total_inferences,
                'avg_inference_time': avg_inference_time,
                'avg_tokens_per_second': avg_tokens_per_second,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'avg_memory_usage_gb': avg_memory_usage,
                'error_rate': error_rate
            },
            'batch_performance': batch_performance,
            'gpu_metrics': gpu_metrics,
            'recent_errors': [{'error': e.error, 'timestamp': e.timestamp.isoformat()} 
                            for e in errors[-5:]]  # Last 5 errors
        }
    
    def compare_models(self, model_names: List[str], hours: int = 24) -> Dict[str, Any]:
        """Compare performance between different models"""
        comparison = {}
        
        for model_name in model_names:
            summary = self.get_model_summary(model_name, hours)
            if 'summary' in summary:
                comparison[model_name] = summary['summary']
        
        if not comparison:
            return {"message": "No data available for model comparison"}
        
        # Find best performing model for each metric
        best_performers = {
            'fastest_inference': min(comparison.items(), 
                                   key=lambda x: x[1].get('avg_inference_time', float('inf')))[0],
            'highest_throughput': max(comparison.items(), 
                                    key=lambda x: x[1].get('avg_tokens_per_second', 0))[0],
            'most_efficient_memory': min(comparison.items(), 
                                       key=lambda x: x[1].get('avg_memory_usage_gb', float('inf')))[0],
            'most_reliable': min(comparison.items(), 
                               key=lambda x: x[1].get('error_rate', float('inf')))[0]
        }
        
        return {
            'comparison': comparison,
            'best_performers': best_performers,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_optimization_recommendations(self, model_name: str = None) -> List[Dict[str, Any]]:
        """Get performance optimization recommendations"""
        recommendations = []
        
        if model_name:
            summary = self.get_model_summary(model_name)
        else:
            summary = self.get_model_summary()
        
        if 'summary' not in summary:
            return recommendations
        
        summary_data = summary['summary']
        
        # Inference time recommendations
        if summary_data.get('avg_inference_time', 0) > 5.0:
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'issue': 'High inference time',
                'recommendation': 'Consider model quantization, smaller model variant, or GPU acceleration',
                'current_value': f"{summary_data['avg_inference_time']:.2f}s",
                'target_value': '<5.0s'
            })
        
        # Throughput recommendations
        if summary_data.get('avg_tokens_per_second', 0) < 10:
            recommendations.append({
                'type': 'throughput',
                'priority': 'medium',
                'issue': 'Low token generation rate',
                'recommendation': 'Optimize batch size, use faster GPU, or implement dynamic batching',
                'current_value': f"{summary_data['avg_tokens_per_second']:.1f} tokens/s",
                'target_value': '>10 tokens/s'
            })
        
        # Memory recommendations
        if summary_data.get('avg_memory_usage_gb', 0) > 16:
            recommendations.append({
                'type': 'memory',
                'priority': 'high',
                'issue': 'High memory usage',
                'recommendation': 'Use model quantization, optimize batch size, or implement model sharding',
                'current_value': f"{summary_data['avg_memory_usage_gb']:.1f}GB",
                'target_value': '<16GB'
            })
        
        # Error rate recommendations
        if summary_data.get('error_rate', 0) > 1:
            recommendations.append({
                'type': 'reliability',
                'priority': 'critical',
                'issue': 'High error rate',
                'recommendation': 'Review model loading, input validation, and resource allocation',
                'current_value': f"{summary_data['error_rate']:.1f}%",
                'target_value': '<1%'
            })
        
        # Batch size optimization
        if 'batch_performance' in summary:
            batch_perf = summary['batch_performance']
            if len(batch_perf) > 1:
                best_batch = max(batch_perf.items(), 
                               key=lambda x: x[1]['avg_tokens_per_second'])
                recommendations.append({
                    'type': 'optimization',
                    'priority': 'low',
                    'issue': 'Batch size optimization',
                    'recommendation': f'Optimal batch size appears to be {best_batch[0]}',
                    'current_value': 'Mixed batch sizes',
                    'target_value': f'Batch size {best_batch[0]}'
                })
        
        return sorted(recommendations, 
                     key=lambda x: {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}[x['priority']], 
                     reverse=True)
    
    def export_model_metrics(self, filepath: str, model_name: str = None, hours: int = 24):
        """Export model performance metrics to JSON file"""
        summary = self.get_model_summary(model_name, hours)
        recommendations = self.get_optimization_recommendations(model_name)
        
        # Add raw metrics
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff]
        
        if model_name:
            recent_metrics = [m for m in recent_metrics if m.model_name == model_name]
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'model_name': model_name or 'all_models',
            'summary': summary,
            'recommendations': recommendations,
            'raw_metrics': [asdict(m) for m in recent_metrics]
        }
        
        # Convert datetime objects to strings
        for metric in export_data['raw_metrics']:
            if isinstance(metric['timestamp'], datetime):
                metric['timestamp'] = metric['timestamp'].isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Model metrics exported to {filepath}")

# Global model profiler instance
model_profiler = ModelProfiler()

# Convenience functions
def profile_model_inference(model_name: str, model_size: str = "unknown", 
                          batch_size: int = 1, quantization: str = None, 
                          precision: str = "fp32"):
    """Context manager for profiling model inference"""
    return model_profiler.profile_inference(model_name, model_size, batch_size, 
                                           quantization, precision)

def get_model_performance_summary(model_name: str = None, hours: int = 24):
    """Get model performance summary"""
    return model_profiler.get_model_summary(model_name, hours)

def get_model_optimization_recommendations(model_name: str = None):
    """Get optimization recommendations for models"""
    return model_profiler.get_optimization_recommendations(model_name)