import hashlib
import json
import os
import time
from typing import Optional

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


def _make_cache_key(model: str, messages: list, temperature: float, max_tokens: int) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        sort_keys=True,
    )
    return f"inference:{hashlib.sha256(payload.encode()).hexdigest()}"


async def get_cached_response(model: str, messages: list, temperature: float, max_tokens: int) -> Optional[dict]:
    try:
        redis = await get_redis()
        key = _make_cache_key(model, messages, temperature, max_tokens)
        data = await redis.get(key)
        if data:
            logger.info("cache.hit", key=key[:20])
            return json.loads(data)
    except Exception as e:
        logger.warning("cache.get_error", error=str(e))
    return None


async def set_cached_response(
    model: str, messages: list, temperature: float, max_tokens: int, response: dict, ttl: int = 300
):
    try:
        redis = await get_redis()
        key = _make_cache_key(model, messages, temperature, max_tokens)
        await redis.setex(key, ttl, json.dumps(response))
        logger.info("cache.set", key=key[:20], ttl=ttl)
    except Exception as e:
        logger.warning("cache.set_error", error=str(e))


async def cache_token_validation(token: str, result: dict, ttl: int = 60):
    try:
        redis = await get_redis()
        key = f"token_val:{hashlib.sha256(token.encode()).hexdigest()}"
        await redis.setex(key, ttl, json.dumps(result))
    except Exception as e:
        logger.warning("cache.token_set_error", error=str(e))


async def get_cached_token_validation(token: str) -> Optional[dict]:
    try:
        redis = await get_redis()
        key = f"token_val:{hashlib.sha256(token.encode()).hexdigest()}"
        data = await redis.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning("cache.token_get_error", error=str(e))
    return None
