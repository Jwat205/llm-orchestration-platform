"""
Graph service operations for knowledge graph management
"""

import asyncio
import logging
import time
import json
import hashlib
from typing import List, Dict, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from ..core.knowledge_graph import KnowledgeGraph, Entity, Relationship, EntityType, RelationshipType
from ..core.vector_store import VectorStore
from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EntityResolutionResult:
    """Result of entity resolution"""
    original_entity: str
    resolved_entity: str
    confidence: float
    resolution_method: str
    alternatives: List[Dict[str, Any]]


@dataclass
class CommunityDetectionResult:
    """Result of community detection"""
    community_id: str
    entities: List[str]
    size: int
    density: float
    central_entities: List[str]


@dataclass
class GraphAnalytics:
    """Graph analytics results"""
    total_entities: int
    total_relationships: int
    avg_degree: float
    density: float
    clustering_coefficient: float
    communities: List[CommunityDetectionResult]
    central_entities: List[Dict[str, Any]]
    relationship_distribution: Dict[str, int]


class GraphService:
    """Enhanced graph service with advanced operations"""
    
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        vector_store: Optional[VectorStore] = None
    ):
        self.knowledge_graph = knowledge_graph
        self.vector_store = vector_store
        
        # Entity resolution settings
        self.similarity_threshold = 0.85
        self.fuzzy_match_threshold = 0.8
        
        # Community detection settings
        self.min_community_size = 3
        self.max_communities = 50
        
        # Caching
        self.analytics_cache = {}
        self.resolution_cache = {}
        self.cache_ttl = 1800  # 30 minutes
        
        # Batch processing
        self.batch_status = {}
        
        # Statistics
        self.stats = {
            "entities_resolved": 0,
            "relationships_analyzed": 0,
            "communities_detected": 0,
            "graph_searches": 0
        }
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        return await self.knowledge_graph.extract_entities(text)
    
    async def extract_entities_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Extract entities from multiple texts in batch"""
        all_entities = []
        
        # Process in parallel batches
        batch_size = 50
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        
        for batch in batches:
            batch_results = await asyncio.gather(
                *[self.knowledge_graph.extract_entities(text) for text in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, list):
                    all_entities.extend(result)
                else:
                    logger.error(f"Error in batch entity extraction: {result}")
        
        # Deduplicate entities
        unique_entities = self._deduplicate_entities(all_entities)
        
        return unique_entities
    
    async def build_graph_from_texts(
        self,
        texts: List[str],
        extract_relationships: bool = True
    ) -> Dict[str, Any]:
        """Build knowledge graph from multiple texts"""
        results = {
            "entities": [],
            "relationships": [],
            "stats": {}
        }
        
        # Process texts in batches
        batch_size = 20
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        
        total_entities = 0
        total_relationships = 0
        
        for i, batch in enumerate(batches):
            logger.info(f"Processing batch {i+1}/{len(batches)}")
            
            batch_results = await asyncio.gather(
                *[
                    self.knowledge_graph.build_graph_from_text(
                        text, 
                        f"batch_processing_{i}"
                    ) 
                    for text in batch
                ],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, dict):
                    results["entities"].extend(result.get("entities", []))
                    results["relationships"].extend(result.get("relationships", []))
                    
                    stats = result.get("stats", {})
                    total_entities += stats.get("entities_created", 0)
                    total_relationships += stats.get("relationships_created", 0)
                else:
                    logger.error(f"Error in batch graph building: {result}")
        
        # Perform entity resolution
        if results["entities"]:
            resolved_entities = await self.resolve_entities_batch(
                [e["name"] for e in results["entities"]]
            )
            results["entity_resolution"] = resolved_entities
        
        results["stats"] = {
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "batches_processed": len(batches),
            "texts_processed": len(texts)
        }
        
        return results
    
    async def resolve_entities_batch(self, entity_names: List[str]) -> List[EntityResolutionResult]:
        """Resolve entity duplicates in batch"""
        results = []
        
        # Group similar entities
        entity_groups = await self._group_similar_entities(entity_names)
        
        for group in entity_groups:
            if len(group) > 1:
                # Resolve duplicates within group
                canonical_entity = await self._select_canonical_entity(group)
                
                for entity_name in group:
                    if entity_name != canonical_entity:
                        resolution = EntityResolutionResult(
                            original_entity=entity_name,
                            resolved_entity=canonical_entity,
                            confidence=0.9,  # High confidence for group resolution
                            resolution_method="similarity_grouping",
                            alternatives=[{"name": e, "score": 0.8} for e in group if e != entity_name]
                        )
                        results.append(resolution)
                        self.stats["entities_resolved"] += 1
        
        return results
    
    async def calculate_relationship_strength(
        self,
        source_entity: str,
        target_entity: str,
        relationship_type: RelationshipType
    ) -> float:
        """Calculate strength of relationship between entities"""
        
        # Find entities in graph
        source_entities = await self.knowledge_graph.graph_db.find_entities(name=source_entity)
        target_entities = await self.knowledge_graph.graph_db.find_entities(name=target_entity)
        
        if not source_entities or not target_entities:
            return 0.0
        
        source_id = source_entities[0].id
        target_id = target_entities[0].id
        
        # Get existing relationships
        relationships = await self.knowledge_graph.graph_db.get_entity_relationships(source_id)
        
        # Find specific relationship
        for rel in relationships:
            if (rel.target_entity_id == target_id and rel.type == relationship_type):
                return rel.strength
        
        # Calculate based on co-occurrence and graph structure
        base_strength = 0.1
        
        # Check for indirect connections
        path, confidence = await self.knowledge_graph.find_entity_path(
            source_entity, target_entity, max_hops=2
        )
        
        if path:
            # Stronger relationship if entities are closely connected
            indirect_strength = confidence * (1.0 / len(path))
            base_strength += indirect_strength
        
        # Check for common neighbors
        source_rels = await self.knowledge_graph.graph_db.get_entity_relationships(source_id)
        target_rels = await self.knowledge_graph.graph_db.get_entity_relationships(target_id)
        
        source_neighbors = set([
            rel.target_entity_id if rel.source_entity_id == source_id else rel.source_entity_id
            for rel in source_rels
        ])
        target_neighbors = set([
            rel.target_entity_id if rel.source_entity_id == target_id else rel.source_entity_id
            for rel in target_rels
        ])
        
        common_neighbors = len(source_neighbors.intersection(target_neighbors))
        if common_neighbors > 0:
            base_strength += min(common_neighbors * 0.1, 0.5)
        
        return min(base_strength, 1.0)
    
    async def detect_communities(self) -> List[CommunityDetectionResult]:
        """Detect communities in the knowledge graph"""
        
        # Check cache
        cache_key = "communities"
        if cache_key in self.analytics_cache:
            cache_entry = self.analytics_cache[cache_key]
            if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                return cache_entry["data"]
        
        # Get all entities and relationships
        all_entities = []
        all_relationships = []
        
        # This is a simplified approach - in practice, you'd page through results
        try:
            # Get sample of entities for community detection
            sample_entities = await self.knowledge_graph.graph_db.find_entities(limit=1000)
            all_entities = sample_entities
            
            # Get relationships for these entities
            for entity in sample_entities[:100]:  # Limit for performance
                entity_rels = await self.knowledge_graph.graph_db.get_entity_relationships(entity.id)
                all_relationships.extend(entity_rels)
        
        except Exception as e:
            logger.error(f"Error getting entities for community detection: {e}")
            return []
        
        if not all_entities or not all_relationships:
            return []
        
        # Build adjacency matrix
        entity_to_idx = {entity.id: idx for idx, entity in enumerate(all_entities)}
        n_entities = len(all_entities)
        adjacency_matrix = np.zeros((n_entities, n_entities))
        
        for rel in all_relationships:
            if rel.source_entity_id in entity_to_idx and rel.target_entity_id in entity_to_idx:
                source_idx = entity_to_idx[rel.source_entity_id]
                target_idx = entity_to_idx[rel.target_entity_id]
                adjacency_matrix[source_idx][target_idx] = rel.strength
                adjacency_matrix[target_idx][source_idx] = rel.strength  # Undirected
        
        # Perform clustering
        communities = await self._cluster_entities(adjacency_matrix, all_entities)
        
        # Cache results
        self.analytics_cache[cache_key] = {
            "data": communities,
            "timestamp": time.time()
        }
        
        self.stats["communities_detected"] = len(communities)
        
        return communities
    
    async def _cluster_entities(
        self,
        adjacency_matrix: np.ndarray,
        entities: List[Entity]
    ) -> List[CommunityDetectionResult]:
        """Cluster entities using adjacency matrix"""
        
        # Use spectral clustering approach
        n_entities = len(entities)
        n_clusters = min(self.max_communities, max(2, n_entities // 10))
        
        try:
            # Simple K-means clustering on adjacency matrix
            def cluster():
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                cluster_labels = kmeans.fit_predict(adjacency_matrix)
                return cluster_labels
            
            cluster_labels = await asyncio.to_thread(cluster)
            
        except Exception as e:
            logger.error(f"Error in clustering: {e}")
            return []
        
        # Build communities
        communities = []
        cluster_groups = defaultdict(list)
        
        for idx, label in enumerate(cluster_labels):
            cluster_groups[label].append(entities[idx])
        
        for cluster_id, cluster_entities in cluster_groups.items():
            if len(cluster_entities) >= self.min_community_size:
                # Calculate community metrics
                entity_ids = [e.id for e in cluster_entities]
                
                # Calculate density (simplified)
                internal_edges = 0
                possible_edges = len(cluster_entities) * (len(cluster_entities) - 1) / 2
                
                for i, entity_i in enumerate(cluster_entities):
                    for entity_j in cluster_entities[i+1:]:
                        if adjacency_matrix[entities.index(entity_i)][entities.index(entity_j)] > 0:
                            internal_edges += 1
                
                density = internal_edges / possible_edges if possible_edges > 0 else 0.0
                
                # Find central entities (simplified - based on degree)
                entity_degrees = []
                for entity in cluster_entities:
                    entity_idx = entities.index(entity)
                    degree = np.sum(adjacency_matrix[entity_idx] > 0)
                    entity_degrees.append((entity.name, degree))
                
                entity_degrees.sort(key=lambda x: x[1], reverse=True)
                central_entities = [name for name, _ in entity_degrees[:3]]
                
                community = CommunityDetectionResult(
                    community_id=f"community_{cluster_id}",
                    entities=[e.name for e in cluster_entities],
                    size=len(cluster_entities),
                    density=density,
                    central_entities=central_entities
                )
                communities.append(community)
        
        return communities
    
    async def analyze_temporal_patterns(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Analyze temporal patterns in graph evolution"""
        
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        # This is a simplified implementation
        # In practice, you'd analyze entity/relationship creation timestamps
        
        patterns = {
            "entity_creation_timeline": [],
            "relationship_formation_timeline": [],
            "growth_rate": 0.0,
            "peak_activity_periods": [],
            "entity_lifecycle_patterns": []
        }
        
        # Placeholder analysis
        patterns["growth_rate"] = 0.1  # 10% growth
        patterns["peak_activity_periods"] = [
            {
                "period": "morning",
                "entity_creation_rate": 0.3,
                "relationship_formation_rate": 0.2
            }
        ]
        
        return patterns
    
    async def validate_graph_consistency(self) -> Dict[str, Any]:
        """Validate graph consistency and identify issues"""
        
        issues = {
            "orphaned_entities": [],
            "dangling_relationships": [],
            "duplicate_entities": [],
            "inconsistent_relationships": [],
            "summary": {}
        }
        
        # Get sample of entities for validation
        try:
            entities = await self.knowledge_graph.graph_db.find_entities(limit=500)
            
            # Check for orphaned entities (no relationships)
            for entity in entities:
                relationships = await self.knowledge_graph.graph_db.get_entity_relationships(entity.id)
                if not relationships:
                    issues["orphaned_entities"].append({
                        "id": entity.id,
                        "name": entity.name,
                        "type": entity.type.value
                    })
            
            # Check for potential duplicates (simplified)
            entity_names = [e.name.lower() for e in entities]
            name_counts = Counter(entity_names)
            
            for name, count in name_counts.items():
                if count > 1:
                    duplicate_entities = [e for e in entities if e.name.lower() == name]
                    issues["duplicate_entities"].append({
                        "name": name,
                        "count": count,
                        "entities": [{"id": e.id, "confidence": e.confidence} for e in duplicate_entities]
                    })
        
        except Exception as e:
            logger.error(f"Error in graph validation: {e}")
        
        # Generate summary
        issues["summary"] = {
            "total_issues": len(issues["orphaned_entities"]) + len(issues["duplicate_entities"]),
            "orphaned_entities_count": len(issues["orphaned_entities"]),
            "duplicate_entities_count": len(issues["duplicate_entities"]),
            "validation_timestamp": datetime.now().isoformat()
        }
        
        return issues
    
    async def get_graph_insights(self) -> Dict[str, Any]:
        """Get comprehensive graph insights and analytics"""
        
        insights = {
            "overview": {},
            "growth_trends": {},
            "entity_analysis": {},
            "relationship_analysis": {},
            "community_structure": {},
            "quality_metrics": {}
        }
        
        try:
            # Basic statistics
            graph_stats = await self.knowledge_graph.get_stats()
            insights["overview"] = graph_stats
            
            # Community analysis
            communities = await self.detect_communities()
            insights["community_structure"] = {
                "total_communities": len(communities),
                "avg_community_size": np.mean([c.size for c in communities]) if communities else 0,
                "largest_community_size": max([c.size for c in communities]) if communities else 0,
                "communities": [asdict(c) for c in communities[:10]]  # Top 10 communities
            }
            
            # Entity type distribution
            sample_entities = await self.knowledge_graph.graph_db.find_entities(limit=1000)
            entity_types = Counter([e.type.value for e in sample_entities])
            insights["entity_analysis"] = {
                "type_distribution": dict(entity_types),
                "total_unique_types": len(entity_types),
                "most_common_type": entity_types.most_common(1)[0] if entity_types else None
            }
            
            # Quality metrics
            validation_results = await self.validate_graph_consistency()
            insights["quality_metrics"] = validation_results["summary"]
            
        except Exception as e:
            logger.error(f"Error generating graph insights: {e}")
            insights["error"] = str(e)
        
        return insights
    
    async def search_entities(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
        include_relationships: bool = True,
        relationship_depth: int = 1
    ) -> Dict[str, Any]:
        """Search for entities and optionally include relationships"""
        
        self.stats["graph_searches"] += 1
        
        # Find entities
        entity_type_enum = EntityType(entity_type) if entity_type else None
        entities = await self.knowledge_graph.graph_db.find_entities(
            name=entity_name,
            entity_type=entity_type_enum,
            limit=50
        )
        
        result = {
            "entities": [e.to_dict() for e in entities],
            "total_found": len(entities)
        }
        
        if include_relationships and entities:
            all_relationships = []
            
            for entity in entities[:10]:  # Limit for performance
                # Get direct relationships
                relationships = await self.knowledge_graph.graph_db.get_entity_relationships(entity.id)
                all_relationships.extend([r.to_dict() for r in relationships])
                
                # Get deeper relationships if requested
                if relationship_depth > 1:
                    for rel in relationships[:5]:  # Limit expansion
                        related_entity_id = (
                            rel.target_entity_id if rel.source_entity_id == entity.id 
                            else rel.source_entity_id
                        )
                        
                        deeper_rels = await self.knowledge_graph.graph_db.get_entity_relationships(
                            related_entity_id
                        )
                        all_relationships.extend([r.to_dict() for r in deeper_rels[:3]])
            
            # Deduplicate relationships
            unique_relationships = {}
            for rel in all_relationships:
                unique_relationships[rel["id"]] = rel
            
            result["relationships"] = list(unique_relationships.values())
            result["relationship_count"] = len(result["relationships"])
        
        return result
    
    async def search_relationships(
        self,
        source_entity: Optional[str] = None,
        target_entity: Optional[str] = None,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.0,
        max_hops: int = 3
    ) -> Dict[str, Any]:
        """Search for relationships with optional filtering"""
        
        relationships = []
        paths = []
        
        if source_entity and target_entity:
            # Find specific path
            path, confidence = await self.knowledge_graph.find_entity_path(
                source_entity,
                target_entity,
                max_hops,
                [RelationshipType(relationship_type)] if relationship_type else None
            )
            
            if path:
                paths.append({
                    "source": source_entity,
                    "target": target_entity,
                    "path": path,
                    "confidence": confidence,
                    "length": len(path) - 1
                })
        
        elif source_entity:
            # Find all relationships from source
            source_entities = await self.knowledge_graph.graph_db.find_entities(name=source_entity)
            
            if source_entities:
                entity_rels = await self.knowledge_graph.graph_db.get_entity_relationships(
                    source_entities[0].id,
                    [RelationshipType(relationship_type)] if relationship_type else None
                )
                
                for rel in entity_rels:
                    if rel.strength >= min_strength:
                        relationships.append(rel.to_dict())
        
        return {
            "relationships": relationships,
            "paths": paths,
            "stats": {
                "total_relationships": len(relationships),
                "total_paths": len(paths),
                "avg_relationship_strength": np.mean([r.get("strength", 0) for r in relationships]) if relationships else 0
            }
        }
    
    async def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
        top_k: int = 10,
        graph_depth: int = 2,
        entity_types: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        boost_entities: Optional[List[str]] = None,
        temporal_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform hybrid search combining vector similarity and graph traversal"""
        
        start_time = time.time()
        
        # Step 1: Extract entities from query
        query_entities = await self.knowledge_graph.extract_entities(query)
        
        # Step 2: Graph-based search
        graph_results = []
        
        if query_entities:
            # Get related entities through graph traversal
            related_entities = await self.knowledge_graph.traverse_graph(
                start_entities=[e["name"] for e in query_entities],
                relationship_types=[RelationshipType(rt) for rt in relationship_types] if relationship_types else None,
                max_hops=graph_depth
            )
            
            graph_results = related_entities
        
        # Step 3: Vector search (if vector store is available)
        vector_results = []
        if self.vector_store:
            try:
                # This would typically create query embedding and search
                # Simplified for now
                vector_results = []
            except Exception as e:
                logger.error(f"Vector search error: {e}")
        
        # Step 4: Combine and rank results
        combined_results = []
        
        # Process graph results
        for entity in graph_results:
            graph_score = 0.8  # Base graph score
            
            # Boost specific entities if requested
            if boost_entities and entity["name"] in boost_entities:
                graph_score *= 1.5
            
            # Apply temporal filter
            if temporal_filter:
                # Check if entity meets temporal criteria
                entity_date = entity.get("created_at")
                if entity_date:
                    # Simplified temporal filtering
                    pass
            
            combined_score = graph_weight * graph_score
            
            combined_results.append({
                "id": entity["id"],
                "name": entity["name"],
                "type": entity["type"],
                "graph_score": graph_score,
                "vector_score": 0.0,
                "combined_score": combined_score,
                "source": "graph"
            })
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        result = {
            "results": combined_results[:top_k],
            "query_time": time.time() - start_time,
            "graph_stats": {
                "query_entities": len(query_entities),
                "graph_results": len(graph_results),
                "vector_results": len(vector_results)
            },
            "insights": {
                "primary_entities": [e["name"] for e in query_entities],
                "search_strategy": "hybrid",
                "weights": {
                    "vector_weight": vector_weight,
                    "graph_weight": graph_weight
                }
            }
        }
        
        return result
    
    async def graph_search(
        self,
        query: str,
        depth: int = 2,
        entity_types: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """Perform pure graph-based search"""
        
        start_time = time.time()
        
        # Extract entities from query
        query_entities = await self.knowledge_graph.extract_entities(query)
        
        if not query_entities:
            return {
                "results": [],
                "query_time": time.time() - start_time,
                "message": "No entities found in query"
            }
        
        # Traverse graph from query entities
        related_entities = await self.knowledge_graph.traverse_graph(
            start_entities=[e["name"] for e in query_entities],
            relationship_types=[RelationshipType(rt) for rt in relationship_types] if relationship_types else None,
            max_hops=depth
        )
        
        # Filter by entity types if specified
        if entity_types:
            related_entities = [
                e for e in related_entities 
                if e["type"] in entity_types
            ]
        
        # Score entities based on relevance to query
        scored_entities = []
        for entity in related_entities:
            # Simple scoring based on name similarity and type match
            score = 0.5  # Base score
            
            # Boost if entity name appears in query
            if entity["name"].lower() in query.lower():
                score += 0.4
            
            # Boost if entity type matches query context
            if entity_types and entity["type"] in entity_types:
                score += 0.1
            
            scored_entities.append({
                **entity,
                "relevance_score": score
            })
        
        # Sort by score and return top results
        scored_entities.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return {
            "results": scored_entities[:top_k],
            "query_time": time.time() - start_time,
            "graph_stats": {
                "query_entities": len(query_entities),
                "traversed_entities": len(related_entities),
                "filtered_entities": len(scored_entities)
            }
        }
    
    async def get_context_for_text(self, text: str, depth: int = 2) -> Dict[str, Any]:
        """Get graph context for a given text"""
        
        # Extract entities from text
        entities = await self.knowledge_graph.extract_entities(text)
        
        if not entities:
            return {"context": "No entities found"}
        
        # Get context for entities
        context = await self.knowledge_graph.get_entity_context(
            [e["name"] for e in entities],
            depth=depth
        )
        
        return context
    
    async def get_context_for_entities(self, entity_names: List[str]) -> Dict[str, Any]:
        """Get graph context for specific entities"""
        return await self.knowledge_graph.get_entity_context(entity_names)
    
    async def summarize_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize a list of entities"""
        
        if not entities:
            return {"summary": "No entities to summarize"}
        
        # Count entity types
        type_counts = Counter([e.get("type", "UNKNOWN") for e in entities])
        
        # Find most confident entities
        confident_entities = sorted(entities, key=lambda x: x.get("confidence", 0), reverse=True)[:5]
        
        summary = {
            "total_entities": len(entities),
            "entity_types": dict(type_counts),
            "most_common_type": type_counts.most_common(1)[0] if type_counts else None,
            "highest_confidence_entities": [
                {"name": e.get("name"), "confidence": e.get("confidence", 0)} 
                for e in confident_entities
            ],
            "avg_confidence": np.mean([e.get("confidence", 0) for e in entities])
        }
        
        return summary
    
    async def analyze_search_patterns(
        self,
        query: str,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze patterns in search results"""
        
        patterns = {
            "query_analysis": {
                "query_length": len(query.split()),
                "entity_mentions": sum(1 for e in entities if e.get("name", "").lower() in query.lower())
            },
            "result_patterns": {
                "entity_type_distribution": Counter([e.get("type") for e in entities]),
                "confidence_distribution": {
                    "high": len([e for e in entities if e.get("confidence", 0) > 0.8]),
                    "medium": len([e for e in entities if 0.5 < e.get("confidence", 0) <= 0.8]),
                    "low": len([e for e in entities if e.get("confidence", 0) <= 0.5])
                }
            },
            "recommendations": []
        }
        
        # Generate recommendations
        if patterns["query_analysis"]["entity_mentions"] == 0:
            patterns["recommendations"].append("Consider using more specific entity names in query")
        
        if patterns["result_patterns"]["confidence_distribution"]["low"] > len(entities) * 0.5:
            patterns["recommendations"].append("Results have low confidence - consider refining query")
        
        return patterns
    
    async def build_relationships_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Build relationships from batch of texts"""
        
        all_relationships = []
        
        # Process texts in smaller batches
        batch_size = 20
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        
        for batch in batches:
            batch_results = await asyncio.gather(
                *[self._extract_relationships_from_text(text) for text in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, list):
                    all_relationships.extend(result)
                else:
                    logger.error(f"Error in batch relationship extraction: {result}")
        
        return all_relationships
    
    async def _extract_relationships_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract relationships from a single text"""
        
        # Extract entities first
        entities = await self.knowledge_graph.extract_entities(text)
        
        if len(entities) < 2:
            return []
        
        # Use the relationship extractor from knowledge graph
        relationships = await self.knowledge_graph.relationship_extractor.extract_relationships(
            text, entities
        )
        
        return relationships
    
    async def update_batch_graph_status(
        self,
        batch_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update batch processing status"""
        
        if batch_id not in self.batch_status:
            self.batch_status[batch_id] = {
                "created_at": datetime.now().isoformat()
            }
        
        self.batch_status[batch_id].update({
            "status": status,
            "updated_at": datetime.now().isoformat()
        })
        
        if metadata:
            self.batch_status[batch_id].update(metadata)
    
    async def get_graph_analytics(self) -> Dict[str, Any]:
        """Get comprehensive graph analytics"""
        
        analytics = {
            "basic_stats": await self.knowledge_graph.get_stats(),
            "service_stats": self.stats,
            "communities": await self.detect_communities(),
            "insights": await self.get_graph_insights(),
            "cache_stats": {
                "analytics_cache_size": len(self.analytics_cache),
                "resolution_cache_size": len(self.resolution_cache),
                "cache_ttl": self.cache_ttl
            }
        }
        
        return analytics
    
    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities from list"""
        
        seen = set()
        unique_entities = []
        
        for entity in entities:
            # Create key from name and type
            key = (entity.get("name", "").lower(), entity.get("type", ""))
            
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)
        
        return unique_entities
    
    async def _group_similar_entities(self, entity_names: List[str]) -> List[List[str]]:
        """Group similar entity names together"""
        
        # Simple similarity grouping based on string similarity
        from difflib import SequenceMatcher
        
        groups = []
        used = set()
        
        for i, name1 in enumerate(entity_names):
            if name1 in used:
                continue
            
            group = [name1]
            used.add(name1)
            
            for j, name2 in enumerate(entity_names[i+1:], i+1):
                if name2 in used:
                    continue
                
                # Calculate similarity
                similarity = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
                
                if similarity >= self.similarity_threshold:
                    group.append(name2)
                    used.add(name2)
            
            groups.append(group)
        
        return groups
    
    async def _select_canonical_entity(self, entity_group: List[str]) -> str:
        """Select canonical entity from a group of similar entities"""
        
        # Simple heuristic: select longest name (often more descriptive)
        return max(entity_group, key=len)
    
    async def expand_entity_context(
        self,
        entity_results: Dict[str, Any],
        include_similar_entities: bool = True
    ) -> Dict[str, Any]:
        """Expand entity search results with additional context"""
        
        expanded_results = entity_results.copy()
        
        if include_similar_entities and "entities" in entity_results:
            similar_entities = []
            
            for entity in entity_results["entities"][:5]:  # Limit for performance
                # Find related entities through graph traversal
                related = await self.knowledge_graph.traverse_graph(
                    start_entities=[entity["name"]],
                    max_hops=1
                )
                
                # Add to similar entities (excluding the original)
                for rel_entity in related:
                    if rel_entity["name"] != entity["name"]:
                        similar_entities.append(rel_entity)
            
            expanded_results["similar_entities"] = similar_entities[:10]
        
        return expanded_results
    
    async def get_relationship_context(
        self,
        relationship_results: Dict[str, Any],
        include_surrounding_entities: bool = True
    ) -> Dict[str, Any]:
        """Get context for relationship search results"""
        
        context = {}
        
        if include_surrounding_entities and "relationships" in relationship_results:
            surrounding_entities = set()
            
            for rel in relationship_results["relationships"][:10]:
                # Get entities involved in the relationship
                source_id = rel.get("source_entity_id")
                target_id = rel.get("target_entity_id")
                
                if source_id:
                    source_entity = await self.knowledge_graph.graph_db.get_entity(source_id)
                    if source_entity:
                        surrounding_entities.add(source_entity.name)
                
                if target_id:
                    target_entity = await self.knowledge_graph.graph_db.get_entity(target_id)
                    if target_entity:
                        surrounding_entities.add(target_entity.name)
            
            context["surrounding_entities"] = list(surrounding_entities)
            context["entity_count"] = len(surrounding_entities)
        
        return context