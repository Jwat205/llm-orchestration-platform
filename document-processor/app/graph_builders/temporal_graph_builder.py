"""
Temporal graph builder for creating time-aware knowledge graphs
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
import hashlib

# Graph libraries (with fallbacks)
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

# Date parsing libraries (with fallbacks)
try:
    from dateutil import parser as date_parser
    from dateutil.relativedelta import relativedelta
    DATE_PARSING_AVAILABLE = True
except ImportError:
    DATE_PARSING_AVAILABLE = False

logger = logging.getLogger(__name__)


class TemporalNodeType(Enum):
    """Types of temporal nodes"""
    TIME_POINT = "TIME_POINT"
    TIME_PERIOD = "TIME_PERIOD"
    EVENT = "EVENT"
    PROCESS = "PROCESS"
    STATE = "STATE"
    MILESTONE = "MILESTONE"
    DURATION = "DURATION"
    FREQUENCY = "FREQUENCY"


class TemporalEdgeType(Enum):
    """Types of temporal relationships"""
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    DURING = "DURING"
    OVERLAPS = "OVERLAPS"
    MEETS = "MEETS"
    STARTS = "STARTS"
    FINISHES = "FINISHES"
    EQUALS = "EQUALS"
    CONTAINS = "CONTAINS"
    CAUSES = "CAUSES"
    ENABLES = "ENABLES"  
    SIMULTANEOUS = "SIMULTANEOUS"


@dataclass
class TemporalNode:
    """Represents a temporal node in the graph"""
    id: str
    label: str
    node_type: TemporalNodeType
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    confidence: float
    properties: Dict[str, Any]
    related_entities: List[str]
    context: str


@dataclass
class TemporalEdge:
    """Represents a temporal relationship"""
    source_id: str
    target_id: str
    edge_type: TemporalEdgeType
    confidence: float
    evidence: List[str]
    properties: Dict[str, Any]
    temporal_distance: Optional[int] = None


class TemporalGraphBuilder:
    """Builder for creating temporal knowledge graphs"""
    
    def __init__(self):
        self.temporal_nodes = {}
        self.temporal_edges = []
        self.temporal_graph = None
        self.timeline = []
        self.time_intervals = {}
        
        # Configuration
        self.time_window_hours = 24
        self.causality_window_days = 30
        self.min_confidence = 0.3
    
    async def build_temporal_graph(
        self,
        temporal_entities: List[Dict[str, Any]],
        temporal_relationships: List[Dict[str, Any]] = None,
        entities: List[Dict[str, Any]] = None,
        reference_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Build a comprehensive temporal graph"""
        
        if reference_time is None:
            reference_time = datetime.now()
        
        self.temporal_nodes = {}
        self.temporal_edges = []
        
        try:
            # Create temporal nodes
            await self._create_temporal_nodes(temporal_entities, entities or [])
            
            # Build temporal relationships
            if temporal_relationships:
                await self._build_temporal_relationships(temporal_relationships)
            
            # Infer additional temporal relationships
            await self._infer_temporal_relationships()
            
            # Build causality relationships
            await self._build_causality_relationships()
            
            # Create timeline
            await self._create_timeline()
            
            # Identify time intervals
            await self._identify_time_intervals()
            
            # Create NetworkX graph if available
            if NETWORKX_AVAILABLE:
                self.temporal_graph = await self._create_temporal_networkx_graph()
            
            # Calculate temporal metrics
            metrics = await self._calculate_temporal_metrics()
            
            # Generate temporal insights
            insights = await self._generate_temporal_insights()
            
            # Analyze temporal patterns
            patterns = await self._analyze_temporal_patterns()
            
            return {
                "temporal_nodes": [self._temporal_node_to_dict(node) for node in self.temporal_nodes.values()],
                "temporal_edges": [self._temporal_edge_to_dict(edge) for edge in self.temporal_edges],
                "timeline": self.timeline,
                "time_intervals": self.time_intervals,
                "metrics": metrics,
                "insights": insights,
                "patterns": patterns,
                "graph_info": {
                    "total_temporal_nodes": len(self.temporal_nodes),
                    "total_temporal_edges": len(self.temporal_edges),
                    "time_span": self._calculate_time_span(),
                    "node_types": self._count_temporal_node_types(),
                    "edge_types": self._count_temporal_edge_types()
                }
            }
            
        except Exception as e:
            logger.error(f"Error building temporal graph: {e}")
            return {"error": str(e)}
    
    # Core methods implementation (simplified for brevity)
    async def _create_temporal_nodes(self, temporal_entities: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Create temporal nodes from temporal entities"""
        
        for temp_entity in temporal_entities:
            node_id = self._generate_temporal_node_id(temp_entity["text"])
            
            # Parse temporal information
            start_time = None
            if temp_entity.get("parsed_datetime"):
                try:
                    start_time = datetime.fromisoformat(temp_entity["parsed_datetime"])
                except:
                    start_time = None
            
            # Determine node type
            node_type = self._classify_temporal_node_type(temp_entity)
            
            # Find related entities
            related_entities = self._find_related_entities(temp_entity, entities)
            
            temporal_node = TemporalNode(
                id=node_id,
                label=temp_entity["text"],
                node_type=node_type,
                start_time=start_time,
                end_time=None,
                duration_seconds=temp_entity.get("duration_seconds"),
                confidence=temp_entity.get("confidence", 0.5),
                properties={
                    "temporal_type": temp_entity.get("temporal_type", ""),
                    "normalized_value": temp_entity.get("normalized_value", ""),
                    "extraction_method": temp_entity.get("extraction_method", ""),
                    "original_text": temp_entity["text"]
                },
                related_entities=related_entities,
                context=temp_entity.get("context", "")
            )
            
            self.temporal_nodes[node_id] = temporal_node
    
    async def _build_temporal_relationships(self, temporal_relationships: List[Dict[str, Any]]):
        """Build temporal relationships from relationship data"""
        
        for rel_data in temporal_relationships:
            source_id = self._generate_temporal_node_id(rel_data["source_entity"])
            target_id = self._generate_temporal_node_id(rel_data["target_entity"])
            
            # Only create edge if both nodes exist
            if source_id in self.temporal_nodes and target_id in self.temporal_nodes:
                edge_type = self._map_temporal_relation_type(rel_data["relation_type"])
                
                temporal_edge = TemporalEdge(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=edge_type,
                    confidence=rel_data.get("confidence", 0.5),
                    evidence=[rel_data.get("evidence_text", "")],
                    properties={
                        "extraction_method": rel_data.get("extraction_method", ""),
                        "original_relation": rel_data["relation_type"]
                    }
                )
                
                self.temporal_edges.append(temporal_edge)
    
    async def _infer_temporal_relationships(self):
        """Infer additional temporal relationships based on time information"""
        
        # Get nodes with time information
        timed_nodes = [
            node for node in self.temporal_nodes.values()
            if node.start_time is not None
        ]
        
        # Sort by start time
        timed_nodes.sort(key=lambda x: x.start_time)
        
        # Infer BEFORE/AFTER relationships
        for i, node1 in enumerate(timed_nodes):
            for node2 in timed_nodes[i+1:]:
                time_diff = (node2.start_time - node1.start_time).total_seconds()
                
                # Only create relationships for events within reasonable proximity
                if time_diff <= self.time_window_hours * 3600:
                    edge_type = TemporalEdgeType.BEFORE
                    confidence = max(0.4, 1.0 - (time_diff / (self.time_window_hours * 3600)))
                    
                    # Check if relationship already exists
                    existing_edge = self._find_existing_edge(node1.id, node2.id)
                    if not existing_edge:
                        temporal_edge = TemporalEdge(
                            source_id=node1.id,
                            target_id=node2.id,
                            edge_type=edge_type,
                            confidence=confidence,
                            evidence=[f"{node1.label} occurs before {node2.label}"],
                            properties={"inferred": True, "time_diff_seconds": time_diff},
                            temporal_distance=int(time_diff)
                        )
                        self.temporal_edges.append(temporal_edge)
    
    async def _build_causality_relationships(self):
        """Build causality relationships based on temporal proximity and context"""
        pass  # Simplified for brevity
    
    async def _create_timeline(self):
        """Create a chronological timeline of temporal nodes"""
        
        # Get all nodes with time information
        timed_nodes = [
            node for node in self.temporal_nodes.values()
            if node.start_time is not None
        ]
        
        # Sort by start time
        timed_nodes.sort(key=lambda x: x.start_time)
        
        # Create timeline entries
        self.timeline = []
        for node in timed_nodes:
            timeline_entry = {
                "timestamp": node.start_time.isoformat(),
                "label": node.label,
                "node_type": node.node_type.value,
                "confidence": node.confidence,
                "duration": node.duration_seconds,
                "related_entities": node.related_entities,
                "context": node.context[:200] if node.context else ""
            }
            self.timeline.append(timeline_entry)
    
    async def _identify_time_intervals(self):
        """Identify significant time intervals and periods"""
        
        timed_nodes = [
            node for node in self.temporal_nodes.values()
            if node.start_time is not None
        ]
        
        if len(timed_nodes) < 2:
            return
        
        # Sort by time
        timed_nodes.sort(key=lambda x: x.start_time)
        
        # Identify periods of high activity
        time_buckets = defaultdict(list)
        
        for node in timed_nodes:
            # Group by day
            date_key = node.start_time.strftime("%Y-%m-%d")
            time_buckets[date_key].append(node)
        
        # Find significant periods
        avg_activity = sum(len(nodes) for nodes in time_buckets.values()) / len(time_buckets)
        
        significant_periods = {}
        for date_key, nodes in time_buckets.items():
            if len(nodes) > avg_activity * 1.5:  # Above average activity
                significant_periods[date_key] = {
                    "event_count": len(nodes),
                    "events": [node.label for node in nodes],
                    "significance_score": len(nodes) / avg_activity
                }
        
        self.time_intervals = {
            "significant_periods": significant_periods,
            "total_time_span": self._calculate_time_span(),
            "average_daily_activity": avg_activity
        }
    
    async def _create_temporal_networkx_graph(self) -> nx.DiGraph:
        """Create NetworkX directed graph for temporal data"""
        
        if not NETWORKX_AVAILABLE:
            return None
        
        G = nx.DiGraph()
        
        # Add temporal nodes
        for node in self.temporal_nodes.values():
            G.add_node(
                node.id,
                label=node.label,
                node_type=node.node_type.value,
                start_time=node.start_time.isoformat() if node.start_time else None,
                confidence=node.confidence,
                **node.properties
            )
        
        # Add temporal edges
        for edge in self.temporal_edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                edge_type=edge.edge_type.value,
                confidence=edge.confidence,
                **edge.properties
            )
        
        return G
    
    async def _calculate_temporal_metrics(self) -> Dict[str, Any]:
        """Calculate metrics for the temporal graph"""
        
        metrics = {
            "basic_stats": {
                "total_temporal_nodes": len(self.temporal_nodes),
                "total_temporal_edges": len(self.temporal_edges),
                "time_span": self._calculate_time_span(),
                "average_confidence": 0.0
            },
            "temporal_density": 0.0
        }
        
        try:
            # Basic statistics
            if self.temporal_nodes:
                avg_confidence = sum(node.confidence for node in self.temporal_nodes.values()) / len(self.temporal_nodes)
                metrics["basic_stats"]["average_confidence"] = avg_confidence
                
        except Exception as e:
            logger.warning(f"Error calculating temporal metrics: {e}")
        
        return metrics
    
    async def _generate_temporal_insights(self) -> Dict[str, Any]:
        """Generate insights about the temporal graph"""
        
        insights = {
            "key_events": [],
            "temporal_clusters": []
        }
        
        try:
            # Key events (high confidence, many relationships)
            event_importance = {}
            for node in self.temporal_nodes.values():
                # Count relationships
                rel_count = sum(
                    1 for edge in self.temporal_edges
                    if edge.source_id == node.id or edge.target_id == node.id
                )
                
                importance = node.confidence * (1 + rel_count * 0.1)
                event_importance[node.id] = importance
            
            # Top key events
            top_events = sorted(event_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            insights["key_events"] = [
                {
                    "label": self.temporal_nodes[node_id].label,
                    "importance": importance,
                    "confidence": self.temporal_nodes[node_id].confidence,
                    "start_time": self.temporal_nodes[node_id].start_time.isoformat() if self.temporal_nodes[node_id].start_time else None
                }
                for node_id, importance in top_events
                if node_id in self.temporal_nodes
            ]
            
        except Exception as e:
            logger.warning(f"Error generating temporal insights: {e}")
        
        return insights
    
    async def _analyze_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in temporal data"""
        
        patterns = {
            "sequence_patterns": [],
            "duration_patterns": {}
        }
        
        try:
            # Duration patterns
            durations = [
                node.duration_seconds for node in self.temporal_nodes.values()
                if node.duration_seconds is not None
            ]
            
            if durations:
                patterns["duration_patterns"] = {
                    "average_duration": sum(durations) / len(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations)
                }
            
        except Exception as e:
            logger.warning(f"Error analyzing temporal patterns: {e}")
        
        return patterns
    
    # Helper methods
    def _generate_temporal_node_id(self, text: str) -> str:
        """Generate consistent temporal node ID"""
        return f"temporal_{hashlib.md5(text.encode()).hexdigest()[:8]}"
    
    def _classify_temporal_node_type(self, temp_entity: Dict[str, Any]) -> TemporalNodeType:
        """Classify the type of temporal node"""
        
        temporal_type = temp_entity.get("temporal_type", "").upper()
        text = temp_entity["text"].lower()
        
        # Map temporal types
        if temporal_type == "ABSOLUTE_DATE" or "date" in text:
            return TemporalNodeType.TIME_POINT
        elif temporal_type == "DURATION" or "duration" in text:
            return TemporalNodeType.DURATION
        elif temporal_type == "FREQUENCY" or any(word in text for word in ["daily", "weekly", "monthly"]):
            return TemporalNodeType.FREQUENCY
        elif temporal_type == "EVENT_TIME" or any(word in text for word in ["event", "meeting", "conference"]):
            return TemporalNodeType.EVENT
        else:
            return TemporalNodeType.TIME_PERIOD
    
    def _find_related_entities(self, temp_entity: Dict[str, Any], entities: List[Dict[str, Any]]) -> List[str]:
        """Find entities related to this temporal entity"""
        
        related = []
        temp_text = temp_entity["text"].lower()
        context = temp_entity.get("context", "").lower()
        
        for entity in entities:
            entity_name = entity["name"].lower()
            
            # Check if entity appears in temporal context
            if entity_name in context or entity_name in temp_text:
                related.append(entity["name"])
        
        return related[:5]  # Limit to 5 related entities
    
    def _map_temporal_relation_type(self, relation_type: str) -> TemporalEdgeType:
        """Map string relation type to TemporalEdgeType"""
        
        type_mapping = {
            "BEFORE": TemporalEdgeType.BEFORE,
            "AFTER": TemporalEdgeType.AFTER,
            "DURING": TemporalEdgeType.DURING,
            "SIMULTANEOUS": TemporalEdgeType.SIMULTANEOUS,
            "OVERLAPS": TemporalEdgeType.OVERLAPS,
            "CONTAINS": TemporalEdgeType.CONTAINS,
            "STARTS": TemporalEdgeType.STARTS,
            "ENDS": TemporalEdgeType.FINISHES
        }
        
        return type_mapping.get(relation_type.upper(), TemporalEdgeType.BEFORE)
    
    def _find_existing_edge(self, source_id: str, target_id: str) -> Optional[TemporalEdge]:
        """Find existing edge between two nodes"""
        
        for edge in self.temporal_edges:
            if ((edge.source_id == source_id and edge.target_id == target_id) or
                (edge.source_id == target_id and edge.target_id == source_id)):
                return edge
        
        return None
    
    def _calculate_time_span(self) -> Dict[str, Any]:
        """Calculate the time span covered by temporal nodes"""
        
        timed_nodes = [
            node for node in self.temporal_nodes.values()
            if node.start_time is not None
        ]
        
        if not timed_nodes:
            return {"start": None, "end": None, "duration_days": 0}
        
        start_time = min(node.start_time for node in timed_nodes)
        end_time = max(node.start_time for node in timed_nodes)
        
        duration = (end_time - start_time).total_seconds() / 86400  # Convert to days
        
        return {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration_days": duration
        }
    
    def _count_temporal_node_types(self) -> Dict[str, int]:
        """Count temporal nodes by type"""
        type_counts = defaultdict(int)
        for node in self.temporal_nodes.values():
            type_counts[node.node_type.value] += 1
        return dict(type_counts)
    
    def _count_temporal_edge_types(self) -> Dict[str, int]:
        """Count temporal edges by type"""
        type_counts = defaultdict(int)
        for edge in self.temporal_edges:
            type_counts[edge.edge_type.value] += 1
        return dict(type_counts)
    
    def _temporal_node_to_dict(self, node: TemporalNode) -> Dict[str, Any]:
        """Convert TemporalNode to dictionary"""
        return {
            "id": node.id,
            "label": node.label,
            "node_type": node.node_type.value,
            "start_time": node.start_time.isoformat() if node.start_time else None,
            "end_time": node.end_time.isoformat() if node.end_time else None,
            "duration_seconds": node.duration_seconds,
            "confidence": node.confidence,
            "properties": node.properties,
            "related_entities": node.related_entities,
            "context": node.context
        }
    
    def _temporal_edge_to_dict(self, edge: TemporalEdge) -> Dict[str, Any]:
        """Convert TemporalEdge to dictionary"""
        return {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "edge_type": edge.edge_type.value,
            "confidence": edge.confidence,
            "evidence": edge.evidence,
            "properties": edge.properties,
            "temporal_distance": edge.temporal_distance
        }