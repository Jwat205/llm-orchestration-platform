"""
Enhanced Pydantic models for API v2
Contains new request/response models with advanced features
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union, Literal
from datetime import datetime
from enum import Enum
import uuid


class LLMProvider(str, Enum):
    """Enhanced LLM providers in v2"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    GOOGLE = "google"
    COHERE = "cohere"


class MessageRole(str, Enum):
    """Enhanced message roles for v2"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class FunctionCall(BaseModel):
    """Function call definition"""
    name: str = Field(..., description="Function name")
    arguments: str = Field(..., description="Function arguments as JSON string")


class ToolCall(BaseModel):
    """Tool call definition for v2"""
    id: str = Field(..., description="Tool call ID")
    type: Literal["function"] = Field("function", description="Tool type")
    function: FunctionCall = Field(..., description="Function call details")


class EnhancedMessage(BaseModel):
    """Enhanced message model for v2"""
    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class Function(BaseModel):
    """Function definition for function calling"""
    name: str = Field(..., description="Function name")
    description: Optional[str] = Field(None, description="Function description")
    parameters: Dict[str, Any] = Field(..., description="Function parameters schema")


class Tool(BaseModel):
    """Tool definition for v2"""
    type: Literal["function"] = Field("function", description="Tool type")
    function: Function = Field(..., description="Function definition")


class ResponseFormat(BaseModel):
    """Response format specification"""
    type: Literal["text", "json_object"] = Field("text", description="Response format type")


class EnhancedChatRequest(BaseModel):
    """Enhanced chat completion request for v2"""
    messages: List[EnhancedMessage] = Field(..., description="Conversation messages")
    model: str = Field(..., description="Model to use")
    max_tokens: Optional[int] = Field(None, ge=1, le=8000, description="Maximum tokens")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Top-p sampling")
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop sequences")
    stream: Optional[bool] = Field(False, description="Stream response")
    provider: Optional[LLMProvider] = Field(LLMProvider.LOCAL, description="Provider")
    tools: Optional[List[Tool]] = Field(None, description="Available tools")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool choice")
    response_format: Optional[ResponseFormat] = Field(None, description="Response format")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="Logit bias")
    user: Optional[str] = Field(None, description="User ID for tracking")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Request metadata")


class BatchRequest(BaseModel):
    """Batch processing request"""
    requests: List[Dict[str, Any]] = Field(..., description="List of requests to process")
    batch_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Batch ID")
    priority: Optional[int] = Field(1, ge=1, le=10, description="Batch priority")
    timeout: Optional[int] = Field(300, ge=1, le=3600, description="Batch timeout in seconds")
    parallel_processing: Optional[bool] = Field(True, description="Enable parallel processing")
    callback_url: Optional[str] = Field(None, description="Callback URL for completion notification")


class BatchStatus(str, Enum):
    """Batch processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchResponse(BaseModel):
    """Batch processing response"""
    batch_id: str = Field(..., description="Batch ID")
    status: BatchStatus = Field(..., description="Batch status")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    total_requests: int = Field(..., description="Total number of requests")
    completed_requests: int = Field(0, description="Number of completed requests")
    failed_requests: int = Field(0, description="Number of failed requests")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="Batch results")
    errors: Optional[List[str]] = Field(None, description="Error messages")
    progress: float = Field(0.0, description="Progress percentage")


class AnalyticsRequest(BaseModel):
    """Analytics query request"""
    metrics: List[str] = Field(..., description="Metrics to retrieve")
    start_date: datetime = Field(..., description="Start date for analytics")
    end_date: datetime = Field(..., description="End date for analytics")
    granularity: Literal["hour", "day", "week", "month"] = Field("day", description="Data granularity")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    group_by: Optional[List[str]] = Field(None, description="Group by fields")


class MetricPoint(BaseModel):
    """Single metric data point"""
    timestamp: datetime = Field(..., description="Data point timestamp")
    metric: str = Field(..., description="Metric name")
    value: Union[int, float] = Field(..., description="Metric value")
    dimensions: Optional[Dict[str, str]] = Field(None, description="Metric dimensions")


class AnalyticsResponse(BaseModel):
    """Analytics query response"""
    metrics: List[str] = Field(..., description="Queried metrics")
    data_points: List[MetricPoint] = Field(..., description="Metric data points")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    period: Dict[str, datetime] = Field(..., description="Query period")
    total_data_points: int = Field(..., description="Total data points")


class EnhancedUsage(BaseModel):
    """Enhanced usage information for v2"""
    prompt_tokens: int = Field(..., description="Prompt tokens")
    completion_tokens: int = Field(..., description="Completion tokens")
    total_tokens: int = Field(..., description="Total tokens")
    cost: Optional[float] = Field(None, description="Estimated cost")
    processing_time_ms: Optional[float] = Field(None, description="Processing time")
    cache_hit: Optional[bool] = Field(None, description="Whether response was cached")


class EnhancedChatChoice(BaseModel):
    """Enhanced chat choice for v2"""
    index: int = Field(..., description="Choice index")
    message: EnhancedMessage = Field(..., description="Generated message")
    finish_reason: Optional[str] = Field(None, description="Finish reason")
    logprobs: Optional[Dict[str, Any]] = Field(None, description="Log probabilities")


class EnhancedChatResponse(BaseModel):
    """Enhanced chat completion response for v2"""
    id: str = Field(..., description="Completion ID")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: List[EnhancedChatChoice] = Field(..., description="Generated choices")
    usage: EnhancedUsage = Field(..., description="Enhanced usage information")
    provider: str = Field(..., description="Provider used")
    system_fingerprint: Optional[str] = Field(None, description="System fingerprint")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")


class ModelCapability(str, Enum):
    """Model capabilities"""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"


class EnhancedModelInfo(BaseModel):
    """Enhanced model information for v2"""
    id: str = Field(..., description="Model ID")
    object: str = Field("model", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    owned_by: str = Field(..., description="Model owner")
    provider: str = Field(..., description="Provider")
    capabilities: List[ModelCapability] = Field(..., description="Model capabilities")
    context_length: Optional[int] = Field(None, description="Context length")
    max_output_tokens: Optional[int] = Field(None, description="Max output tokens")
    description: Optional[str] = Field(None, description="Model description")
    pricing: Optional[Dict[str, float]] = Field(None, description="Pricing information")
    performance_metrics: Optional[Dict[str, float]] = Field(None, description="Performance metrics")
    supported_languages: Optional[List[str]] = Field(None, description="Supported languages")
    version: Optional[str] = Field(None, description="Model version")
    status: Optional[str] = Field(None, description="Model status")


class MonitoringAlert(BaseModel):
    """Monitoring alert definition"""
    alert_id: str = Field(..., description="Alert ID")
    name: str = Field(..., description="Alert name")
    description: str = Field(..., description="Alert description")
    condition: str = Field(..., description="Alert condition")
    threshold: Union[int, float] = Field(..., description="Alert threshold")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Alert severity")
    enabled: bool = Field(True, description="Whether alert is enabled")
    notification_channels: List[str] = Field(..., description="Notification channels")


class SystemHealth(BaseModel):
    """Enhanced system health for v2"""
    overall_status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    services: List[Dict[str, Any]] = Field(..., description="Service health details")
    performance_metrics: Dict[str, float] = Field(..., description="Performance metrics")
    resource_usage: Dict[str, float] = Field(..., description="Resource usage")
    alerts: List[MonitoringAlert] = Field(..., description="Active alerts")
    uptime_seconds: float = Field(..., description="System uptime")
    version: str = Field(..., description="API version")


class WebhookEvent(BaseModel):
    """Webhook event for v2"""
    event_id: str = Field(..., description="Event ID")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Event data")
    source: str = Field(..., description="Event source")
    version: str = Field("2.0", description="Event version")


class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    requests_per_minute: int = Field(..., description="Requests per minute")
    tokens_per_minute: int = Field(..., description="Tokens per minute")
    concurrent_requests: int = Field(..., description="Concurrent requests limit")
    burst_allowance: int = Field(..., description="Burst allowance")
    window_size_seconds: int = Field(60, description="Rate limit window size")


class EnhancedErrorResponse(BaseModel):
    """Enhanced error response for v2"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    code: int = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: str = Field(..., description="Request ID")
    documentation_url: Optional[str] = Field(None, description="Documentation URL")
    suggested_action: Optional[str] = Field(None, description="Suggested action")
    retry_after: Optional[int] = Field(None, description="Retry after seconds")