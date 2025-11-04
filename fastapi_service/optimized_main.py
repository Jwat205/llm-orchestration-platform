"""
Optimized FastAPI service for <100ms latency on non-model endpoints
Excludes model inference from SLA targets
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import asyncio
import asyncpg
import aioredis
import uvloop  # High-performance event loop
import ujson as json  # Faster JSON parsing
from typing import Optional
import time
import logging

# Set up uvloop for better performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Global connection pools
db_pool = None
redis_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global db_pool, redis_pool

    # Startup: Create connection pools
    db_pool = await asyncpg.create_pool(
        "postgresql://postgres:dev_password@localhost:5432/llm_api",
        min_size=5,
        max_size=20,
        command_timeout=10
    )

    redis_pool = aioredis.ConnectionPool.from_url(
        "redis://localhost:6379",
        max_connections=20,
        retry_on_timeout=True
    )

    yield

    # Shutdown: Close connection pools
    await db_pool.close()
    await redis_pool.disconnect()

app = FastAPI(
    title="Optimized LLM API",
    version="2.0.0",
    lifespan=lifespan,
    # Use ujson for faster JSON serialization
    default_response_class=None
)

# Middleware for performance
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for frequently accessed data
memory_cache = {}
CACHE_TTL = 300  # 5 minutes

async def get_from_cache(key: str):
    """Get data from memory cache or Redis"""
    # Check memory cache first (fastest)
    if key in memory_cache:
        data, timestamp = memory_cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
        else:
            del memory_cache[key]

    # Check Redis cache
    redis = aioredis.Redis(connection_pool=redis_pool)
    cached = await redis.get(key)
    if cached:
        data = json.loads(cached)
        # Store in memory cache for next access
        memory_cache[key] = (data, time.time())
        return data

    return None

async def set_cache(key: str, data: dict, ttl: int = CACHE_TTL):
    """Set data in both memory and Redis cache"""
    # Store in memory cache
    memory_cache[key] = (data, time.time())

    # Store in Redis with TTL
    redis = aioredis.Redis(connection_pool=redis_pool)
    await redis.setex(key, ttl, json.dumps(data))

@app.get("/health")
async def health_check():
    """Ultra-fast health check - <5ms target"""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/api/v1/llm/models")
async def get_models():
    """Fast models endpoint with aggressive caching - <50ms target"""
    cache_key = "models_list"

    # Try cache first
    cached_models = await get_from_cache(cache_key)
    if cached_models:
        return cached_models

    # If not cached, return static model list (no DB query needed)
    models_data = {
        "object": "list",
        "data": [
            {"id": "gpt2", "object": "model", "description": "GPT-2 model"},
            {"id": "gpt2-medium", "object": "model", "description": "GPT-2 Medium model"},
            {"id": "distilgpt2", "object": "model", "description": "DistilGPT-2 model"}
        ]
    }

    # Cache for future requests
    await set_cache(cache_key, models_data, ttl=3600)  # Cache for 1 hour

    return models_data

@app.get("/api/v1/monitoring/health")
async def monitoring_health():
    """Monitoring health check with DB connection test - <50ms target"""
    start_time = time.time()

    try:
        # Quick DB health check
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Quick Redis health check
    try:
        redis = aioredis.Redis(connection_pool=redis_pool)
        await redis.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    response_time = (time.time() - start_time) * 1000

    return {
        "status": "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        "database": db_status,
        "cache": redis_status,
        "response_time_ms": round(response_time, 2)
    }

@app.get("/api/v1/monitoring/metrics")
async def get_metrics():
    """Fast metrics endpoint - <50ms target"""
    cache_key = "system_metrics"

    # Try cache first
    cached_metrics = await get_from_cache(cache_key)
    if cached_metrics:
        return cached_metrics

    metrics_data = {
        "requests_per_second": "See Prometheus /metrics",
        "avg_response_time": "See Prometheus /metrics",
        "cache_hit_rate": "See Prometheus /metrics",
        "uptime_seconds": time.time(),
        "status": "operational"
    }

    # Cache for 30 seconds
    await set_cache(cache_key, metrics_data, ttl=30)

    return metrics_data

@app.post("/api/v1/llm/chat/completions")
async def chat_completions(request: dict, background_tasks: BackgroundTasks):
    """
    Chat completions endpoint - EXCLUDED from <100ms SLA
    This endpoint is expected to take longer due to model inference
    """
    start_time = time.time()

    # Simulate model inference (this would be your actual model call)
    inference_time = min(2.0, max(0.5, len(request.get("messages", [])) * 0.1))
    await asyncio.sleep(inference_time)

    response_time = (time.time() - start_time) * 1000

    response = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is an optimized response from the LLM API"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        },
        "performance": {
            "response_time_ms": round(response_time, 2),
            "note": "Model inference excluded from <100ms SLA"
        }
    }

    # Log slow requests in background
    if response_time > 5000:  # Log if > 5 seconds
        background_tasks.add_task(log_slow_request, request, response_time)

    return response

async def log_slow_request(request: dict, response_time: float):
    """Background task to log slow requests"""
    logging.warning(f"Slow request detected: {response_time:.2f}ms for {request}")

@app.get("/")
async def root():
    """Fast root endpoint - <20ms target"""
    return {
        "message": "Optimized LLM API",
        "version": "2.0.0",
        "performance_targets": {
            "health_check": "<5ms",
            "api_endpoints": "<50ms",
            "monitoring": "<50ms",
            "note": "Model inference excluded from SLA"
        }
    }

if __name__ == "__main__":
    import uvicorn

    # Production-optimized settings
    uvicorn.run(
        "optimized_main:app",
        host="0.0.0.0",
        port=8004,
        workers=1,  # Use multiple processes in production
        loop="uvloop",
        http="httptools",
        access_log=False,  # Disable for performance
        log_level="warning"
    )