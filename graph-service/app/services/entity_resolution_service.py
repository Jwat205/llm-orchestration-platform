"""
Entity Resolution Service using Embeddings and Graph Analysis.
Identifies and merges duplicate entities in the knowledge graph.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class ResolutionStrategy(Enum):
    EMBEDDING_ONLY = "embedding_only"
    GRAPH_ONLY = "graph_only"
    HYBRID = "hybrid"
    ACTIVE_LEARNING = "active_learning"

class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class EntityMatch:
    entity1_id: str
    entity2_id: str
    similarity_score: float
    confidence_level: ConfidenceLevel
    matching_features: List[str]
    resolution_method: str
    evidence: Dict[str, Any]
    
@dataclass
class ResolutionConfig:
    strategy: ResolutionStrategy = ResolutionStrategy.HYBRID
    similarity_threshold: float = 0.8
    name_similarity_weight: float = 0.4
    embedding_similarity_weight: float = 0.3
    graph_similarity_weight: float = 0.3
    require_type_match: bool = True
    max_candidates_per_entity: int = 10
    batch_size: int = 100

class EntityResolutionService:
    """Service for entity resolution and deduplication."""
    
    def __init__(self, graph_engine, embedding_service):
        self.logger = logging.getLogger(__name__)
        self.graph_engine = graph_engine
        self.embedding_service = embedding_service
        
        # Resolution cache and state
        self.resolution_cache = {}
        self.known_matches = set()  # Set of (id1, id2) tuples
        self.known_non_matches = set()
        
        # Statistics
        self.stats = {
            "total_resolutions": 0,
            "matches_found": 0,
            "entities_merged": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "precision": 0.0,
            "recall": 0.0
        }
    
    async def initialize(self):
        """Initialize entity resolution service"""
        await self._load_known_matches()
        self.logger.info("Entity resolution service initialized")
    
    async def find_duplicate_entities(self, entity_ids: List[str] = None, 
                                    config: ResolutionConfig = None) -> List[EntityMatch]:
        """Find duplicate entities in the graph"""
        try:
            if config is None:
                config = ResolutionConfig()
            
            # Get entities to analyze
            if entity_ids is None:
                entities = await self._get_entities_for_resolution(config.batch_size)
            else:
                entities = []
                for entity_id in entity_ids:
                    entity = await self.graph_engine.get_entity(entity_id)
                    if entity:
                        entities.append(entity)
            
            if len(entities) < 2:
                return []
            
            # Find matches based on strategy
            if config.strategy == ResolutionStrategy.EMBEDDING_ONLY:
                matches = await self._find_matches_embedding_only(entities, config)
            elif config.strategy == ResolutionStrategy.GRAPH_ONLY:
                matches = await self._find_matches_graph_only(entities, config)
            elif config.strategy == ResolutionStrategy.HYBRID:
                matches = await self._find_matches_hybrid(entities, config)
            elif config.strategy == ResolutionStrategy.ACTIVE_LEARNING:
                matches = await self._find_matches_active_learning(entities, config)
            else:
                matches = await self._find_matches_hybrid(entities, config)
            
            # Filter and validate matches
            validated_matches = await self._validate_matches(matches, config)
            
            # Update statistics
            self.stats["total_resolutions"] += 1
            self.stats["matches_found"] += len(validated_matches)
            
            return validated_matches
            
        except Exception as e:
            self.logger.error(f"Error finding duplicate entities: {e}")
            return []
    
    async def resolve_entity_duplicates(self, matches: List[EntityMatch], 
                                      auto_merge: bool = False) -> Dict[str, Any]:
        """Resolve entity duplicates by merging"""
        try:
            resolution_results = {
                "merged_entities": [],
                "failed_merges": [],
                "conflicts": [],
                "summary": {}
            }
            
            # Group matches into clusters
            clusters = await self._cluster_matches(matches)
            
            for cluster in clusters:
                try:
                    if auto_merge or await self._should_auto_merge(cluster):
                        merge_result = await self._merge_entity_cluster(cluster)
                        if merge_result["success"]:
                            resolution_results["merged_entities"].append(merge_result)
                            self.stats["entities_merged"] += len(cluster) - 1
                        else:
                            resolution_results["failed_merges"].append({
                                "cluster": cluster,
                                "error": merge_result["error"]
                            })
                    else:
                        # Flag for manual review
                        resolution_results["conflicts"].append({
                            "cluster": cluster,
                            "reason": "requires_manual_review"
                        })
                        
                except Exception as e:
                    self.logger.error(f"Error merging cluster: {e}")
                    resolution_results["failed_merges"].append({
                        "cluster": cluster,
                        "error": str(e)
                    })
            
            # Generate summary
            resolution_results["summary"] = {
                "total_clusters": len(clusters),
                "merged_clusters": len(resolution_results["merged_entities"]),
                "failed_merges": len(resolution_results["failed_merges"]),
                "conflicts": len(resolution_results["conflicts"]),
                "entities_processed": sum(len(cluster) for cluster in clusters)
            }
            
            return resolution_results
            
        except Exception as e:
            self.logger.error(f"Error resolving entity duplicates: {e}")
            return {"error": str(e)}
    
    async def _find_matches_embedding_only(self, entities: List[Dict[str, Any]], 
                                         config: ResolutionConfig) -> List[EntityMatch]:
        """Find matches using embedding similarity only"""
        matches = []
        
        try:
            # Get embeddings for all entities
            entity_texts = []
            for entity in entities:
                entity_text = self._create_entity_signature(entity)
                entity_texts.append(entity_text)
            
            embeddings = await self.embedding_service.get_embeddings_batch(
                entity_texts, "entity"
            )
            
            # Compare all pairs
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    entity1 = entities[i]
                    entity2 = entities[j]
                    
                    # Skip if different types and type matching required
                    if (config.require_type_match and 
                        entity1.get("type") != entity2.get("type")):
                        continue
                    
                    # Calculate embedding similarity
                    similarity = await self.embedding_service.compute_similarity(
                        embeddings[i], embeddings[j]
                    )
                    
                    if similarity >= config.similarity_threshold:
                        confidence = self._determine_confidence_level(similarity)
                        
                        match = EntityMatch(
                            entity1_id=entity1["id"],
                            entity2_id=entity2["id"],
                            similarity_score=similarity,
                            confidence_level=confidence,
                            matching_features=["embedding_similarity"],
                            resolution_method="embedding_only",
                            evidence={"embedding_similarity": similarity}
                        )
                        matches.append(match)
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error in embedding-only matching: {e}")
            return []
    
    async def _find_matches_graph_only(self, entities: List[Dict[str, Any]], 
                                     config: ResolutionConfig) -> List[EntityMatch]:
        """Find matches using graph structure only"""
        matches = []
        
        try:
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    entity1 = entities[i]
                    entity2 = entities[j]
                    
                    # Skip if different types and type matching required
                    if (config.require_type_match and 
                        entity1.get("type") != entity2.get("type")):
                        continue
                    
                    # Calculate graph-based similarity
                    graph_similarity = await self._calculate_graph_similarity(
                        entity1["id"], entity2["id"]
                    )
                    
                    if graph_similarity >= config.similarity_threshold:
                        confidence = self._determine_confidence_level(graph_similarity)
                        
                        match = EntityMatch(
                            entity1_id=entity1["id"],
                            entity2_id=entity2["id"],
                            similarity_score=graph_similarity,
                            confidence_level=confidence,
                            matching_features=["graph_structure"],
                            resolution_method="graph_only",
                            evidence={"graph_similarity": graph_similarity}
                        )
                        matches.append(match)
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error in graph-only matching: {e}")
            return []
    
    async def _find_matches_hybrid(self, entities: List[Dict[str, Any]], 
                                 config: ResolutionConfig) -> List[EntityMatch]:
        """Find matches using hybrid approach"""
        matches = []
        
        try:
            # Get embeddings for all entities
            entity_texts = []
            for entity in entities:
                entity_text = self._create_entity_signature(entity)
                entity_texts.append(entity_text)
            
            embeddings = await self.embedding_service.get_embeddings_batch(
                entity_texts, "entity"
            )
            
            # Compare all pairs
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    entity1 = entities[i]
                    entity2 = entities[j]
                    
                    # Skip if different types and type matching required
                    if (config.require_type_match and 
                        entity1.get("type") != entity2.get("type")):
                        continue
                    
                    # Calculate multiple similarity measures
                    name_similarity = self._calculate_name_similarity(entity1, entity2)
                    
                    embedding_similarity = await self.embedding_service.compute_similarity(
                        embeddings[i], embeddings[j]
                    )
                    
                    graph_similarity = await self._calculate_graph_similarity(
                        entity1["id"], entity2["id"]
                    )
                    
                    # Weighted combination
                    combined_similarity = (
                        config.name_similarity_weight * name_similarity +
                        config.embedding_similarity_weight * embedding_similarity +
                        config.graph_similarity_weight * graph_similarity
                    )
                    
                    if combined_similarity >= config.similarity_threshold:
                        # Determine matching features
                        matching_features = []
                        if name_similarity > 0.7:
                            matching_features.append("name_similarity")
                        if embedding_similarity > 0.7:
                            matching_features.append("embedding_similarity")
                        if graph_similarity > 0.5:
                            matching_features.append("graph_structure")
                        
                        confidence = self._determine_confidence_level(combined_similarity)
                        
                        match = EntityMatch(
                            entity1_id=entity1["id"],
                            entity2_id=entity2["id"],
                            similarity_score=combined_similarity,
                            confidence_level=confidence,
                            matching_features=matching_features,
                            resolution_method="hybrid",
                            evidence={
                                "name_similarity": name_similarity,
                                "embedding_similarity": embedding_similarity,
                                "graph_similarity": graph_similarity,
                                "combined_similarity": combined_similarity
                            }
                        )
                        matches.append(match)
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error in hybrid matching: {e}")
            return []
    
    async def _find_matches_active_learning(self, entities: List[Dict[str, Any]], 
                                          config: ResolutionConfig) -> List[EntityMatch]:
        """Find matches using active learning approach"""
        try:
            # Start with hybrid approach
            candidate_matches = await self._find_matches_hybrid(entities, config)
            
            # Filter based on known matches/non-matches
            filtered_matches = []
            uncertain_matches = []
            
            for match in candidate_matches:
                pair = (match.entity1_id, match.entity2_id)
                reverse_pair = (match.entity2_id, match.entity1_id)
                
                if pair in self.known_matches or reverse_pair in self.known_matches:
                    match.confidence_level = ConfidenceLevel.VERY_HIGH
                    filtered_matches.append(match)
                elif pair in self.known_non_matches or reverse_pair in self.known_non_matches:
                    # Skip known non-matches
                    continue
                elif match.confidence_level == ConfidenceLevel.MEDIUM:
                    uncertain_matches.append(match)
                else:
                    filtered_matches.append(match)
            
            # For uncertain matches, could trigger manual review or additional analysis
            # For now, we'll include them with adjusted confidence
            for match in uncertain_matches:
                match.confidence_level = ConfidenceLevel.LOW
                filtered_matches.append(match)
            
            return filtered_matches
            
        except Exception as e:
            self.logger.error(f"Error in active learning matching: {e}")
            return []
    
    def _create_entity_signature(self, entity: Dict[str, Any]) -> str:
        """Create a text signature for entity comparison"""
        parts = []
        
        # Add name/title
        properties = entity.get("properties", {})
        if "name" in entity:
            parts.append(entity["name"])
        elif "name" in properties:
            parts.append(properties["name"])
        elif "title" in properties:
            parts.append(properties["title"])
        
        # Add type
        if "type" in entity:
            parts.append(f"Type: {entity['type']}")
        
        # Add key properties
        key_properties = ["description", "email", "phone", "address", "website"]
        for prop in key_properties:
            if prop in properties and properties[prop]:
                parts.append(f"{prop}: {properties[prop]}")
        
        return " | ".join(parts)
    
    def _calculate_name_similarity(self, entity1: Dict[str, Any], 
                                 entity2: Dict[str, Any]) -> float:
        """Calculate name-based similarity"""
        try:
            name1 = self._get_entity_name(entity1)
            name2 = self._get_entity_name(entity2)
            
            if not name1 or not name2:
                return 0.0
            
            # Simple string similarity (could use more sophisticated methods)
            name1_lower = name1.lower().strip()
            name2_lower = name2.lower().strip()
            
            if name1_lower == name2_lower:
                return 1.0
            
            # Calculate Levenshtein-like similarity
            return self._string_similarity(name1_lower, name2_lower)
            
        except Exception as e:
            self.logger.error(f"Error calculating name similarity: {e}")
            return 0.0
    
    def _get_entity_name(self, entity: Dict[str, Any]) -> Optional[str]:
        """Extract name from entity"""
        if "name" in entity:
            return entity["name"]
        
        properties = entity.get("properties", {})
        for name_field in ["name", "title", "label", "display_name"]:
            if name_field in properties:
                return properties[name_field]
        
        return None
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using Jaccard similarity of character n-grams"""
        try:
            if not s1 or not s2:
                return 0.0
            
            # Create character bigrams
            bigrams1 = set(s1[i:i+2] for i in range(len(s1)-1))
            bigrams2 = set(s2[i:i+2] for i in range(len(s2)-1))
            
            if not bigrams1 and not bigrams2:
                return 1.0
            
            if not bigrams1 or not bigrams2:
                return 0.0
            
            # Jaccard similarity
            intersection = len(bigrams1 & bigrams2)
            union = len(bigrams1 | bigrams2)
            
            return intersection / union if union > 0 else 0.0
            
        except Exception:
            return 0.0
    
    async def _calculate_graph_similarity(self, entity1_id: str, entity2_id: str) -> float:
        """Calculate graph-based similarity between entities"""
        try:
            # Get relationships for both entities
            rels1 = await self.graph_engine.get_entity_relationships(entity1_id)
            rels2 = await self.graph_engine.get_entity_relationships(entity2_id)
            
            if not rels1 and not rels2:
                return 0.5  # Both have no relationships - neutral
            
            if not rels1 or not rels2:
                return 0.1  # One has relationships, other doesn't - low similarity
            
            # Extract neighbor sets
            neighbors1 = set()
            neighbors2 = set()
            
            for rel in rels1:
                neighbor = rel["target_id"] if rel["source_id"] == entity1_id else rel["source_id"]
                neighbors1.add(neighbor)
            
            for rel in rels2:
                neighbor = rel["target_id"] if rel["source_id"] == entity2_id else rel["source_id"]
                neighbors2.add(neighbor)
            
            # Calculate Jaccard similarity of neighbors
            intersection = len(neighbors1 & neighbors2)
            union = len(neighbors1 | neighbors2)
            
            jaccard_similarity = intersection / union if union > 0 else 0.0
            
            # Consider relationship types similarity
            rel_types1 = set(rel["type"] for rel in rels1)
            rel_types2 = set(rel["type"] for rel in rels2)
            
            type_intersection = len(rel_types1 & rel_types2)
            type_union = len(rel_types1 | rel_types2)
            
            type_similarity = type_intersection / type_union if type_union > 0 else 0.0
            
            # Weighted combination
            graph_similarity = 0.7 * jaccard_similarity + 0.3 * type_similarity
            
            return graph_similarity
            
        except Exception as e:
            self.logger.error(f"Error calculating graph similarity: {e}")
            return 0.0
    
    def _determine_confidence_level(self, similarity_score: float) -> ConfidenceLevel:
        """Determine confidence level based on similarity score"""
        if similarity_score >= 0.95:
            return ConfidenceLevel.VERY_HIGH
        elif similarity_score >= 0.85:
            return ConfidenceLevel.HIGH
        elif similarity_score >= 0.75:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    async def _validate_matches(self, matches: List[EntityMatch], 
                              config: ResolutionConfig) -> List[EntityMatch]:
        """Validate and filter matches"""
        validated_matches = []
        
        for match in matches:
            # Check if already in known non-matches
            pair = (match.entity1_id, match.entity2_id)
            reverse_pair = (match.entity2_id, match.entity1_id)
            
            if pair in self.known_non_matches or reverse_pair in self.known_non_matches:
                continue
            
            # Additional validation rules
            if await self._passes_validation_rules(match):
                validated_matches.append(match)
        
        return validated_matches
    
    async def _passes_validation_rules(self, match: EntityMatch) -> bool:
        """Check if match passes validation rules"""
        try:
            # Get entities
            entity1 = await self.graph_engine.get_entity(match.entity1_id)
            entity2 = await self.graph_engine.get_entity(match.entity2_id)
            
            if not entity1 or not entity2:
                return False
            
            # Rule 1: Must have some overlapping information
            if not self._has_overlapping_info(entity1, entity2):
                return False
            
            # Rule 2: Check for conflicting information
            if self._has_conflicting_info(entity1, entity2):
                return False
            
            # Rule 3: Temporal consistency (if applicable)
            if not self._is_temporally_consistent(entity1, entity2):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating match: {e}")
            return False
    
    def _has_overlapping_info(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Check if entities have overlapping information"""
        props1 = entity1.get("properties", {})
        props2 = entity2.get("properties", {})
        
        # Check for common properties with same values
        common_props = set(props1.keys()) & set(props2.keys())
        
        for prop in common_props:
            if props1[prop] == props2[prop]:
                return True
        
        return False
    
    def _has_conflicting_info(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Check if entities have conflicting information"""
        props1 = entity1.get("properties", {})
        props2 = entity2.get("properties", {})
        
        # Check for properties that should be unique but differ
        unique_props = ["email", "phone", "ssn", "id_number"]
        
        for prop in unique_props:
            if (prop in props1 and prop in props2 and 
                props1[prop] != props2[prop]):
                return True
        
        return False
    
    def _is_temporally_consistent(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Check temporal consistency"""
        # Simple temporal consistency check
        # Could be expanded for specific domain logic
        return True
    
    async def _cluster_matches(self, matches: List[EntityMatch]) -> List[List[str]]:
        """Cluster matches into groups of duplicate entities"""
        try:
            # Create graph of matches
            entity_graph = {}
            
            for match in matches:
                if match.entity1_id not in entity_graph:
                    entity_graph[match.entity1_id] = set()
                if match.entity2_id not in entity_graph:
                    entity_graph[match.entity2_id] = set()
                
                entity_graph[match.entity1_id].add(match.entity2_id)
                entity_graph[match.entity2_id].add(match.entity1_id)
            
            # Find connected components
            visited = set()
            clusters = []
            
            for entity_id in entity_graph:
                if entity_id not in visited:
                    cluster = []
                    stack = [entity_id]
                    
                    while stack:
                        current = stack.pop()
                        if current not in visited:
                            visited.add(current)
                            cluster.append(current)
                            
                            for neighbor in entity_graph.get(current, set()):
                                if neighbor not in visited:
                                    stack.append(neighbor)
                    
                    if len(cluster) > 1:
                        clusters.append(cluster)
            
            return clusters
            
        except Exception as e:
            self.logger.error(f"Error clustering matches: {e}")
            return []
    
    async def _should_auto_merge(self, cluster: List[str]) -> bool:
        """Determine if cluster should be auto-merged"""
        try:
            # Only auto-merge small clusters with high confidence
            if len(cluster) > 3:
                return False
            
            # Check if all pairs have high confidence matches
            # This is a simplified check
            return len(cluster) == 2  # Only auto-merge pairs for now
            
        except Exception as e:
            self.logger.error(f"Error determining auto-merge: {e}")
            return False
    
    async def _merge_entity_cluster(self, cluster: List[str]) -> Dict[str, Any]:
        """Merge entities in a cluster"""
        try:
            if len(cluster) < 2:
                return {"success": False, "error": "Cluster too small"}
            
            # Get all entities in cluster
            entities = []
            for entity_id in cluster:
                entity = await self.graph_engine.get_entity(entity_id)
                if entity:
                    entities.append(entity)
            
            if len(entities) != len(cluster):
                return {"success": False, "error": "Could not retrieve all entities"}
            
            # Create merged entity
            merged_entity = await self._create_merged_entity(entities)
            
            # Create new merged entity
            created_entities = await self.graph_engine.create_entities([merged_entity])
            
            if not created_entities:
                return {"success": False, "error": "Failed to create merged entity"}
            
            merged_id = created_entities[0].id
            
            # Transfer relationships
            await self._transfer_relationships(cluster, merged_id)
            
            # Delete original entities
            for entity_id in cluster:
                await self.graph_engine.delete_entity(entity_id)
            
            return {
                "success": True,
                "merged_entity_id": merged_id,
                "original_entities": cluster,
                "merged_entity": merged_entity
            }
            
        except Exception as e:
            self.logger.error(f"Error merging entity cluster: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_merged_entity(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create merged entity from multiple entities"""
        try:
            # Start with first entity as base
            base_entity = entities[0].copy()
            merged_properties = base_entity.get("properties", {}).copy()
            
            # Merge properties from other entities
            for entity in entities[1:]:
                entity_props = entity.get("properties", {})
                
                for key, value in entity_props.items():
                    if key not in merged_properties:
                        merged_properties[key] = value
                    elif merged_properties[key] != value:
                        # Handle conflicts by creating lists
                        if not isinstance(merged_properties[key], list):
                            merged_properties[key] = [merged_properties[key]]
                        if value not in merged_properties[key]:
                            merged_properties[key].append(value)
            
            # Add merge metadata
            merged_properties["_merged_from"] = [e["id"] for e in entities]
            merged_properties["_merge_timestamp"] = datetime.now().isoformat()
            
            # Create merged entity
            merged_entity = {
                "type": base_entity["type"],
                "properties": merged_properties
            }
            
            return merged_entity
            
        except Exception as e:
            self.logger.error(f"Error creating merged entity: {e}")
            raise
    
    async def _transfer_relationships(self, original_entity_ids: List[str], merged_entity_id: str):
        """Transfer relationships from original entities to merged entity"""
        try:
            transferred_relationships = set()
            
            for entity_id in original_entity_ids:
                relationships = await self.graph_engine.get_entity_relationships(entity_id)
                
                for rel in relationships:
                    # Skip self-relationships and duplicate relationships
                    other_entity = (rel["target_id"] if rel["source_id"] == entity_id 
                                  else rel["source_id"])
                    
                    if other_entity in original_entity_ids:
                        continue  # Skip internal relationships
                    
                    rel_key = (other_entity, rel["type"])
                    if rel_key in transferred_relationships:
                        continue  # Already transferred this relationship
                    
                    # Create new relationship
                    new_rel = {
                        "source_id": merged_entity_id if rel["source_id"] == entity_id else other_entity,
                        "target_id": other_entity if rel["source_id"] == entity_id else merged_entity_id,
                        "type": rel["type"],
                        "properties": rel.get("properties", {}),
                        "strength": rel.get("strength", 1.0)
                    }
                    
                    await self.graph_engine.create_relationships([new_rel])
                    transferred_relationships.add(rel_key)
            
        except Exception as e:
            self.logger.error(f"Error transferring relationships: {e}")
    
    async def _get_entities_for_resolution(self, limit: int) -> List[Dict[str, Any]]:
        """Get entities for resolution analysis"""
        try:
            # This would be optimized in production
            return []  # Placeholder
            
        except Exception as e:
            self.logger.error(f"Error getting entities for resolution: {e}")
            return []
    
    async def _load_known_matches(self):
        """Load known matches from storage"""
        # This would load from persistent storage
        self.logger.debug("Loading known matches from storage")
    
    async def add_known_match(self, entity1_id: str, entity2_id: str):
        """Add known match for training"""
        self.known_matches.add((entity1_id, entity2_id))
        self.known_matches.add((entity2_id, entity1_id))
    
    async def add_known_non_match(self, entity1_id: str, entity2_id: str):
        """Add known non-match for training"""
        self.known_non_matches.add((entity1_id, entity2_id))
        self.known_non_matches.add((entity2_id, entity1_id))
    
    async def get_resolution_statistics(self) -> Dict[str, Any]:
        """Get resolution statistics"""
        return self.stats.copy()
    
    async def shutdown(self):
        """Shutdown entity resolution service"""
        self.logger.info("Entity resolution service shutdown")