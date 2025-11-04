"""
Core Graph Engine for Knowledge Graph operations.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid
from dataclasses import dataclass, asdict

@dataclass
class GraphEntity:
    id: str
    type: str
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
@dataclass
class GraphRelationship:
    id: str
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any]
    strength: float
    created_at: datetime
    updated_at: datetime

class GraphEngine:
    """Core engine for knowledge graph operations."""
    
    def __init__(self, primary_storage=None, secondary_storage=None, cache=None):
        self.logger = logging.getLogger(__name__)
        self.primary_storage = primary_storage
        self.secondary_storage = secondary_storage
        self.cache = cache
        
        # Service registries
        self.extractors = {}
        self.builders = {}
        self.algorithms = {}
        
        # Build task tracking
        self.build_tasks = {}
        
        # Statistics
        self.stats = {
            "entities": 0,
            "relationships": 0,
            "queries_executed": 0,
            "last_updated": datetime.now()
        }
    
    async def initialize(self):
        """Initialize the graph engine"""
        try:
            if self.primary_storage:
                await self.primary_storage.connect()
            if self.secondary_storage:
                await self.secondary_storage.connect()
            if self.cache:
                await self.cache.connect()
            
            # Load initial statistics
            await self._load_statistics()
            
            self.logger.info("Graph engine initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize graph engine: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the graph engine"""
        try:
            if self.primary_storage:
                await self.primary_storage.disconnect()
            if self.secondary_storage:
                await self.secondary_storage.disconnect()
            if self.cache:
                await self.cache.disconnect()
            
            self.logger.info("Graph engine shutdown completed")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    # Entity Management
    async def create_entities(self, entities: List[Dict[str, Any]]) -> List[GraphEntity]:
        """Create new entities in the graph"""
        created_entities = []
        
        for entity_data in entities:
            try:
                entity = GraphEntity(
                    id=entity_data.get('id', str(uuid.uuid4())),
                    type=entity_data['type'],
                    properties=entity_data.get('properties', {}),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                # Store in primary storage
                if self.primary_storage:
                    await self.primary_storage.create_entity(asdict(entity))
                
                # Store in secondary storage
                if self.secondary_storage:
                    await self.secondary_storage.create_entity(asdict(entity))
                
                # Cache entity
                if self.cache:
                    await self.cache.set_entity(entity.id, asdict(entity))
                
                created_entities.append(entity)
                self.stats["entities"] += 1
                
            except Exception as e:
                self.logger.error(f"Error creating entity: {e}")
                continue
        
        await self._update_statistics()
        return created_entities
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID"""
        try:
            # Try cache first
            if self.cache:
                cached_entity = await self.cache.get_entity(entity_id)
                if cached_entity:
                    return cached_entity
            
            # Try primary storage
            if self.primary_storage:
                entity = await self.primary_storage.get_entity(entity_id)
                if entity:
                    # Cache for future use
                    if self.cache:
                        await self.cache.set_entity(entity_id, entity)
                    return entity
            
            # Try secondary storage
            if self.secondary_storage:
                entity = await self.secondary_storage.get_entity(entity_id)
                if entity:
                    # Cache for future use
                    if self.cache:
                        await self.cache.set_entity(entity_id, entity)
                    return entity
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting entity {entity_id}: {e}")
            return None
    
    async def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update entity"""
        try:
            # Get current entity
            current_entity = await self.get_entity(entity_id)
            if not current_entity:
                return None
            
            # Apply updates
            current_entity['properties'].update(updates.get('properties', {}))
            if 'type' in updates:
                current_entity['type'] = updates['type']
            current_entity['updated_at'] = datetime.now().isoformat()
            
            # Update in storages
            if self.primary_storage:
                await self.primary_storage.update_entity(entity_id, current_entity)
            
            if self.secondary_storage:
                await self.secondary_storage.update_entity(entity_id, current_entity)
            
            # Update cache
            if self.cache:
                await self.cache.set_entity(entity_id, current_entity)
            
            return current_entity
            
        except Exception as e:
            self.logger.error(f"Error updating entity {entity_id}: {e}")
            return None
    
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity"""
        try:
            # Delete from storages
            success = True
            
            if self.primary_storage:
                success &= await self.primary_storage.delete_entity(entity_id)
            
            if self.secondary_storage:
                await self.secondary_storage.delete_entity(entity_id)
            
            # Remove from cache
            if self.cache:
                await self.cache.delete_entity(entity_id)
            
            if success:
                self.stats["entities"] -= 1
                await self._update_statistics()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error deleting entity {entity_id}: {e}")
            return False
    
    # Relationship Management
    async def create_relationships(self, relationships: List[Dict[str, Any]]) -> List[GraphRelationship]:
        """Create new relationships in the graph"""
        created_relationships = []
        
        for rel_data in relationships:
            try:
                relationship = GraphRelationship(
                    id=rel_data.get('id', str(uuid.uuid4())),
                    source_id=rel_data['source_id'],
                    target_id=rel_data['target_id'],
                    type=rel_data['type'],
                    properties=rel_data.get('properties', {}),
                    strength=rel_data.get('strength', 1.0),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                # Store in primary storage
                if self.primary_storage:
                    await self.primary_storage.create_relationship(asdict(relationship))
                
                # Store in secondary storage
                if self.secondary_storage:
                    await self.secondary_storage.create_relationship(asdict(relationship))
                
                # Cache relationship
                if self.cache:
                    await self.cache.set_relationship(relationship.id, asdict(relationship))
                
                created_relationships.append(relationship)
                self.stats["relationships"] += 1
                
            except Exception as e:
                self.logger.error(f"Error creating relationship: {e}")
                continue
        
        await self._update_statistics()
        return created_relationships
    
    async def get_relationship(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """Get relationship by ID"""
        try:
            # Try cache first
            if self.cache:
                cached_rel = await self.cache.get_relationship(relationship_id)
                if cached_rel:
                    return cached_rel
            
            # Try primary storage
            if self.primary_storage:
                relationship = await self.primary_storage.get_relationship(relationship_id)
                if relationship:
                    # Cache for future use
                    if self.cache:
                        await self.cache.set_relationship(relationship_id, relationship)
                    return relationship
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting relationship {relationship_id}: {e}")
            return None
    
    # Service Registry Methods
    async def register_extractor(self, name: str, extractor):
        """Register an entity/relationship extractor"""
        self.extractors[name] = extractor
        await extractor.initialize() if hasattr(extractor, 'initialize') else None
        self.logger.info(f"Registered extractor: {name}")
    
    async def register_builder(self, name: str, builder):
        """Register a graph builder"""
        self.builders[name] = builder
        await builder.initialize() if hasattr(builder, 'initialize') else None
        self.logger.info(f"Registered builder: {name}")
    
    async def register_algorithm(self, name: str, algorithm):
        """Register a graph algorithm"""
        self.algorithms[name] = algorithm
        await algorithm.initialize() if hasattr(algorithm, 'initialize') else None
        self.logger.info(f"Registered algorithm: {name}")
    
    async def get_extractor(self, name: str):
        """Get registered extractor"""
        return self.extractors.get(name)
    
    async def get_builder(self, name: str):
        """Get registered builder"""
        return self.builders.get(name)
    
    async def get_algorithm(self, name: str):
        """Get registered algorithm"""
        return self.algorithms.get(name)
    
    # Search and Query Methods
    async def search_entities(self, query: str, entity_types: Optional[List[str]] = None, 
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Search entities by text query"""
        try:
            results = []
            
            if self.primary_storage:
                primary_results = await self.primary_storage.search_entities(
                    query, entity_types, limit
                )
                results.extend(primary_results)
            
            # Remove duplicates and sort by relevance
            unique_results = {r['id']: r for r in results}.values()
            return list(unique_results)[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching entities: {e}")
            return []
    
    async def get_entity_relationships(self, entity_id: str, 
                                     relationship_types: Optional[List[str]] = None,
                                     direction: str = "both") -> List[Dict[str, Any]]:
        """Get relationships for an entity"""
        try:
            if self.primary_storage:
                return await self.primary_storage.get_entity_relationships(
                    entity_id, relationship_types, direction
                )
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting entity relationships: {e}")
            return []
    
    async def get_subgraph(self, entity_ids: List[str], max_hops: int = 2) -> Dict[str, Any]:
        """Extract subgraph around given entities"""
        try:
            if self.primary_storage:
                return await self.primary_storage.get_subgraph(entity_ids, max_hops)
            return {"entities": [], "relationships": []}
            
        except Exception as e:
            self.logger.error(f"Error getting subgraph: {e}")
            return {"entities": [], "relationships": []}
    
    # Build Task Management
    async def get_build_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get build task status"""
        return self.build_tasks.get(task_id)
    
    async def register_build_task(self, task_id: str, task_info: Dict[str, Any]):
        """Register a build task"""
        self.build_tasks[task_id] = {
            **task_info,
            "created_at": datetime.now().isoformat(),
            "status": "running"
        }
    
    async def update_build_task(self, task_id: str, updates: Dict[str, Any]):
        """Update build task status"""
        if task_id in self.build_tasks:
            self.build_tasks[task_id].update(updates)
            self.build_tasks[task_id]["updated_at"] = datetime.now().isoformat()
    
    # Statistics and Monitoring
    async def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        # Refresh statistics from storage
        await self._load_statistics()
        return self.stats.copy()
    
    async def _load_statistics(self):
        """Load statistics from storage"""
        try:
            if self.primary_storage:
                storage_stats = await self.primary_storage.get_statistics()
                self.stats.update(storage_stats)
                self.stats["last_updated"] = datetime.now()
        except Exception as e:
            self.logger.error(f"Error loading statistics: {e}")
    
    async def _update_statistics(self):
        """Update statistics"""
        self.stats["last_updated"] = datetime.now()
        
        # Optionally persist to storage
        if self.primary_storage:
            try:
                await self.primary_storage.update_statistics(self.stats)
            except Exception as e:
                self.logger.error(f"Error updating statistics: {e}")
    
    # Health and Diagnostics
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Check primary storage
        if self.primary_storage:
            try:
                await self.primary_storage.health_check()
                health["components"]["primary_storage"] = "healthy"
            except Exception as e:
                health["components"]["primary_storage"] = f"unhealthy: {e}"
                health["status"] = "degraded"
        
        # Check secondary storage
        if self.secondary_storage:
            try:
                await self.secondary_storage.health_check()
                health["components"]["secondary_storage"] = "healthy"
            except Exception as e:
                health["components"]["secondary_storage"] = f"unhealthy: {e}"
        
        # Check cache
        if self.cache:
            try:
                await self.cache.health_check()
                health["components"]["cache"] = "healthy"
            except Exception as e:
                health["components"]["cache"] = f"unhealthy: {e}"
        
        return health