"""
Temporal Knowledge Graph Service.
Handles time-aware entities, relationships, and temporal queries.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

class TemporalRelationType(Enum):
    VALID_TIME = "valid_time"  # When the fact was true in the real world
    TRANSACTION_TIME = "transaction_time"  # When the fact was stored in the database
    BOTH = "both"

class TemporalQueryType(Enum):
    SNAPSHOT = "snapshot"  # State at specific time
    EVOLUTION = "evolution"  # Changes over time
    TEMPORAL_JOIN = "temporal_join"  # Join entities at specific time
    DURATION = "duration"  # How long something was true
    SUCCESSION = "succession"  # What happened before/after

@dataclass
class TemporalInterval:
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    
    def __post_init__(self):
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("Start time cannot be after end time")
    
    def contains(self, timestamp: datetime) -> bool:
        """Check if timestamp is within interval"""
        start_ok = self.start_time is None or timestamp >= self.start_time
        end_ok = self.end_time is None or timestamp <= self.end_time
        return start_ok and end_ok
    
    def overlaps(self, other: 'TemporalInterval') -> bool:
        """Check if this interval overlaps with another"""
        if self.end_time and other.start_time and self.end_time < other.start_time:
            return False
        if self.start_time and other.end_time and self.start_time > other.end_time:
            return False
        return True
    
    def duration(self) -> Optional[timedelta]:
        """Get duration of interval"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

@dataclass
class TemporalEntity:
    entity_id: str
    entity_data: Dict[str, Any]
    valid_time: TemporalInterval
    transaction_time: TemporalInterval
    version: int = 1

@dataclass
class TemporalRelationship:
    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: str
    properties: Dict[str, Any]
    valid_time: TemporalInterval
    transaction_time: TemporalInterval
    strength: float = 1.0
    version: int = 1

@dataclass
class TemporalQuery:
    query_type: TemporalQueryType
    target_time: Optional[datetime] = None
    time_range: Optional[TemporalInterval] = None
    entity_ids: Optional[List[str]] = None
    relationship_types: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None

class TemporalGraphService:
    """Service for temporal knowledge graph operations."""
    
    def __init__(self, graph_engine):
        self.logger = logging.getLogger(__name__)
        self.graph_engine = graph_engine
        
        # Temporal storage
        self.temporal_entities = {}  # entity_id -> List[TemporalEntity]
        self.temporal_relationships = {}  # rel_id -> List[TemporalRelationship]
        self.entity_versions = {}  # entity_id -> current_version
        self.relationship_versions = {}  # rel_id -> current_version
        
        # Temporal indexes
        self.time_index = {}  # timestamp -> [entity_ids, relationship_ids]
        self.entity_time_index = {}  # entity_id -> [timestamps]
        
        # Statistics
        self.stats = {
            "temporal_entities": 0,
            "temporal_relationships": 0,
            "temporal_queries": 0,
            "snapshots_created": 0,
            "evolution_queries": 0
        }
    
    async def initialize(self):
        """Initialize temporal graph service"""
        await self._build_temporal_indexes()
        self.logger.info("Temporal graph service initialized")
    
    async def create_temporal_entity(self, entity_data: Dict[str, Any], 
                                   valid_time: TemporalInterval = None,
                                   transaction_time: TemporalInterval = None) -> str:
        """Create a temporal entity"""
        try:
            entity_id = entity_data.get("id")
            if not entity_id:
                # Create new entity in base graph
                created_entities = await self.graph_engine.create_entities([entity_data])
                if not created_entities:
                    raise ValueError("Failed to create base entity")
                entity_id = created_entities[0].id
            
            # Set default temporal intervals
            now = datetime.now()
            if valid_time is None:
                valid_time = TemporalInterval(now, None)  # Valid from now, indefinitely
            if transaction_time is None:
                transaction_time = TemporalInterval(now, None)
            
            # Create temporal entity
            version = self.entity_versions.get(entity_id, 0) + 1
            temporal_entity = TemporalEntity(
                entity_id=entity_id,
                entity_data=entity_data,
                valid_time=valid_time,
                transaction_time=transaction_time,
                version=version
            )
            
            # Store temporal entity
            if entity_id not in self.temporal_entities:
                self.temporal_entities[entity_id] = []
            
            self.temporal_entities[entity_id].append(temporal_entity)
            self.entity_versions[entity_id] = version
            
            # Update indexes
            await self._update_temporal_indexes(temporal_entity)
            
            self.stats["temporal_entities"] += 1
            self.logger.info(f"Created temporal entity: {entity_id} (version {version})")
            
            return entity_id
            
        except Exception as e:
            self.logger.error(f"Error creating temporal entity: {e}")
            raise
    
    async def create_temporal_relationship(self, source_id: str, target_id: str, 
                                         relationship_type: str, properties: Dict[str, Any] = None,
                                         valid_time: TemporalInterval = None,
                                         transaction_time: TemporalInterval = None,
                                         strength: float = 1.0) -> str:
        """Create a temporal relationship"""
        try:
            # Create base relationship
            rel_data = {
                "source_id": source_id,
                "target_id": target_id,
                "type": relationship_type,
                "properties": properties or {},
                "strength": strength
            }
            
            created_rels = await self.graph_engine.create_relationships([rel_data])
            if not created_rels:
                raise ValueError("Failed to create base relationship")
            
            relationship_id = created_rels[0].id
            
            # Set default temporal intervals
            now = datetime.now()
            if valid_time is None:
                valid_time = TemporalInterval(now, None)
            if transaction_time is None:
                transaction_time = TemporalInterval(now, None)
            
            # Create temporal relationship
            version = self.relationship_versions.get(relationship_id, 0) + 1
            temporal_rel = TemporalRelationship(
                relationship_id=relationship_id,
                source_id=source_id,
                target_id=target_id,
                relationship_type=relationship_type,
                properties=properties or {},
                valid_time=valid_time,
                transaction_time=transaction_time,
                strength=strength,
                version=version
            )
            
            # Store temporal relationship
            if relationship_id not in self.temporal_relationships:
                self.temporal_relationships[relationship_id] = []
            
            self.temporal_relationships[relationship_id].append(temporal_rel)
            self.relationship_versions[relationship_id] = version
            
            # Update indexes
            await self._update_temporal_indexes(temporal_rel)
            
            self.stats["temporal_relationships"] += 1
            self.logger.info(f"Created temporal relationship: {relationship_id} (version {version})")
            
            return relationship_id
            
        except Exception as e:
            self.logger.error(f"Error creating temporal relationship: {e}")
            raise
    
    async def update_temporal_entity(self, entity_id: str, updates: Dict[str, Any],
                                   valid_time: TemporalInterval = None) -> bool:
        """Update temporal entity (creates new version)"""
        try:
            # Get current entity
            current_entities = self.temporal_entities.get(entity_id, [])
            if not current_entities:
                return False
            
            # Get latest version
            latest_entity = max(current_entities, key=lambda x: x.version)
            
            # Create updated entity data
            updated_data = latest_entity.entity_data.copy()
            updated_data.update(updates)
            
            # Set temporal intervals
            now = datetime.now()
            if valid_time is None:
                valid_time = TemporalInterval(now, None)
            
            # End previous version's valid time
            if latest_entity.valid_time.end_time is None:
                latest_entity.valid_time.end_time = now
            
            # Create new version
            new_version = latest_entity.version + 1
            new_temporal_entity = TemporalEntity(
                entity_id=entity_id,
                entity_data=updated_data,
                valid_time=valid_time,
                transaction_time=TemporalInterval(now, None),
                version=new_version
            )
            
            # Store new version
            self.temporal_entities[entity_id].append(new_temporal_entity)
            self.entity_versions[entity_id] = new_version
            
            # Update base entity
            await self.graph_engine.update_entity(entity_id, updates)
            
            # Update indexes
            await self._update_temporal_indexes(new_temporal_entity)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating temporal entity: {e}")
            return False
    
    async def get_entity_at_time(self, entity_id: str, timestamp: datetime,
                               time_type: TemporalRelationType = TemporalRelationType.VALID_TIME) -> Optional[TemporalEntity]:
        """Get entity state at specific time"""
        try:
            entities = self.temporal_entities.get(entity_id, [])
            if not entities:
                return None
            
            # Find entity valid at timestamp
            for entity in entities:
                if time_type == TemporalRelationType.VALID_TIME:
                    if entity.valid_time.contains(timestamp):
                        return entity
                elif time_type == TemporalRelationType.TRANSACTION_TIME:
                    if entity.transaction_time.contains(timestamp):
                        return entity
                elif time_type == TemporalRelationType.BOTH:
                    if (entity.valid_time.contains(timestamp) and 
                        entity.transaction_time.contains(timestamp)):
                        return entity
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting entity at time: {e}")
            return None
    
    async def get_entity_evolution(self, entity_id: str, 
                                 time_range: TemporalInterval = None) -> List[TemporalEntity]:
        """Get evolution of entity over time"""
        try:
            entities = self.temporal_entities.get(entity_id, [])
            if not entities:
                return []
            
            if time_range is None:
                return sorted(entities, key=lambda x: x.version)
            
            # Filter by time range
            filtered_entities = []
            for entity in entities:
                if entity.valid_time.overlaps(time_range):
                    filtered_entities.append(entity)
            
            return sorted(filtered_entities, key=lambda x: x.version)
            
        except Exception as e:
            self.logger.error(f"Error getting entity evolution: {e}")
            return []
    
    async def execute_temporal_query(self, query: TemporalQuery) -> Dict[str, Any]:
        """Execute temporal query"""
        try:
            self.stats["temporal_queries"] += 1
            
            if query.query_type == TemporalQueryType.SNAPSHOT:
                return await self._execute_snapshot_query(query)
            elif query.query_type == TemporalQueryType.EVOLUTION:
                return await self._execute_evolution_query(query)
            elif query.query_type == TemporalQueryType.TEMPORAL_JOIN:
                return await self._execute_temporal_join_query(query)
            elif query.query_type == TemporalQueryType.DURATION:
                return await self._execute_duration_query(query)
            elif query.query_type == TemporalQueryType.SUCCESSION:
                return await self._execute_succession_query(query)
            else:
                raise ValueError(f"Unsupported query type: {query.query_type}")
            
        except Exception as e:
            self.logger.error(f"Error executing temporal query: {e}")
            return {"error": str(e)}
    
    async def _execute_snapshot_query(self, query: TemporalQuery) -> Dict[str, Any]:
        """Execute snapshot query - get graph state at specific time"""
        try:
            if not query.target_time:
                raise ValueError("Snapshot query requires target_time")
            
            snapshot_entities = []
            snapshot_relationships = []
            
            # Get entities at target time
            if query.entity_ids:
                entity_ids = query.entity_ids
            else:
                entity_ids = list(self.temporal_entities.keys())
            
            for entity_id in entity_ids:
                entity = await self.get_entity_at_time(entity_id, query.target_time)
                if entity:
                    snapshot_entities.append(entity)
            
            # Get relationships at target time
            for rel_id, rel_versions in self.temporal_relationships.items():
                for rel in rel_versions:
                    if rel.valid_time.contains(query.target_time):
                        # Check if relationship type matches filter
                        if (not query.relationship_types or 
                            rel.relationship_type in query.relationship_types):
                            snapshot_relationships.append(rel)
                        break  # Only one version per relationship at a time
            
            self.stats["snapshots_created"] += 1
            
            return {
                "query_type": "snapshot",
                "target_time": query.target_time.isoformat(),
                "entities": [self._temporal_entity_to_dict(e) for e in snapshot_entities],
                "relationships": [self._temporal_relationship_to_dict(r) for r in snapshot_relationships],
                "count": {
                    "entities": len(snapshot_entities),
                    "relationships": len(snapshot_relationships)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in snapshot query: {e}")
            return {"error": str(e)}
    
    async def _execute_evolution_query(self, query: TemporalQuery) -> Dict[str, Any]:
        """Execute evolution query - get changes over time"""
        try:
            if not query.entity_ids:
                raise ValueError("Evolution query requires entity_ids")
            
            evolution_data = {}
            
            for entity_id in query.entity_ids:
                evolution = await self.get_entity_evolution(entity_id, query.time_range)
                if evolution:
                    evolution_data[entity_id] = [
                        self._temporal_entity_to_dict(e) for e in evolution
                    ]
            
            self.stats["evolution_queries"] += 1
            
            return {
                "query_type": "evolution",
                "time_range": {
                    "start": query.time_range.start_time.isoformat() if query.time_range and query.time_range.start_time else None,
                    "end": query.time_range.end_time.isoformat() if query.time_range and query.time_range.end_time else None
                },
                "evolution_data": evolution_data,
                "entities_tracked": len(evolution_data)
            }
            
        except Exception as e:
            self.logger.error(f"Error in evolution query: {e}")
            return {"error": str(e)}
    
    async def _execute_temporal_join_query(self, query: TemporalQuery) -> Dict[str, Any]:
        """Execute temporal join query - join entities at specific time"""
        try:
            if not query.target_time or not query.entity_ids or len(query.entity_ids) < 2:
                raise ValueError("Temporal join requires target_time and at least 2 entity_ids")
            
            # Get entities at target time
            joined_entities = []
            for entity_id in query.entity_ids:
                entity = await self.get_entity_at_time(entity_id, query.target_time)
                if entity:
                    joined_entities.append(entity)
            
            # Find relationships between these entities at target time
            connecting_relationships = []
            entity_ids_set = set(query.entity_ids)
            
            for rel_id, rel_versions in self.temporal_relationships.items():
                for rel in rel_versions:
                    if (rel.valid_time.contains(query.target_time) and
                        rel.source_id in entity_ids_set and
                        rel.target_id in entity_ids_set):
                        connecting_relationships.append(rel)
                        break
            
            return {
                "query_type": "temporal_join",
                "target_time": query.target_time.isoformat(),
                "joined_entities": [self._temporal_entity_to_dict(e) for e in joined_entities],
                "connecting_relationships": [self._temporal_relationship_to_dict(r) for r in connecting_relationships],
                "join_success": len(joined_entities) == len(query.entity_ids)
            }
            
        except Exception as e:
            self.logger.error(f"Error in temporal join query: {e}")
            return {"error": str(e)}
    
    async def _execute_duration_query(self, query: TemporalQuery) -> Dict[str, Any]:
        """Execute duration query - calculate how long facts were true"""
        try:
            if not query.entity_ids:
                raise ValueError("Duration query requires entity_ids")
            
            duration_data = {}
            
            for entity_id in query.entity_ids:
                entities = self.temporal_entities.get(entity_id, [])
                entity_durations = []
                
                for entity in entities:
                    duration = entity.valid_time.duration()
                    if duration:
                        entity_durations.append({
                            "version": entity.version,
                            "start_time": entity.valid_time.start_time.isoformat(),
                            "end_time": entity.valid_time.end_time.isoformat(),
                            "duration_seconds": duration.total_seconds(),
                            "duration_days": duration.days
                        })
                    else:
                        entity_durations.append({
                            "version": entity.version,
                            "start_time": entity.valid_time.start_time.isoformat() if entity.valid_time.start_time else None,
                            "end_time": None,
                            "duration_seconds": None,
                            "duration_days": None,
                            "status": "ongoing"
                        })
                
                duration_data[entity_id] = entity_durations
            
            return {
                "query_type": "duration",
                "duration_data": duration_data
            }
            
        except Exception as e:
            self.logger.error(f"Error in duration query: {e}")
            return {"error": str(e)}
    
    async def _execute_succession_query(self, query: TemporalQuery) -> Dict[str, Any]:
        """Execute succession query - find what happened before/after"""
        try:
            if not query.target_time or not query.entity_ids:
                raise ValueError("Succession query requires target_time and entity_ids")
            
            succession_data = {}
            
            for entity_id in query.entity_ids:
                entities = self.temporal_entities.get(entity_id, [])
                
                before_events = []
                after_events = []
                
                for entity in entities:
                    if entity.valid_time.start_time and entity.valid_time.start_time < query.target_time:
                        before_events.append({
                            "version": entity.version,
                            "start_time": entity.valid_time.start_time.isoformat(),
                            "end_time": entity.valid_time.end_time.isoformat() if entity.valid_time.end_time else None,
                            "data": entity.entity_data
                        })
                    elif entity.valid_time.start_time and entity.valid_time.start_time > query.target_time:
                        after_events.append({
                            "version": entity.version,
                            "start_time": entity.valid_time.start_time.isoformat(),
                            "end_time": entity.valid_time.end_time.isoformat() if entity.valid_time.end_time else None,
                            "data": entity.entity_data
                        })
                
                # Sort by time
                before_events.sort(key=lambda x: x["start_time"])
                after_events.sort(key=lambda x: x["start_time"])
                
                succession_data[entity_id] = {
                    "before": before_events,
                    "after": after_events
                }
            
            return {
                "query_type": "succession",
                "reference_time": query.target_time.isoformat(),
                "succession_data": succession_data
            }
            
        except Exception as e:
            self.logger.error(f"Error in succession query: {e}")
            return {"error": str(e)}
    
    async def _update_temporal_indexes(self, temporal_item):
        """Update temporal indexes"""
        try:
            if isinstance(temporal_item, TemporalEntity):
                entity_id = temporal_item.entity_id
                
                # Update entity time index
                if entity_id not in self.entity_time_index:
                    self.entity_time_index[entity_id] = []
                
                if temporal_item.valid_time.start_time:
                    self.entity_time_index[entity_id].append(temporal_item.valid_time.start_time)
                
                # Update global time index
                for timestamp in [temporal_item.valid_time.start_time, temporal_item.valid_time.end_time]:
                    if timestamp:
                        timestamp_key = timestamp.isoformat()
                        if timestamp_key not in self.time_index:
                            self.time_index[timestamp_key] = {"entities": [], "relationships": []}
                        
                        if entity_id not in self.time_index[timestamp_key]["entities"]:
                            self.time_index[timestamp_key]["entities"].append(entity_id)
            
            elif isinstance(temporal_item, TemporalRelationship):
                rel_id = temporal_item.relationship_id
                
                # Update global time index
                for timestamp in [temporal_item.valid_time.start_time, temporal_item.valid_time.end_time]:
                    if timestamp:
                        timestamp_key = timestamp.isoformat()
                        if timestamp_key not in self.time_index:
                            self.time_index[timestamp_key] = {"entities": [], "relationships": []}
                        
                        if rel_id not in self.time_index[timestamp_key]["relationships"]:
                            self.time_index[timestamp_key]["relationships"].append(rel_id)
            
        except Exception as e:
            self.logger.error(f"Error updating temporal indexes: {e}")
    
    async def _build_temporal_indexes(self):
        """Build temporal indexes from existing data"""
        try:
            # Build indexes for entities
            for entity_id, entity_versions in self.temporal_entities.items():
                for entity in entity_versions:
                    await self._update_temporal_indexes(entity)
            
            # Build indexes for relationships
            for rel_id, rel_versions in self.temporal_relationships.items():
                for rel in rel_versions:
                    await self._update_temporal_indexes(rel)
            
            self.logger.info("Temporal indexes built successfully")
            
        except Exception as e:
            self.logger.error(f"Error building temporal indexes: {e}")
    
    def _temporal_entity_to_dict(self, entity: TemporalEntity) -> Dict[str, Any]:
        """Convert temporal entity to dictionary"""
        return {
            "entity_id": entity.entity_id,
            "entity_data": entity.entity_data,
            "valid_time": {
                "start": entity.valid_time.start_time.isoformat() if entity.valid_time.start_time else None,
                "end": entity.valid_time.end_time.isoformat() if entity.valid_time.end_time else None
            },
            "transaction_time": {
                "start": entity.transaction_time.start_time.isoformat() if entity.transaction_time.start_time else None,
                "end": entity.transaction_time.end_time.isoformat() if entity.transaction_time.end_time else None
            },
            "version": entity.version
        }
    
    def _temporal_relationship_to_dict(self, rel: TemporalRelationship) -> Dict[str, Any]:
        """Convert temporal relationship to dictionary"""
        return {
            "relationship_id": rel.relationship_id,
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "relationship_type": rel.relationship_type,
            "properties": rel.properties,
            "valid_time": {
                "start": rel.valid_time.start_time.isoformat() if rel.valid_time.start_time else None,
                "end": rel.valid_time.end_time.isoformat() if rel.valid_time.end_time else None
            },
            "transaction_time": {
                "start": rel.transaction_time.start_time.isoformat() if rel.transaction_time.start_time else None,
                "end": rel.transaction_time.end_time.isoformat() if rel.transaction_time.end_time else None
            },
            "strength": rel.strength,
            "version": rel.version
        }
    
    async def get_temporal_statistics(self) -> Dict[str, Any]:
        """Get temporal graph statistics"""
        return {
            **self.stats,
            "total_entity_versions": sum(len(versions) for versions in self.temporal_entities.values()),
            "total_relationship_versions": sum(len(versions) for versions in self.temporal_relationships.values()),
            "indexed_timestamps": len(self.time_index),
            "entities_with_temporal_data": len(self.temporal_entities),
            "relationships_with_temporal_data": len(self.temporal_relationships)
        }
    
    async def shutdown(self):
        """Shutdown temporal graph service"""
        self.temporal_entities.clear()
        self.temporal_relationships.clear()
        self.time_index.clear()
        self.entity_time_index.clear()
        self.logger.info("Temporal graph service shutdown")