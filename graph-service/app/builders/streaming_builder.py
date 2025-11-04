"""
Streaming Graph Builder
Builds knowledge graphs from real-time streaming data with low latency and high throughput.
"""
import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator, Callable, Set
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from collections import defaultdict, deque
import uuid
from datetime import datetime, timedelta
try:
    import aioredis
    HAS_AIOREDIS = True
except ImportError:
    HAS_AIOREDIS = False
    aioredis = None
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class StreamStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

class StreamSourceType(Enum):
    KAFKA = "kafka"
    REDIS_STREAM = "redis_stream"
    WEBSOCKET = "websocket"
    HTTP_STREAM = "http_stream"
    FILE_WATCH = "file_watch"
    DATABASE_CDC = "database_cdc"

@dataclass
class StreamConfig:
    source_type: StreamSourceType
    connection_params: Dict[str, Any]
    batch_size: int = 100
    batch_timeout_ms: int = 1000
    max_concurrent_batches: int = 5
    enable_backpressure: bool = True
    backpressure_threshold: int = 1000
    enable_deduplication: bool = True
    dedup_window_seconds: int = 60
    enable_ordering: bool = False
    ordering_field: Optional[str] = None
    enable_filtering: bool = False
    filter_rules: List[Dict[str, Any]] = field(default_factory=list)
    enable_transformation: bool = False
    transformation_rules: List[Dict[str, Any]] = field(default_factory=list)
    error_handling: str = "skip"  # skip, retry, dead_letter
    max_retries: int = 3
    retry_delay_ms: int = 1000
    enable_metrics: bool = True
    checkpoint_interval_ms: int = 5000

@dataclass
class StreamMetrics:
    messages_received: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    messages_skipped: int = 0
    bytes_processed: int = 0
    processing_rate: float = 0.0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    backpressure_events: int = 0
    last_checkpoint: Optional[datetime] = None
    uptime_seconds: float = 0.0

@dataclass
class StreamMessage:
    message_id: str
    source: str
    timestamp: datetime
    data: Dict[str, Any]
    partition_key: Optional[str] = None
    headers: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    processing_start_time: Optional[datetime] = None

class StreamSource(ABC):
    """Abstract base class for stream sources"""
    
    @abstractmethod
    async def connect(self, config: StreamConfig) -> bool:
        pass
    
    @abstractmethod
    async def disconnect(self):
        pass
    
    @abstractmethod
    async def consume(self) -> AsyncIterator[StreamMessage]:
        pass
    
    @abstractmethod
    async def acknowledge(self, message_id: str):
        pass
    
    @abstractmethod
    async def reject(self, message_id: str):
        pass

class RedisStreamSource(StreamSource):
    """Redis Streams source implementation"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.stream_name: str = ""
        self.consumer_group: str = ""
        self.consumer_name: str = ""
    
    async def connect(self, config: StreamConfig) -> bool:
        try:
            if not HAS_AIOREDIS:
                logger.error("aioredis not available")
                return False
            
            params = config.connection_params
            self.redis = aioredis.from_url(
                params.get("url", "redis://localhost:6379"),
                decode_responses=True
            )
            
            self.stream_name = params.get("stream_name", "graph_stream")
            self.consumer_group = params.get("consumer_group", "graph_builders")
            self.consumer_name = params.get("consumer_name", f"builder_{uuid.uuid4().hex[:8]}")
            
            # Create consumer group if it doesn't exist
            try:
                await self.redis.xgroup_create(
                    self.stream_name,
                    self.consumer_group,
                    id="0",
                    mkstream=True
                )
            except aioredis.RedisError:
                pass  # Group might already exist
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to Redis: {e}")
            return False
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
    
    async def consume(self) -> AsyncIterator[StreamMessage]:
        try:
            while True:
                # Read from stream
                messages = await self.redis.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=1,
                    block=1000
                )
                
                for stream, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        # Parse message data
                        data = {}
                        for i in range(0, len(fields), 2):
                            key = fields[i]
                            value = fields[i + 1]
                            try:
                                data[key] = json.loads(value)
                            except json.JSONDecodeError:
                                data[key] = value
                        
                        yield StreamMessage(
                            message_id=message_id,
                            source=stream,
                            timestamp=datetime.now(),
                            data=data
                        )
                        
        except Exception as e:
            logger.error(f"Error consuming from Redis stream: {e}")
    
    async def acknowledge(self, message_id: str):
        try:
            await self.redis.xack(self.stream_name, self.consumer_group, message_id)
        except Exception as e:
            logger.error(f"Error acknowledging message: {e}")
    
    async def reject(self, message_id: str):
        # For Redis streams, we can add to a dead letter stream
        try:
            await self.redis.xadd(
                f"{self.stream_name}:dead_letter",
                {"original_id": message_id, "timestamp": time.time()}
            )
        except Exception as e:
            logger.error(f"Error rejecting message: {e}")

class KafkaStreamSource(StreamSource):
    """Kafka source implementation (placeholder)"""
    
    async def connect(self, config: StreamConfig) -> bool:
        # Would implement Kafka consumer using aiokafka or similar
        logger.warning("Kafka source not implemented")
        return False
    
    async def disconnect(self):
        pass
    
    async def consume(self) -> AsyncIterator[StreamMessage]:
        # Placeholder
        return
        yield  # Make it a generator
    
    async def acknowledge(self, message_id: str):
        pass
    
    async def reject(self, message_id: str):
        pass

class WebSocketStreamSource(StreamSource):
    """WebSocket source implementation (placeholder)"""
    
    async def connect(self, config: StreamConfig) -> bool:
        logger.warning("WebSocket source not implemented")
        return False
    
    async def disconnect(self):
        pass
    
    async def consume(self) -> AsyncIterator[StreamMessage]:
        return
        yield
    
    async def acknowledge(self, message_id: str):
        pass
    
    async def reject(self, message_id: str):
        pass

class StreamingBuilder:
    """Build knowledge graphs from streaming data"""
    
    def __init__(self, graph_engine=None, config: Optional[Dict[str, Any]] = None):
        self.graph_engine = graph_engine
        self.config = StreamConfig(**config) if config else StreamConfig(
            source_type=StreamSourceType.REDIS_STREAM,
            connection_params={}
        )
        
        # Stream management
        self.status = StreamStatus.STOPPED
        self.stream_source: Optional[StreamSource] = None
        self.processing_tasks: Set[asyncio.Task] = set()
        
        # Buffering and batching
        self.message_buffer: deque = deque()
        self.processing_batches: Dict[str, List[StreamMessage]] = {}
        self.batch_semaphore = asyncio.Semaphore(self.config.max_concurrent_batches)
        
        # Deduplication
        self.recent_message_ids: Set[str] = set()
        self.dedup_cleanup_task: Optional[asyncio.Task] = None
        
        # Metrics and monitoring
        self.metrics = StreamMetrics()
        self.start_time: Optional[datetime] = None
        self.metrics_task: Optional[asyncio.Task] = None
        
        # Error handling
        self.dead_letter_queue: deque = deque(maxlen=1000)
        
        # Shutdown event
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize the streaming builder"""
        try:
            logger.info("Initializing streaming builder...")
            
            # Create appropriate stream source
            self.stream_source = self._create_stream_source()
            
            # Try to connect to stream source, but don't fail if unavailable
            try:
                if await self.stream_source.connect(self.config):
                    logger.info(f"Streaming builder initialized with {self.config.source_type.value} source")
                else:
                    logger.warning(f"Failed to connect to {self.config.source_type.value} source - streaming will be disabled")
                    self.status = StreamStatus.ERROR
            except Exception as connect_error:
                logger.warning(f"Could not connect to stream source ({connect_error}) - streaming will be disabled")
                self.status = StreamStatus.ERROR
            
        except Exception as e:
            logger.error(f"Error initializing streaming builder: {e}")
            raise
    
    def _create_stream_source(self) -> StreamSource:
        """Create appropriate stream source based on configuration"""
        if self.config.source_type == StreamSourceType.REDIS_STREAM:
            return RedisStreamSource()
        elif self.config.source_type == StreamSourceType.KAFKA:
            return KafkaStreamSource()
        elif self.config.source_type == StreamSourceType.WEBSOCKET:
            return WebSocketStreamSource()
        else:
            raise ValueError(f"Unsupported stream source type: {self.config.source_type}")
    
    async def start_streaming(self) -> bool:
        """Start streaming processing"""
        try:
            if self.status != StreamStatus.STOPPED:
                logger.warning("Streaming already started or starting")
                return False
            
            self.status = StreamStatus.STARTING
            self.start_time = datetime.now()
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Start main processing loop
            self.processing_tasks.add(
                asyncio.create_task(self._main_processing_loop())
            )
            
            self.status = StreamStatus.RUNNING
            logger.info("Streaming processing started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            self.status = StreamStatus.ERROR
            return False
    
    async def stop_streaming(self) -> bool:
        """Stop streaming processing"""
        try:
            if self.status not in [StreamStatus.RUNNING, StreamStatus.PAUSED]:
                return False
            
            self.status = StreamStatus.STOPPING
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Cancel all processing tasks
            for task in self.processing_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self.processing_tasks, return_exceptions=True)
            self.processing_tasks.clear()
            
            # Stop background tasks
            await self._stop_background_tasks()
            
            # Disconnect from stream source
            if self.stream_source:
                await self.stream_source.disconnect()
            
            self.status = StreamStatus.STOPPED
            logger.info("Streaming processing stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return False
    
    async def pause_streaming(self) -> bool:
        """Pause streaming processing"""
        if self.status == StreamStatus.RUNNING:
            self.status = StreamStatus.PAUSED
            logger.info("Streaming processing paused")
            return True
        return False
    
    async def resume_streaming(self) -> bool:
        """Resume streaming processing"""
        if self.status == StreamStatus.PAUSED:
            self.status = StreamStatus.RUNNING
            logger.info("Streaming processing resumed")
            return True
        return False
    
    async def _start_background_tasks(self):
        """Start background maintenance tasks"""
        # Metrics collection task
        if self.config.enable_metrics:
            self.metrics_task = asyncio.create_task(self._metrics_collection_loop())
        
        # Deduplication cleanup task
        if self.config.enable_deduplication:
            self.dedup_cleanup_task = asyncio.create_task(self._dedup_cleanup_loop())
    
    async def _stop_background_tasks(self):
        """Stop background maintenance tasks"""
        if self.metrics_task:
            self.metrics_task.cancel()
            self.metrics_task = None
        
        if self.dedup_cleanup_task:
            self.dedup_cleanup_task.cancel()
            self.dedup_cleanup_task = None
    
    async def _main_processing_loop(self):
        """Main loop for processing streaming messages"""
        try:
            batch_buffer = []
            last_batch_time = time.time()
            
            async for message in self.stream_source.consume():
                if self.shutdown_event.is_set():
                    break
                
                if self.status == StreamStatus.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                
                # Update metrics
                self.metrics.messages_received += 1
                self.metrics.bytes_processed += len(json.dumps(message.data).encode())
                
                # Apply filtering if enabled
                if self.config.enable_filtering and not await self._filter_message(message):
                    self.metrics.messages_skipped += 1
                    continue
                
                # Apply transformation if enabled
                if self.config.enable_transformation:
                    message = await self._transform_message(message)
                
                # Check for duplicates
                if self.config.enable_deduplication:
                    if await self._is_duplicate(message):
                        self.metrics.messages_skipped += 1
                        await self.stream_source.acknowledge(message.message_id)
                        continue
                    
                    self.recent_message_ids.add(message.message_id)
                
                # Add to batch buffer
                batch_buffer.append(message)
                
                # Check if we should process the batch
                current_time = time.time()
                should_process_batch = (
                    len(batch_buffer) >= self.config.batch_size or
                    (current_time - last_batch_time) * 1000 >= self.config.batch_timeout_ms
                )
                
                if should_process_batch and batch_buffer:
                    # Check backpressure
                    if self.config.enable_backpressure:
                        if len(self.message_buffer) > self.config.backpressure_threshold:
                            self.metrics.backpressure_events += 1
                            logger.warning("Backpressure detected, throttling processing")
                            await asyncio.sleep(0.1)
                            continue
                    
                    # Process batch asynchronously
                    batch_id = str(uuid.uuid4())
                    batch_copy = batch_buffer.copy()
                    batch_buffer.clear()
                    last_batch_time = current_time
                    
                    # Start batch processing task
                    task = asyncio.create_task(
                        self._process_batch(batch_id, batch_copy)
                    )
                    self.processing_tasks.add(task)
                    
                    # Clean up completed tasks
                    self.processing_tasks = {t for t in self.processing_tasks if not t.done()}
        
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")
            self.status = StreamStatus.ERROR
    
    async def _process_batch(self, batch_id: str, messages: List[StreamMessage]):
        """Process a batch of messages"""
        async with self.batch_semaphore:
            try:
                logger.debug(f"Processing batch {batch_id} with {len(messages)} messages")
                
                # Group messages by type
                entities = []
                relationships = []
                
                for message in messages:
                    message.processing_start_time = datetime.now()
                    
                    try:
                        # Extract graph data from message
                        graph_data = await self._extract_graph_data(message)
                        
                        if "entities" in graph_data:
                            entities.extend(graph_data["entities"])
                        
                        if "relationships" in graph_data:
                            relationships.extend(graph_data["relationships"])
                        
                    except Exception as e:
                        logger.error(f"Error extracting graph data from message {message.message_id}: {e}")
                        await self._handle_message_error(message, str(e))
                        continue
                
                # Process entities and relationships
                success_count = 0
                error_count = 0
                
                if entities and self.graph_engine:
                    try:
                        created_entities = await self.graph_engine.create_entities(entities)
                        success_count += len(created_entities)
                    except Exception as e:
                        logger.error(f"Error creating entities: {e}")
                        error_count += len(entities)
                
                if relationships and self.graph_engine:
                    try:
                        created_relationships = await self.graph_engine.create_relationships(relationships)
                        success_count += len(created_relationships)
                    except Exception as e:
                        logger.error(f"Error creating relationships: {e}")
                        error_count += len(relationships)
                
                # Acknowledge successful messages
                for message in messages:
                    if message.processing_start_time:
                        # Calculate latency
                        latency_ms = (datetime.now() - message.processing_start_time).total_seconds() * 1000
                        self._update_latency_metrics(latency_ms)
                    
                    try:
                        await self.stream_source.acknowledge(message.message_id)
                        self.metrics.messages_processed += 1
                    except Exception as e:
                        logger.error(f"Error acknowledging message {message.message_id}: {e}")
                
                logger.debug(f"Batch {batch_id} completed: {success_count} success, {error_count} errors")
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_id}: {e}")
                
                # Handle batch error
                for message in messages:
                    await self._handle_message_error(message, str(e))
    
    async def _extract_graph_data(self, message: StreamMessage) -> Dict[str, Any]:
        """Extract graph entities and relationships from message"""
        # This would integrate with existing extractors
        # For now, assume message data contains graph elements directly
        
        graph_data = {"entities": [], "relationships": []}
        
        data = message.data
        
        # Check if message contains direct graph data
        if "entities" in data:
            graph_data["entities"] = data["entities"]
        
        if "relationships" in data:
            graph_data["relationships"] = data["relationships"]
        
        # If message contains raw text, extract entities/relationships
        if "text" in data and not graph_data["entities"] and not graph_data["relationships"]:
            # This would use text extractors to extract entities/relationships
            # For now, create a simple entity from the text
            entity = {
                "id": str(uuid.uuid4()),
                "type": "Document",
                "name": f"Message_{message.message_id}",
                "content": data["text"],
                "source": message.source,
                "timestamp": message.timestamp.isoformat()
            }
            graph_data["entities"].append(entity)
        
        return graph_data
    
    async def _filter_message(self, message: StreamMessage) -> bool:
        """Apply filtering rules to message"""
        try:
            for rule in self.config.filter_rules:
                rule_type = rule.get("type")
                
                if rule_type == "field_exists":
                    field = rule.get("field")
                    if field not in message.data:
                        return False
                
                elif rule_type == "field_equals":
                    field = rule.get("field")
                    value = rule.get("value")
                    if message.data.get(field) != value:
                        return False
                
                elif rule_type == "field_contains":
                    field = rule.get("field")
                    value = rule.get("value")
                    field_value = str(message.data.get(field, ""))
                    if value not in field_value:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error filtering message: {e}")
            return True  # Default to accepting message
    
    async def _transform_message(self, message: StreamMessage) -> StreamMessage:
        """Apply transformation rules to message"""
        try:
            for rule in self.config.transformation_rules:
                rule_type = rule.get("type")
                
                if rule_type == "add_field":
                    field = rule.get("field")
                    value = rule.get("value")
                    message.data[field] = value
                
                elif rule_type == "rename_field":
                    old_field = rule.get("old_field")
                    new_field = rule.get("new_field")
                    if old_field in message.data:
                        message.data[new_field] = message.data.pop(old_field)
                
                elif rule_type == "remove_field":
                    field = rule.get("field")
                    message.data.pop(field, None)
            
            return message
            
        except Exception as e:
            logger.error(f"Error transforming message: {e}")
            return message
    
    async def _is_duplicate(self, message: StreamMessage) -> bool:
        """Check if message is a duplicate"""
        return message.message_id in self.recent_message_ids
    
    async def _handle_message_error(self, message: StreamMessage, error: str):
        """Handle message processing error"""
        message.retry_count += 1
        
        if self.config.error_handling == "retry" and message.retry_count <= self.config.max_retries:
            # Add back to processing queue with delay
            await asyncio.sleep(self.config.retry_delay_ms / 1000)
            # Would re-queue message for retry
            logger.info(f"Retrying message {message.message_id} (attempt {message.retry_count})")
        
        elif self.config.error_handling == "dead_letter":
            # Add to dead letter queue
            self.dead_letter_queue.append({
                "message_id": message.message_id,
                "data": message.data,
                "error": error,
                "timestamp": datetime.now().isoformat(),
                "retry_count": message.retry_count
            })
            await self.stream_source.reject(message.message_id)
        
        else:
            # Skip message
            await self.stream_source.acknowledge(message.message_id)
        
        self.metrics.messages_failed += 1
    
    def _update_latency_metrics(self, latency_ms: float):
        """Update latency metrics"""
        # Update average latency using exponential moving average
        alpha = 0.1
        if self.metrics.avg_latency_ms == 0:
            self.metrics.avg_latency_ms = latency_ms
        else:
            self.metrics.avg_latency_ms = alpha * latency_ms + (1 - alpha) * self.metrics.avg_latency_ms
        
        # Update max latency
        self.metrics.max_latency_ms = max(self.metrics.max_latency_ms, latency_ms)
    
    async def _metrics_collection_loop(self):
        """Background task for collecting and updating metrics"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(1)
                
                # Update processing rate
                if self.start_time:
                    elapsed_seconds = (datetime.now() - self.start_time).total_seconds()
                    self.metrics.uptime_seconds = elapsed_seconds
                    
                    if elapsed_seconds > 0:
                        self.metrics.processing_rate = self.metrics.messages_processed / elapsed_seconds
                        
                        total_messages = self.metrics.messages_processed + self.metrics.messages_failed
                        if total_messages > 0:
                            self.metrics.error_rate = self.metrics.messages_failed / total_messages
                
                # Update checkpoint
                if time.time() * 1000 % self.config.checkpoint_interval_ms < 1000:
                    self.metrics.last_checkpoint = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")
    
    async def _dedup_cleanup_loop(self):
        """Background task for cleaning up deduplication cache"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(self.config.dedup_window_seconds)
                
                # Clear old message IDs
                self.recent_message_ids.clear()
                logger.debug("Cleared deduplication cache")
        
        except Exception as e:
            logger.error(f"Error in dedup cleanup: {e}")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get current streaming metrics"""
        return {
            "status": self.status.value,
            "messages_received": self.metrics.messages_received,
            "messages_processed": self.metrics.messages_processed,
            "messages_failed": self.metrics.messages_failed,
            "messages_skipped": self.metrics.messages_skipped,
            "bytes_processed": self.metrics.bytes_processed,
            "processing_rate": self.metrics.processing_rate,
            "error_rate": self.metrics.error_rate,
            "avg_latency_ms": self.metrics.avg_latency_ms,
            "max_latency_ms": self.metrics.max_latency_ms,
            "backpressure_events": self.metrics.backpressure_events,
            "uptime_seconds": self.metrics.uptime_seconds,
            "last_checkpoint": self.metrics.last_checkpoint.isoformat() if self.metrics.last_checkpoint else None,
            "buffer_size": len(self.message_buffer),
            "active_batches": len(self.processing_batches),
            "dead_letter_queue_size": len(self.dead_letter_queue)
        }
    
    async def get_dead_letter_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages from dead letter queue"""
        return list(self.dead_letter_queue)[-limit:]
    
    async def reprocess_dead_letter_message(self, message_id: str) -> bool:
        """Reprocess a message from dead letter queue"""
        try:
            # Find message in dead letter queue
            for i, dead_message in enumerate(self.dead_letter_queue):
                if dead_message["message_id"] == message_id:
                    # Remove from dead letter queue
                    message_data = self.dead_letter_queue[i]
                    del self.dead_letter_queue[i]
                    
                    # Create new message for reprocessing
                    message = StreamMessage(
                        message_id=message_id,
                        source="dead_letter_reprocess",
                        timestamp=datetime.now(),
                        data=message_data["data"]
                    )
                    
                    # Process in single-message batch
                    await self._process_batch(f"reprocess_{message_id}", [message])
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error reprocessing dead letter message: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the streaming builder"""
        try:
            logger.info("Shutting down streaming builder...")
            
            await self.stop_streaming()
            
            logger.info("Streaming builder shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")