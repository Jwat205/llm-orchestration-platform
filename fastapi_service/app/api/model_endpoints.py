# fastapi-service/app/api/model_endpoints.py
from fastapi import APIRouter, HTTPException, Response, Depends
from typing import Dict, Any, List, Optional
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from app.core.model_registry import ModelRegistry
from app.services.model_router import ModelRouter
from shared.schemas.models import ModelRequest, ResourceRequirements

router = APIRouter()
registry = ModelRegistry()
router_service = ModelRouter()

# Prometheus metrics
inference_counter = Counter('inference_requests_total', 'Total inference requests', ['model'])
inference_latency = Gauge('inference_latency_ms', 'Inference latency in ms', ['model'])
model_load_counter = Counter('model_loads_total', 'Total model loads', ['model'])
model_unload_counter = Counter('model_unloads_total', 'Total model unloads', ['model'])
benchmark_counter = Counter('model_benchmarks_total', 'Total benchmarks run', ['model'])

@router.post('/models/load')
def load_model(name: str, repo_id: str, version: Optional[str] = None,
               quant_bits: Optional[int] = None, max_memory: Optional[Dict[str,str]] = None):
    try:
        registry.load_model(name, repo_id, version=version,
                            quant_bits=quant_bits, max_memory=max_memory)
        model_load_counter.labels(model=name).inc()
        return {'status': 'loaded', 'name': name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/models/unload')
def unload_model(name: str):
    try:
        registry.unload_model(name)
        model_unload_counter.labels(model=name).inc()
        return {'status': 'unloaded', 'name': name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/models/rollback')
def rollback_model(name: str, target_version: str):
    try:
        registry.rollback(name, target_version)
        return {'status': 'rolled_back', 'name': name, 'to': target_version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/models/hot-swap')
def hot_swap_model(name: str, repo_id: str, version: str, quant_bits: Optional[int] = None,
                   max_memory: Optional[Dict[str,str]] = None):
    try:
        registry.hot_swap(name, repo_id, version,
                          quant_bits=quant_bits, max_memory=max_memory)
        return {'status': 'hot_swapped', 'name': name, 'to': version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/models/benchmark')
def benchmark_model(name: str, prompts: List[str],
                    generation_config: Optional[Dict[str,Any]] = None):
    try:
        metrics = registry.benchmark_model(name, prompts, **(generation_config or {}))
        benchmark_counter.labels(model=name).inc()
        return {'status': 'benchmarked', 'name': name, 'metrics': metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/v1/chat/completions')
def chat_completions(request: ModelRequest):
    # Allocate resources based on config and capabilities
    req = request.dict()
    if request.generation_config:
        registry.allocate_resources(request.prompt, **request.generation_config.dict())
    result = router_service.route_request(request)
    inference_counter.labels(model=result['model']).inc()
    inference_latency.labels(model=result['model']).set(result['metrics'].get('latency_ms', 0))
    return result

@router.get('/metrics')
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
