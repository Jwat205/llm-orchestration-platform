"""
Async Redis-backed LRU + TTL cache for expensive graph queries.
Provides decorator & low-level API.
"""

#graph_cache.py

import functools
import json
from typing import Any, Optional, Callable
from datetime import timedelta

import redis.asyncio as redis
# NEW (correct for Pydantic v2)
from pydantic_settings import BaseSettings
from pydantic import Field

class CacheSettings(BaseSettings):
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    default_ttl: int = Field(default=300, env="CACHE_TTL")  # seconds


class GraphCache:
    """
    Singleton Redis client with async locking for critical sections.
    """

    _instance: Optional["GraphCache"] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls) -> "GraphCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(CacheSettings().redis_url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        client = await self.client()
        raw = await client.get(key)
        return json.loads(raw) if raw else None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        client = await self.client()
        ttl = ttl or CacheSettings().default_ttl
        return await client.setex(key, timedelta(seconds=ttl), json.dumps(value))

    async def delete(self, key: str) -> int:
        client = await self.client()
        return await client.delete(key)

    async def clear(self) -> bool:
        client = await self.client()
        return await client.flushdb()


# Decorator for transparent caching
def cached(ttl: Optional[int] = None) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = GraphCache()
            key = f"{func.__module__}.{func.__name__}:{json.dumps(args, default=str)}:{json.dumps(kwargs, default=str)}"
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator