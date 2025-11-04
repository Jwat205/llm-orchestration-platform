# fastapi-service/app/services/function_service.py
import structlog
from cachetools import TTLCache
from app.core.function_engine import FunctionEngine, FunctionRegistry
from app.models.functions import FunctionDefinition, FunctionCall, FunctionResult

class FunctionService:
    def __init__(self):
        self.registry = FunctionRegistry()
        self.engine = FunctionEngine(self.registry)
        self.definitions: Dict[str, FunctionDefinition] = {}
        self.cache = TTLCache(maxsize=100, ttl=300)
        self.logger = structlog.get_logger()

    def register_function(self, definition: FunctionDefinition, func):
        self.definitions[definition.name] = definition
        self.registry.register(definition.name, func)

    def validate_and_execute(self, call: FunctionCall) -> FunctionResult:
        definition = self.definitions.get(call.name)
        if not definition:
            raise ValueError(f"Function '{call.name}' not registered")
        key = f"{call.name}:{tuple(call.parameters.items())}"
        if key in self.cache:
            return self.cache[key]
        try:
            result = self.engine.execute(call.name, call.parameters)
            fr = FunctionResult(name=call.name, result=result)
            self.cache[key] = fr
            return fr
        except Exception as e:
            self.logger.error("Function execution failed", name=call.name, error=str(e))
            return FunctionResult(name=call.name, result=None, error=str(e))

    def execute_parallel(self, parallel_calls: 'ParallelFunctionCalls') -> List[FunctionResult]:
        raw = self.engine.execute_parallel([c.dict() for c in parallel_calls.calls])
        return [FunctionResult(**r) for r in raw]