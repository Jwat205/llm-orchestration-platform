"""Standalone server for benchmarking — run by benchmark_local.py via subprocess."""
import os, sys, asyncio, json, time

os.environ["ENV"] = "development"
os.environ["DEBUG"] = "True"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

import fakeredis.aioredis as fake_aioredis
import fakeredis
import redis.asyncio as real_aioredis

_fake_server = fakeredis.FakeServer()
real_aioredis.from_url = lambda url, **kw: fake_aioredis.FakeRedis(
    server=_fake_server, decode_responses=True
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fastapi_service"))

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from app.services.cache_service import (
    get_cached_response, set_cached_response, close_redis
)
from app.api.dependencies import authenticate_user, check_rate_limit

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()

app = FastAPI(title="Benchmark Server", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/v1/chat/completions",
          dependencies=[Depends(authenticate_user), Depends(check_rate_limit)])
async def chat_completions(request: Request, user=Depends(authenticate_user)):
    body = await request.json()
    messages = body.get("messages", [])
    model    = body.get("model", "default")
    temp     = float(body.get("temperature", 1.0))
    max_tok  = int(body.get("max_tokens", 100))
    cached = await get_cached_response(model, messages, temp, max_tok)
    if cached:
        return JSONResponse(cached)
    response = {
        "id": f"chatcmpl-{int(time.time())}", "object": "chat.completion",
        "created": int(time.time()), "model": model,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": "Paris."},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    await set_cached_response(model, messages, temp, max_tok, response)
    return JSONResponse(response)

if __name__ == "__main__":
    import asyncio
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="127.0.0.1", port=18001,
                log_level="error", access_log=False)
