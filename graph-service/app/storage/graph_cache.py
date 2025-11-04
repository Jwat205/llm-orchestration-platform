"""
Graph Cache Implementation
Provides high-performance caching for graph data with intelligent eviction and consistency management.
"""
import asyncio
from typing import List, Dict, Any, Optional, Union, Set, Tuple
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
import time
import hashlib
from collections import OrderedDict, defaultdict
import weakref
import pickle
from datetime import datetime, timedelta
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

class CacheLevel(Enum):
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"

class EvictionPolicy(Enum):
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    FIFO = "fifo"

@dataclass
class CacheConfig:
    cache_level: CacheLevel = CacheLevel.HYBRID
    memory_cache_size: int = 10000
    memory_ttl_seconds: int = 3600
    redis_url: Optional[str] = "redis://localhost:6379"
    redis_ttl_seconds: int = 86400  # 24 hours
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    compression_enabled: bool = True
    consistency_check_interval: int = 300  # 5 minutes
    max_key_size: int = 1024
    max_value_size: int = 1024 * 1024  # 1MB
    cache_warming_enabled: bool = True
    metrics_enabled: bool = True

@dataclass
class CacheItem:
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl: Optional[float] = None
    size_bytes: int = 0
    tags: Set[str] = field(default_factory=set)

@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    errors: int = 0
    total_requests: int = 0
    avg_response_time_ms: float = 0.0
    memory_usage_bytes: int = 0
    redis_usage_bytes: int = 0
    hit_rate: float = 0.0

class GraphCache:
    """High-performance graph data cache with multi-level storage"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = CacheConfig(**config) if config else CacheConfig()
        
        # Memory cache (L1)
        self.memory_cache: OrderedDict[str, CacheItem] = OrderedDict()
        self.memory_cache_lock = asyncio.Lock()
        
        # Redis client (L2)
        self.redis_client: Optional[aioredis.Redis] = None
        
        # Cache statistics
        self.metrics = CacheMetrics()
        
        # Key tracking for consistency
        self.entity_keys: Set[str] = set()
        self.relationship_keys: Set[str] = set()
        self.query_keys: Set[str] = set()
        
        # Tag-based invalidation
        self.tag_to_keys: Dict[str, Set[str]] = defaultdict(set)
        self.key_to_tags: Dict[str, Set[str]] = defaultdict(set)
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.consistency_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        
        # Shutdown event
        self.shutdown_event = asyncio.Event()
        
        # Cache warming
        self.warming_queue: asyncio.Queue = asyncio.Queue()
        self.warming_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize the cache system"""
        try:
            logger.info("Initializing graph cache...")
            
            # Initialize Redis if configured
            if self.config.cache_level in [CacheLevel.REDIS, CacheLevel.HYBRID]:
                await self._initialize_redis()
            
            # Start background tasks
            await self._start_background_tasks()
            
            logger.info(f"Graph cache initialized with {self.config.cache_level.value} level")
            
        except Exception as e:
            logger.error(f"Error initializing graph cache: {e}")
            raise
    
    async def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            if self.config.redis_url:
                self.redis_client = aioredis.from_url(
                    self.config.redis_url,
                    decode_responses=False,  # Keep binary for compression
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis cache connection established")
            else:
                logger.warning("Redis URL not configured, using memory-only cache")
                
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            if self.config.cache_level == CacheLevel.REDIS:
                raise
            else:
                logger.warning("Falling back to memory-only cache")
                self.config.cache_level = CacheLevel.MEMORY
    
    async def _start_background_tasks(self):
        """Start background maintenance tasks"""
        # Cleanup task for expired items
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Consistency check task
        self.consistency_task = asyncio.create_task(self._consistency_check_loop())
        
        # Metrics collection task
        if self.config.metrics_enabled:
            self.metrics_task = asyncio.create_task(self._metrics_loop())
        
        # Cache warming task
        if self.config.cache_warming_enabled:
            self.warming_task = asyncio.create_task(self._warming_loop())
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        start_time = time.time()
        
        try:
            self.metrics.total_requests += 1
            
            # Validate key
            if not self._validate_key(key):
                return None
            
            # Try memory cache first (L1)
            if self.config.cache_level in [CacheLevel.MEMORY, CacheLevel.HYBRID]:
                value = await self._get_from_memory(key)
                if value is not None:
                    await self._update_metrics(start_time, hit=True)
                    return value
            
            # Try Redis cache (L2)
            if self.config.cache_level in [CacheLevel.REDIS, CacheLevel.HYBRID]:
                value = await self._get_from_redis(key)
                if value is not None:
                    # Promote to memory cache if hybrid
                    if self.config.cache_level == CacheLevel.HYBRID:
                        await self._set_to_memory(key, value)
                    
                    await self._update_metrics(start_time, hit=True)
                    return value
            
            # Cache miss
            await self._update_metrics(start_time, hit=False)
            return None
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            self.metrics.errors += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[Set[str]] = None) -> bool:
        """Set value in cache"""
        try:
            self.metrics.sets += 1
            
            # Validate key and value
            if not self._validate_key(key) or not self._validate_value(value):
                return False
            
            # Set TTL
            if ttl is None:
                ttl = self.config.memory_ttl_seconds if self.config.cache_level == CacheLevel.MEMORY else self.config.redis_ttl_seconds
            
            # Create cache item
            cache_item = CacheItem(
                key=key,
                value=value,
                created_at=time.time(),
                accessed_at=time.time(),
                ttl=ttl,
                size_bytes=self._calculate_size(value),
                tags=tags or set()
            )
            
            # Set in memory cache
            if self.config.cache_level in [CacheLevel.MEMORY, CacheLevel.HYBRID]:
                await self._set_to_memory_with_item(key, cache_item)
            
            # Set in Redis cache
            if self.config.cache_level in [CacheLevel.REDIS, CacheLevel.HYBRID]:
                await self._set_to_redis(key, value, ttl)
            
            # Update tag mappings
            if tags:
                await self._update_tag_mappings(key, tags)
            
            # Track key type
            await self._track_key_type(key)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            self.metrics.errors += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            self.metrics.deletes += 1
            
            deleted = False
            
            # Delete from memory cache
            if self.config.cache_level in [CacheLevel.MEMORY, CacheLevel.HYBRID]:
                deleted |= await self._delete_from_memory(key)
            
            # Delete from Redis cache
            if self.config.cache_level in [CacheLevel.REDIS, CacheLevel.HYBRID]:
                deleted |= await self._delete_from_redis(key)
            
            # Clean up tag mappings
            await self._cleanup_tag_mappings(key)
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            self.metrics.errors += 1
            return False
    
    async def delete_by_tags(self, tags: Set[str]) -> int:
        """Delete all keys associated with given tags"""
        try:
            keys_to_delete = set()
            
            for tag in tags:
                keys_to_delete.update(self.tag_to_keys.get(tag, set()))
            
            deleted_count = 0
            for key in keys_to_delete:
                if await self.delete(key):
                    deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} keys by tags: {tags}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting by tags: {e}")
            return 0
    
    async def invalidate_entity_cache(self, entity_id: str):
        """Invalidate all cache entries related to an entity"""
        try:
            # Create tags for entity
            entity_tags = {f"entity:{entity_id}", "entities"}
            
            # Delete by tags
            await self.delete_by_tags(entity_tags)
            
            # Also invalidate queries that might include this entity
            query_pattern = f"*{entity_id}*"
            await self._delete_by_pattern(query_pattern)
            
        except Exception as e:
            logger.error(f"Error invalidating entity cache: {e}")
    
    async def invalidate_relationship_cache(self, relationship_id: str, source_id: Optional[str] = None, target_id: Optional[str] = None):
        """Invalidate all cache entries related to a relationship"""
        try:
            # Create tags for relationship
            rel_tags = {f"relationship:{relationship_id}", "relationships"}
            
            if source_id:
                rel_tags.add(f"entity:{source_id}")
            
            if target_id:
                rel_tags.add(f"entity:{target_id}")
            
            # Delete by tags
            await self.delete_by_tags(rel_tags)
            
        except Exception as e:
            logger.error(f"Error invalidating relationship cache: {e}")
    
    async def _get_from_memory(self, key: str) -> Optional[Any]:
        """Get value from memory cache"""
        async with self.memory_cache_lock:
            if key in self.memory_cache:
                item = self.memory_cache[key]
                
                # Check TTL
                if item.ttl and time.time() - item.created_at > item.ttl:
                    del self.memory_cache[key]
                    self.metrics.evictions += 1
                    return None
                
                # Update access info
                item.accessed_at = time.time()
                item.access_count += 1
                
                # Move to end for LRU
                if self.config.eviction_policy == EvictionPolicy.LRU:
                    self.memory_cache.move_to_end(key)
                
                self.metrics.hits += 1
                return item.value
            
            self.metrics.misses += 1
            return None
    
    async def _set_to_memory(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in memory cache"""
        cache_item = CacheItem(
            key=key,
            value=value,
            created_at=time.time(),
            accessed_at=time.time(),
            ttl=ttl or self.config.memory_ttl_seconds,
            size_bytes=self._calculate_size(value)
        )
        
        await self._set_to_memory_with_item(key, cache_item)
    
    async def _set_to_memory_with_item(self, key: str, item: CacheItem):
        """Set cache item in memory cache"""
        async with self.memory_cache_lock:
            # Check if we need to evict items
            while len(self.memory_cache) >= self.config.memory_cache_size:
                await self._evict_from_memory()
            
            self.memory_cache[key] = item
            
            # Update memory usage
            self.metrics.memory_usage_bytes += item.size_bytes
    
    async def _delete_from_memory(self, key: str) -> bool:
        """Delete value from memory cache"""
        async with self.memory_cache_lock:
            if key in self.memory_cache:
                item = self.memory_cache.pop(key)
                self.metrics.memory_usage_bytes -= item.size_bytes
                return True
            return False
    
    async def _evict_from_memory(self):
        """Evict item from memory cache based on eviction policy"""
        if not self.memory_cache:
            return
        
        if self.config.eviction_policy == EvictionPolicy.LRU:
            # Remove least recently used (first item)
            key, item = self.memory_cache.popitem(last=False)
        elif self.config.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            key = min(self.memory_cache.keys(), key=lambda k: self.memory_cache[k].access_count)
            item = self.memory_cache.pop(key)
        elif self.config.eviction_policy == EvictionPolicy.FIFO:
            # Remove first in (first item)
            key, item = self.memory_cache.popitem(last=False)
        else:  # TTL
            # Remove expired items first, then oldest
            now = time.time()
            expired_keys = [
                k for k, v in self.memory_cache.items()
                if v.ttl and now - v.created_at > v.ttl
            ]
            
            if expired_keys:
                key = expired_keys[0]
                item = self.memory_cache.pop(key)
            else:
                key, item = self.memory_cache.popitem(last=False)
        
        self.metrics.memory_usage_bytes -= item.size_bytes
        self.metrics.evictions += 1
    
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.redis_client:
            return None
        
        try:
            data = await self.redis_client.get(key)
            if data:
                # Decompress and deserialize
                value = await self._deserialize(data)
                self.metrics.hits += 1
                return value
            
            self.metrics.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Error getting from Redis: {e}")
            return None
    
    async def _set_to_redis(self, key: str, value: Any, ttl: int):
        """Set value in Redis cache"""
        if not self.redis_client:
            return
        
        try:
            # Serialize and compress
            data = await self._serialize(value)
            
            # Set with TTL
            await self.redis_client.setex(key, ttl, data)
            
        except Exception as e:
            logger.error(f"Error setting to Redis: {e}")
    
    async def _delete_from_redis(self, key: str) -> bool:
        """Delete value from Redis cache"""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting from Redis: {e}")
            return False
    
    async def _delete_by_pattern(self, pattern: str):
        """Delete keys matching pattern from Redis"""
        if not self.redis_client:
            return
        
        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                
                if keys:
                    await self.redis_client.delete(*keys)
                
                if cursor == 0:
                    break
                    
        except Exception as e:
            logger.error(f"Error deleting by pattern: {e}")
    
    async def _serialize(self, value: Any) -> bytes:
        """Serialize and optionally compress value"""
        try:
            # Serialize to bytes
            data = pickle.dumps(value)
            
            # Compress if enabled and beneficial
            if self.config.compression_enabled and len(data) > 1024:
                import gzip
                compressed = gzip.compress(data)
                if len(compressed) < len(data) * 0.9:  # Only if significant compression
                    return b'GZIP:' + compressed
            
            return data
            
        except Exception as e:
            logger.error(f"Error serializing value: {e}")
            raise
    
    async def _deserialize(self, data: bytes) -> Any:
        """Deserialize and optionally decompress value"""
        try:
            # Check if compressed
            if data.startswith(b'GZIP:'):
                import gzip
                data = gzip.decompress(data[5:])
            
            # Deserialize
            return pickle.loads(data)
            
        except Exception as e:
            logger.error(f"Error deserializing value: {e}")
            raise
    
    def _validate_key(self, key: str) -> bool:
        """Validate cache key"""
        if not key or len(key) > self.config.max_key_size:
            return False
        
        # Check for invalid characters
        if any(c in key for c in ['\n', '\r', '\t', '\0']):
            return False
        
        return True
    
    def _validate_value(self, value: Any) -> bool:
        """Validate cache value"""
        try:
            # Check size
            size = self._calculate_size(value)
            if size > self.config.max_value_size:
                return False
            
            # Check if serializable
            pickle.dumps(value)
            return True
            
        except Exception:
            return False
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of value in bytes"""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 0
    
    async def _update_tag_mappings(self, key: str, tags: Set[str]):
        """Update tag to key mappings"""
        for tag in tags:
            self.tag_to_keys[tag].add(key)
            self.key_to_tags[key].add(tag)
    
    async def _cleanup_tag_mappings(self, key: str):
        """Clean up tag mappings for deleted key"""
        tags = self.key_to_tags.get(key, set())
        for tag in tags:
            self.tag_to_keys[tag].discard(key)
            if not self.tag_to_keys[tag]:
                del self.tag_to_keys[tag]
        
        if key in self.key_to_tags:
            del self.key_to_tags[key]
    
    async def _track_key_type(self, key: str):
        """Track key by type for organized invalidation"""
        if key.startswith("entity:"):
            self.entity_keys.add(key)
        elif key.startswith("relationship:"):
            self.relationship_keys.add(key)
        elif key.startswith("query:"):
            self.query_keys.add(key)
    
    async def _cleanup_loop(self):
        """Background task for cleaning up expired items"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(60)  # Run every minute
                
                # Clean up memory cache
                await self._cleanup_expired_memory_items()
                
                # Update memory usage metric
                async with self.memory_cache_lock:
                    self.metrics.memory_usage_bytes = sum(
                        item.size_bytes for item in self.memory_cache.values()
                    )
        
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired_memory_items(self):
        """Clean up expired items from memory cache"""
        async with self.memory_cache_lock:
            now = time.time()
            expired_keys = []
            
            for key, item in self.memory_cache.items():
                if item.ttl and now - item.created_at > item.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                item = self.memory_cache.pop(key)
                self.metrics.memory_usage_bytes -= item.size_bytes
                self.metrics.evictions += 1
                await self._cleanup_tag_mappings(key)
    
    async def _consistency_check_loop(self):
        """Background task for consistency checks"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(self.config.consistency_check_interval)
                
                # Perform consistency checks
                await self._check_cache_consistency()
        
        except Exception as e:
            logger.error(f"Error in consistency check loop: {e}")
    
    async def _check_cache_consistency(self):
        """Check consistency between cache levels"""
        if self.config.cache_level != CacheLevel.HYBRID:
            return
        
        try:
            # Sample some keys and check consistency
            sample_size = min(100, len(self.memory_cache))
            if sample_size == 0:
                return
            
            import random
            sample_keys = random.sample(list(self.memory_cache.keys()), sample_size)
            
            inconsistent_count = 0
            
            for key in sample_keys:
                memory_value = await self._get_from_memory(key)
                redis_value = await self._get_from_redis(key)
                
                if memory_value != redis_value:
                    inconsistent_count += 1
                    logger.warning(f"Cache inconsistency detected for key: {key}")
            
            if inconsistent_count > sample_size * 0.1:  # More than 10% inconsistent
                logger.warning(f"High cache inconsistency detected: {inconsistent_count}/{sample_size}")
        
        except Exception as e:
            logger.error(f"Error checking cache consistency: {e}")
    
    async def _metrics_loop(self):
        """Background task for updating metrics"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(30)  # Update every 30 seconds
                
                # Calculate hit rate
                total_requests = self.metrics.hits + self.metrics.misses
                if total_requests > 0:
                    self.metrics.hit_rate = self.metrics.hits / total_requests
                
                # Get Redis memory usage if available
                if self.redis_client:
                    try:
                        info = await self.redis_client.info("memory")
                        self.metrics.redis_usage_bytes = info.get("used_memory", 0)
                    except Exception:
                        pass
        
        except Exception as e:
            logger.error(f"Error in metrics loop: {e}")
    
    async def _warming_loop(self):
        """Background task for cache warming"""
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Get warming request from queue with timeout
                    warming_request = await asyncio.wait_for(
                        self.warming_queue.get(), timeout=1.0
                    )
                    
                    # Process warming request
                    await self._process_warming_request(warming_request)
                    
                except asyncio.TimeoutError:
                    continue
        
        except Exception as e:
            logger.error(f"Error in warming loop: {e}")
    
    async def _process_warming_request(self, request: Dict[str, Any]):
        """Process cache warming request"""
        try:
            # This would implement cache warming logic
            # For now, just log the request
            logger.info(f"Processing cache warming request: {request}")
        except Exception as e:
            logger.error(f"Error processing warming request: {e}")
    
    async def warm_cache(self, keys: List[str], values: List[Any]):
        """Warm cache with predefined key-value pairs"""
        try:
            for key, value in zip(keys, values):
                await self.set(key, value)
            
            logger.info(f"Warmed cache with {len(keys)} items")
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
    
    async def _update_metrics(self, start_time: float, hit: bool):
        """Update response time metrics"""
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Update average response time using exponential moving average
        alpha = 0.1
        if self.metrics.avg_response_time_ms == 0:
            self.metrics.avg_response_time_ms = response_time
        else:
            self.metrics.avg_response_time_ms = (
                alpha * response_time + (1 - alpha) * self.metrics.avg_response_time_ms
            )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        return {
            "hits": self.metrics.hits,
            "misses": self.metrics.misses,
            "hit_rate": self.metrics.hit_rate,
            "sets": self.metrics.sets,
            "deletes": self.metrics.deletes,
            "evictions": self.metrics.evictions,
            "errors": self.metrics.errors,
            "total_requests": self.metrics.total_requests,
            "avg_response_time_ms": self.metrics.avg_response_time_ms,
            "memory_usage_bytes": self.metrics.memory_usage_bytes,
            "redis_usage_bytes": self.metrics.redis_usage_bytes,
            "memory_cache_size": len(self.memory_cache),
            "entity_keys_count": len(self.entity_keys),
            "relationship_keys_count": len(self.relationship_keys),
            "query_keys_count": len(self.query_keys),
            "tag_count": len(self.tag_to_keys)
        }
    
    async def clear(self):
        """Clear all cache data"""
        try:
            # Clear memory cache
            async with self.memory_cache_lock:
                self.memory_cache.clear()
                self.metrics.memory_usage_bytes = 0
            
            # Clear Redis cache
            if self.redis_client:
                await self.redis_client.flushdb()
            
            # Clear tracking data
            self.entity_keys.clear()
            self.relationship_keys.clear()
            self.query_keys.clear()
            self.tag_to_keys.clear()
            self.key_to_tags.clear()
            
            logger.info("Cache cleared")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    async def shutdown(self):
        """Shutdown cache and cleanup resources"""
        try:
            logger.info("Shutting down graph cache...")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Cancel background tasks
            for task in [self.cleanup_task, self.consistency_task, self.metrics_task, self.warming_task]:
                if task:
                    task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(
                *[t for t in [self.cleanup_task, self.consistency_task, self.metrics_task, self.warming_task] if t],
                return_exceptions=True
            )
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("Graph cache shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during cache shutdown: {e}")