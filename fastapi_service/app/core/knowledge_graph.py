"""
Knowledge graph engine with entity extraction and relationship mapping
"""

import asyncio
import logging
import time
import json
import hashlib
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import networkx as nx
import numpy as np

# NLP libraries for entity extraction
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Graph database integrations
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

try:
    from arango import ArangoClient
    ARANGO_AVAILABLE = True
except ImportError:
    ARANGO_AVAILABLE = False

from ..core.config import settings

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Common entity types"""
    PERSON = "PERSON"
    ORGANIZATION = "ORG"
    LOCATION = "LOC"
    MISCELLANEOUS = "MISC"
    DATE = "DATE"
    TIME = "TIME"
    MONEY = "MONEY"
    PERCENT = "PERCENT"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    CONCEPT = "CONCEPT"
    TECHNOLOGY = "TECH"
    DOCUMENT = "DOCUMENT"


class RelationshipType(Enum):
    """Common relationship types"""
    WORKS_FOR = "WORKS_FOR"
    LOCATED_IN = "LOCATED_IN"
    PART_OF = "PART_OF"
    RELATED_TO = "RELATED_TO"
    SIMILAR_TO = "SIMILAR_TO"
    CAUSED_BY = "CAUSED_BY"
    LEADS_TO = "LEADS_TO"
    CONTAINS = "CONTAINS"
    MENTIONED_IN = "MENTIONED_IN"
    CO_OCCURS_WITH = "CO_OCCURS_WITH"
    TEMPORAL_BEFORE = "TEMPORAL_BEFORE"
    TEMPORAL_AFTER = "TEMPORAL_AFTER"
    HIERARCHICAL_PARENT = "HIERARCHICAL_PARENT"
    HIERARCHICAL_CHILD = "HIERARCHICAL_CHILD"


@dataclass
class Entity:
    """Knowledge graph entity"""
    id: str
    name: str
    type: EntityType
    aliases: List[str]
    attributes: Dict[str, Any]
    confidence: float
    source: str
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "aliases": self.aliases,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Relationship:
    """Knowledge graph relationship"""
    id: str
    source_entity_id: str
    target_entity_id: str
    type: RelationshipType
    attributes: Dict[str, Any]
    strength: float
    confidence: float
    source: str
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "type": self.type.value,
            "attributes": self.attributes,
            "strength": self.strength,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class GraphPath:
    """Path between entities in the graph"""
    start_entity: str
    end_entity: str
    path: List[Dict[str, Any]]
    length: int
    total_strength: float
    confidence: float


class GraphDatabase(ABC):
    """Abstract graph database interface"""
    
    @abstractmethod
    async def create_entity(self, entity: Entity) -> str:
        """Create an entity in the graph"""
        pass
    
    @abstractmethod
    async def create_relationship(self, relationship: Relationship) -> str:
        """Create a relationship in the graph"""
        pass
    
    @abstractmethod
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def find_entities(
        self, 
        name: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        limit: int = 100
    ) -> List[Entity]:
        """Find entities by criteria"""
        pass
    
    @abstractmethod
    async def get_entity_relationships(
        self,
        entity_id: str,
        relationship_types: Optional[List[RelationshipType]] = None,
        direction: str = "both"
    ) -> List[Relationship]:
        """Get relationships for an entity"""
        pass
    
    @abstractmethod
    async def find_path(
        self,
        start_entity_id: str,
        end_entity_id: str,
        max_hops: int = 3,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> Optional[GraphPath]:
        """Find path between entities"""
        pass


class Neo4jGraphDatabase(GraphDatabase):
    """Neo4j graph database implementation"""
    
    def __init__(self, uri: str, user: str, password: str):
        if not NEO4J_AVAILABLE:
            raise ImportError("Neo4j driver not available")
        
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    async def create_entity(self, entity: Entity) -> str:
        """Create entity in Neo4j"""
        async with self.driver.session() as session:
            query = """
            MERGE (e:Entity {id: $id})
            SET e.name = $name,
                e.type = $type,
                e.aliases = $aliases,
                e.attributes = $attributes,
                e.confidence = $confidence,
                e.source = $source,
                e.created_at = $created_at,
                e.updated_at = $updated_at
            RETURN e.id
            """
            
            result = await session.run(query, **entity.to_dict())
            record = await result.single()
            return record["e.id"]
    
    async def create_relationship(self, relationship: Relationship) -> str:
        """Create relationship in Neo4j"""
        async with self.driver.session() as session:
            query = """
            MATCH (s:Entity {id: $source_entity_id})
            MATCH (t:Entity {id: $target_entity_id})
            MERGE (s)-[r:RELATED {id: $id, type: $type}]->(t)
            SET r.attributes = $attributes,
                r.strength = $strength,
                r.confidence = $confidence,
                r.source = $source,
                r.created_at = $created_at,
                r.updated_at = $updated_at
            RETURN r.id
            """
            
            result = await session.run(query, **relationship.to_dict())
            record = await result.single()
            return record["r.id"]
    
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity from Neo4j"""
        async with self.driver.session() as session:
            query = "MATCH (e:Entity {id: $entity_id}) RETURN e"
            result = await session.run(query, entity_id=entity_id)
            record = await result.single()
            
            if record:
                entity_data = record["e"]
                return Entity(
                    id=entity_data["id"],
                    name=entity_data["name"],
                    type=EntityType(entity_data["type"]),
                    aliases=entity_data.get("aliases", []),
                    attributes=entity_data.get("attributes", {}),
                    confidence=entity_data.get("confidence", 0.0),
                    source=entity_data.get("source", ""),
                    created_at=datetime.fromisoformat(entity_data["created_at"]),
                    updated_at=datetime.fromisoformat(entity_data["updated_at"])
                )
            return None
    
    async def find_entities(
        self, 
        name: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        limit: int = 100
    ) -> List[Entity]:
        """Find entities in Neo4j"""
        async with self.driver.session() as session:
            conditions = []
            params = {"limit": limit}
            
            if name:
                conditions.append("e.name CONTAINS $name")
                params["name"] = name
            
            if entity_type:
                conditions.append("e.type = $entity_type")
                params["entity_type"] = entity_type.value
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
            MATCH (e:Entity)
            {where_clause}
            RETURN e
            LIMIT $limit
            """
            
            result = await session.run(query, **params)
            entities = []
            
            async for record in result:
                entity_data = record["e"]
                entity = Entity(
                    id=entity_data["id"],
                    name=entity_data["name"],
                    type=EntityType(entity_data["type"]),
                    aliases=entity_data.get("aliases", []),
                    attributes=entity_data.get("attributes", {}),
                    confidence=entity_data.get("confidence", 0.0),
                    source=entity_data.get("source", ""),
                    created_at=datetime.fromisoformat(entity_data["created_at"]),
                    updated_at=datetime.fromisoformat(entity_data["updated_at"])
                )
                entities.append(entity)
            
            return entities
    
    async def get_entity_relationships(
        self,
        entity_id: str,
        relationship_types: Optional[List[RelationshipType]] = None,
        direction: str = "both"
    ) -> List[Relationship]:
        """Get relationships for entity in Neo4j"""
        async with self.driver.session() as session:
            type_filter = ""
            params = {"entity_id": entity_id}
            
            if relationship_types:
                type_filter = "AND r.type IN $types"
                params["types"] = [rt.value for rt in relationship_types]
            
            if direction == "outgoing":
                pattern = "(e:Entity {id: $entity_id})-[r:RELATED]->(t:Entity)"
            elif direction == "incoming":
                pattern = "(s:Entity)-[r:RELATED]->(e:Entity {id: $entity_id})"
            else:  # both
                pattern = "(e:Entity {id: $entity_id})-[r:RELATED]-(t:Entity)"
            
            query = f"""
            MATCH {pattern}
            WHERE true {type_filter}
            RETURN r, startNode(r) as source, endNode(r) as target
            """
            
            result = await session.run(query, **params)
            relationships = []
            
            async for record in result:
                rel_data = record["r"]
                source_node = record["source"]
                target_node = record["target"]
                
                relationship = Relationship(
                    id=rel_data["id"],
                    source_entity_id=source_node["id"],
                    target_entity_id=target_node["id"],
                    type=RelationshipType(rel_data["type"]),
                    attributes=rel_data.get("attributes", {}),
                    strength=rel_data.get("strength", 0.0),
                    confidence=rel_data.get("confidence", 0.0),
                    source=rel_data.get("source", ""),
                    created_at=datetime.fromisoformat(rel_data["created_at"]),
                    updated_at=datetime.fromisoformat(rel_data["updated_at"])
                )
                relationships.append(relationship)
            
            return relationships
    
    async def find_path(
        self,
        start_entity_id: str,
        end_entity_id: str,
        max_hops: int = 3,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> Optional[GraphPath]:
        """Find path between entities in Neo4j"""
        async with self.driver.session() as session:
            type_filter = ""
            params = {
                "start_id": start_entity_id,
                "end_id": end_entity_id,
                "max_hops": max_hops
            }
            
            if relationship_types:
                type_filter = "AND ALL(r IN relationships(p) WHERE r.type IN $types)"
                params["types"] = [rt.value for rt in relationship_types]
            
            query = f"""
            MATCH p = shortestPath((start:Entity {{id: $start_id}})-[*1..{max_hops}]-(end:Entity {{id: $end_id}}))
            WHERE true {type_filter}
            RETURN p, length(p) as path_length,
                   reduce(total = 0, r in relationships(p) | total + r.strength) as total_strength,
                   reduce(conf = 1, r in relationships(p) | conf * r.confidence) as path_confidence
            """
            
            result = await session.run(query, **params)
            record = await result.single()
            
            if record:
                path_data = record["p"]
                path_nodes = path_data.nodes
                path_relationships = path_data.relationships
                
                path_elements = []
                for i, node in enumerate(path_nodes):
                    element = {
                        "entity": {
                            "id": node["id"],
                            "name": node["name"],
                            "type": node["type"]
                        }
                    }
                    
                    if i < len(path_relationships):
                        rel = path_relationships[i]
                        element["relationship"] = {
                            "id": rel["id"],
                            "type": rel["type"],
                            "strength": rel["strength"]
                        }
                    
                    path_elements.append(element)
                
                return GraphPath(
                    start_entity=start_entity_id,
                    end_entity=end_entity_id,
                    path=path_elements,
                    length=record["path_length"],
                    total_strength=record["total_strength"],
                    confidence=record["path_confidence"]
                )
            
            return None
    
    async def close(self):
        """Close Neo4j connection"""
        await self.driver.close()


class InMemoryGraphDatabase(GraphDatabase):
    """In-memory graph database using NetworkX"""
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.entities = {}
        self.relationships = {}
    
    async def create_entity(self, entity: Entity) -> str:
        """Create entity in memory"""
        self.entities[entity.id] = entity
        self.graph.add_node(entity.id, **entity.to_dict())
        return entity.id
    
    async def create_relationship(self, relationship: Relationship) -> str:
        """Create relationship in memory"""
        self.relationships[relationship.id] = relationship
        self.graph.add_edge(
            relationship.source_entity_id,
            relationship.target_entity_id,
            key=relationship.id,
            **relationship.to_dict()
        )
        return relationship.id
    
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity from memory"""
        return self.entities.get(entity_id)
    
    async def find_entities(
        self, 
        name: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        limit: int = 100
    ) -> List[Entity]:
        """Find entities in memory"""
        results = []
        
        for entity in self.entities.values():
            if name and name.lower() not in entity.name.lower():
                continue
            
            if entity_type and entity.type != entity_type:
                continue
            
            results.append(entity)
            
            if len(results) >= limit:
                break
        
        return results
    
    async def get_entity_relationships(
        self,
        entity_id: str,
        relationship_types: Optional[List[RelationshipType]] = None,
        direction: str = "both"
    ) -> List[Relationship]:
        """Get relationships for entity in memory"""
        relationships = []
        
        if direction in ["outgoing", "both"]:
            # Outgoing relationships
            for target_id in self.graph.successors(entity_id):
                for edge_key in self.graph[entity_id][target_id]:
                    rel_id = edge_key
                    relationship = self.relationships.get(rel_id)
                    
                    if relationship and (
                        not relationship_types or 
                        relationship.type in relationship_types
                    ):
                        relationships.append(relationship)
        
        if direction in ["incoming", "both"]:
            # Incoming relationships
            for source_id in self.graph.predecessors(entity_id):
                for edge_key in self.graph[source_id][entity_id]:
                    rel_id = edge_key
                    relationship = self.relationships.get(rel_id)
                    
                    if relationship and (
                        not relationship_types or 
                        relationship.type in relationship_types
                    ):
                        relationships.append(relationship)
        
        return relationships
    
    async def find_path(
        self,
        start_entity_id: str,
        end_entity_id: str,
        max_hops: int = 3,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> Optional[GraphPath]:
        """Find path between entities in memory"""
        try:
            # Use NetworkX to find shortest path
            path = nx.shortest_path(
                self.graph.to_undirected(),
                start_entity_id,
                end_entity_id
            )
            
            if len(path) - 1 > max_hops:
                return None
            
            # Build path elements
            path_elements = []
            total_strength = 0.0
            path_confidence = 1.0
            
            for i, node_id in enumerate(path):
                entity = self.entities.get(node_id)
                element = {
                    "entity": {
                        "id": node_id,
                        "name": entity.name if entity else node_id,
                        "type": entity.type.value if entity else "UNKNOWN"
                    }
                }
                
                if i < len(path) - 1:
                    next_node_id = path[i + 1]
                    # Find relationship between current and next node
                    for edge_key in self.graph[node_id][next_node_id]:
                        relationship = self.relationships.get(edge_key)
                        if relationship and (
                            not relationship_types or 
                            relationship.type in relationship_types
                        ):
                            element["relationship"] = {
                                "id": relationship.id,
                                "type": relationship.type.value,
                                "strength": relationship.strength
                            }
                            total_strength += relationship.strength
                            path_confidence *= relationship.confidence
                            break
                
                path_elements.append(element)
            
            return GraphPath(
                start_entity=start_entity_id,
                end_entity=end_entity_id,
                path=path_elements,
                length=len(path) - 1,
                total_strength=total_strength,
                confidence=path_confidence
            )
            
        except nx.NetworkXNoPath:
            return None


class EntityExtractor:
    """Entity extraction from text"""
    
    def __init__(self):
        self.spacy_model = None
        self.transformer_pipeline = None
        
        # Initialize NLP models
        if SPACY_AVAILABLE:
            try:
                import spacy
                self.spacy_model = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model 'en_core_web_sm' not found")
        
        if TRANSFORMERS_AVAILABLE:
            try:
                self.transformer_pipeline = pipeline(
                    "ner",
                    model="dbmdz/bert-large-cased-finetuned-conll03-english",
                    tokenizer="dbmdz/bert-large-cased-finetuned-conll03-english"
                )
            except Exception as e:
                logger.warning(f"Failed to load transformer NER model: {e}")
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        entities = []
        
        # Extract using spaCy
        if self.spacy_model:
            spacy_entities = await self._extract_with_spacy(text)
            entities.extend(spacy_entities)
        
        # Extract using transformers
        if self.transformer_pipeline:
            transformer_entities = await self._extract_with_transformers(text)
            entities.extend(transformer_entities)
        
        # Deduplicate and merge entities
        merged_entities = self._merge_entities(entities)
        
        return merged_entities
    
    async def _extract_with_spacy(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using spaCy"""
        def extract():
            doc = self.spacy_model(text)
            entities = []
            
            for ent in doc.ents:
                entity = {
                    "name": ent.text,
                    "type": self._map_spacy_label(ent.label_),
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 0.8,  # Default confidence for spaCy
                    "source": "spacy"
                }
                entities.append(entity)
            
            return entities
        
        return await asyncio.to_thread(extract)
    
    async def _extract_with_transformers(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using transformers"""
        def extract():
            results = self.transformer_pipeline(text)
            entities = []
            
            for result in results:
                entity = {
                    "name": result["word"],
                    "type": self._map_transformer_label(result["entity"]),
                    "start": result["start"],
                    "end": result["end"],
                    "confidence": result["score"],
                    "source": "transformers"
                }
                entities.append(entity)
            
            return entities
        
        return await asyncio.to_thread(extract)
    
    def _map_spacy_label(self, label: str) -> str:
        """Map spaCy labels to our entity types"""
        mapping = {
            "PERSON": EntityType.PERSON.value,
            "ORG": EntityType.ORGANIZATION.value,
            "GPE": EntityType.LOCATION.value,
            "LOC": EntityType.LOCATION.value,
            "DATE": EntityType.DATE.value,
            "TIME": EntityType.TIME.value,
            "MONEY": EntityType.MONEY.value,
            "PERCENT": EntityType.PERCENT.value,
            "PRODUCT": EntityType.PRODUCT.value,
            "EVENT": EntityType.EVENT.value
        }
        return mapping.get(label, EntityType.MISCELLANEOUS.value)
    
    def _map_transformer_label(self, label: str) -> str:
        """Map transformer NER labels to our entity types"""
        # Remove B- and I- prefixes
        clean_label = label.replace("B-", "").replace("I-", "")
        
        mapping = {
            "PER": EntityType.PERSON.value,
            "ORG": EntityType.ORGANIZATION.value,
            "LOC": EntityType.LOCATION.value,
            "MISC": EntityType.MISCELLANEOUS.value
        }
        return mapping.get(clean_label, EntityType.MISCELLANEOUS.value)
    
    def _merge_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge duplicate entities"""
        merged = {}
        
        for entity in entities:
            key = (entity["name"].lower(), entity["type"])
            
            if key in merged:
                # Update confidence with average
                existing = merged[key]
                existing["confidence"] = (existing["confidence"] + entity["confidence"]) / 2
                existing["sources"] = list(set(existing.get("sources", [existing["source"]]) + [entity["source"]]))
            else:
                entity["sources"] = [entity["source"]]
                merged[key] = entity
        
        return list(merged.values())


class RelationshipExtractor:
    """Relationship extraction from text"""
    
    def __init__(self):
        self.dependency_patterns = self._load_dependency_patterns()
    
    async def extract_relationships(
        self, 
        text: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relationships from text given entities"""
        relationships = []
        
        # Co-occurrence relationships
        cooccurrence_rels = await self._extract_cooccurrence_relationships(text, entities)
        relationships.extend(cooccurrence_rels)
        
        # Dependency-based relationships
        if SPACY_AVAILABLE:
            dependency_rels = await self._extract_dependency_relationships(text, entities)
            relationships.extend(dependency_rels)
        
        # Pattern-based relationships
        pattern_rels = await self._extract_pattern_relationships(text, entities)
        relationships.extend(pattern_rels)
        
        return relationships
    
    async def _extract_cooccurrence_relationships(
        self, 
        text: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract co-occurrence relationships"""
        relationships = []
        
        # Create relationships between entities that appear in the same sentence
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence_entities = [
                entity for entity in entities 
                if entity["name"].lower() in sentence.lower()
            ]
            
            # Create relationships between all pairs in the sentence
            for i, entity1 in enumerate(sentence_entities):
                for entity2 in sentence_entities[i+1:]:
                    relationship = {
                        "source_entity": entity1["name"],
                        "target_entity": entity2["name"],
                        "type": RelationshipType.CO_OCCURS_WITH.value,
                        "strength": 0.5,
                        "confidence": 0.6,
                        "source": "cooccurrence",
                        "context": sentence.strip()
                    }
                    relationships.append(relationship)
        
        return relationships
    
    async def _extract_dependency_relationships(
        self, 
        text: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relationships using dependency parsing"""
        # This would use spaCy dependency parsing
        # Simplified implementation for now
        return []
    
    async def _extract_pattern_relationships(
        self, 
        text: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relationships using predefined patterns"""
        relationships = []
        
        # Simple pattern matching
        patterns = {
            r"(.+) works for (.+)": RelationshipType.WORKS_FOR,
            r"(.+) is located in (.+)": RelationshipType.LOCATED_IN,
            r"(.+) is part of (.+)": RelationshipType.PART_OF,
            r"(.+) caused (.+)": RelationshipType.CAUSED_BY,
            r"(.+) leads to (.+)": RelationshipType.LEADS_TO
        }
        
        import re
        
        for pattern, rel_type in patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                source_text = match.group(1).strip()
                target_text = match.group(2).strip()
                
                # Find matching entities
                source_entity = self._find_matching_entity(source_text, entities)
                target_entity = self._find_matching_entity(target_text, entities)
                
                if source_entity and target_entity:
                    relationship = {
                        "source_entity": source_entity["name"],
                        "target_entity": target_entity["name"],
                        "type": rel_type.value,
                        "strength": 0.8,
                        "confidence": 0.7,
                        "source": "pattern_matching",
                        "context": match.group(0)
                    }
                    relationships.append(relationship)
        
        return relationships
    
    def _find_matching_entity(self, text: str, entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find entity that matches the given text"""
        text_lower = text.lower()
        
        for entity in entities:
            if entity["name"].lower() in text_lower or text_lower in entity["name"].lower():
                return entity
        
        return None
    
    def _load_dependency_patterns(self) -> Dict[str, Any]:
        """Load dependency patterns for relationship extraction"""
        # This would load pre-defined dependency patterns
        return {}


class KnowledgeGraph:
    """Main knowledge graph engine"""
    
    def __init__(self, graph_db: GraphDatabase):
        self.graph_db = graph_db
        self.entity_extractor = EntityExtractor()
        self.relationship_extractor = RelationshipExtractor()
        
        # Caching
        self.entity_cache = {}
        self.relationship_cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Statistics
        self.stats = {
            "entities_created": 0,
            "relationships_created": 0,
            "queries_processed": 0
        }
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        self.stats["queries_processed"] += 1
        
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.entity_cache:
            cache_entry = self.entity_cache[cache_key]
            if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                return cache_entry["entities"]
        
        # Extract entities
        entities = await self.entity_extractor.extract_entities(text)
        
        # Cache results
        self.entity_cache[cache_key] = {
            "entities": entities,
            "timestamp": time.time()
        }
        
        return entities
    
    async def build_graph_from_text(
        self, 
        text: str,
        source: str = "text_processing"
    ) -> Dict[str, Any]:
        """Build knowledge graph from text"""
        
        # Extract entities
        entities = await self.extract_entities(text)
        
        # Create entities in graph
        created_entities = []
        for entity_data in entities:
            entity = Entity(
                id=self._generate_entity_id(entity_data["name"]),
                name=entity_data["name"],
                type=EntityType(entity_data["type"]),
                aliases=[],
                attributes={
                    "confidence": entity_data["confidence"],
                    "extraction_source": entity_data["source"]
                },
                confidence=entity_data["confidence"],
                source=source,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Check if entity already exists
            existing_entities = await self.graph_db.find_entities(name=entity.name)
            if not existing_entities:
                await self.graph_db.create_entity(entity)
                created_entities.append(entity)
                self.stats["entities_created"] += 1
        
        # Extract relationships
        relationships = await self.relationship_extractor.extract_relationships(text, entities)
        
        # Create relationships in graph
        created_relationships = []
        for rel_data in relationships:
            # Find entities
            source_entities = await self.graph_db.find_entities(name=rel_data["source_entity"])
            target_entities = await self.graph_db.find_entities(name=rel_data["target_entity"])
            
            if source_entities and target_entities:
                relationship = Relationship(
                    id=self._generate_relationship_id(
                        source_entities[0].id,
                        target_entities[0].id,
                        rel_data["type"]
                    ),
                    source_entity_id=source_entities[0].id,
                    target_entity_id=target_entities[0].id,
                    type=RelationshipType(rel_data["type"]),
                    attributes={
                        "context": rel_data.get("context", ""),
                        "extraction_source": rel_data["source"]
                    },
                    strength=rel_data["strength"],
                    confidence=rel_data["confidence"],
                    source=source,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                await self.graph_db.create_relationship(relationship)
                created_relationships.append(relationship)
                self.stats["relationships_created"] += 1
        
        return {
            "entities": [e.to_dict() for e in created_entities],
            "relationships": [r.to_dict() for r in created_relationships],
            "stats": {
                "entities_created": len(created_entities),
                "relationships_created": len(created_relationships)
            }
        }
    
    async def find_entity_path(
        self,
        start_entity_name: str,
        end_entity_name: str,
        max_hops: int = 3,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Find path between two entities"""
        
        # Find entities
        start_entities = await self.graph_db.find_entities(name=start_entity_name)
        end_entities = await self.graph_db.find_entities(name=end_entity_name)
        
        if not start_entities or not end_entities:
            return [], 0.0
        
        # Find path
        path = await self.graph_db.find_path(
            start_entities[0].id,
            end_entities[0].id,
            max_hops,
            relationship_types
        )
        
        if path:
            return path.path, path.confidence
        
        return [], 0.0
    
    async def get_entity_context(
        self,
        entity_names: Union[str, List[str]],
        depth: int = 1
    ) -> Dict[str, Any]:
        """Get context for entities"""
        if isinstance(entity_names, str):
            entity_names = [entity_names]
        
        context = {
            "entities": [],
            "related_entities": [],
            "relationships": [],
            "summary": {}
        }
        
        for entity_name in entity_names:
            entities = await self.graph_db.find_entities(name=entity_name)
            
            if entities:
                entity = entities[0]
                context["entities"].append(entity.to_dict())
                
                # Get relationships
                relationships = await self.graph_db.get_entity_relationships(entity.id)
                context["relationships"].extend([r.to_dict() for r in relationships])
                
                # Get related entities
                for relationship in relationships:
                    related_entity_id = (
                        relationship.target_entity_id 
                        if relationship.source_entity_id == entity.id 
                        else relationship.source_entity_id
                    )
                    
                    related_entity = await self.graph_db.get_entity(related_entity_id)
                    if related_entity:
                        context["related_entities"].append(related_entity.to_dict())
        
        # Generate summary
        context["summary"] = {
            "total_entities": len(context["entities"]),
            "total_relationships": len(context["relationships"]),
            "entity_types": list(set([e["type"] for e in context["entities"]])),
            "relationship_types": list(set([r["type"] for r in context["relationships"]]))
        }
        
        return context
    
    async def traverse_graph(
        self,
        start_entities: List[str],
        relationship_types: Optional[List[RelationshipType]] = None,
        max_hops: int = 2
    ) -> List[Dict[str, Any]]:
        """Traverse graph from starting entities"""
        visited_entities = set()
        result_entities = []
        
        current_entities = start_entities.copy()
        
        for hop in range(max_hops):
            next_entities = []
            
            for entity_name in current_entities:
                if entity_name in visited_entities:
                    continue
                
                visited_entities.add(entity_name)
                entities = await self.graph_db.find_entities(name=entity_name)
                
                if entities:
                    entity = entities[0]
                    result_entities.append(entity.to_dict())
                    
                    # Get related entities
                    relationships = await self.graph_db.get_entity_relationships(
                        entity.id,
                        relationship_types
                    )
                    
                    for relationship in relationships:
                        related_entity_id = (
                            relationship.target_entity_id 
                            if relationship.source_entity_id == entity.id 
                            else relationship.source_entity_id
                        )
                        
                        related_entity = await self.graph_db.get_entity(related_entity_id)
                        if related_entity and related_entity.name not in visited_entities:
                            next_entities.append(related_entity.name)
            
            current_entities = next_entities
            
            if not current_entities:
                break
        
        return result_entities
    
    async def calculate_graph_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """Calculate similarity between two texts using graph structure"""
        
        # Extract entities from both texts
        entities1 = await self.extract_entities(text1)
        entities2 = await self.extract_entities(text2)
        
        if not entities1 or not entities2:
            return 0.0
        
        # Calculate entity overlap
        names1 = set([e["name"].lower() for e in entities1])
        names2 = set([e["name"].lower() for e in entities2])
        
        direct_overlap = len(names1.intersection(names2))
        total_entities = len(names1.union(names2))
        
        if total_entities == 0:
            return 0.0
        
        direct_similarity = direct_overlap / total_entities
        
        # Calculate graph-based similarity
        graph_similarity = 0.0
        path_count = 0
        
        for name1 in names1:
            for name2 in names2:
                if name1 != name2:
                    path, confidence = await self.find_entity_path(name1, name2, max_hops=2)
                    if path:
                        graph_similarity += confidence
                        path_count += 1
        
        if path_count > 0:
            graph_similarity /= path_count
        
        # Combined similarity
        combined_similarity = (direct_similarity * 0.6) + (graph_similarity * 0.4)
        
        return min(combined_similarity, 1.0)
    
    def _generate_entity_id(self, name: str) -> str:
        """Generate unique entity ID"""
        return f"entity_{hashlib.md5(name.encode()).hexdigest()[:16]}"
    
    def _generate_relationship_id(self, source_id: str, target_id: str, rel_type: str) -> str:
        """Generate unique relationship ID"""
        combined = f"{source_id}_{target_id}_{rel_type}"
        return f"rel_{hashlib.md5(combined.encode()).hexdigest()[:16]}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        graph_stats = await self.graph_db.get_stats()
        
        return {
            **self.stats,
            **graph_stats,
            "cache_stats": {
                "entity_cache_size": len(self.entity_cache),
                "relationship_cache_size": len(self.relationship_cache),
                "cache_ttl": self.cache_ttl
            }
        }
    
    async def close(self):
        """Close knowledge graph connections"""
        if hasattr(self.graph_db, 'close'):
            await self.graph_db.close()


# Factory function for creating knowledge graphs
def create_knowledge_graph(
    db_type: str = "memory",
    **kwargs
) -> KnowledgeGraph:
    """Factory function to create knowledge graph instances"""
    
    if db_type == "neo4j":
        if not NEO4J_AVAILABLE:
            raise ImportError("Neo4j driver not available")
        
        graph_db = Neo4jGraphDatabase(**kwargs)
    elif db_type == "memory":
        graph_db = InMemoryGraphDatabase()
    else:
        raise ValueError(f"Unsupported graph database type: {db_type}")
    
    return KnowledgeGraph(graph_db)


# Default knowledge graph factory
def get_default_knowledge_graph() -> KnowledgeGraph:
    """Get default knowledge graph based on configuration"""
    
    # Try Neo4j if configured
    if hasattr(settings, 'NEO4J_URI') and settings.NEO4J_URI:
        return create_knowledge_graph(
            "neo4j",
            uri=settings.NEO4J_URI,
            user=getattr(settings, 'NEO4J_USER', 'neo4j'),
            password=getattr(settings, 'NEO4J_PASSWORD', 'password')
        )
    
    # Fall back to in-memory
    return create_knowledge_graph("memory")