"""
Multi-level cache manager for LLM Platform
"""

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
import redis.asyncio as redis
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels in order of priority"""
    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.last_accessed is None:
            self.last_accessed = self.created_at


class CacheBackend(ABC):
    """Abstract cache backend"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        pass
    
    @abstractmethod
    async def invalidate_by_tag(self, tag: str) -> int:
        pass


class MemoryCache(CacheBackend):
    """In-memory cache backend with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: Dict[str, CacheEntry] = {}
        self.current_memory = 0
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            # Check expiration
            if entry.expires_at and datetime.now() > entry.expires_at:
                del self.cache[key]
                self.current_memory -= entry.size_bytes
                return None
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        async with self._lock:
            now = datetime.now()
            expires_at = now + timedelta(seconds=ttl) if ttl else None
            
            # Calculate size
            try:
                size_bytes = len(json.dumps(value, default=str).encode('utf-8'))
            except:
                size_bytes = 1024  # Fallback estimate
            
            # Remove old entry if exists
            if key in self.cache:
                self.current_memory -= self.cache[key].size_bytes
            
            # Check memory limits
            while (self.current_memory + size_bytes > self.max_memory_bytes or 
                   len(self.cache) >= self.max_size):
                if not self._evict_lru():
                    break
            
            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                size_bytes=size_bytes,
                tags=tags or []
            )
            
            self.cache[key] = entry
            self.current_memory += size_bytes
            
            return True
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                del self.cache[key]
                self.current_memory -= entry.size_bytes
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        return key in self.cache
    
    async def clear(self) -> bool:
        async with self._lock:
            self.cache.clear()
            self.current_memory = 0
            return True
    
    async def invalidate_by_tag(self, tag: str) -> int:
        async with self._lock:
            keys_to_delete = []
            for key, entry in self.cache.items():
                if tag in entry.tags:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                entry = self.cache[key]
                del self.cache[key]
                self.current_memory -= entry.size_bytes
            
            return len(keys_to_delete)
    
    def _evict_lru(self) -> bool:
        """Evict least recently used item"""
        if not self.cache:
            return False
        
        # Find LRU item
        lru_key = min(self.cache.keys(), 
                     key=lambda k: self.cache[k].last_accessed or datetime.min)
        
        entry = self.cache[lru_key]
        del self.cache[lru_key]
        self.current_memory -= entry.size_bytes
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_access_count = sum(entry.access_count for entry in self.cache.values())
        return {
            "entries": len(self.cache),
            "memory_usage_mb": self.current_memory / (1024 * 1024),
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "memory_utilization": self.current_memory / self.max_memory_bytes,
            "total_accesses": total_access_count,
            "hit_rate": total_access_count / max(len(self.cache), 1)
        }


class RedisCache(CacheBackend):
    """Redis cache backend"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", prefix: str = "llm_cache:"):
        self.redis_url = redis_url
        self.prefix = prefix
        self.redis_pool = None
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if self.redis_pool is None:
            self.redis_pool = redis.ConnectionPool.from_url(self.redis_url)
        return redis.Redis(connection_pool=self.redis_pool)
    
    def _make_key(self, key: str) -> str:
        """Add prefix to key"""
        return f"{self.prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            r = await self._get_redis()
            data = await r.get(self._make_key(key))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        try:
            r = await self._get_redis()
            data = json.dumps(value, default=str)
            
            redis_key = self._make_key(key)
            
            if ttl:
                await r.setex(redis_key, ttl, data)
            else:
                await r.set(redis_key, data)
            
            # Store tags if provided
            if tags:
                for tag in tags:
                    await r.sadd(f"{self.prefix}tag:{tag}", key)
            
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        try:
            r = await self._get_redis()
            result = await r.delete(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        try:
            r = await self._get_redis()
            result = await r.exists(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> bool:
        try:
            r = await self._get_redis()
            keys = await r.keys(f"{self.prefix}*")
            if keys:
                await r.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False
    
    async def invalidate_by_tag(self, tag: str) -> int:
        try:
            r = await self._get_redis()
            tag_key = f"{self.prefix}tag:{tag}"
            keys = await r.smembers(tag_key)
            
            if keys:
                # Delete the actual cache entries
                redis_keys = [self._make_key(key.decode()) for key in keys]
                await r.delete(*redis_keys)
                
                # Clean up the tag set
                await r.delete(tag_key)
                
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Redis invalidate_by_tag error: {e}")
            return 0


class MultiLevelCacheManager:
    """Multi-level cache manager with automatic failover"""
    
    def __init__(self, backends: List[CacheBackend]):
        self.backends = backends
        self.write_through = True  # Write to all levels
        self.read_through = True   # Try each level until found
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate consistent cache key"""
        key_parts = [prefix]
        
        # Add positional args
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True, default=str))
            else:
                key_parts.append(str(arg))
        
        # Add keyword args
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.append(json.dumps(sorted_kwargs, default=str))
        
        # Create hash of combined key
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, trying each level"""
        for i, backend in enumerate(self.backends):
            try:
                value = await backend.get(key)
                if value is not None:
                    # Populate higher-priority caches
                    if i > 0 and self.write_through:
                        for j in range(i):
                            try:
                                await self.backends[j].set(key, value)
                            except Exception as e:
                                logger.warning(f"Failed to populate cache level {j}: {e}")
                    
                    return value
            except Exception as e:
                logger.warning(f"Cache level {i} get failed: {e}")
                continue
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        """Set value in cache"""
        success_count = 0
        
        for i, backend in enumerate(self.backends):
            try:
                if await backend.set(key, value, ttl, tags):
                    success_count += 1
            except Exception as e:
                logger.warning(f"Cache level {i} set failed: {e}")
        
        return success_count > 0
    
    async def delete(self, key: str) -> bool:
        """Delete value from all cache levels"""
        success_count = 0
        
        for i, backend in enumerate(self.backends):
            try:
                if await backend.delete(key):
                    success_count += 1
            except Exception as e:
                logger.warning(f"Cache level {i} delete failed: {e}")
        
        return success_count > 0
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with the given tag"""
        total_invalidated = 0
        
        for i, backend in enumerate(self.backends):
            try:
                count = await backend.invalidate_by_tag(tag)
                total_invalidated += count
            except Exception as e:
                logger.warning(f"Cache level {i} invalidate_by_tag failed: {e}")
        
        return total_invalidated
    
    async def clear_all(self) -> bool:
        """Clear all cache levels"""
        success_count = 0
        
        for i, backend in enumerate(self.backends):
            try:
                if await backend.clear():
                    success_count += 1
            except Exception as e:
                logger.warning(f"Cache level {i} clear failed: {e}")
        
        return success_count > 0


class CacheDecorator:
    """Decorator for caching function results"""
    
    def __init__(self, cache_manager: MultiLevelCacheManager, ttl: int = 3600, tags: List[str] = None):
        self.cache_manager = cache_manager
        self.ttl = ttl
        self.tags = tags or []
    
    def __call__(self, func: Callable):
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self.cache_manager._generate_cache_key(
                f"func:{func.__name__}", *args, **kwargs
            )
            
            # Try to get from cache
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the result
            await self.cache_manager.set(cache_key, result, self.ttl, self.tags)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run async operations in a loop
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


# Convenience functions for common cache operations
async def cache_model_response(cache_manager: MultiLevelCacheManager, 
                             model: str, 
                             messages: List[Dict], 
                             response: Any,
                             ttl: int = 3600) -> None:
    """Cache model response"""
    key = cache_manager._generate_cache_key("model_response", model, messages)
    tags = [f"model:{model}", "responses"]
    await cache_manager.set(key, response, ttl, tags)


async def get_cached_model_response(cache_manager: MultiLevelCacheManager,
                                  model: str,
                                  messages: List[Dict]) -> Optional[Any]:
    """Get cached model response"""
    key = cache_manager._generate_cache_key("model_response", model, messages)
    return await cache_manager.get(key)


async def invalidate_model_cache(cache_manager: MultiLevelCacheManager, model: str) -> int:
    """Invalidate all cache entries for a specific model"""
    return await cache_manager.invalidate_by_tag(f"model:{model}")


# Factory function to create cache manager
def create_cache_manager(config: Dict[str, Any]) -> MultiLevelCacheManager:
    """Create cache manager from configuration"""
    backends = []
    
    # Memory cache (always first level)
    if config.get("memory", {}).get("enabled", True):
        memory_config = config.get("memory", {})
        backends.append(MemoryCache(
            max_size=memory_config.get("max_size", 1000),
            max_memory_mb=memory_config.get("max_memory_mb", 100)
        ))
    
    # Redis cache (second level)
    if config.get("redis", {}).get("enabled", True):
        redis_config = config.get("redis", {})
        backends.append(RedisCache(
            redis_url=redis_config.get("url", "redis://localhost:6379"),
            prefix=redis_config.get("prefix", "llm_cache:")
        ))
    
    return MultiLevelCacheManager(backends)


# Example usage and testing
if __name__ == "__main__":
    async def main():
        # Create cache configuration
        config = {
            "memory": {
                "enabled": True,
                "max_size": 100,
                "max_memory_mb": 50
            },
            "redis": {
                "enabled": True,
                "url": "redis://localhost:6379",
                "prefix": "test_cache:"
            }
        }
        
        # Create cache manager
        cache_manager = create_cache_manager(config)
        
        # Test caching
        await cache_manager.set("test_key", {"message": "Hello, World!"}, ttl=60, tags=["test"])
        
        result = await cache_manager.get("test_key")
        print(f"Cached result: {result}")
        
        # Test decorator
        @CacheDecorator(cache_manager, ttl=300, tags=["function_results"])
        async def expensive_function(x: int, y: int) -> int:
            await asyncio.sleep(1)  # Simulate expensive operation
            return x + y
        
        # First call (will be cached)
        start_time = time.time()
        result1 = await expensive_function(5, 3)
        time1 = time.time() - start_time
        
        # Second call (from cache)
        start_time = time.time()
        result2 = await expensive_function(5, 3)
        time2 = time.time() - start_time
        
        print(f"First call: {result1} in {time1:.3f}s")
        print(f"Second call: {result2} in {time2:.3f}s")
        
        # Clean up
        await cache_manager.clear_all()
    
    asyncio.run(main())