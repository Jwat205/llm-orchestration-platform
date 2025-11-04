"""
Distributed tracing system for LLM Platform
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from contextvars import ContextVar
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Context variables for tracing
current_trace: ContextVar[Optional['Trace']] = ContextVar('current_trace', default=None)
current_span: ContextVar[Optional['Span']] = ContextVar('current_span', default=None)


class SpanKind(Enum):
    """Types of spans"""
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


class SpanStatus(Enum):
    """Span status"""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SpanContext:
    """Span context for propagation"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = None
    
    def __post_init__(self):
        if self.baggage is None:
            self.baggage = {}


@dataclass
class SpanEvent:
    """Event within a span"""
    timestamp: float
    name: str
    attributes: Dict[str, Any]


@dataclass
class SpanLog:
    """Log entry within a span"""
    timestamp: float
    level: str
    message: str
    attributes: Dict[str, Any]


class Span:
    """Distributed tracing span"""
    
    def __init__(self, 
                 operation_name: str,
                 context: SpanContext,
                 kind: SpanKind = SpanKind.INTERNAL,
                 tags: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.context = context
        self.kind = kind
        self.tags = tags or {}
        self.status = SpanStatus.OK
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None
        self.events: List[SpanEvent] = []
        self.logs: List[SpanLog] = []
        self.error: Optional[Exception] = None
        self.finished = False
    
    def set_tag(self, key: str, value: Any) -> 'Span':
        """Set span tag"""
        self.tags[key] = value
        return self
    
    def set_baggage(self, key: str, value: str) -> 'Span':
        """Set baggage item"""
        self.context.baggage[key] = value
        return self
    
    def get_baggage(self, key: str) -> Optional[str]:
        """Get baggage item"""
        return self.context.baggage.get(key)
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> 'Span':
        """Add event to span"""
        event = SpanEvent(
            timestamp=time.time(),
            name=name,
            attributes=attributes or {}
        )
        self.events.append(event)
        return self
    
    def log(self, level: str, message: str, attributes: Optional[Dict[str, Any]] = None) -> 'Span':
        """Add log entry to span"""
        log_entry = SpanLog(
            timestamp=time.time(),
            level=level,
            message=message,
            attributes=attributes or {}
        )
        self.logs.append(log_entry)
        return self
    
    def log_exception(self, exception: Exception) -> 'Span':
        """Log exception to span"""
        self.error = exception
        self.status = SpanStatus.ERROR
        self.set_tag("error", True)
        self.set_tag("error.type", type(exception).__name__)
        self.set_tag("error.message", str(exception))
        
        import traceback
        self.log("error", f"Exception occurred: {exception}", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
            "exception.traceback": traceback.format_exc()
        })
        return self
    
    def finish(self, end_time: Optional[float] = None) -> 'Span':
        """Finish the span"""
        if self.finished:
            return self
        
        self.end_time = end_time or time.time()
        self.duration = self.end_time - self.start_time
        self.finished = True
        
        # Notify tracer
        tracer = get_current_tracer()
        if tracer:
            tracer._finish_span(self)
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary"""
        return {
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "operation_name": self.operation_name,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "tags": self.tags,
            "baggage": self.context.baggage,
            "events": [asdict(event) for event in self.events],
            "logs": [asdict(log) for log in self.logs],
            "error": str(self.error) if self.error else None
        }
    
    def __enter__(self) -> 'Span':
        """Context manager entry"""
        current_span.set(self)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_val:
            self.log_exception(exc_val)
        self.finish()
        current_span.set(None)


class Trace:
    """Distributed trace containing multiple spans"""
    
    def __init__(self, trace_id: Optional[str] = None, operation_name: str = "root"):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.operation_name = operation_name
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.spans: Dict[str, Span] = {}
        self.root_span: Optional[Span] = None
        self.finished = False
    
    def create_span(self, 
                   operation_name: str,
                   parent_span: Optional[Span] = None,
                   kind: SpanKind = SpanKind.INTERNAL,
                   tags: Optional[Dict[str, Any]] = None) -> Span:
        """Create new span in this trace"""
        
        if parent_span is None:
            parent_span = current_span.get()
        
        span_id = str(uuid.uuid4())
        parent_span_id = parent_span.context.span_id if parent_span else None
        
        context = SpanContext(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            baggage=parent_span.context.baggage.copy() if parent_span else {}
        )
        
        span = Span(operation_name, context, kind, tags)
        self.spans[span_id] = span
        
        if self.root_span is None:
            self.root_span = span
        
        return span
    
    def get_span(self, span_id: str) -> Optional[Span]:
        """Get span by ID"""
        return self.spans.get(span_id)
    
    def finish(self) -> 'Trace':
        """Finish the trace"""
        if self.finished:
            return self
        
        self.end_time = time.time()
        self.finished = True
        
        # Finish any unfinished spans
        for span in self.spans.values():
            if not span.finished:
                span.finish()
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary"""
        return {
            "trace_id": self.trace_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time - self.start_time) if self.end_time else None,
            "spans": [span.to_dict() for span in self.spans.values()]
        }


class TracingBackend:
    """Abstract tracing backend"""
    
    async def send_spans(self, spans: List[Span]):
        """Send spans to backend"""
        raise NotImplementedError
    
    async def send_trace(self, trace: Trace):
        """Send complete trace to backend"""
        raise NotImplementedError


class JaegerBackend(TracingBackend):
    """Jaeger tracing backend"""
    
    def __init__(self, endpoint: str, service_name: str):
        self.endpoint = endpoint
        self.service_name = service_name
    
    async def send_spans(self, spans: List[Span]):
        """Send spans to Jaeger"""
        import aiohttp
        
        jaeger_spans = []
        for span in spans:
            jaeger_span = {
                "traceID": span.context.trace_id.replace("-", ""),
                "spanID": span.context.span_id.replace("-", ""),
                "parentSpanID": span.context.parent_span_id.replace("-", "") if span.context.parent_span_id else "",
                "operationName": span.operation_name,
                "startTime": int(span.start_time * 1_000_000),  # microseconds
                "duration": int((span.duration or 0) * 1_000_000),
                "tags": [{"key": k, "value": str(v)} for k, v in span.tags.items()],
                "logs": [
                    {
                        "timestamp": int(log.timestamp * 1_000_000),
                        "fields": [
                            {"key": "level", "value": log.level},
                            {"key": "message", "value": log.message},
                            *[{"key": k, "value": str(v)} for k, v in log.attributes.items()]
                        ]
                    } for log in span.logs
                ],
                "process": {
                    "serviceName": self.service_name,
                    "tags": []
                }
            }
            jaeger_spans.append(jaeger_span)
        
        payload = {"spans": jaeger_spans}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.endpoint}/api/traces", json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send spans to Jaeger: {response.status}")
        except Exception as e:
            logger.error(f"Error sending spans to Jaeger: {e}")


class ZipkinBackend(TracingBackend):
    """Zipkin tracing backend"""
    
    def __init__(self, endpoint: str, service_name: str):
        self.endpoint = endpoint
        self.service_name = service_name
    
    async def send_spans(self, spans: List[Span]):
        """Send spans to Zipkin"""
        import aiohttp
        
        zipkin_spans = []
        for span in spans:
            zipkin_span = {
                "traceId": span.context.trace_id.replace("-", ""),
                "id": span.context.span_id.replace("-", ""),
                "parentId": span.context.parent_span_id.replace("-", "") if span.context.parent_span_id else None,
                "name": span.operation_name,
                "timestamp": int(span.start_time * 1_000_000),
                "duration": int((span.duration or 0) * 1_000_000),
                "kind": span.kind.value.upper(),
                "localEndpoint": {"serviceName": self.service_name},
                "tags": {k: str(v) for k, v in span.tags.items()}
            }
            
            if span.context.parent_span_id:
                zipkin_span["parentId"] = span.context.parent_span_id.replace("-", "")
            
            zipkin_spans.append(zipkin_span)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.endpoint}/api/v2/spans", json=zipkin_spans) as response:
                    if response.status != 202:
                        logger.error(f"Failed to send spans to Zipkin: {response.status}")
        except Exception as e:
            logger.error(f"Error sending spans to Zipkin: {e}")


class Tracer:
    """Distributed tracer"""
    
    def __init__(self, service_name: str, backend: Optional[TracingBackend] = None):
        self.service_name = service_name
        self.backend = backend
        self.active_traces: Dict[str, Trace] = {}
        self.finished_spans: List[Span] = []
        self.batch_size = 100
        self.flush_interval = 30
        
        # Start background task to flush spans
        if self.backend:
            asyncio.create_task(self._flush_periodically())
    
    def start_trace(self, operation_name: str, trace_id: Optional[str] = None) -> Trace:
        """Start new trace"""
        trace = Trace(trace_id, operation_name)
        self.active_traces[trace.trace_id] = trace
        current_trace.set(trace)
        return trace
    
    def start_span(self, 
                  operation_name: str,
                  parent_span: Optional[Span] = None,
                  kind: SpanKind = SpanKind.INTERNAL,
                  tags: Optional[Dict[str, Any]] = None) -> Span:
        """Start new span"""
        
        # Get current trace or create new one
        trace = current_trace.get()
        if trace is None:
            trace = self.start_trace(operation_name)
        
        span = trace.create_span(operation_name, parent_span, kind, tags)
        current_span.set(span)
        return span
    
    def finish_trace(self, trace_id: str):
        """Finish trace"""
        trace = self.active_traces.pop(trace_id, None)
        if trace:
            trace.finish()
            if self.backend:
                asyncio.create_task(self.backend.send_trace(trace))
    
    def _finish_span(self, span: Span):
        """Called when span is finished"""
        self.finished_spans.append(span)
        
        if len(self.finished_spans) >= self.batch_size:
            asyncio.create_task(self._flush_spans())
    
    async def _flush_spans(self):
        """Flush spans to backend"""
        if not self.backend or not self.finished_spans:
            return
        
        spans_to_send = self.finished_spans.copy()
        self.finished_spans.clear()
        
        await self.backend.send_spans(spans_to_send)
    
    async def _flush_periodically(self):
        """Periodically flush spans"""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_spans()
    
    def extract_context(self, headers: Dict[str, str]) -> Optional[SpanContext]:
        """Extract span context from headers"""
        trace_id = headers.get('X-Trace-ID')
        span_id = headers.get('X-Span-ID')
        parent_span_id = headers.get('X-Parent-Span-ID')
        
        if trace_id and span_id:
            return SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id
            )
        
        return None
    
    def inject_context(self, span: Span, headers: Dict[str, str]):
        """Inject span context into headers"""
        headers['X-Trace-ID'] = span.context.trace_id
        headers['X-Span-ID'] = span.context.span_id
        if span.context.parent_span_id:
            headers['X-Parent-Span-ID'] = span.context.parent_span_id
        
        # Inject baggage
        for key, value in span.context.baggage.items():
            headers[f'X-Baggage-{key}'] = value


# Global tracer instance
_current_tracer: Optional[Tracer] = None


def initialize_tracer(service_name: str, backend: Optional[TracingBackend] = None):
    """Initialize global tracer"""
    global _current_tracer
    _current_tracer = Tracer(service_name, backend)


def get_current_tracer() -> Optional[Tracer]:
    """Get current tracer"""
    return _current_tracer


def start_span(operation_name: str, 
               kind: SpanKind = SpanKind.INTERNAL,
               tags: Optional[Dict[str, Any]] = None) -> Optional[Span]:
    """Start new span using global tracer"""
    tracer = get_current_tracer()
    if tracer:
        return tracer.start_span(operation_name, kind=kind, tags=tags)
    return None


def trace_function(operation_name: Optional[str] = None, 
                  kind: SpanKind = SpanKind.INTERNAL,
                  tags: Optional[Dict[str, Any]] = None):
    """Decorator to trace function execution"""
    def decorator(func: Callable):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        def sync_wrapper(*args, **kwargs):
            span = start_span(operation_name, kind, tags)
            if span:
                with span:
                    span.set_tag("function.name", func.__name__)
                    span.set_tag("function.module", func.__module__)
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        async def async_wrapper(*args, **kwargs):
            span = start_span(operation_name, kind, tags)
            if span:
                with span:
                    span.set_tag("function.name", func.__name__)
                    span.set_tag("function.module", func.__module__)
                    return await func(*args, **kwargs)
            else:
                return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Middleware for FastAPI/Django
class TracingMiddleware:
    """Middleware for automatic request tracing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request with tracing"""
        tracer = get_current_tracer()
        if not tracer:
            return self.get_response(request)
        
        # Extract context from headers
        context = tracer.extract_context(dict(request.headers))
        
        # Start request span
        with tracer.start_span(
            f"{request.method} {request.path}",
            kind=SpanKind.SERVER,
            tags={
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "http.scheme": request.scheme,
                "http.host": request.get_host(),
                "http.target": request.get_full_path(),
                "user_agent": request.headers.get('User-Agent', ''),
            }
        ) as span:
            
            # Process request
            response = self.get_response(request)
            
            # Add response tags
            span.set_tag("http.status_code", response.status_code)
            span.set_tag("http.response_size", len(response.content) if hasattr(response, 'content') else 0)
            
            # Inject context into response headers
            response_headers = {}
            tracer.inject_context(span, response_headers)
            for key, value in response_headers.items():
                response[key] = value
            
            return response


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize tracer with Jaeger backend
        jaeger_backend = JaegerBackend("http://localhost:14268", "llm-platform")
        initialize_tracer("llm-platform", jaeger_backend)
        
        tracer = get_current_tracer()
        
        # Start trace
        trace = tracer.start_trace("example_operation")
        
        # Create spans
        with tracer.start_span("database_query", kind=SpanKind.CLIENT) as db_span:
            db_span.set_tag("db.statement", "SELECT * FROM users")
            db_span.set_tag("db.type", "postgresql")
            db_span.add_event("query_started")
            
            # Simulate database work
            await asyncio.sleep(0.1)
            
            db_span.add_event("query_completed", {"rows_returned": 5})
        
        with tracer.start_span("model_inference", kind=SpanKind.INTERNAL) as ml_span:
            ml_span.set_tag("model.name", "gpt-3.5-turbo")
            ml_span.set_tag("model.version", "1.0")
            ml_span.set_baggage("user_id", "12345")
            
            # Simulate ML inference
            await asyncio.sleep(0.5)
            
            ml_span.set_tag("tokens.input", 100)
            ml_span.set_tag("tokens.output", 50)
        
        # Example with decorator
        @trace_function("external_api_call", SpanKind.CLIENT, {"service": "openai"})
        async def call_external_api():
            await asyncio.sleep(0.2)
            return {"status": "success"}
        
        result = await call_external_api()
        
        # Finish trace
        tracer.finish_trace(trace.trace_id)
        
        print("Tracing example completed")
        
        # Wait for spans to be sent
        await asyncio.sleep(1)
    
    asyncio.run(main())