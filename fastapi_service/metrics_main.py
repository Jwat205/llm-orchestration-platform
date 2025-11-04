"""
FastAPI with Prometheus Metrics Integration
This adds /metrics endpoint to track all performance claims
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from metrics import (
    track_metrics,
    track_cache_hit,
    track_cache_miss,
    get_metrics_response,
    get_performance_summary
)
import asyncio
import random

app = FastAPI(title="LLM API with Metrics", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return get_metrics_response()

@app.get("/health")
@track_metrics(endpoint_type="api")
async def health():
    """Health check with metrics tracking"""
    return {"status": "healthy", "service": "fastapi-with-metrics"}

@app.get("/api/v1/llm/models")
@track_metrics(endpoint_type="cached")
async def get_models():
    """Models endpoint with cache simulation"""
    # Simulate cache behavior
    if random.random() < 0.7:  # 70% cache hit rate
        track_cache_hit()
        await asyncio.sleep(0.01)  # Fast cached response
    else:
        track_cache_miss()
        await asyncio.sleep(0.05)  # Slower uncached response

    return {
        "object": "list",
        "data": [
            {"id": "gpt2", "object": "model", "description": "GPT-2 model"},
            {"id": "gpt2-medium", "object": "model", "description": "GPT-2 Medium model"},
            {"id": "distilgpt2", "object": "model", "description": "DistilGPT-2 model"}
        ]
    }

@app.post("/api/v1/llm/chat/completions")
@track_metrics(endpoint_type="model")
async def chat_completions(request: dict):
    """Chat completions with metrics"""
    # Simulate model inference time
    await asyncio.sleep(random.uniform(0.5, 2.0))

    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a test response from the metrics-enabled API"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}
    }

@app.get("/performance")
async def performance_summary():
    """Get performance summary for SLA monitoring"""
    return get_performance_summary()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "FastAPI with Prometheus Metrics",
        "metrics_endpoint": "/metrics",
        "performance_summary": "/performance",
        "health_check": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)