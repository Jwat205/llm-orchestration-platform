"""
Batch Graph Builder
Builds knowledge graphs from large datasets in batch processing mode for optimal performance.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Iterator, AsyncIterator
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from collections import defaultdict
import uuid
from datetime import datetime
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import tempfile
import os
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

class BatchStatus(Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    PROCESSING = "processing"
    POSTPROCESSING = "postprocessing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProcessingMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL_THREADS = "parallel_threads"
    PARALLEL_PROCESSES = "parallel_processes"
    DISTRIBUTED = "distributed"

@dataclass
class BatchConfig:
    batch_size: int = 1000
    max_workers: int = mp.cpu_count()
    processing_mode: ProcessingMode = ProcessingMode.PARALLEL_THREADS
    memory_limit_mb: int = 2048
    temp_dir: Optional[str] = None
    enable_compression: bool = True
    enable_checkpoints: bool = True
    checkpoint_interval: int = 10000
    enable_validation: bool = True
    enable_deduplication: bool = True
    dedupe_similarity_threshold: float = 0.85
    enable_statistics: bool = True
    max_retries: int = 3
    error_threshold: float = 0.1  # Max 10% errors allowed

@dataclass
class BatchTask:
    task_id: str
    status: BatchStatus
    data_sources: List[Dict[str, Any]]
    config: BatchConfig
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    total_items: int = 0
    processed_items: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    statistics: Dict[str, Any] = field(default_factory=dict)
    temp_files: List[str] = field(default_factory=list)

@dataclass
class BatchItem:
    item_id: str
    item_type: str  # entity, relationship, document, etc.
    data: Dict[str, Any]
    source_info: Dict[str, Any]
    processing_status: str = "pending"
    error_message: Optional[str] = None
    retry_count: int = 0

class BatchBuilder:
    """Build knowledge graphs from large datasets in batch mode"""
    
    def __init__(self, graph_engine=None, config: Optional[Dict[str, Any]] = None):
        self.graph_engine = graph_engine
        self.config = BatchConfig(**config) if config else BatchConfig()
        
        # Task management
        self.active_tasks: Dict[str, BatchTask] = {}
        
        # Processing resources
        self.thread_executor: Optional[ThreadPoolExecutor] = None
        self.process_executor: Optional[ProcessPoolExecutor] = None
        
        # Statistics
        self.global_stats = {
            "total_batches_processed": 0,
            "total_items_processed": 0,
            "total_errors": 0,
            "average_processing_time": 0.0,
            "peak_memory_usage": 0
        }
        
        # Locks for thread safety
        self._task_lock = asyncio.Lock()
        
        # Temporary directory for batch processing
        self.temp_dir = Path(self.config.temp_dir) if self.config.temp_dir else Path(tempfile.gettempdir()) / "graph_batch_builder"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def initialize(self):
        """Initialize the batch builder"""
        try:
            logger.info("Initializing batch builder...")
            
            # Initialize executors based on processing mode
            if self.config.processing_mode == ProcessingMode.PARALLEL_THREADS:
                self.thread_executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
            elif self.config.processing_mode == ProcessingMode.PARALLEL_PROCESSES:
                self.process_executor = ProcessPoolExecutor(max_workers=self.config.max_workers)
            
            logger.info(f"Batch builder initialized with {self.config.max_workers} workers in {self.config.processing_mode.value} mode")
            
        except Exception as e:
            logger.error(f"Error initializing batch builder: {e}")
            raise
    
    async def start_batch_build(self, data_sources: List[Dict[str, Any]], config: Optional[Dict[str, Any]] = None) -> str:
        """Start a batch build task"""
        try:
            task_id = str(uuid.uuid4())
            
            # Merge configuration
            merged_config = BatchConfig(**{**self.config.__dict__, **(config or {})})
            
            # Create batch task
            task = BatchTask(
                task_id=task_id,
                status=BatchStatus.PENDING,
                data_sources=data_sources,
                config=merged_config,
                created_at=datetime.now(),
                total_items=await self._calculate_total_items(data_sources)
            )
            
            async with self._task_lock:
                self.active_tasks[task_id] = task
            
            # Start processing in background
            asyncio.create_task(self._process_batch_task(task_id))
            
            logger.info(f"Started batch build task {task_id} with {task.total_items} items")
            return task_id
            
        except Exception as e:
            logger.error(f"Error starting batch build: {e}")
            raise
    
    async def get_build_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a batch build task"""
        async with self._task_lock:
            task = self.active_tasks.get(task_id)
            
            if not task:
                return {"error": "Task not found"}
            
            return {
                "task_id": task.task_id,
                "status": task.status.value,
                "progress": task.progress,
                "total_items": task.total_items,
                "processed_items": task.processed_items,
                "success_count": task.success_count,
                "error_count": task.error_count,
                "skipped_count": task.skipped_count,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message,
                "statistics": task.statistics
            }
    
    async def cancel_batch_build(self, task_id: str) -> bool:
        """Cancel a batch build task"""
        try:
            async with self._task_lock:
                task = self.active_tasks.get(task_id)
                
                if not task:
                    return False
                
                if task.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
                    return False
                
                task.status = BatchStatus.CANCELLED
                task.completed_at = datetime.now()
                
                # Clean up temporary files
                await self._cleanup_temp_files(task)
            
            logger.info(f"Cancelled batch build task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling batch build: {e}")
            return False
    
    async def _process_batch_task(self, task_id: str):
        """Process a batch build task"""
        start_time = time.time()
        
        try:
            async with self._task_lock:
                task = self.active_tasks[task_id]
                task.status = BatchStatus.PREPROCESSING
                task.started_at = datetime.now()
            
            logger.info(f"Starting batch processing for task {task_id}")
            
            # Phase 1: Preprocessing
            batch_items = await self._preprocess_data_sources(task)
            
            if task.status == BatchStatus.CANCELLED:
                return
            
            # Phase 2: Main processing
            task.status = BatchStatus.PROCESSING
            await self._process_batch_items(task, batch_items)
            
            if task.status == BatchStatus.CANCELLED:
                return
            
            # Phase 3: Post-processing
            task.status = BatchStatus.POSTPROCESSING
            await self._postprocess_results(task)
            
            # Mark as completed
            async with self._task_lock:
                if task.status != BatchStatus.CANCELLED:
                    task.status = BatchStatus.COMPLETED
                    task.completed_at = datetime.now()
                    
                    # Update global statistics
                    self.global_stats["total_batches_processed"] += 1
                    self.global_stats["total_items_processed"] += task.processed_items
                    self.global_stats["total_errors"] += task.error_count
                    
                    processing_time = time.time() - start_time
                    avg_time = self.global_stats["average_processing_time"]
                    total_batches = self.global_stats["total_batches_processed"]
                    self.global_stats["average_processing_time"] = (avg_time * (total_batches - 1) + processing_time) / total_batches
            
            logger.info(f"Completed batch task {task_id}: {task.success_count} success, {task.error_count} errors")
            
        except Exception as e:
            logger.error(f"Error processing batch task {task_id}: {e}")
            
            async with self._task_lock:
                task.status = BatchStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now()
        
        finally:
            # Clean up resources
            await self._cleanup_temp_files(task)
    
    async def _calculate_total_items(self, data_sources: List[Dict[str, Any]]) -> int:
        """Calculate total number of items to process"""
        total = 0
        
        for source in data_sources:
            if source.get("type") == "file":
                # Estimate based on file size or content
                file_path = source.get("path")
                if file_path and os.path.exists(file_path):
                    # Simple estimation based on file size
                    file_size = os.path.getsize(file_path)
                    estimated_items = max(1, file_size // 1024)  # Rough estimate
                    total += estimated_items
            elif source.get("type") == "data":
                # Count items in provided data
                data = source.get("data", {})
                for key in ["entities", "relationships", "documents"]:
                    if key in data:
                        total += len(data[key])
            elif source.get("type") == "database":
                # Would query database for count
                total += source.get("estimated_count", 1000)
        
        return total
    
    async def _preprocess_data_sources(self, task: BatchTask) -> List[BatchItem]:
        """Preprocess data sources into batch items"""
        batch_items = []
        
        try:
            for source in task.data_sources:
                items = await self._process_data_source(source)
                batch_items.extend(items)
                
                # Update progress
                task.progress = len(batch_items) / task.total_items * 0.3  # Preprocessing is 30% of progress
            
            # Deduplication if enabled
            if task.config.enable_deduplication:
                batch_items = await self._deduplicate_items(batch_items, task)
            
            # Validation if enabled
            if task.config.enable_validation:
                batch_items = await self._validate_items(batch_items, task)
            
            logger.info(f"Preprocessed {len(batch_items)} items for task {task.task_id}")
            return batch_items
            
        except Exception as e:
            logger.error(f"Error in preprocessing: {e}")
            raise
    
    async def _process_data_source(self, source: Dict[str, Any]) -> List[BatchItem]:
        """Process a single data source"""
        items = []
        
        try:
            source_type = source.get("type")
            
            if source_type == "file":
                items = await self._process_file_source(source)
            elif source_type == "data":
                items = await self._process_data_source_direct(source)
            elif source_type == "database":
                items = await self._process_database_source(source)
            elif source_type == "api":
                items = await self._process_api_source(source)
            else:
                logger.warning(f"Unknown source type: {source_type}")
        
        except Exception as e:
            logger.error(f"Error processing data source: {e}")
        
        return items
    
    async def _process_file_source(self, source: Dict[str, Any]) -> List[BatchItem]:
        """Process file-based data source"""
        items = []
        file_path = source.get("path")
        
        try:
            if not file_path or not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return items
            
            file_format = source.get("format", "json")
            
            if file_format == "json":
                items = await self._process_json_file(file_path, source)
            elif file_format == "csv":
                items = await self._process_csv_file(file_path, source)
            elif file_format == "jsonl":
                items = await self._process_jsonl_file(file_path, source)
            else:
                logger.warning(f"Unsupported file format: {file_format}")
        
        except Exception as e:
            logger.error(f"Error processing file source: {e}")
        
        return items
    
    async def _process_json_file(self, file_path: str, source: Dict[str, Any]) -> List[BatchItem]:
        """Process JSON file"""
        items = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert data to batch items
            for item_type in ["entities", "relationships", "documents"]:
                if item_type in data:
                    for item_data in data[item_type]:
                        item = BatchItem(
                            item_id=str(uuid.uuid4()),
                            item_type=item_type[:-1],  # Remove 's' from plural
                            data=item_data,
                            source_info={"file": file_path, "type": "json"}
                        )
                        items.append(item)
        
        except Exception as e:
            logger.error(f"Error processing JSON file: {e}")
        
        return items
    
    async def _process_csv_file(self, file_path: str, source: Dict[str, Any]) -> List[BatchItem]:
        """Process CSV file"""
        items = []
        
        try:
            import csv
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    item = BatchItem(
                        item_id=str(uuid.uuid4()),
                        item_type=source.get("item_type", "entity"),
                        data=dict(row),
                        source_info={"file": file_path, "type": "csv"}
                    )
                    items.append(item)
        
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
        
        return items
    
    async def _process_jsonl_file(self, file_path: str, source: Dict[str, Any]) -> List[BatchItem]:
        """Process JSONL file"""
        items = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line.strip())
                        item = BatchItem(
                            item_id=str(uuid.uuid4()),
                            item_type=source.get("item_type", "entity"),
                            data=data,
                            source_info={"file": file_path, "type": "jsonl", "line": line_num}
                        )
                        items.append(item)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON on line {line_num}: {e}")
        
        except Exception as e:
            logger.error(f"Error processing JSONL file: {e}")
        
        return items
    
    async def _process_data_source_direct(self, source: Dict[str, Any]) -> List[BatchItem]:
        """Process direct data source"""
        items = []
        data = source.get("data", {})
        
        for item_type in ["entities", "relationships", "documents"]:
            if item_type in data:
                for item_data in data[item_type]:
                    item = BatchItem(
                        item_id=str(uuid.uuid4()),
                        item_type=item_type[:-1],  # Remove 's' from plural
                        data=item_data,
                        source_info={"type": "direct"}
                    )
                    items.append(item)
        
        return items
    
    async def _process_database_source(self, source: Dict[str, Any]) -> List[BatchItem]:
        """Process database source"""
        # Placeholder for database processing
        # Would implement actual database connection and querying
        return []
    
    async def _process_api_source(self, source: Dict[str, Any]) -> List[BatchItem]:
        """Process API source"""
        # Placeholder for API processing
        # Would implement actual API calls and data fetching
        return []
    
    async def _deduplicate_items(self, items: List[BatchItem], task: BatchTask) -> List[BatchItem]:
        """Remove duplicate items"""
        try:
            # Group items by type
            items_by_type = defaultdict(list)
            for item in items:
                items_by_type[item.item_type].append(item)
            
            deduplicated_items = []
            removed_count = 0
            
            for item_type, type_items in items_by_type.items():
                if item_type == "entity":
                    unique_items = await self._deduplicate_entities(type_items, task.config.dedupe_similarity_threshold)
                elif item_type == "relationship":
                    unique_items = await self._deduplicate_relationships(type_items)
                else:
                    unique_items = type_items  # No deduplication for other types
                
                deduplicated_items.extend(unique_items)
                removed_count += len(type_items) - len(unique_items)
            
            logger.info(f"Deduplication removed {removed_count} duplicate items")
            task.skipped_count += removed_count
            
            return deduplicated_items
            
        except Exception as e:
            logger.error(f"Error in deduplication: {e}")
            return items
    
    async def _deduplicate_entities(self, entities: List[BatchItem], similarity_threshold: float) -> List[BatchItem]:
        """Deduplicate entities based on similarity"""
        if len(entities) <= 1:
            return entities
        
        unique_entities = []
        seen_signatures = set()
        
        for entity in entities:
            # Create signature for entity
            signature = self._create_entity_signature(entity.data)
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_entities.append(entity)
        
        return unique_entities
    
    def _create_entity_signature(self, entity_data: Dict[str, Any]) -> str:
        """Create a signature for entity deduplication"""
        # Simple signature based on key fields
        key_fields = ["name", "title", "id", "identifier"]
        signature_parts = []
        
        for field in key_fields:
            if field in entity_data:
                value = str(entity_data[field]).lower().strip()
                signature_parts.append(value)
        
        return "|".join(signature_parts) or str(hash(json.dumps(entity_data, sort_keys=True)))
    
    async def _deduplicate_relationships(self, relationships: List[BatchItem]) -> List[BatchItem]:
        """Deduplicate relationships"""
        unique_relationships = []
        seen_signatures = set()
        
        for rel in relationships:
            # Create signature for relationship
            source = rel.data.get("source_id", "")
            target = rel.data.get("target_id", "")
            rel_type = rel.data.get("type", "")
            signature = f"{source}|{rel_type}|{target}"
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_relationships.append(rel)
        
        return unique_relationships
    
    async def _validate_items(self, items: List[BatchItem], task: BatchTask) -> List[BatchItem]:
        """Validate batch items"""
        valid_items = []
        invalid_count = 0
        
        for item in items:
            if await self._validate_item(item):
                valid_items.append(item)
            else:
                invalid_count += 1
                item.processing_status = "invalid"
        
        logger.info(f"Validation removed {invalid_count} invalid items")
        task.skipped_count += invalid_count
        
        return valid_items
    
    async def _validate_item(self, item: BatchItem) -> bool:
        """Validate a single item"""
        try:
            if item.item_type == "entity":
                return self._validate_entity_item(item.data)
            elif item.item_type == "relationship":
                return self._validate_relationship_item(item.data)
            else:
                return True  # Default to valid for other types
        except Exception:
            return False
    
    def _validate_entity_item(self, data: Dict[str, Any]) -> bool:
        """Validate entity item"""
        # Basic validation
        if not data.get("id") and not data.get("name"):
            return False
        
        if not data.get("type"):
            return False
        
        return True
    
    def _validate_relationship_item(self, data: Dict[str, Any]) -> bool:
        """Validate relationship item"""
        # Basic validation
        if not data.get("source_id"):
            return False
        
        if not data.get("target_id"):
            return False
        
        if not data.get("type"):
            return False
        
        return True
    
    async def _process_batch_items(self, task: BatchTask, batch_items: List[BatchItem]):
        """Process batch items based on configuration"""
        try:
            if task.config.processing_mode == ProcessingMode.SEQUENTIAL:
                await self._process_sequential(task, batch_items)
            elif task.config.processing_mode == ProcessingMode.PARALLEL_THREADS:
                await self._process_parallel_threads(task, batch_items)
            elif task.config.processing_mode == ProcessingMode.PARALLEL_PROCESSES:
                await self._process_parallel_processes(task, batch_items)
            else:
                logger.warning(f"Unsupported processing mode: {task.config.processing_mode}")
                await self._process_sequential(task, batch_items)
                
        except Exception as e:
            logger.error(f"Error processing batch items: {e}")
            raise
    
    async def _process_sequential(self, task: BatchTask, batch_items: List[BatchItem]):
        """Process items sequentially"""
        for i, item in enumerate(batch_items):
            if task.status == BatchStatus.CANCELLED:
                break
            
            success = await self._process_single_item(item, task)
            
            # Update progress
            task.processed_items = i + 1
            task.progress = 0.3 + (task.processed_items / len(batch_items)) * 0.6
            
            if success:
                task.success_count += 1
            else:
                task.error_count += 1
            
            # Check error threshold
            if self._check_error_threshold(task):
                break
            
            # Checkpoint if needed
            if task.config.enable_checkpoints and task.processed_items % task.config.checkpoint_interval == 0:
                await self._create_checkpoint(task)
    
    async def _process_parallel_threads(self, task: BatchTask, batch_items: List[BatchItem]):
        """Process items using thread pool"""
        if not self.thread_executor:
            await self._process_sequential(task, batch_items)
            return
        
        # Process in batches
        batch_size = task.config.batch_size
        
        for i in range(0, len(batch_items), batch_size):
            if task.status == BatchStatus.CANCELLED:
                break
            
            batch = batch_items[i:i + batch_size]
            
            # Submit batch to thread pool
            loop = asyncio.get_event_loop()
            futures = []
            
            for item in batch:
                future = loop.run_in_executor(
                    self.thread_executor,
                    self._process_item_sync,
                    item, task.config
                )
                futures.append(future)
            
            # Wait for batch completion
            results = await asyncio.gather(*futures, return_exceptions=True)
            
            # Update progress
            for result in results:
                task.processed_items += 1
                if isinstance(result, Exception):
                    task.error_count += 1
                    logger.error(f"Error processing item: {result}")
                else:
                    task.success_count += 1
            
            task.progress = 0.3 + (task.processed_items / len(batch_items)) * 0.6
            
            # Check error threshold
            if self._check_error_threshold(task):
                break
    
    async def _process_parallel_processes(self, task: BatchTask, batch_items: List[BatchItem]):
        """Process items using process pool"""
        if not self.process_executor:
            await self._process_sequential(task, batch_items)
            return
        
        # For multiprocessing, we need to serialize the graph_engine operations
        # This is a simplified implementation
        logger.warning("Process-based parallel processing not fully implemented, falling back to threads")
        await self._process_parallel_threads(task, batch_items)
    
    async def _process_single_item(self, item: BatchItem, task: BatchTask) -> bool:
        """Process a single batch item"""
        try:
            if item.item_type == "entity":
                return await self._process_entity_item(item)
            elif item.item_type == "relationship":
                return await self._process_relationship_item(item)
            elif item.item_type == "document":
                return await self._process_document_item(item)
            else:
                logger.warning(f"Unknown item type: {item.item_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing item {item.item_id}: {e}")
            item.error_message = str(e)
            item.processing_status = "failed"
            return False
    
    def _process_item_sync(self, item: BatchItem, config: BatchConfig) -> bool:
        """Synchronous version for thread pool processing"""
        # This would need to be implemented with synchronous graph operations
        # For now, return True as placeholder
        return True
    
    async def _process_entity_item(self, item: BatchItem) -> bool:
        """Process an entity item"""
        try:
            if not self.graph_engine:
                return False
            
            result = await self.graph_engine.create_entities([item.data])
            item.processing_status = "completed"
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"Error processing entity: {e}")
            item.error_message = str(e)
            item.processing_status = "failed"
            return False
    
    async def _process_relationship_item(self, item: BatchItem) -> bool:
        """Process a relationship item"""
        try:
            if not self.graph_engine:
                return False
            
            result = await self.graph_engine.create_relationships([item.data])
            item.processing_status = "completed"
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"Error processing relationship: {e}")
            item.error_message = str(e)
            item.processing_status = "failed"
            return False
    
    async def _process_document_item(self, item: BatchItem) -> bool:
        """Process a document item"""
        try:
            # Document processing would involve:
            # 1. Text extraction
            # 2. Entity extraction
            # 3. Relationship extraction
            # 4. Graph construction
            
            # For now, return True as placeholder
            item.processing_status = "completed"
            return True
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            item.error_message = str(e)
            item.processing_status = "failed"
            return False
    
    def _check_error_threshold(self, task: BatchTask) -> bool:
        """Check if error threshold is exceeded"""
        if task.processed_items == 0:
            return False
        
        error_rate = task.error_count / task.processed_items
        
        if error_rate > task.config.error_threshold:
            task.status = BatchStatus.FAILED
            task.error_message = f"Error threshold exceeded: {error_rate:.2%} > {task.config.error_threshold:.2%}"
            logger.error(task.error_message)
            return True
        
        return False
    
    async def _create_checkpoint(self, task: BatchTask):
        """Create a checkpoint for recovery"""
        try:
            checkpoint_file = self.temp_dir / f"checkpoint_{task.task_id}_{task.processed_items}.pkl"
            
            checkpoint_data = {
                "task_id": task.task_id,
                "processed_items": task.processed_items,
                "success_count": task.success_count,
                "error_count": task.error_count,
                "skipped_count": task.skipped_count,
                "timestamp": datetime.now()
            }
            
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(checkpoint_data, f)
            
            task.temp_files.append(str(checkpoint_file))
            logger.info(f"Created checkpoint at {task.processed_items} items")
            
        except Exception as e:
            logger.error(f"Error creating checkpoint: {e}")
    
    async def _postprocess_results(self, task: BatchTask):
        """Post-process results after main processing"""
        try:
            # Calculate final statistics
            task.statistics = {
                "processing_rate": task.processed_items / (time.time() - task.started_at.timestamp()) if task.started_at else 0,
                "success_rate": task.success_count / task.processed_items if task.processed_items > 0 else 0,
                "error_rate": task.error_count / task.processed_items if task.processed_items > 0 else 0,
                "total_processing_time": time.time() - task.started_at.timestamp() if task.started_at else 0
            }
            
            # Final progress update
            task.progress = 1.0
            
            logger.info(f"Post-processing completed for task {task.task_id}")
            
        except Exception as e:
            logger.error(f"Error in post-processing: {e}")
    
    async def _cleanup_temp_files(self, task: BatchTask):
        """Clean up temporary files"""
        try:
            for temp_file in task.temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            task.temp_files.clear()
            logger.info(f"Cleaned up temporary files for task {task.task_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
    
    async def get_global_statistics(self) -> Dict[str, Any]:
        """Get global processing statistics"""
        return {
            **self.global_stats,
            "active_tasks": len(self.active_tasks),
            "available_workers": self.config.max_workers
        }
    
    async def shutdown(self):
        """Shutdown the batch builder"""
        try:
            logger.info("Shutting down batch builder...")
            
            # Cancel all active tasks
            async with self._task_lock:
                for task in self.active_tasks.values():
                    if task.status not in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
                        task.status = BatchStatus.CANCELLED
                        task.completed_at = datetime.now()
                        await self._cleanup_temp_files(task)
            
            # Shutdown executors
            if self.thread_executor:
                self.thread_executor.shutdown(wait=True)
            
            if self.process_executor:
                self.process_executor.shutdown(wait=True)
            
            # Clean up temp directory
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            logger.info("Batch builder shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")