"""
Concept graph builder for creating knowledge graphs focused on concepts and their relationships
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
import math

# Graph libraries (with fallbacks)
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import KMeans, DBSCAN
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConceptNodeType(Enum):
    """Types of concept nodes"""
    CORE_CONCEPT = "CORE_CONCEPT"
    DERIVED_CONCEPT = "DERIVED_CONCEPT"
    THEME = "THEME"
    TOPIC = "TOPIC"
    DOMAIN = "DOMAIN"
    METHODOLOGY = "METHODOLOGY"
    PRINCIPLE = "PRINCIPLE"
    CATEGORY = "CATEGORY"


class ConceptRelationType(Enum):
    """Types of relationships between concepts"""
    IS_A = "IS_A"
    PART_OF = "PART_OF" 
    RELATES_TO = "RELATES_TO"
    SIMILAR_TO = "SIMILAR_TO"
    OPPOSITE_OF = "OPPOSITE_OF"
    ENABLES = "ENABLES"
    REQUIRES = "REQUIRES"
    INFLUENCES = "INFLUENCES"
    EXEMPLIFIES = "EXEMPLIFIES"
    GENERALIZES = "GENERALIZES"
    SPECIALIZES = "SPECIALIZES"
    CO_OCCURS = "CO_OCCURS"


@dataclass
class ConceptNode:
    """Represents a concept node in the concept graph"""
    id: str
    name: str
    concept_type: ConceptNodeType
    importance_score: float
    frequency: int
    abstraction_level: int
    properties: Dict[str, Any]
    related_terms: List[str]
    context_examples: List[str]
    semantic_embedding: Optional[List[float]] = None


@dataclass
class ConceptRelation:
    """Represents a relationship between concepts"""
    source_id: str
    target_id: str
    relation_type: ConceptRelationType
    strength: float
    confidence: float
    evidence: List[str]
    properties: Dict[str, Any]


class ConceptGraphBuilder:
    """Builder for creating concept-focused knowledge graphs"""
    
    def __init__(self):
        self.concept_nodes = {}
        self.concept_relations = []
        self.concept_graph = None
        self.concept_hierarchy = {}
        self.concept_clusters = {}
        
        # Configuration
        self.similarity_threshold = 0.7
        self.min_concept_frequency = 2
        self.max_abstraction_levels = 5
    
    async def build_concept_graph(
        self,
        concepts: List[Dict[str, Any]],
        text_content: str = "",
        include_hierarchy: bool = True,
        include_clustering: bool = True,
        include_semantic_relations: bool = True
    ) -> Dict[str, Any]:
        """Build a comprehensive concept graph"""
        
        self.concept_nodes = {}
        self.concept_relations = []
        
        try:
            # Create concept nodes
            await self._create_concept_nodes(concepts)
            
            # Build concept hierarchy
            if include_hierarchy:
                await self._build_concept_hierarchy(concepts, text_content)
            
            # Perform concept clustering
            if include_clustering and ML_AVAILABLE:
                await self._perform_concept_clustering()
            
            # Build semantic relations
            if include_semantic_relations:
                await self._build_semantic_relations(concepts, text_content)
            
            # Build co-occurrence relations
            await self._build_co_occurrence_relations(concepts, text_content)
            
            # Create NetworkX graph if available
            if NETWORKX_AVAILABLE:
                self.concept_graph = await self._create_concept_networkx_graph()
            
            # Calculate concept graph metrics
            metrics = await self._calculate_concept_metrics()
            
            # Generate concept insights
            insights = await self._generate_concept_insights()
            
            # Identify concept patterns
            patterns = await self._identify_concept_patterns()
            
            return {
                "concept_nodes": [self._concept_node_to_dict(node) for node in self.concept_nodes.values()],
                "concept_relations": [self._concept_relation_to_dict(rel) for rel in self.concept_relations],
                "concept_hierarchy": self.concept_hierarchy,
                "concept_clusters": self.concept_clusters,
                "metrics": metrics,
                "insights": insights,
                "patterns": patterns,
                "graph_info": {
                    "total_concepts": len(self.concept_nodes),
                    "total_relations": len(self.concept_relations),
                    "concept_types": self._count_concept_types(),
                    "relation_types": self._count_relation_types()
                }
            }
            
        except Exception as e:
            logger.error(f"Error building concept graph: {e}")
            return {"error": str(e)}
    
    async def analyze_concept_evolution(
        self,
        concept_graphs: List[Dict[str, Any]],
        time_points: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze how concepts evolve across multiple graphs"""
        
        if time_points is None:
            time_points = [f"T{i}" for i in range(len(concept_graphs))]
        
        evolution_analysis = {
            "concept_timeline": {},
            "emerging_concepts": [],
            "declining_concepts": [], 
            "stable_concepts": [],
            "relationship_evolution": {},
            "hierarchy_changes": []
        }
        
        try:
            # Track concept importance over time
            all_concepts = set()
            for graph in concept_graphs:
                for node in graph.get("concept_nodes", []):
                    all_concepts.add(node["name"])
            
            # Analyze concept evolution
            for concept_name in all_concepts:
                importance_timeline = []
                relation_timeline = []
                
                for i, graph in enumerate(concept_graphs):
                    # Find concept in current graph
                    concept_data = None
                    for node in graph.get("concept_nodes", []):
                        if node["name"] == concept_name:
                            concept_data = node
                            break
                    
                    if concept_data:
                        importance_timeline.append(concept_data["importance_score"])
                        
                        # Count relations
                        relation_count = 0
                        for rel in graph.get("concept_relations", []):
                            if (rel["source_id"].endswith(hashlib.md5(concept_name.encode()).hexdigest()[:8]) or
                                rel["target_id"].endswith(hashlib.md5(concept_name.encode()).hexdigest()[:8])):
                                relation_count += 1
                        relation_timeline.append(relation_count)
                    else:
                        importance_timeline.append(0.0)
                        relation_timeline.append(0)
                
                evolution_analysis["concept_timeline"][concept_name] = {
                    "importance": importance_timeline,
                    "relations": relation_timeline,
                    "time_points": time_points
                }
                
                # Classify evolution pattern
                if self._is_emerging_pattern(importance_timeline):
                    evolution_analysis["emerging_concepts"].append(concept_name)
                elif self._is_declining_pattern(importance_timeline):
                    evolution_analysis["declining_concepts"].append(concept_name)
                elif self._is_stable_pattern(importance_timeline):
                    evolution_analysis["stable_concepts"].append(concept_name)
            
            return evolution_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing concept evolution: {e}")
            return {"error": str(e)}
    
    async def extract_concept_themes(
        self,
        concepts: List[Dict[str, Any]],
        theme_count: int = 5
    ) -> Dict[str, Any]:
        """Extract major themes from concepts"""
        
        themes = {
            "identified_themes": [],
            "theme_concepts": {},
            "theme_relationships": {},
            "theme_hierarchy": {}
        }
        
        try:
            if not ML_AVAILABLE:
                logger.warning("ML libraries not available for theme extraction")
                return themes
            
            # Extract concept embeddings if available
            concept_embeddings = []
            concept_names = []
            
            for concept in concepts:
                if "semantic_embedding" in concept and concept["semantic_embedding"]:
                    concept_embeddings.append(concept["semantic_embedding"])
                    concept_names.append(concept["name"])
            
            if len(concept_embeddings) < theme_count:
                # Fallback to text-based clustering
                return await self._extract_themes_by_text(concepts, theme_count)
            
            # Perform K-means clustering
            concept_embeddings = np.array(concept_embeddings)
            kmeans = KMeans(n_clusters=theme_count, random_state=42)
            cluster_labels = kmeans.fit_predict(concept_embeddings)
            
            # Group concepts by theme
            theme_groups = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                theme_groups[label].append({
                    "name": concept_names[i],
                    "concept": concepts[i]
                })
            
            # Generate theme information
            for theme_id, theme_concepts in theme_groups.items():
                # Calculate theme centroid
                theme_embeddings = [concept["concept"]["semantic_embedding"] for concept in theme_concepts]
                theme_centroid = np.mean(theme_embeddings, axis=0)
                
                # Find representative concept (closest to centroid)
                distances = [
                    cosine_similarity([theme_centroid], [emb])[0][0] 
                    for emb in theme_embeddings
                ]
                representative_idx = np.argmax(distances)
                representative_concept = theme_concepts[representative_idx]["name"]
                
                # Calculate theme coherence
                coherence = self._calculate_theme_coherence(theme_concepts)
                
                theme_info = {
                    "theme_id": f"theme_{theme_id}",
                    "representative_concept": representative_concept,
                    "concept_count": len(theme_concepts),
                    "coherence_score": coherence,
                    "concepts": [tc["name"] for tc in theme_concepts]
                }
                
                themes["identified_themes"].append(theme_info)
                themes["theme_concepts"][f"theme_{theme_id}"] = [tc["name"] for tc in theme_concepts]
            
            return themes
            
        except Exception as e:
            logger.error(f"Error extracting concept themes: {e}")
            return themes
    
    # Graph building methods
    async def _create_concept_nodes(self, concepts: List[Dict[str, Any]]):
        """Create concept nodes from concept data"""
        
        for concept in concepts:
            concept_id = self._generate_concept_id(concept["name"])
            
            # Determine concept type and abstraction level
            concept_type = self._classify_concept_node_type(concept)
            abstraction_level = self._determine_abstraction_level(concept)
            
            concept_node = ConceptNode(
                id=concept_id,
                name=concept["name"],
                concept_type=concept_type,
                importance_score=concept.get("importance_score", 0.0),
                frequency=concept.get("frequency", 1),
                abstraction_level=abstraction_level,
                properties={
                    "concept_type": concept.get("concept_type", ""),
                    "confidence": concept.get("confidence", 0.0),
                    "extraction_method": concept.get("extraction_method", ""),
                    "definition": concept.get("definition", "")
                },
                related_terms=concept.get("related_terms", []),
                context_examples=concept.get("context_examples", []),
                semantic_embedding=concept.get("semantic_embedding")
            )
            
            self.concept_nodes[concept_id] = concept_node
    
    async def _build_concept_hierarchy(self, concepts: List[Dict[str, Any]], text_content: str):
        """Build hierarchical relationships between concepts"""
        
        # Group concepts by abstraction level
        levels = defaultdict(list)
        for node in self.concept_nodes.values():
            levels[node.abstraction_level].append(node)
        
        # Build hierarchy from high to low abstraction
        for level in sorted(levels.keys()):
            current_level_nodes = levels[level]
            
            # Find parent-child relationships
            for higher_level in range(level + 1, self.max_abstraction_levels + 1):
                if higher_level in levels:
                    parent_nodes = levels[higher_level]
                    
                    for child_node in current_level_nodes:
                        for parent_node in parent_nodes:
                            # Check if child is a specialization of parent
                            if self._is_specialization(child_node, parent_node, text_content):
                                relation = ConceptRelation(
                                    source_id=child_node.id,
                                    target_id=parent_node.id,
                                    relation_type=ConceptRelationType.IS_A,
                                    strength=0.8,
                                    confidence=0.7,
                                    evidence=[f"{child_node.name} is a type of {parent_node.name}"],
                                    properties={"hierarchy_level": level}
                                )
                                self.concept_relations.append(relation)
                                
                                # Update hierarchy structure
                                if parent_node.id not in self.concept_hierarchy:
                                    self.concept_hierarchy[parent_node.id] = {
                                        "name": parent_node.name,
                                        "children": []
                                    }
                                
                                self.concept_hierarchy[parent_node.id]["children"].append({
                                    "id": child_node.id,
                                    "name": child_node.name,
                                    "abstraction_level": child_node.abstraction_level
                                })
    
    async def _perform_concept_clustering(self):
        """Perform semantic clustering of concepts"""
        
        if not ML_AVAILABLE:
            return
        
        # Collect concept embeddings
        embeddings = []
        concept_ids = []
        
        for concept_id, concept_node in self.concept_nodes.items():
            if concept_node.semantic_embedding:
                embeddings.append(concept_node.semantic_embedding)
                concept_ids.append(concept_id)
        
        if len(embeddings) < 3:
            return
        
        try:
            embeddings = np.array(embeddings)
            
            # Try different clustering algorithms
            optimal_clusters = min(5, len(embeddings) // 2)
            
            # K-means clustering
            kmeans = KMeans(n_clusters=optimal_clusters, random_state=42)
            kmeans_labels = kmeans.fit_predict(embeddings)
            
            # DBSCAN clustering
            dbscan = DBSCAN(eps=0.3, min_samples=2)
            dbscan_labels = dbscan.fit_predict(embeddings)
            
            # Store clustering results
            self.concept_clusters["kmeans"] = {}
            self.concept_clusters["dbscan"] = {}
            
            # Process K-means results
            for i, label in enumerate(kmeans_labels):
                cluster_key = f"kmeans_cluster_{label}"
                if cluster_key not in self.concept_clusters["kmeans"]:
                    self.concept_clusters["kmeans"][cluster_key] = []
                
                self.concept_clusters["kmeans"][cluster_key].append({
                    "concept_id": concept_ids[i],
                    "concept_name": self.concept_nodes[concept_ids[i]].name
                })
            
            # Process DBSCAN results
            for i, label in enumerate(dbscan_labels):
                if label == -1:  # Noise point
                    cluster_key = "noise"
                else:
                    cluster_key = f"dbscan_cluster_{label}"
                
                if cluster_key not in self.concept_clusters["dbscan"]:
                    self.concept_clusters["dbscan"][cluster_key] = []
                
                self.concept_clusters["dbscan"][cluster_key].append({
                    "concept_id": concept_ids[i],
                    "concept_name": self.concept_nodes[concept_ids[i]].name
                })
            
        except Exception as e:
            logger.warning(f"Error in concept clustering: {e}")
    
    async def _build_semantic_relations(self, concepts: List[Dict[str, Any]], text_content: str):
        """Build semantic relationships between concepts"""
        
        concept_list = list(self.concept_nodes.values())
        
        for i, concept1 in enumerate(concept_list):
            for concept2 in concept_list[i+1:]:
                # Calculate semantic similarity
                similarity = self._calculate_concept_similarity(concept1, concept2)
                
                if similarity > self.similarity_threshold:
                    # Determine relationship type
                    relation_type = self._determine_semantic_relation_type(
                        concept1, concept2, similarity, text_content
                    )
                    
                    relation = ConceptRelation(
                        source_id=concept1.id,
                        target_id=concept2.id,
                        relation_type=relation_type,
                        strength=similarity,
                        confidence=similarity,
                        evidence=self._find_relation_evidence(concept1, concept2, text_content),
                        properties={
                            "similarity_score": similarity,
                            "method": "semantic_analysis"
                        }
                    )
                    self.concept_relations.append(relation)
    
    async def _build_co_occurrence_relations(self, concepts: List[Dict[str, Any]], text_content: str):
        """Build co-occurrence relationships between concepts"""
        
        if not text_content:
            return
        
        concept_list = list(self.concept_nodes.values())
        
        for i, concept1 in enumerate(concept_list):
            for concept2 in concept_list[i+1:]:
                # Calculate co-occurrence score
                co_occurrence = self._calculate_concept_co_occurrence(
                    concept1, concept2, text_content
                )
                
                if co_occurrence > 0.1:  # Minimum threshold
                    relation = ConceptRelation(
                        source_id=concept1.id,
                        target_id=concept2.id,
                        relation_type=ConceptRelationType.CO_OCCURS,
                        strength=co_occurrence,
                        confidence=co_occurrence,
                        evidence=self._find_co_occurrence_evidence(concept1, concept2, text_content),
                        properties={
                            "co_occurrence_score": co_occurrence,
                            "method": "co_occurrence_analysis"
                        }
                    )
                    self.concept_relations.append(relation)
    
    async def _create_concept_networkx_graph(self) -> nx.Graph:
        """Create NetworkX graph for concepts"""
        
        if not NETWORKX_AVAILABLE:
            return None
        
        G = nx.DiGraph()  # Directed graph for hierarchical relations
        
        # Add concept nodes
        for concept_node in self.concept_nodes.values():
            G.add_node(
                concept_node.id,
                name=concept_node.name,
                concept_type=concept_node.concept_type.value,
                importance_score=concept_node.importance_score,
                frequency=concept_node.frequency,
                abstraction_level=concept_node.abstraction_level,
                **concept_node.properties
            )
        
        # Add concept relations
        for relation in self.concept_relations:
            G.add_edge(
                relation.source_id,
                relation.target_id,
                relation_type=relation.relation_type.value,
                strength=relation.strength,
                confidence=relation.confidence,
                **relation.properties
            )
        
        return G
    
    async def _calculate_concept_metrics(self) -> Dict[str, Any]:
        """Calculate metrics for the concept graph"""
        
        metrics = {
            "basic_stats": {
                "total_concepts": len(self.concept_nodes),
                "total_relations": len(self.concept_relations),
                "average_importance": 0.0,
                "concept_density": 0.0
            },
            "hierarchy_stats": {
                "abstraction_levels": 0,
                "hierarchical_relations": 0,
                "root_concepts": 0
            },
            "clustering_stats": {},
            "centrality": {}
        }
        
        try:
            # Basic statistics
            if self.concept_nodes:
                avg_importance = sum(node.importance_score for node in self.concept_nodes.values()) / len(self.concept_nodes)
                metrics["basic_stats"]["average_importance"] = avg_importance
                
                # Calculate concept density
                max_relations = len(self.concept_nodes) * (len(self.concept_nodes) - 1)
                metrics["basic_stats"]["concept_density"] = len(self.concept_relations) / max_relations if max_relations > 0 else 0.0
            
            # Hierarchy statistics
            abstraction_levels = set(node.abstraction_level for node in self.concept_nodes.values())
            metrics["hierarchy_stats"]["abstraction_levels"] = len(abstraction_levels)
            
            hierarchical_relations = sum(
                1 for rel in self.concept_relations 
                if rel.relation_type in [ConceptRelationType.IS_A, ConceptRelationType.PART_OF]
            )
            metrics["hierarchy_stats"]["hierarchical_relations"] = hierarchical_relations
            
            # Root concepts (high abstraction, high importance)
            root_concepts = [
                node for node in self.concept_nodes.values()
                if node.abstraction_level >= 3 and node.importance_score > 0.7
            ]
            metrics["hierarchy_stats"]["root_concepts"] = len(root_concepts)
            
            # Clustering statistics
            for method, clusters in self.concept_clusters.items():
                metrics["clustering_stats"][method] = {
                    "cluster_count": len(clusters),
                    "largest_cluster_size": max(len(cluster) for cluster in clusters.values()) if clusters else 0
                }
            
            # Centrality measures if graph is available
            if self.concept_graph and NETWORKX_AVAILABLE:
                try:
                    degree_centrality = nx.degree_centrality(self.concept_graph)
                    betweenness_centrality = nx.betweenness_centrality(self.concept_graph)
                    
                    # Top 5 central concepts
                    metrics["centrality"] = {
                        "degree": dict(sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5]),
                        "betweenness": dict(sorted(betweenness_centrality.items(), key=lambda x: x[1], reverse=True)[:5])
                    }
                except Exception as e:
                    logger.warning(f"Error calculating centrality: {e}")
            
        except Exception as e:
            logger.warning(f"Error calculating concept metrics: {e}")
        
        return metrics
    
    async def _generate_concept_insights(self) -> Dict[str, Any]:
        """Generate insights about the concept graph"""
        
        insights = {
            "dominant_concepts": [],
            "key_themes": [],
            "concept_relationships": [],
            "abstraction_analysis": {},
            "knowledge_gaps": []
        }
        
        try:
            # Dominant concepts (highest importance)
            sorted_concepts = sorted(
                self.concept_nodes.values(),
                key=lambda x: x.importance_score,
                reverse=True
            )
            
            insights["dominant_concepts"] = [
                {
                    "name": concept.name,
                    "importance_score": concept.importance_score,
                    "frequency": concept.frequency,
                    "abstraction_level": concept.abstraction_level
                }
                for concept in sorted_concepts[:10]
            ]
            
            # Key themes from clustering
            if self.concept_clusters:
                theme_analysis = []
                for method, clusters in self.concept_clusters.items():
                    for cluster_name, cluster_concepts in clusters.items():
                        if len(cluster_concepts) >= 2:  # Meaningful clusters
                            theme_analysis.append({
                                "theme": cluster_name,
                                "concepts": [c["concept_name"] for c in cluster_concepts],
                                "size": len(cluster_concepts),
                                "method": method
                            })
                
                insights["key_themes"] = sorted(theme_analysis, key=lambda x: x["size"], reverse=True)[:5]
            
            # Important concept relationships
            sorted_relations = sorted(
                self.concept_relations,
                key=lambda x: x.strength,
                reverse=True
            )
            
            insights["concept_relationships"] = [
                {
                    "source": self.concept_nodes[rel.source_id].name,
                    "target": self.concept_nodes[rel.target_id].name,
                    "relation_type": rel.relation_type.value,
                    "strength": rel.strength
                }
                for rel in sorted_relations[:10]
            ]
            
            # Abstraction analysis
            level_counts = Counter(node.abstraction_level for node in self.concept_nodes.values())
            insights["abstraction_analysis"] = {
                "level_distribution": dict(level_counts),
                "most_abstract_concepts": [
                    node.name for node in sorted_concepts 
                    if node.abstraction_level == max(level_counts.keys())
                ][:5],
                "most_concrete_concepts": [
                    node.name for node in sorted_concepts
                    if node.abstraction_level == min(level_counts.keys())
                ][:5]
            }
            
            # Knowledge gaps (isolated concepts)
            isolated_concepts = []
            for concept_id, concept_node in self.concept_nodes.items():
                # Count relations involving this concept
                relation_count = sum(
                    1 for rel in self.concept_relations
                    if rel.source_id == concept_id or rel.target_id == concept_id
                )
                
                if relation_count == 0:
                    isolated_concepts.append(concept_node.name)
            
            insights["knowledge_gaps"] = isolated_concepts[:10]
            
        except Exception as e:
            logger.warning(f"Error generating concept insights: {e}")
        
        return insights
    
    async def _identify_concept_patterns(self) -> Dict[str, Any]:
        """Identify patterns in the concept graph"""
        
        patterns = {
            "hierarchy_patterns": [],
            "similarity_clusters": [],
            "evolution_patterns": [],
            "relation_patterns": {}
        }
        
        try:
            # Hierarchy patterns
            hierarchy_patterns = []
            for parent_id, hierarchy_info in self.concept_hierarchy.items():
                if len(hierarchy_info["children"]) >= 2:
                    hierarchy_patterns.append({
                        "parent": hierarchy_info["name"],
                        "children": [child["name"] for child in hierarchy_info["children"]],
                        "pattern_type": "generalization"
                    })
            
            patterns["hierarchy_patterns"] = hierarchy_patterns
            
            # Relation type patterns
            relation_type_counts = Counter(rel.relation_type for rel in self.concept_relations)
            patterns["relation_patterns"] = {
                "most_common_relations": dict(relation_type_counts.most_common()),
                "relation_distribution": dict(relation_type_counts)
            }
            
        except Exception as e:
            logger.warning(f"Error identifying concept patterns: {e}")
        
        return patterns
    
    # Helper methods
    def _generate_concept_id(self, concept_name: str) -> str:
        """Generate consistent concept ID"""
        return f"concept_{hashlib.md5(concept_name.encode()).hexdigest()[:8]}"
    
    def _classify_concept_node_type(self, concept: Dict[str, Any]) -> ConceptNodeType:
        """Classify the type of concept node"""
        
        concept_type_str = concept.get("concept_type", "").upper()
        importance = concept.get("importance_score", 0.0)
        frequency = concept.get("frequency", 1)
        
        # Map concept types
        if concept_type_str == "THEME":
            return ConceptNodeType.THEME
        elif concept_type_str == "TOPIC":
            return ConceptNodeType.TOPIC
        elif concept_type_str == "DOMAIN":
            return ConceptNodeType.DOMAIN
        elif concept_type_str == "METHODOLOGY":
            return ConceptNodeType.METHODOLOGY
        elif concept_type_str == "PRINCIPLE":
            return ConceptNodeType.PRINCIPLE
        elif importance > 0.8 and frequency > 5:
            return ConceptNodeType.CORE_CONCEPT
        else:
            return ConceptNodeType.DERIVED_CONCEPT
    
    def _determine_abstraction_level(self, concept: Dict[str, Any]) -> int:
        """Determine the abstraction level of a concept"""
        
        concept_name = concept["name"].lower()
        concept_type = concept.get("concept_type", "").lower()
        
        # High abstraction (level 4-5)
        high_abstraction_indicators = ["principle", "theory", "paradigm", "philosophy", "approach"]
        if any(indicator in concept_name or indicator in concept_type for indicator in high_abstraction_indicators):
            return 4
        
        # Medium-high abstraction (level 3)
        medium_high_indicators = ["methodology", "framework", "model", "concept", "strategy"]
        if any(indicator in concept_name or indicator in concept_type for indicator in medium_high_indicators):
            return 3
        
        # Medium abstraction (level 2)
        medium_indicators = ["process", "method", "technique", "system", "tool"]
        if any(indicator in concept_name or indicator in concept_type for indicator in medium_indicators):
            return 2
        
        # Low abstraction (level 1)
        return 1
    
    def _calculate_concept_similarity(self, concept1: ConceptNode, concept2: ConceptNode) -> float:
        """Calculate similarity between two concepts"""
        
        # Semantic embedding similarity
        if concept1.semantic_embedding and concept2.semantic_embedding and ML_AVAILABLE:
            try:
                embedding_sim = cosine_similarity(
                    [concept1.semantic_embedding],
                    [concept2.semantic_embedding]
                )[0][0]
                return max(0, embedding_sim)  # Ensure non-negative
            except:
                pass
        
        # Fallback to text-based similarity
        name_similarity = self._calculate_text_similarity(concept1.name, concept2.name)
        
        # Related terms overlap
        terms_similarity = 0.0
        if concept1.related_terms and concept2.related_terms:
            terms1 = set(concept1.related_terms)
            terms2 = set(concept2.related_terms)
            if terms1.union(terms2):
                terms_similarity = len(terms1.intersection(terms2)) / len(terms1.union(terms2))
        
        # Context examples overlap
        context_similarity = 0.0
        if concept1.context_examples and concept2.context_examples:
            context1 = " ".join(concept1.context_examples).lower()
            context2 = " ".join(concept2.context_examples).lower()
            context_similarity = self._calculate_text_similarity(context1, context2)
        
        # Combine similarities with weights
        combined_similarity = (
            name_similarity * 0.4 +
            terms_similarity * 0.3 +
            context_similarity * 0.3
        )
        
        return combined_similarity
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using word overlap"""
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1.union(words2):
            return 0.0
        
        return len(words1.intersection(words2)) / len(words1.union(words2))
    
    def _determine_semantic_relation_type(
        self,
        concept1: ConceptNode,
        concept2: ConceptNode,
        similarity: float,
        text_content: str
    ) -> ConceptRelationType:
        """Determine the type of semantic relationship"""
        
        # Check abstraction levels
        if abs(concept1.abstraction_level - concept2.abstraction_level) > 1:
            if concept1.abstraction_level > concept2.abstraction_level:
                return ConceptRelationType.GENERALIZES
            else:
                return ConceptRelationType.SPECIALIZES
        
        # Check for hierarchical relationships
        if self._is_part_of_relationship(concept1, concept2, text_content):
            return ConceptRelationType.PART_OF
        
        # Check for opposite concepts
        if self._are_opposite_concepts(concept1, concept2):
            return ConceptRelationType.OPPOSITE_OF
        
        # Check for enabling relationships
        if self._is_enabling_relationship(concept1, concept2, text_content):
            return ConceptRelationType.ENABLES
        
        # Default to similarity
        if similarity > 0.8:
            return ConceptRelationType.SIMILAR_TO
        else:
            return ConceptRelationType.RELATES_TO
    
    def _is_specialization(self, child: ConceptNode, parent: ConceptNode, text_content: str) -> bool:
        """Check if child concept is a specialization of parent concept"""
        
        # Abstraction level check
        if child.abstraction_level >= parent.abstraction_level:
            return False
        
        # Name-based heuristics
        if parent.name.lower() in child.name.lower():
            return True
        
        # Related terms check
        parent_terms = set(term.lower() for term in parent.related_terms)
        child_terms = set(term.lower() for term in child.related_terms)
        
        # Child should have more specific terms
        if parent_terms.issubset(child_terms) and len(child_terms) > len(parent_terms):
            return True
        
        return False
    
    def _is_part_of_relationship(self, concept1: ConceptNode, concept2: ConceptNode, text_content: str) -> bool:
        """Check if concept1 is part of concept2"""
        
        # Simple heuristic based on names
        if concept2.name.lower() in concept1.name.lower():
            return True
        
        # Check context for "part of" indicators
        combined_context = " ".join(concept1.context_examples + concept2.context_examples).lower()
        part_of_indicators = ["part of", "component of", "element of", "aspect of"]
        
        return any(indicator in combined_context for indicator in part_of_indicators)
    
    def _are_opposite_concepts(self, concept1: ConceptNode, concept2: ConceptNode) -> bool:
        """Check if concepts are opposites"""
        
        opposite_pairs = [
            ("positive", "negative"), ("good", "bad"), ("high", "low"),
            ("increase", "decrease"), ("success", "failure"), ("advantage", "disadvantage")
        ]
        
        name1, name2 = concept1.name.lower(), concept2.name.lower()
        
        for pair in opposite_pairs:
            if (pair[0] in name1 and pair[1] in name2) or (pair[1] in name1 and pair[0] in name2):
                return True
        
        return False
    
    def _is_enabling_relationship(self, concept1: ConceptNode, concept2: ConceptNode, text_content: str) -> bool:
        """Check if concept1 enables concept2"""
        
        combined_context = " ".join(concept1.context_examples + concept2.context_examples).lower()
        enabling_indicators = ["enables", "facilitates", "supports", "allows", "helps"]
        
        return any(indicator in combined_context for indicator in enabling_indicators)
    
    def _calculate_concept_co_occurrence(self, concept1: ConceptNode, concept2: ConceptNode, text_content: str) -> float:
        """Calculate co-occurrence score between concepts"""
        
        text_lower = text_content.lower()
        name1, name2 = concept1.name.lower(), concept2.name.lower()
        
        # Find positions of both concepts
        positions1 = [i for i in range(len(text_lower)) if text_lower.startswith(name1, i)]
        positions2 = [i for i in range(len(text_lower)) if text_lower.startswith(name2, i)]
        
        if not positions1 or not positions2:
            return 0.0
        
        # Count co-occurrences within a window
        window_size = 200
        co_occurrences = 0
        
        for pos1 in positions1:
            for pos2 in positions2:
                if abs(pos1 - pos2) <= window_size:
                    co_occurrences += 1
        
        # Normalize by maximum possible co-occurrences
        max_co_occurrences = len(positions1) * len(positions2)
        return co_occurrences / max_co_occurrences if max_co_occurrences > 0 else 0.0
    
    def _find_relation_evidence(self, concept1: ConceptNode, concept2: ConceptNode, text_content: str) -> List[str]:
        """Find evidence for relationship between concepts"""
        
        evidence = []
        
        # Search for sentences containing both concepts
        sentences = text_content.split('.')
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if concept1.name.lower() in sentence_lower and concept2.name.lower() in sentence_lower:
                evidence.append(sentence.strip())
                if len(evidence) >= 3:  # Limit evidence
                    break
        
        return evidence
    
    def _find_co_occurrence_evidence(self, concept1: ConceptNode, concept2: ConceptNode, text_content: str) -> List[str]:
        """Find evidence for co-occurrence between concepts"""
        return self._find_relation_evidence(concept1, concept2, text_content)
    
    def _calculate_theme_coherence(self, theme_concepts: List[Dict[str, Any]]) -> float:
        """Calculate coherence score for a theme"""
        
        if len(theme_concepts) < 2:
            return 1.0
        
        # Simple coherence based on average importance
        importance_scores = [concept["concept"].get("importance_score", 0.0) for concept in theme_concepts]
        return sum(importance_scores) / len(importance_scores)
    
    def _extract_themes_by_text(self, concepts: List[Dict[str, Any]], theme_count: int) -> Dict[str, Any]:
        """Fallback theme extraction using text analysis"""
        
        themes = {
            "identified_themes": [],
            "theme_concepts": {},
            "theme_relationships": {},
            "theme_hierarchy": {}
        }
        
        # Group concepts by their concept_type
        type_groups = defaultdict(list)
        for concept in concepts:
            concept_type = concept.get("concept_type", "general")
            type_groups[concept_type].append(concept)
        
        # Create themes from type groups
        for i, (theme_type, theme_concepts) in enumerate(list(type_groups.items())[:theme_count]):
            theme_info = {
                "theme_id": f"theme_{i}",
                "representative_concept": theme_concepts[0]["name"] if theme_concepts else "",
                "concept_count": len(theme_concepts),
                "coherence_score": 0.8,  # Default coherence
                "concepts": [c["name"] for c in theme_concepts]
            }
            
            themes["identified_themes"].append(theme_info)
            themes["theme_concepts"][f"theme_{i}"] = [c["name"] for c in theme_concepts]
        
        return themes
    
    def _is_emerging_pattern(self, timeline: List[float]) -> bool:
        """Check if concept shows emerging pattern"""
        if len(timeline) < 3:
            return False
        
        recent_avg = sum(timeline[-2:]) / 2
        early_avg = sum(timeline[:2]) / 2
        
        return recent_avg > early_avg * 1.5
    
    def _is_declining_pattern(self, timeline: List[float]) -> bool:
        """Check if concept shows declining pattern"""
        if len(timeline) < 3:
            return False
        
        recent_avg = sum(timeline[-2:]) / 2
        early_avg = sum(timeline[:2]) / 2
        
        return recent_avg < early_avg * 0.5
    
    def _is_stable_pattern(self, timeline: List[float]) -> bool:
        """Check if concept shows stable pattern"""
        if len(timeline) < 3:
            return False
        
        # Check for consistent non-zero values
        non_zero_count = sum(1 for x in timeline if x > 0.1)
        return non_zero_count >= len(timeline) * 0.7
    
    def _count_concept_types(self) -> Dict[str, int]:
        """Count concepts by type"""
        type_counts = defaultdict(int)
        for concept in self.concept_nodes.values():
            type_counts[concept.concept_type.value] += 1
        return dict(type_counts)
    
    def _count_relation_types(self) -> Dict[str, int]:
        """Count relations by type"""
        type_counts = defaultdict(int)
        for relation in self.concept_relations:
            type_counts[relation.relation_type.value] += 1
        return dict(type_counts)
    
    def _concept_node_to_dict(self, node: ConceptNode) -> Dict[str, Any]:
        """Convert ConceptNode to dictionary"""
        return {
            "id": node.id,
            "name": node.name,
            "concept_type": node.concept_type.value,
            "importance_score": node.importance_score,
            "frequency": node.frequency,
            "abstraction_level": node.abstraction_level,
            "properties": node.properties,
            "related_terms": node.related_terms,
            "context_examples": node.context_examples,
            "semantic_embedding": node.semantic_embedding
        }
    
    def _concept_relation_to_dict(self, relation: ConceptRelation) -> Dict[str, Any]:
        """Convert ConceptRelation to dictionary"""
        return {
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "relation_type": relation.relation_type.value,
            "strength": relation.strength,
            "confidence": relation.confidence,
            "evidence": relation.evidence,
            "properties": relation.properties
        }