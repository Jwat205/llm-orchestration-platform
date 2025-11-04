"""
Incremental Graph Builder
Builds knowledge graphs incrementally as new data arrives, maintaining consistency and performance.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from collections import defaultdict, deque
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class BuildStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class ChangeType(Enum):
    ADD_ENTITY = "add_entity"
    UPDATE_ENTITY = "update_entity"
    DELETE_ENTITY = "delete_entity"
    ADD_RELATIONSHIP = "add_relationship"
    UPDATE_RELATIONSHIP = "update_relationship"
    DELETE_RELATIONSHIP = "delete_relationship"

@dataclass
class BuildTask:
    task_id: str
    status: BuildStatus
    data: Dict[str, Any]
    config: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    changes_applied: int = 0
    total_changes: int = 0

@dataclass
class GraphChange:
    change_id: str
    change_type: ChangeType
    data: Dict[str, Any]
    timestamp: datetime
    dependencies: Set[str] = field(default_factory=set)
    applied: bool = False
    rollback_data: Optional[Dict[str, Any]] = None

@dataclass
class BuildConfig:
    batch_size: int = 100
    max_concurrent_operations: int = 10
    enable_validation: bool = True
    enable_deduplication: bool = True
    enable_rollback: bool = True
    conflict_resolution: str = "latest_wins"  # latest_wins, merge, manual
    consistency_checks: bool = True
    checkpoint_interval: int = 1000
    max_retries: int = 3

class IncrementalBuilder:
    """Incrementally build and update knowledge graphs"""
    
    def __init__(self, graph_engine=None, config: Optional[Dict[str, Any]] = None):
        self.graph_engine = graph_engine
        self.config = BuildConfig(**config) if config else BuildConfig()
        
        # Task management
        self.active_tasks: Dict[str, BuildTask] = {}
        self.task_queue: deque = deque()
        self.change_log: List[GraphChange] = []
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # Performance tracking
        self.performance_metrics = {
            "total_builds": 0,
            "successful_builds": 0,
            "failed_builds": 0,
            "average_build_time": 0.0,
            "changes_processed": 0
        }
        
        # Locks for thread safety
        self._task_lock = asyncio.Lock()
        self._change_lock = asyncio.Lock()
        
        # Worker management
        self.workers: List[asyncio.Task] = []
        self.worker_count = self.config.max_concurrent_operations
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize the incremental builder"""
        try:
            logger.info("Initializing incremental builder...")
            
            # Start worker tasks
            for i in range(self.worker_count):
                worker = asyncio.create_task(self._worker(f"worker-{i}"))
                self.workers.append(worker)
            
            logger.info(f"Incremental builder initialized with {self.worker_count} workers")
            
        except Exception as e:
            logger.error(f"Error initializing incremental builder: {e}")
            raise
    
    async def start_build(self, data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> str:
        """Start an incremental build task"""
        try:
            task_id = str(uuid.uuid4())
            
            # Merge configuration
            merged_config = {**self.config.__dict__}
            if config:
                merged_config.update(config)
            
            # Create build task
            task = BuildTask(
                task_id=task_id,
                status=BuildStatus.PENDING,
                data=data,
                config=merged_config,
                created_at=datetime.now()
            )
            
            # Calculate total changes
            task.total_changes = await self._calculate_total_changes(data)
            
            async with self._task_lock:
                self.active_tasks[task_id] = task
                self.task_queue.append(task_id)
            
            logger.info(f"Started incremental build task {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error starting build: {e}")
            raise
    
    async def get_build_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a build task"""
        async with self._task_lock:
            task = self.active_tasks.get(task_id)
            
            if not task:
                return {"error": "Task not found"}
            
            return {
                "task_id": task.task_id,
                "status": task.status.value,
                "progress": task.progress,
                "changes_applied": task.changes_applied,
                "total_changes": task.total_changes,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message
            }
    
    async def cancel_build(self, task_id: str) -> bool:
        """Cancel a build task"""
        try:
            async with self._task_lock:
                task = self.active_tasks.get(task_id)
                
                if not task:
                    return False
                
                if task.status in [BuildStatus.COMPLETED, BuildStatus.FAILED, BuildStatus.CANCELLED]:
                    return False
                
                task.status = BuildStatus.CANCELLED
                task.completed_at = datetime.now()
            
            logger.info(f"Cancelled build task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling build: {e}")
            return False
    
    async def pause_build(self, task_id: str) -> bool:
        """Pause a build task"""
        try:
            async with self._task_lock:
                task = self.active_tasks.get(task_id)
                
                if not task or task.status != BuildStatus.RUNNING:
                    return False
                
                task.status = BuildStatus.PAUSED
            
            logger.info(f"Paused build task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error pausing build: {e}")
            return False
    
    async def resume_build(self, task_id: str) -> bool:
        """Resume a paused build task"""
        try:
            async with self._task_lock:
                task = self.active_tasks.get(task_id)
                
                if not task or task.status != BuildStatus.PAUSED:
                    return False
                
                task.status = BuildStatus.PENDING
                self.task_queue.append(task_id)
            
            logger.info(f"Resumed build task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resuming build: {e}")
            return False
    
    async def add_incremental_data(self, data: Dict[str, Any], priority: bool = False) -> str:
        """Add data for incremental processing"""
        return await self.start_build(data, {"priority": priority})
    
    async def _worker(self, worker_name: str):
        """Worker task to process build queue"""
        logger.info(f"Started worker {worker_name}")
        
        while not self.shutdown_event.is_set():
            try:
                # Get next task
                task_id = None
                async with self._task_lock:
                    if self.task_queue:
                        task_id = self.task_queue.popleft()
                
                if not task_id:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process task
                await self._process_build_task(task_id, worker_name)
                
            except Exception as e:
                logger.error(f"Error in worker {worker_name}: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _process_build_task(self, task_id: str, worker_name: str):
        """Process a single build task"""
        start_time = time.time()
        
        try:
            async with self._task_lock:
                task = self.active_tasks.get(task_id)
                
                if not task or task.status == BuildStatus.CANCELLED:
                    return
                
                task.status = BuildStatus.RUNNING
                task.started_at = datetime.now()
            
            logger.info(f"Worker {worker_name} processing task {task_id}")
            
            # Generate changes from data
            changes = await self._generate_changes(task.data)
            
            # Sort changes by dependencies
            sorted_changes = await self._sort_changes_by_dependencies(changes)
            
            # Apply changes incrementally
            applied_changes = 0
            for i, change in enumerate(sorted_changes):
                # Check if task is cancelled or paused
                if task.status in [BuildStatus.CANCELLED, BuildStatus.PAUSED]:
                    break
                
                # Apply change
                success = await self._apply_change(change)
                
                if success:
                    applied_changes += 1
                    async with self._change_lock:
                        self.change_log.append(change)
                
                # Update progress
                progress = (i + 1) / len(sorted_changes)
                async with self._task_lock:
                    task.progress = progress
                    task.changes_applied = applied_changes
                
                # Checkpoint if needed
                if (i + 1) % self.config.checkpoint_interval == 0:
                    await self._create_checkpoint(task_id)
            
            # Mark task as completed
            async with self._task_lock:
                if task.status == BuildStatus.RUNNING:
                    task.status = BuildStatus.COMPLETED
                    task.completed_at = datetime.now()
                    task.changes_applied = applied_changes
                    
                    # Update performance metrics
                    self.performance_metrics["total_builds"] += 1
                    self.performance_metrics["successful_builds"] += 1
                    self.performance_metrics["changes_processed"] += applied_changes
                    
                    build_time = time.time() - start_time
                    avg_time = self.performance_metrics["average_build_time"]
                    total_builds = self.performance_metrics["total_builds"]
                    self.performance_metrics["average_build_time"] = (avg_time * (total_builds - 1) + build_time) / total_builds
            
            logger.info(f"Completed task {task_id}: {applied_changes} changes applied")
            
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            
            async with self._task_lock:
                task.status = BuildStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now()
                
                self.performance_metrics["total_builds"] += 1
                self.performance_metrics["failed_builds"] += 1
    
    async def _calculate_total_changes(self, data: Dict[str, Any]) -> int:
        """Calculate total number of changes in the data"""
        total = 0
        
        # Count entities
        if "entities" in data:
            total += len(data["entities"])
        
        # Count relationships
        if "relationships" in data:
            total += len(data["relationships"])
        
        # Count other data types
        for key in ["documents", "concepts", "events"]:
            if key in data:
                total += len(data[key])
        
        return total
    
    async def _generate_changes(self, data: Dict[str, Any]) -> List[GraphChange]:
        """Generate graph changes from input data"""
        changes = []
        
        try:
            # Process entities
            if "entities" in data:
                for entity_data in data["entities"]:
                    change = GraphChange(
                        change_id=str(uuid.uuid4()),
                        change_type=ChangeType.ADD_ENTITY,
                        data=entity_data,
                        timestamp=datetime.now()
                    )
                    changes.append(change)
            
            # Process relationships
            if "relationships" in data:
                for rel_data in data["relationships"]:
                    change = GraphChange(
                        change_id=str(uuid.uuid4()),
                        change_type=ChangeType.ADD_RELATIONSHIP,
                        data=rel_data,
                        timestamp=datetime.now()
                    )
                    
                    # Add dependencies on source and target entities
                    if "source_id" in rel_data:
                        change.dependencies.add(rel_data["source_id"])
                    if "target_id" in rel_data:
                        change.dependencies.add(rel_data["target_id"])
                    
                    changes.append(change)
            
            # Process updates
            if "updates" in data:
                for update_data in data["updates"]:
                    change_type = ChangeType.UPDATE_ENTITY if update_data.get("type") == "entity" else ChangeType.UPDATE_RELATIONSHIP
                    change = GraphChange(
                        change_id=str(uuid.uuid4()),
                        change_type=change_type,
                        data=update_data,
                        timestamp=datetime.now()
                    )
                    changes.append(change)
            
            # Process deletions
            if "deletions" in data:
                for delete_data in data["deletions"]:
                    change_type = ChangeType.DELETE_ENTITY if delete_data.get("type") == "entity" else ChangeType.DELETE_RELATIONSHIP
                    change = GraphChange(
                        change_id=str(uuid.uuid4()),
                        change_type=change_type,
                        data=delete_data,
                        timestamp=datetime.now()
                    )
                    changes.append(change)
            
        except Exception as e:
            logger.error(f"Error generating changes: {e}")
        
        return changes
    
    async def _sort_changes_by_dependencies(self, changes: List[GraphChange]) -> List[GraphChange]:
        """Sort changes by their dependencies using topological sort"""
        try:
            # Build dependency graph
            change_map = {change.change_id: change for change in changes}
            in_degree = {change.change_id: 0 for change in changes}
            
            for change in changes:
                for dep in change.dependencies:
                    if dep in change_map:
                        in_degree[change.change_id] += 1
            
            # Topological sort
            queue = deque([change_id for change_id, degree in in_degree.items() if degree == 0])
            sorted_changes = []
            
            while queue:
                change_id = queue.popleft()
                change = change_map[change_id]
                sorted_changes.append(change)
                
                # Update in-degree for dependent changes
                for other_change in changes:
                    if change_id in other_change.dependencies:
                        in_degree[other_change.change_id] -= 1
                        if in_degree[other_change.change_id] == 0:
                            queue.append(other_change.change_id)
            
            # Handle circular dependencies
            if len(sorted_changes) < len(changes):
                logger.warning("Circular dependencies detected, adding remaining changes")
                remaining = [c for c in changes if c not in sorted_changes]
                sorted_changes.extend(remaining)
            
            return sorted_changes
            
        except Exception as e:
            logger.error(f"Error sorting changes: {e}")
            return changes
    
    async def _apply_change(self, change: GraphChange) -> bool:
        """Apply a single graph change"""
        try:
            if not self.graph_engine:
                logger.warning("No graph engine available")
                return False
            
            # Store rollback data if enabled
            if self.config.enable_rollback:
                change.rollback_data = await self._prepare_rollback_data(change)
            
            # Apply the change based on type
            if change.change_type == ChangeType.ADD_ENTITY:
                success = await self._add_entity(change.data)
            elif change.change_type == ChangeType.UPDATE_ENTITY:
                success = await self._update_entity(change.data)
            elif change.change_type == ChangeType.DELETE_ENTITY:
                success = await self._delete_entity(change.data)
            elif change.change_type == ChangeType.ADD_RELATIONSHIP:
                success = await self._add_relationship(change.data)
            elif change.change_type == ChangeType.UPDATE_RELATIONSHIP:
                success = await self._update_relationship(change.data)
            elif change.change_type == ChangeType.DELETE_RELATIONSHIP:
                success = await self._delete_relationship(change.data)
            else:
                logger.warning(f"Unknown change type: {change.change_type}")
                return False
            
            if success:
                change.applied = True
            
            return success
            
        except Exception as e:
            logger.error(f"Error applying change {change.change_id}: {e}")
            return False
    
    async def _add_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Add an entity to the graph"""
        try:
            # Check for duplicates if enabled
            if self.config.enable_deduplication:
                existing = await self._find_similar_entities(entity_data)
                if existing:
                    logger.info(f"Found duplicate entity, merging: {entity_data.get('id', 'unknown')}")
                    return await self._merge_entities(existing[0], entity_data)
            
            # Validate entity if enabled
            if self.config.enable_validation:
                if not await self._validate_entity(entity_data):
                    logger.warning(f"Entity validation failed: {entity_data}")
                    return False
            
            # Add entity using graph engine
            result = await self.graph_engine.create_entities([entity_data])
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"Error adding entity: {e}")
            return False
    
    async def _update_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Update an entity in the graph"""
        try:
            entity_id = entity_data.get("id")
            if not entity_id:
                logger.error("No entity ID provided for update")
                return False
            
            result = await self.graph_engine.update_entity(entity_id, entity_data)
            return result is not None
            
        except Exception as e:
            logger.error(f"Error updating entity: {e}")
            return False
    
    async def _delete_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Delete an entity from the graph"""
        try:
            entity_id = entity_data.get("id")
            if not entity_id:
                logger.error("No entity ID provided for deletion")
                return False
            
            result = await self.graph_engine.delete_entity(entity_id)
            return result
            
        except Exception as e:
            logger.error(f"Error deleting entity: {e}")
            return False
    
    async def _add_relationship(self, rel_data: Dict[str, Any]) -> bool:
        """Add a relationship to the graph"""
        try:
            # Validate relationship if enabled
            if self.config.enable_validation:
                if not await self._validate_relationship(rel_data):
                    logger.warning(f"Relationship validation failed: {rel_data}")
                    return False
            
            result = await self.graph_engine.create_relationships([rel_data])
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"Error adding relationship: {e}")
            return False
    
    async def _update_relationship(self, rel_data: Dict[str, Any]) -> bool:
        """Update a relationship in the graph"""
        try:
            rel_id = rel_data.get("id")
            if not rel_id:
                logger.error("No relationship ID provided for update")
                return False
            
            # This would need to be implemented in the graph engine
            # For now, return True as placeholder
            return True
            
        except Exception as e:
            logger.error(f"Error updating relationship: {e}")
            return False
    
    async def _delete_relationship(self, rel_data: Dict[str, Any]) -> bool:
        """Delete a relationship from the graph"""
        try:
            rel_id = rel_data.get("id")
            if not rel_id:
                logger.error("No relationship ID provided for deletion")
                return False
            
            # This would need to be implemented in the graph engine
            # For now, return True as placeholder
            return True
            
        except Exception as e:
            logger.error(f"Error deleting relationship: {e}")
            return False
    
    async def _find_similar_entities(self, entity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar entities for deduplication"""
        try:
            # This would use the graph engine to find similar entities
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error finding similar entities: {e}")
            return []
    
    async def _merge_entities(self, existing: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Merge two entities"""
        try:
            # Implement entity merging logic based on conflict resolution strategy
            if self.config.conflict_resolution == "latest_wins":
                merged = {**existing, **new}
            elif self.config.conflict_resolution == "merge":
                merged = self._merge_entity_attributes(existing, new)
            else:
                # Manual resolution - for now, use latest_wins
                merged = {**existing, **new}
            
            # Update the existing entity
            return await self._update_entity(merged)
            
        except Exception as e:
            logger.error(f"Error merging entities: {e}")
            return False
    
    def _merge_entity_attributes(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Merge entity attributes intelligently"""
        merged = existing.copy()
        
        for key, value in new.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, list) and isinstance(merged[key], list):
                # Merge lists, removing duplicates
                merged[key] = list(set(merged[key] + value))
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                # Recursively merge dictionaries
                merged[key] = {**merged[key], **value}
            else:
                # Use new value for other types
                merged[key] = value
        
        return merged
    
    async def _validate_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Validate entity data"""
        try:
            # Basic validation
            if not entity_data.get("id"):
                return False
            
            if not entity_data.get("type"):
                return False
            
            # Additional validation rules can be added here
            return True
            
        except Exception as e:
            logger.error(f"Error validating entity: {e}")
            return False
    
    async def _validate_relationship(self, rel_data: Dict[str, Any]) -> bool:
        """Validate relationship data"""
        try:
            # Basic validation
            if not rel_data.get("source_id"):
                return False
            
            if not rel_data.get("target_id"):
                return False
            
            if not rel_data.get("type"):
                return False
            
            # Check if source and target entities exist
            if self.graph_engine:
                source_exists = await self.graph_engine.get_entity(rel_data["source_id"])
                target_exists = await self.graph_engine.get_entity(rel_data["target_id"])
                
                if not source_exists or not target_exists:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating relationship: {e}")
            return False
    
    async def _prepare_rollback_data(self, change: GraphChange) -> Optional[Dict[str, Any]]:
        """Prepare data needed for rollback"""
        try:
            if change.change_type in [ChangeType.UPDATE_ENTITY, ChangeType.DELETE_ENTITY]:
                entity_id = change.data.get("id")
                if entity_id and self.graph_engine:
                    return await self.graph_engine.get_entity(entity_id)
            elif change.change_type in [ChangeType.UPDATE_RELATIONSHIP, ChangeType.DELETE_RELATIONSHIP]:
                rel_id = change.data.get("id")
                if rel_id and self.graph_engine:
                    return await self.graph_engine.get_relationship(rel_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error preparing rollback data: {e}")
            return None
    
    async def _create_checkpoint(self, task_id: str):
        """Create a checkpoint for the build task"""
        try:
            logger.info(f"Creating checkpoint for task {task_id}")
            # Implementation would save current state for recovery
            pass
        except Exception as e:
            logger.error(f"Error creating checkpoint: {e}")
    
    async def rollback_changes(self, task_id: str) -> bool:
        """Rollback changes for a task"""
        try:
            if not self.config.enable_rollback:
                logger.warning("Rollback is disabled")
                return False
            
            # Find changes for this task
            task_changes = [c for c in self.change_log if c.change_id.startswith(task_id)]
            
            # Rollback changes in reverse order
            for change in reversed(task_changes):
                if change.applied and change.rollback_data:
                    await self._rollback_single_change(change)
            
            logger.info(f"Rolled back {len(task_changes)} changes for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back changes: {e}")
            return False
    
    async def _rollback_single_change(self, change: GraphChange):
        """Rollback a single change"""
        try:
            if change.change_type == ChangeType.ADD_ENTITY:
                await self._delete_entity(change.data)
            elif change.change_type == ChangeType.DELETE_ENTITY:
                await self._add_entity(change.rollback_data)
            elif change.change_type == ChangeType.UPDATE_ENTITY:
                await self._update_entity(change.rollback_data)
            # Add similar logic for relationships
            
        except Exception as e:
            logger.error(f"Error rolling back change: {e}")
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            **self.performance_metrics,
            "active_tasks": len(self.active_tasks),
            "queued_tasks": len(self.task_queue),
            "total_changes_logged": len(self.change_log)
        }
    
    async def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """Clean up completed tasks older than specified hours"""
        try:
            cutoff_time = datetime.now().timestamp() - (older_than_hours * 3600)
            
            async with self._task_lock:
                tasks_to_remove = []
                for task_id, task in self.active_tasks.items():
                    if (task.status in [BuildStatus.COMPLETED, BuildStatus.FAILED, BuildStatus.CANCELLED] and
                        task.completed_at and task.completed_at.timestamp() < cutoff_time):
                        tasks_to_remove.append(task_id)
                
                for task_id in tasks_to_remove:
                    del self.active_tasks[task_id]
            
            logger.info(f"Cleaned up {len(tasks_to_remove)} completed tasks")
            
        except Exception as e:
            logger.error(f"Error cleaning up tasks: {e}")
    
    async def shutdown(self):
        """Shutdown the incremental builder"""
        try:
            logger.info("Shutting down incremental builder...")
            
            # Signal workers to stop
            self.shutdown_event.set()
            
            # Cancel all workers
            for worker in self.workers:
                worker.cancel()
            
            # Wait for workers to finish
            await asyncio.gather(*self.workers, return_exceptions=True)
            
            # Cancel pending tasks
            async with self._task_lock:
                for task in self.active_tasks.values():
                    if task.status in [BuildStatus.PENDING, BuildStatus.RUNNING]:
                        task.status = BuildStatus.CANCELLED
                        task.completed_at = datetime.now()
            
            logger.info("Incremental builder shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")