"""
Memory Optimization Tools
Advanced memory management and optimization for LLM applications
"""

import gc
import psutil
import tracemalloc
import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
import weakref
from contextlib import contextmanager
import pickle
import sys

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class MemoryStats:
    """Memory usage statistics"""
    timestamp: datetime
    process_memory_mb: float
    system_memory_percent: float
    available_memory_mb: float
    gpu_memory_mb: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    python_objects: int = 0
    gc_collections: Dict[int, int] = field(default_factory=dict)

class MemoryProfiler:
    """
    Advanced memory profiler for tracking memory usage patterns
    """
    
    def __init__(self, track_allocations: bool = False):
        self.track_allocations = track_allocations
        self.memory_history: List[MemoryStats] = []
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.allocation_snapshots: List[Any] = []
        
        if self.track_allocations:
            tracemalloc.start()
    
    def get_current_memory_stats(self) -> MemoryStats:
        """Get current memory usage statistics"""
        process = psutil.Process()
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        
        # Get Python object count
        python_objects = len(gc.get_objects())
        
        # Get GC statistics
        gc_stats = {}
        for i in range(3):
            gc_stats[i] = gc.get_count()[i]
        
        stats = MemoryStats(
            timestamp=datetime.now(),
            process_memory_mb=memory_info.rss / (1024 * 1024),
            system_memory_percent=system_memory.percent,
            available_memory_mb=system_memory.available / (1024 * 1024),
            python_objects=python_objects,
            gc_collections=gc_stats
        )
        
        # Add GPU stats if available
        if TORCH_AVAILABLE and torch.cuda.is_available():
            try:
                gpu_memory_allocated = torch.cuda.memory_allocated() / (1024 * 1024)
                gpu_memory_reserved = torch.cuda.memory_reserved() / (1024 * 1024)
                gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
                
                stats.gpu_memory_mb = gpu_memory_allocated
                stats.gpu_memory_percent = (gpu_memory_reserved / gpu_memory_total) * 100
            except Exception as e:
                logger.warning(f"Failed to get GPU memory stats: {e}")
        
        return stats
    
    def start_monitoring(self, interval: float = 5.0):
        """Start continuous memory monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,), 
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Memory monitoring started (interval: {interval}s)")
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self, interval: float):
        """Background monitoring loop"""
        while self.monitoring_active:
            try:
                stats = self.get_current_memory_stats()
                self.memory_history.append(stats)
                
                # Keep only last 1000 entries to prevent memory bloat
                if len(self.memory_history) > 1000:
                    self.memory_history = self.memory_history[-800:]
                
                # Log warnings for high memory usage
                if stats.process_memory_mb > 4000:  # 4GB
                    logger.warning(f"High process memory usage: {stats.process_memory_mb:.1f}MB")
                
                if stats.system_memory_percent > 85:
                    logger.warning(f"High system memory usage: {stats.system_memory_percent:.1f}%")
                
                if stats.gpu_memory_percent and stats.gpu_memory_percent > 90:
                    logger.warning(f"High GPU memory usage: {stats.gpu_memory_percent:.1f}%")
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
            
            time.sleep(interval)
    
    def take_snapshot(self, description: str = "") -> Dict[str, Any]:
        """Take a memory allocation snapshot"""
        if not tracemalloc.is_tracing():
            logger.warning("Tracemalloc not active, starting now")
            tracemalloc.start()
        
        snapshot = tracemalloc.take_snapshot()
        stats = self.get_current_memory_stats()
        
        snapshot_data = {
            'timestamp': datetime.now(),
            'description': description,
            'memory_stats': stats,
            'snapshot': snapshot
        }
        
        self.allocation_snapshots.append(snapshot_data)
        logger.info(f"Memory snapshot taken: {description}")
        
        return snapshot_data
    
    def compare_snapshots(self, snapshot1_idx: int = -2, snapshot2_idx: int = -1) -> Dict[str, Any]:
        """Compare two memory snapshots"""
        if len(self.allocation_snapshots) < 2:
            return {"error": "Need at least 2 snapshots for comparison"}
        
        snap1 = self.allocation_snapshots[snapshot1_idx]
        snap2 = self.allocation_snapshots[snapshot2_idx]
        
        # Compare snapshots
        top_stats = snap2['snapshot'].compare_to(snap1['snapshot'], 'lineno')
        
        # Get top memory differences
        top_differences = []
        for stat in top_stats[:10]:  # Top 10 differences
            top_differences.append({
                'filename': stat.traceback.format()[0],
                'size_diff_mb': stat.size_diff / (1024 * 1024),
                'count_diff': stat.count_diff,
                'size_mb': stat.size / (1024 * 1024)
            })
        
        memory_diff = snap2['memory_stats'].process_memory_mb - snap1['memory_stats'].process_memory_mb
        
        return {
            'snapshot1': snap1['description'],
            'snapshot2': snap2['description'],
            'memory_diff_mb': memory_diff,
            'top_differences': top_differences,
            'timestamp1': snap1['timestamp'],
            'timestamp2': snap2['timestamp']
        }
    
    def get_memory_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze memory usage trends"""
        if not self.memory_history:
            return {"message": "No memory history available"}
        
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_stats = [s for s in self.memory_history if s.timestamp > cutoff]
        
        if not recent_stats:
            return {"message": f"No memory data for last {hours} hours"}
        
        # Calculate trends
        memory_values = [s.process_memory_mb for s in recent_stats]
        gpu_memory_values = [s.gpu_memory_mb for s in recent_stats if s.gpu_memory_mb is not None]
        
        trends = {
            'time_period_hours': hours,
            'data_points': len(recent_stats),
            'memory_mb': {
                'min': min(memory_values),
                'max': max(memory_values),
                'avg': sum(memory_values) / len(memory_values),
                'current': memory_values[-1] if memory_values else 0,
                'trend': 'increasing' if memory_values[-1] > memory_values[0] else 'decreasing'
            },
            'python_objects': {
                'min': min(s.python_objects for s in recent_stats),
                'max': max(s.python_objects for s in recent_stats),
                'avg': sum(s.python_objects for s in recent_stats) / len(recent_stats)
            }
        }
        
        if gpu_memory_values:
            trends['gpu_memory_mb'] = {
                'min': min(gpu_memory_values),
                'max': max(gpu_memory_values),
                'avg': sum(gpu_memory_values) / len(gpu_memory_values),
                'current': gpu_memory_values[-1] if gpu_memory_values else 0
            }
        
        return trends

class MemoryOptimizer:
    """
    Memory optimization utilities and automatic cleanup
    """
    
    def __init__(self):
        self.cleanup_callbacks: List[Callable] = []
        self.object_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self.optimization_stats = {
            'gc_runs': 0,
            'objects_cleaned': 0,
            'memory_freed_mb': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def register_cleanup_callback(self, callback: Callable):
        """Register a cleanup callback function"""
        self.cleanup_callbacks.append(callback)
    
    def optimize_garbage_collection(self):
        """Optimize garbage collection settings"""
        # Adjust GC thresholds for better performance
        original_thresholds = gc.get_threshold()
        
        # More aggressive collection for generation 0 (short-lived objects)
        # Less frequent for generations 1 and 2 (long-lived objects)
        new_thresholds = (original_thresholds[0] // 2, 
                         original_thresholds[1] * 2, 
                         original_thresholds[2] * 3)
        
        gc.set_threshold(*new_thresholds)
        logger.info(f"GC thresholds adjusted: {original_thresholds} -> {new_thresholds}")
    
    def force_cleanup(self) -> Dict[str, Any]:
        """Force comprehensive memory cleanup"""
        initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        
        # Run cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Cleanup callback failed: {e}")
        
        # Clear GPU cache if available
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        # Force garbage collection
        collected = 0
        for generation in range(3):
            collected += gc.collect(generation)
        
        # Clear weakref cache
        cache_size = len(self.object_cache)
        self.object_cache.clear()
        
        final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_freed = initial_memory - final_memory
        
        # Update stats
        self.optimization_stats['gc_runs'] += 1
        self.optimization_stats['objects_cleaned'] += collected
        self.optimization_stats['memory_freed_mb'] += memory_freed
        
        cleanup_result = {
            'objects_collected': collected,
            'memory_freed_mb': memory_freed,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'cache_cleared': cache_size
        }
        
        logger.info(f"Memory cleanup completed: {cleanup_result}")
        return cleanup_result
    
    @contextmanager
    def memory_limit_context(self, max_memory_mb: float):
        """Context manager that enforces memory limits"""
        def check_memory():
            current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            if current_memory > max_memory_mb:
                self.force_cleanup()
                current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
                if current_memory > max_memory_mb:
                    raise MemoryError(f"Memory limit exceeded: {current_memory:.1f}MB > {max_memory_mb}MB")
        
        check_memory()
        try:
            yield
        finally:
            check_memory()
    
    def optimize_tensor_memory(self):
        """Optimize PyTorch tensor memory usage"""
        if not TORCH_AVAILABLE:
            return
        
        # Enable memory-efficient attention if available
        try:
            torch.backends.cuda.enable_flash_sdp(True)
        except:
            pass
        
        # Set memory fraction to prevent OOM
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(0.9)
            
            # Enable memory pool optimization
            try:
                torch.cuda.memory._set_allocator_settings("max_split_size_mb:128")
            except:
                pass
    
    def get_memory_recommendations(self) -> List[Dict[str, Any]]:
        """Get memory optimization recommendations"""
        recommendations = []
        
        current_stats = MemoryProfiler().get_current_memory_stats()
        
        # High memory usage recommendations
        if current_stats.process_memory_mb > 8000:  # 8GB
            recommendations.append({
                'type': 'memory_usage',
                'priority': 'high',
                'issue': 'High process memory usage',
                'recommendation': 'Consider model quantization, batch size reduction, or memory-efficient models',
                'current_value': f'{current_stats.process_memory_mb:.1f}MB',
                'suggested_action': 'force_cleanup'
            })
        
        # High object count
        if current_stats.python_objects > 1000000:  # 1M objects
            recommendations.append({
                'type': 'object_count',
                'priority': 'medium',
                'issue': 'High Python object count',
                'recommendation': 'Review object lifecycle and implement object pooling',
                'current_value': f'{current_stats.python_objects:,} objects',
                'suggested_action': 'optimize_gc'
            })
        
        # GPU memory recommendations
        if current_stats.gpu_memory_percent and current_stats.gpu_memory_percent > 85:
            recommendations.append({
                'type': 'gpu_memory',
                'priority': 'high',
                'issue': 'High GPU memory usage',
                'recommendation': 'Clear GPU cache, reduce batch size, or use gradient checkpointing',
                'current_value': f'{current_stats.gpu_memory_percent:.1f}%',
                'suggested_action': 'clear_gpu_cache'
            })
        
        return recommendations
    
    def auto_optimize(self) -> Dict[str, Any]:
        """Automatically apply memory optimizations"""
        recommendations = self.get_memory_recommendations()
        actions_taken = []
        
        for rec in recommendations:
            action = rec.get('suggested_action')
            
            if action == 'force_cleanup':
                result = self.force_cleanup()
                actions_taken.append({
                    'action': 'force_cleanup',
                    'result': result
                })
            
            elif action == 'optimize_gc':
                self.optimize_garbage_collection()
                actions_taken.append({
                    'action': 'optimize_gc',
                    'result': 'GC thresholds optimized'
                })
            
            elif action == 'clear_gpu_cache' and TORCH_AVAILABLE:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    actions_taken.append({
                        'action': 'clear_gpu_cache',
                        'result': 'GPU cache cleared'
                    })
        
        return {
            'recommendations_found': len(recommendations),
            'actions_taken': actions_taken,
            'timestamp': datetime.now().isoformat()
        }

# Global instances
memory_profiler = MemoryProfiler()
memory_optimizer = MemoryOptimizer()

# Convenience functions
def start_memory_monitoring(interval: float = 5.0):
    """Start global memory monitoring"""
    memory_profiler.start_monitoring(interval)

def stop_memory_monitoring():
    """Stop global memory monitoring"""
    memory_profiler.stop_monitoring()

def get_memory_stats():
    """Get current memory statistics"""
    return memory_profiler.get_current_memory_stats()

def optimize_memory():
    """Run automatic memory optimization"""
    return memory_optimizer.auto_optimize()

def force_memory_cleanup():
    """Force comprehensive memory cleanup"""
    return memory_optimizer.force_cleanup()