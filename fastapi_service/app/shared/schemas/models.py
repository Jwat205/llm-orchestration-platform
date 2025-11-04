# shared/schemas/models.py
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class GenerationConfig(BaseModel):
    max_new_tokens: int = 50
    temperature: float = 1.0
    top_k: int = 50
    top_p: float = 1.0
    do_sample: bool = False

class ModelRequest(BaseModel):
    prompt: str
    generation_config: Optional[GenerationConfig] = None
    capabilities: Optional[Dict[str, Any]] = None
    ab_test: Optional[str] = None

class ModelInfo(BaseModel):
    name: str
    version: str
    capabilities: List[str]
    loaded: bool

class ModelVersionInfo(BaseModel):
    name: str
    version: str
    path: str
    created_at: str

class ModelPerformanceData(BaseModel):
    latency_ms: float
    throughput: float
    memory_mb: float

class ResourceRequirements(BaseModel):
    gpu: Optional[int]
    cpu: Optional[int]
    memory_mb: Optional[int]