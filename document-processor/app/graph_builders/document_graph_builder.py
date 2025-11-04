"""
Document graph builder for creating knowledge graphs from processed documents
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
import re

# Graph libraries (with fallbacks)
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    import igraph as ig
    IGRAPH_AVAILABLE = True
except ImportError:
    IGRAPH_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the document graph"""
    DOCUMENT = "DOCUMENT"
    SECTION = "SECTION"
    PARAGRAPH = "PARAGRAPH"
    SENTENCE = "SENTENCE"
    ENTITY = "ENTITY"
    CONCEPT = "CONCEPT"
    TOPIC = "TOPIC"
    KEYWORD = "KEYWORD"
    TEMPORAL = "TEMPORAL"


class EdgeType(Enum):
    """Types of edges in the document graph"""
    CONTAINS = "CONTAINS"
    REFERENCES = "REFERENCES"
    RELATES_TO = "RELATES_TO"
    FOLLOWS = "FOLLOWS"
    MENTIONED_IN = "MENTIONED_IN"
    CO_OCCURS = "CO_OCCURS"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    TEMPORAL_RELATION = "TEMPORAL_RELATION"
    CAUSAL_RELATION = "CAUSAL_RELATION"
    HIERARCHICAL = "HIERARCHICAL"


@dataclass
class GraphNode:
    """Represents a node in the document graph"""
    id: str
    type: NodeType
    label: str
    properties: Dict[str, Any]
    position: Optional[Tuple[int, int]] = None
    weight: float = 1.0


@dataclass
class GraphEdge:
    """Represents an edge in the document graph"""
    source_id: str
    target_id: str
    type: EdgeType
    properties: Dict[str, Any]
    weight: float = 1.0
    confidence: float = 1.0


class DocumentGraphBuilder:
    """Builder for creating comprehensive document knowledge graphs"""
    
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.graph = None
        self.node_counter = 0
        
        # Configuration
        self.max_co_occurrence_distance = 100
        self.min_edge_weight = 0.1
        self.similarity_threshold = 0.7
    
    async def build_document_graph(
        self,
        document_data: Dict[str, Any],
        include_structure: bool = True,
        include_entities: bool = True,
        include_concepts: bool = True,
        include_temporal: bool = True,
        include_semantic_relations: bool = True
    ) -> Dict[str, Any]:
        """Build a comprehensive document graph"""
        
        self.nodes = {}
        self.edges = []
        self.node_counter = 0
        
        try:
            # Build document structure nodes
            if include_structure:
                await self._build_structure_nodes(document_data)
            
            # Add entity nodes
            if include_entities and "entities" in document_data:
                await self._add_entity_nodes(document_data["entities"])
            
            # Add concept nodes
            if include_concepts and "concepts" in document_data:
                await self._add_concept_nodes(document_data["concepts"])
            
            # Add temporal nodes
            if include_temporal and "temporal_entities" in document_data:
                await self._add_temporal_nodes(document_data["temporal_entities"])
            
            # Build relationships
            if include_semantic_relations:
                await self._build_semantic_relations(document_data)
            
            # Build co-occurrence relations
            await self._build_co_occurrence_relations(document_data)
            
            # Build temporal relations
            if include_temporal and "temporal_relationships" in document_data:
                await self._build_temporal_relations(document_data["temporal_relationships"])
            
            # Create NetworkX graph if available
            if NETWORKX_AVAILABLE:
                self.graph = await self._create_networkx_graph()
            
            # Calculate graph metrics
            metrics = await self._calculate_graph_metrics()
            
            # Generate graph insights
            insights = await self._generate_graph_insights()
            
            return {
                "nodes": [self._node_to_dict(node) for node in self.nodes.values()],
                "edges": [self._edge_to_dict(edge) for edge in self.edges],
                "metrics": metrics,
                "insights": insights,
                "graph_info": {
                    "total_nodes": len(self.nodes),
                    "total_edges": len(self.edges),
                    "node_types": self._count_node_types(),
                    "edge_types": self._count_edge_types()
                }
            }
            
        except Exception as e:
            logger.error(f"Error building document graph: {e}")
            return {"error": str(e)}
    
    # Graph building methods (implementation continues...)
    async def _build_structure_nodes(self, document_data: Dict[str, Any]):
        """Build document structure nodes"""
        
        # Document node
        doc_id = self._generate_node_id()
        doc_node = GraphNode(
            id=doc_id,
            type=NodeType.DOCUMENT,
            label=document_data.get("title", "Document"),
            properties={
                "title": document_data.get("title", ""),
                "length": document_data.get("length", 0),
                "language": document_data.get("language", "en"),
                "created_at": document_data.get("created_at", ""),
                "file_type": document_data.get("file_type", "")
            }
        )
        self.nodes[doc_id] = doc_node
    
    async def _add_entity_nodes(self, entities: List[Dict[str, Any]]):
        """Add entity nodes to the graph"""
        
        for entity in entities:
            entity_id = self._generate_entity_id(entity["name"], entity["type"])
            
            if entity_id not in self.nodes:
                entity_node = GraphNode(
                    id=entity_id,
                    type=NodeType.ENTITY,
                    label=entity["name"],
                    properties={
                        "name": entity["name"],
                        "entity_type": entity["type"],
                        "confidence": entity.get("confidence", 0.0),
                        "frequency": entity.get("frequency", 1),
                        "extraction_method": entity.get("extraction_method", ""),
                        "context": entity.get("context", {})
                    },
                    weight=entity.get("confidence", 0.5)
                )
                self.nodes[entity_id] = entity_node
    
    async def _add_concept_nodes(self, concepts: List[Dict[str, Any]]):
        """Add concept nodes to the graph"""
        
        for concept in concepts:
            concept_id = self._generate_concept_id(concept["name"])
            
            if concept_id not in self.nodes:
                concept_node = GraphNode(
                    id=concept_id,
                    type=NodeType.CONCEPT,
                    label=concept["name"],
                    properties={
                        "name": concept["name"],
                        "concept_type": concept.get("concept_type", ""),
                        "confidence": concept.get("confidence", 0.0),
                        "importance_score": concept.get("importance_score", 0.0),
                        "frequency": concept.get("frequency", 1),
                        "extraction_method": concept.get("extraction_method", ""),
                        "related_terms": concept.get("related_terms", [])
                    },
                    weight=concept.get("importance_score", 0.5)
                )
                self.nodes[concept_id] = concept_node
    
    async def _add_temporal_nodes(self, temporal_entities: List[Dict[str, Any]]):
        """Add temporal nodes to the graph"""
        
        for temporal in temporal_entities:
            temporal_id = self._generate_temporal_id(temporal["text"])
            
            if temporal_id not in self.nodes:
                temporal_node = GraphNode(
                    id=temporal_id,
                    type=NodeType.TEMPORAL,
                    label=temporal["text"],
                    properties={
                        "text": temporal["text"],
                        "temporal_type": temporal.get("temporal_type", ""),
                        "normalized_value": temporal.get("normalized_value", ""),
                        "confidence": temporal.get("confidence", 0.0),
                        "parsed_datetime": temporal.get("parsed_datetime", ""),
                        "extraction_method": temporal.get("extraction_method", "")
                    },
                    weight=temporal.get("confidence", 0.5)
                )
                self.nodes[temporal_id] = temporal_node
    
    async def _build_semantic_relations(self, document_data: Dict[str, Any]):
        """Build semantic relations between nodes"""
        
        # Entity-concept relations
        entities = document_data.get("entities", [])
        concepts = document_data.get("concepts", [])
        
        for entity in entities:
            entity_id = self._generate_entity_id(entity["name"], entity["type"])
            
            for concept in concepts:
                concept_id = self._generate_concept_id(concept["name"])
                
                # Check if entity and concept are semantically related
                semantic_similarity = self._calculate_semantic_similarity(
                    entity, concept
                )
                
                if semantic_similarity > self.similarity_threshold:
                    self.edges.append(GraphEdge(
                        source_id=entity_id,
                        target_id=concept_id,
                        type=EdgeType.RELATES_TO,
                        properties={
                            "similarity_score": semantic_similarity,
                            "relation_type": "semantic"
                        },
                        weight=semantic_similarity,
                        confidence=semantic_similarity
                    ))
    
    async def _build_co_occurrence_relations(self, document_data: Dict[str, Any]):
        """Build co-occurrence relations between entities"""
        
        entities = document_data.get("entities", [])
        text = document_data.get("content", "")
        
        # Find co-occurring entities
        for i, entity1 in enumerate(entities):
            entity1_id = self._generate_entity_id(entity1["name"], entity1["type"])
            
            for entity2 in entities[i+1:]:
                entity2_id = self._generate_entity_id(entity2["name"], entity2["type"])
                
                # Calculate co-occurrence score
                co_occurrence_score = self._calculate_co_occurrence(
                    entity1, entity2, text
                )
                
                if co_occurrence_score > 0:
                    self.edges.append(GraphEdge(
                        source_id=entity1_id,
                        target_id=entity2_id,
                        type=EdgeType.CO_OCCURS,
                        properties={
                            "co_occurrence_score": co_occurrence_score,
                            "context_windows": self._find_co_occurrence_contexts(
                                entity1, entity2, text
                            )
                        },
                        weight=co_occurrence_score,
                        confidence=min(co_occurrence_score, 1.0)
                    ))
    
    async def _build_temporal_relations(self, temporal_relationships: List[Dict[str, Any]]):
        """Build temporal relations between nodes"""
        
        for rel in temporal_relationships:
            source_id = self._generate_temporal_id(rel["source_entity"])
            target_id = self._generate_temporal_id(rel["target_entity"])
            
            # Only add edge if both nodes exist
            if source_id in self.nodes and target_id in self.nodes:
                self.edges.append(GraphEdge(
                    source_id=source_id,
                    target_id=target_id,
                    type=EdgeType.TEMPORAL_RELATION,
                    properties={
                        "relation_type": rel["relation_type"],
                        "evidence_text": rel.get("evidence_text", ""),
                        "extraction_method": rel.get("extraction_method", "")
                    },
                    weight=rel.get("confidence", 0.5),
                    confidence=rel.get("confidence", 0.5)
                ))
    
    async def _create_networkx_graph(self) -> nx.Graph:
        """Create NetworkX graph from nodes and edges"""
        
        if not NETWORKX_AVAILABLE:
            return None
        
        G = nx.Graph()
        
        # Add nodes
        for node in self.nodes.values():
            G.add_node(
                node.id,
                type=node.type.value,
                label=node.label,
                weight=node.weight,
                **node.properties
            )
        
        # Add edges
        for edge in self.edges:
            if edge.source_id in self.nodes and edge.target_id in self.nodes:
                G.add_edge(
                    edge.source_id,
                    edge.target_id,
                    type=edge.type.value,
                    weight=edge.weight,
                    confidence=edge.confidence,
                    **edge.properties
                )
        
        return G
    
    async def _calculate_graph_metrics(self) -> Dict[str, Any]:
        """Calculate various graph metrics"""
        
        metrics = {
            "basic_stats": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "density": 0.0
            },
            "centrality": {},
            "clustering": {},
            "connectivity": {}
        }
        
        if not self.graph or not NETWORKX_AVAILABLE:
            return metrics
        
        try:
            # Basic statistics
            num_nodes = self.graph.number_of_nodes()
            num_edges = self.graph.number_of_edges()
            
            metrics["basic_stats"] = {
                "nodes": num_nodes,
                "edges": num_edges,
                "density": nx.density(self.graph) if num_nodes > 1 else 0.0,
                "is_connected": nx.is_connected(self.graph)
            }
            
            # Centrality measures
            if num_nodes > 0:
                degree_centrality = nx.degree_centrality(self.graph)
                
                # Get top 5 central nodes
                metrics["centrality"] = {
                    "degree": dict(sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5])
                }
            
        except Exception as e:
            logger.warning(f"Error calculating graph metrics: {e}")
        
        return metrics
    
    async def _generate_graph_insights(self) -> Dict[str, Any]:
        """Generate insights about the document graph"""
        
        insights = {
            "key_entities": [],
            "central_concepts": [],
            "important_relationships": [],
            "graph_structure": {}
        }
        
        try:
            # Key entities (highest weight entity nodes)
            entity_nodes = [node for node in self.nodes.values() if node.type == NodeType.ENTITY]
            entity_nodes.sort(key=lambda x: x.weight, reverse=True)
            insights["key_entities"] = [
                {"name": node.label, "type": node.properties.get("entity_type", ""), "weight": node.weight}
                for node in entity_nodes[:10]
            ]
            
            # Central concepts
            concept_nodes = [node for node in self.nodes.values() if node.type == NodeType.CONCEPT]
            concept_nodes.sort(key=lambda x: x.weight, reverse=True)
            insights["central_concepts"] = [
                {"name": node.label, "importance": node.weight}
                for node in concept_nodes[:10]
            ]
            
            # Important relationships (highest weight edges)
            sorted_edges = sorted(self.edges, key=lambda x: x.weight, reverse=True)
            insights["important_relationships"] = [
                {
                    "source": self.nodes[edge.source_id].label if edge.source_id in self.nodes else edge.source_id,
                    "target": self.nodes[edge.target_id].label if edge.target_id in self.nodes else edge.target_id,
                    "type": edge.type.value,
                    "weight": edge.weight
                }
                for edge in sorted_edges[:10]
            ]
            
            # Graph structure insights
            node_type_counts = self._count_node_types()
            edge_type_counts = self._count_edge_types()
            
            insights["graph_structure"] = {
                "node_distribution": node_type_counts,
                "edge_distribution": edge_type_counts
            }
            
        except Exception as e:
            logger.warning(f"Error generating graph insights: {e}")
        
        return insights
    
    # Helper methods
    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        self.node_counter += 1
        return f"node_{self.node_counter}"
    
    def _generate_entity_id(self, name: str, entity_type: str) -> str:
        """Generate consistent entity ID"""
        return f"entity_{hashlib.md5((name + entity_type).encode()).hexdigest()[:8]}"
    
    def _generate_concept_id(self, name: str) -> str:
        """Generate consistent concept ID"""
        return f"concept_{hashlib.md5(name.encode()).hexdigest()[:8]}"
    
    def _generate_temporal_id(self, text: str) -> str:
        """Generate consistent temporal ID"""
        return f"temporal_{hashlib.md5(text.encode()).hexdigest()[:8]}"
    
    def _calculate_semantic_similarity(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> float:
        """Calculate semantic similarity between two items"""
        
        # Simple similarity based on shared terms
        name1 = item1.get("name", "").lower()
        name2 = item2.get("name", "").lower()
        
        # Exact match
        if name1 == name2:
            return 1.0
        
        # Substring match
        if name1 in name2 or name2 in name1:
            return 0.8
        
        # Word overlap
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if len(words1.union(words2)) > 0:
            overlap = len(words1.intersection(words2)) / len(words1.union(words2))
            return overlap
        
        return 0.0
    
    def _calculate_co_occurrence(self, entity1: Dict[str, Any], entity2: Dict[str, Any], text: str) -> float:
        """Calculate co-occurrence score between entities"""
        
        name1 = entity1["name"]
        name2 = entity2["name"]
        text_lower = text.lower()
        
        # Find all positions of both entities
        positions1 = []
        positions2 = []
        
        start = 0
        while True:
            pos = text_lower.find(name1.lower(), start)
            if pos == -1:
                break
            positions1.append(pos)
            start = pos + 1
        
        start = 0
        while True:
            pos = text_lower.find(name2.lower(), start)
            if pos == -1:
                break
            positions2.append(pos)
            start = pos + 1
        
        # Count co-occurrences within distance threshold
        co_occurrences = 0
        for pos1 in positions1:
            for pos2 in positions2:
                if abs(pos1 - pos2) <= self.max_co_occurrence_distance:
                    co_occurrences += 1
        
        # Normalize by frequency
        max_possible = len(positions1) * len(positions2)
        return co_occurrences / max_possible if max_possible > 0 else 0.0
    
    def _find_co_occurrence_contexts(self, entity1: Dict[str, Any], entity2: Dict[str, Any], text: str) -> List[str]:
        """Find context windows where entities co-occur"""
        
        contexts = []
        name1 = entity1["name"].lower()
        name2 = entity2["name"].lower()
        text_lower = text.lower()
        
        # Find positions
        for match1 in re.finditer(re.escape(name1), text_lower):
            for match2 in re.finditer(re.escape(name2), text_lower):
                if abs(match1.start() - match2.start()) <= self.max_co_occurrence_distance:
                    # Extract context window
                    start = min(match1.start(), match2.start()) - 50
                    end = max(match1.end(), match2.end()) + 50
                    start = max(0, start)
                    end = min(len(text), end)
                    
                    context = text[start:end].strip()
                    if context and context not in contexts:
                        contexts.append(context)
        
        return contexts[:3]  # Limit to 3 contexts
    
    def _count_node_types(self) -> Dict[str, int]:
        """Count nodes by type"""
        type_counts = defaultdict(int)
        for node in self.nodes.values():
            type_counts[node.type.value] += 1
        return dict(type_counts)
    
    def _count_edge_types(self) -> Dict[str, int]:
        """Count edges by type"""
        type_counts = defaultdict(int)
        for edge in self.edges:
            type_counts[edge.type.value] += 1
        return dict(type_counts)
    
    def _node_to_dict(self, node: GraphNode) -> Dict[str, Any]:
        """Convert GraphNode to dictionary"""
        return {
            "id": node.id,
            "type": node.type.value,
            "label": node.label,
            "properties": node.properties,
            "position": node.position,
            "weight": node.weight
        }
    
    def _edge_to_dict(self, edge: GraphEdge) -> Dict[str, Any]:
        """Convert GraphEdge to dictionary"""
        return {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "type": edge.type.value,
            "properties": edge.properties,
            "weight": edge.weight,
            "confidence": edge.confidence
        }