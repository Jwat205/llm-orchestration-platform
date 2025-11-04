
# fastapi-service/app/services/model_router.py
import heapq
import random
from typing import Dict, Any, Optional
import structlog
from app.core.model_registry import ModelRegistry
from shared.schemas.models import ModelRequest

class ModelRouter:
    def __init__(self):
        self.registry = ModelRegistry()
        self.logger = structlog.get_logger()
        self._loads = {name: 0 for name in self.registry.list_models()}
        self._heap = [(0, name) for name in self._loads]
        heapq.heapify(self._heap)

    def select_model(self, capabilities: Dict[str, Any], ab_test: Optional[str] = None) -> Any:
        if ab_test:
            candidates = [n for n in self.registry.list_models() if ab_test in n]
        else:
            _, candidate = self._heap[0]
            candidates = [candidate]
        model_name = random.choice(candidates)
        return self.registry.get_model(model_name)

    def get_model_name(self, wrapper: Any) -> str:
        for name, w in self.registry.models.items():
            if w is wrapper:
                return name
        return "unknown"

    def route_request(self, request: ModelRequest) -> Dict[str, Any]:
        model_wrapper = self.select_model(request.capabilities or {}, request.ab_test)
        model_name = self.get_model_name(model_wrapper)
        self.balance_load(model_name)
        try:
            gen_kwargs = request.generation_config.dict() if request.generation_config else {}
            response = model_wrapper.generate(request.prompt, **gen_kwargs)
            metrics = self.registry.monitor_performance(model_name)
            return {"model": model_name, "response": response, "metrics": metrics}
        except Exception as e:
            self.logger.error("Inference failed", model=model_name, error=str(e))
            return self.handle_fallback(e, request)

    def balance_load(self, model_name: str) -> None:
        load = self._loads.get(model_name, 0) + 1
        self._loads[model_name] = load
        heapq.heappush(self._heap, (load, model_name))
        while self._heap and self._loads[self._heap[0][1]] != self._heap[0][0]:
            heapq.heappop(self._heap)
        self.logger.info("Load balanced", model=model_name, current_load=load)

    def handle_fallback(self, error: Exception, request: ModelRequest) -> Dict[str, Any]:
        available = list(self.registry.list_models().keys())
        failed = getattr(request, "model_used", None)
        candidates = [n for n in available if n != failed]
        if not candidates:
            return {"error": str(error)}
        alt_name = random.choice(candidates)
        alt_wrapper = self.registry.get_model(alt_name)
        try:
            gen_kwargs = request.generation_config.dict() if request.generation_config else {}
            response = alt_wrapper.generate(request.prompt, **gen_kwargs)
            metrics = self.registry.monitor_performance(alt_name)
            return {"model": alt_name, "response": response, "metrics": metrics}
        except Exception as e2:
            self.logger.error("Fallback inference failed", model=alt_name, error=str(e2))
            return {"error": f"Primary error: {error}; Fallback error: {e2}"}