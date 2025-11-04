"""
Structured logging system for LLM Platform
"""

import json
import logging
import time
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from contextvars import ContextVar
import sys
import os

# Context variables for request tracing
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


class LogLevel(Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEventType(Enum):
    """Types of log events"""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    SYSTEM = "system"
    AUDIT = "audit"


@dataclass
class LogContext:
    """Log context information"""
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    component: Optional[str] = None
    service: Optional[str] = None
    version: Optional[str] = None


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    level: str
    message: str
    event_type: str
    context: LogContext
    metadata: Dict[str, Any]
    exception: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        # Remove None values for cleaner output
        result = {k: v for k, v in result.items() if v is not None}
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class StructuredLogger:
    """Structured logger with context management"""
    
    def __init__(self, name: str, service: str = "llm-platform", version: str = "1.0.0"):
        self.name = name
        self.service = service
        self.version = version
        self.logger = logging.getLogger(name)
        
        # Set up structured logging formatter
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _create_log_entry(self, 
                         level: LogLevel, 
                         message: str, 
                         event_type: LogEventType,
                         extra: Optional[Dict[str, Any]] = None,
                         exception: Optional[Exception] = None) -> LogEntry:
        """Create structured log entry"""
        
        # Get context from context variables
        context = LogContext(
            request_id=request_id_var.get(),
            trace_id=trace_id_var.get(),
            user_id=user_id_var.get(),
            component=self.name,
            service=self.service,
            version=self.version
        )
        
        # Prepare metadata
        metadata = {
            "hostname": os.getenv("HOSTNAME", "unknown"),
            "pid": os.getpid(),
            "thread_id": threading.get_ident() if 'threading' in sys.modules else None,
        }
        
        if extra:
            metadata.update(extra)
        
        # Handle exception
        exception_data = None
        if exception:
            exception_data = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": traceback.format_exc()
            }
        
        return LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level.value,
            message=message,
            event_type=event_type.value,
            context=context,
            metadata=metadata,
            exception=exception_data
        )
    
    def debug(self, message: str, event_type: LogEventType = LogEventType.SYSTEM, **kwargs):
        """Log debug message"""
        entry = self._create_log_entry(LogLevel.DEBUG, message, event_type, kwargs)
        self.logger.debug(entry.to_json())
    
    def info(self, message: str, event_type: LogEventType = LogEventType.SYSTEM, **kwargs):
        """Log info message"""
        entry = self._create_log_entry(LogLevel.INFO, message, event_type, kwargs)
        self.logger.info(entry.to_json())
    
    def warning(self, message: str, event_type: LogEventType = LogEventType.SYSTEM, **kwargs):
        """Log warning message"""
        entry = self._create_log_entry(LogLevel.WARNING, message, event_type, kwargs)
        self.logger.warning(entry.to_json())
    
    def error(self, message: str, event_type: LogEventType = LogEventType.ERROR, 
              exception: Optional[Exception] = None, **kwargs):
        """Log error message"""
        entry = self._create_log_entry(LogLevel.ERROR, message, event_type, kwargs, exception)
        self.logger.error(entry.to_json())
    
    def critical(self, message: str, event_type: LogEventType = LogEventType.ERROR,
                exception: Optional[Exception] = None, **kwargs):
        """Log critical message"""
        entry = self._create_log_entry(LogLevel.CRITICAL, message, event_type, kwargs, exception)
        self.logger.critical(entry.to_json())
    
    def log_request(self, method: str, path: str, status_code: Optional[int] = None, 
                   duration: Optional[float] = None, **kwargs):
        """Log HTTP request"""
        message = f"{method} {path}"
        if status_code:
            message += f" -> {status_code}"
        if duration:
            message += f" ({duration:.3f}s)"
        
        self.info(message, LogEventType.REQUEST, 
                 method=method, path=path, status_code=status_code, 
                 duration=duration, **kwargs)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        self.info(f"Performance: {operation} took {duration:.3f}s", 
                 LogEventType.PERFORMANCE, operation=operation, 
                 duration=duration, **kwargs)
    
    def log_security_event(self, event: str, severity: str = "medium", **kwargs):
        """Log security event"""
        self.warning(f"Security event: {event}", LogEventType.SECURITY,
                    security_event=event, severity=severity, **kwargs)
    
    def log_business_event(self, event: str, **kwargs):
        """Log business event"""
        self.info(f"Business event: {event}", LogEventType.BUSINESS,
                 business_event=event, **kwargs)
    
    def log_audit_event(self, action: str, resource: str, **kwargs):
        """Log audit event"""
        self.info(f"Audit: {action} on {resource}", LogEventType.AUDIT,
                 action=action, resource=resource, **kwargs)


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # If the message is already JSON, return as-is
        if isinstance(record.msg, str) and record.msg.startswith('{'):
            return record.msg
        
        # Otherwise, create basic structured format
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data, default=str)


class RequestContextMiddleware:
    """Middleware to manage request context"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request with context"""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        # Set trace ID if provided
        trace_id = request.headers.get('X-Trace-ID') or str(uuid.uuid4())
        trace_id_var.set(trace_id)
        
        # Set user ID if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id_var.set(str(request.user.id))
        
        # Add to request for downstream use
        request.request_id = request_id
        request.trace_id = trace_id
        
        response = self.get_response(request)
        
        # Add trace headers to response
        response['X-Request-ID'] = request_id
        response['X-Trace-ID'] = trace_id
        
        return response


class LogAggregator:
    """Aggregate and forward logs to external systems"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.buffer = []
        self.buffer_size = config.get('buffer_size', 100)
        self.flush_interval = config.get('flush_interval', 30)
        self.enabled = config.get('enabled', True)
        
        if self.enabled:
            # Start background task to flush logs
            asyncio.create_task(self._flush_periodically())
    
    async def add_log(self, log_entry: LogEntry):
        """Add log entry to buffer"""
        if not self.enabled:
            return
        
        self.buffer.append(log_entry)
        
        if len(self.buffer) >= self.buffer_size:
            await self._flush_logs()
    
    async def _flush_logs(self):
        """Flush logs to external systems"""
        if not self.buffer:
            return
        
        logs_to_send = self.buffer.copy()
        self.buffer.clear()
        
        # Send to configured destinations
        tasks = []
        
        if self.config.get('elasticsearch'):
            tasks.append(self._send_to_elasticsearch(logs_to_send))
        
        if self.config.get('kafka'):
            tasks.append(self._send_to_kafka(logs_to_send))
        
        if self.config.get('webhook'):
            tasks.append(self._send_to_webhook(logs_to_send))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _flush_periodically(self):
        """Periodically flush logs"""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_logs()
    
    async def _send_to_elasticsearch(self, logs: list):
        """Send logs to Elasticsearch"""
        # Implementation would depend on elasticsearch-py library
        pass
    
    async def _send_to_kafka(self, logs: list):
        """Send logs to Kafka"""
        # Implementation would depend on kafka-python library
        pass
    
    async def _send_to_webhook(self, logs: list):
        """Send logs to webhook"""
        import aiohttp
        
        webhook_url = self.config['webhook']['url']
        
        async with aiohttp.ClientSession() as session:
            try:
                payload = [log.to_dict() for log in logs]
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 200:
                        print(f"Failed to send logs to webhook: {response.status}")
            except Exception as e:
                print(f"Error sending logs to webhook: {e}")


class MetricsLogger:
    """Logger specifically for metrics and telemetry"""
    
    def __init__(self, name: str):
        self.logger = StructuredLogger(name)
    
    def counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Log counter metric"""
        self.logger.info(f"Counter: {name} = {value}", LogEventType.PERFORMANCE,
                        metric_type="counter", metric_name=name, metric_value=value, tags=tags)
    
    def gauge(self, name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """Log gauge metric"""
        self.logger.info(f"Gauge: {name} = {value}", LogEventType.PERFORMANCE,
                        metric_type="gauge", metric_name=name, metric_value=value, tags=tags)
    
    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Log histogram metric"""
        self.logger.info(f"Histogram: {name} = {value}", LogEventType.PERFORMANCE,
                        metric_type="histogram", metric_name=name, metric_value=value, tags=tags)
    
    def timing(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Log timing metric"""
        self.logger.info(f"Timing: {name} = {duration}ms", LogEventType.PERFORMANCE,
                        metric_type="timing", metric_name=name, metric_value=duration, tags=tags)


# Convenience functions and decorators
def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)


def log_execution_time(operation_name: str, logger: Optional[StructuredLogger] = None):
    """Decorator to log function execution time"""
    def decorator(func):
        def sync_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.log_performance(operation_name, duration, 
                                     function=func.__name__, success=True)
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Error in {operation_name}", exception=e,
                           function=func.__name__, duration=duration)
                raise
        
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.log_performance(operation_name, duration,
                                     function=func.__name__, success=True)
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Error in {operation_name}", exception=e,
                           function=func.__name__, duration=duration)
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global logger instances
system_logger = get_logger("system")
api_logger = get_logger("api")
ml_logger = get_logger("ml")
security_logger = get_logger("security")
metrics_logger = MetricsLogger("metrics")


# Example usage
if __name__ == "__main__":
    import threading
    
    # Example of structured logging
    logger = get_logger("example")
    
    # Set request context
    request_id_var.set("req-123")
    user_id_var.set("user-456")
    
    # Log various types of events
    logger.info("Application started", LogEventType.SYSTEM, version="1.0.0")
    
    logger.log_request("GET", "/api/v1/models", 200, 0.045)
    
    logger.log_performance("model_inference", 1.234, model="gpt-3.5-turbo", tokens=150)
    
    logger.log_security_event("failed_login", severity="high", 
                             ip_address="192.168.1.100", username="admin")
    
    logger.log_business_event("subscription_created", plan="premium", 
                             user_id="user-456", amount=29.99)
    
    # Example with decorator
    @log_execution_time("database_query")
    def slow_database_query():
        time.sleep(0.1)  # Simulate slow query
        return "result"
    
    result = slow_database_query()
    
    # Example error logging
    try:
        raise ValueError("Something went wrong")
    except Exception as e:
        logger.error("Operation failed", exception=e, operation="test_operation")
    
    print("Structured logging examples completed")