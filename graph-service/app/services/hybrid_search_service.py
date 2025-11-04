"""
Hybrid Vector-Graph Search Service.
Combines vector similarity search with graph traversal algorithms.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class SearchStrategy(Enum):
    VECTOR_FIRST = "vector_first"
    GRAPH_FIRST = "graph_first"
    PARALLEL = "parallel"
    WEIGHTED_FUSION = "weighted_fusion"

@dataclass
class SearchResult:
    entity_id: str
    entity_data: Dict[str, Any]
    relevance_score: float
    vector_score: float
    graph_score: float
    reasoning_path: List[str]
    search_strategy: str

@dataclass
class HybridSearchConfig:
    strategy: SearchStrategy = SearchStrategy.WEIGHTED_FUSION
    vector_weight: float = 0.6
    graph_weight: float = 0.4
    max_hops: int = 3
    min_vector_threshold: float = 0.3
    min_graph_threshold: float = 0.2
    top_k: int = 20
    enable_reranking: bool = True
    diversification_factor: float = 0.1

class HybridSearchService:
    """Service for hybrid vector-graph search."""
    
    def __init__(self, graph_engine, embedding_service):
        self.logger = logging.getLogger(__name__)
        self.graph_engine = graph_engine
        self.embedding_service = embedding_service
        
        # Search statistics
        self.stats = {
            "total_searches": 0,
            "vector_first_searches": 0,
            "graph_first_searches": 0,
            "parallel_searches": 0,
            "weighted_fusion_searches": 0,
            "average_results_returned": 0.0,
            "average_search_time": 0.0
        }
    
    async def initialize(self):
        """Initialize hybrid search service"""
        self.logger.info("Hybrid search service initialized")
    
    async def search(self, query: str, config: HybridSearchConfig = None, 
                    context_entities: List[str] = None) -> List[SearchResult]:
        """Perform hybrid vector-graph search"""
        start_time = datetime.now()
        
        try:
            if config is None:
                config = HybridSearchConfig()
            
            self.stats["total_searches"] += 1
            
            # Execute search based on strategy
            if config.strategy == SearchStrategy.VECTOR_FIRST:
                results = await self._vector_first_search(query, config, context_entities)
                self.stats["vector_first_searches"] += 1
            
            elif config.strategy == SearchStrategy.GRAPH_FIRST:
                results = await self._graph_first_search(query, config, context_entities)
                self.stats["graph_first_searches"] += 1
            
            elif config.strategy == SearchStrategy.PARALLEL:
                results = await self._parallel_search(query, config, context_entities)
                self.stats["parallel_searches"] += 1
            
            elif config.strategy == SearchStrategy.WEIGHTED_FUSION:
                results = await self._weighted_fusion_search(query, config, context_entities)
                self.stats["weighted_fusion_searches"] += 1
            
            else:
                results = await self._weighted_fusion_search(query, config, context_entities)
            
            # Post-processing
            if config.enable_reranking:
                results = await self._rerank_results(query, results, config)
            
            results = await self._diversify_results(results, config)
            
            # Update statistics
            search_time = (datetime.now() - start_time).total_seconds()
            self._update_search_stats(len(results), search_time)
            
            return results[:config.top_k]
            
        except Exception as e:
            self.logger.error(f"Error in hybrid search: {e}")
            return []
    
    async def _vector_first_search(self, query: str, config: HybridSearchConfig, 
                                 context_entities: List[str] = None) -> List[SearchResult]:
        """Vector-first search strategy"""
        try:
            # Step 1: Vector similarity search
            vector_results = await self._vector_similarity_search(query, config)
            
            # Step 2: Expand with graph traversal
            graph_expanded = await self._expand_with_graph_traversal(
                vector_results, config, context_entities
            )
            
            # Step 3: Combine and score
            combined_results = await self._combine_vector_graph_results(
                vector_results, graph_expanded, config, "vector_first"
            )
            
            return combined_results
            
        except Exception as e:
            self.logger.error(f"Error in vector-first search: {e}")
            return []
    
    async def _graph_first_search(self, query: str, config: HybridSearchConfig, 
                                context_entities: List[str] = None) -> List[SearchResult]:
        """Graph-first search strategy"""
        try:
            # Step 1: Graph traversal search
            graph_results = await self._graph_traversal_search(query, config, context_entities)
            
            # Step 2: Enhance with vector similarity
            vector_enhanced = await self._enhance_with_vector_similarity(
                graph_results, query, config
            )
            
            # Step 3: Combine and score
            combined_results = await self._combine_vector_graph_results(
                vector_enhanced, graph_results, config, "graph_first"
            )
            
            return combined_results
            
        except Exception as e:
            self.logger.error(f"Error in graph-first search: {e}")
            return []
    
    async def _parallel_search(self, query: str, config: HybridSearchConfig, 
                             context_entities: List[str] = None) -> List[SearchResult]:
        """Parallel search strategy"""
        try:
            # Execute vector and graph searches in parallel
            vector_task = asyncio.create_task(
                self._vector_similarity_search(query, config)
            )
            graph_task = asyncio.create_task(
                self._graph_traversal_search(query, config, context_entities)
            )
            
            vector_results, graph_results = await asyncio.gather(vector_task, graph_task)
            
            # Combine results
            combined_results = await self._merge_parallel_results(
                vector_results, graph_results, config
            )
            
            return combined_results
            
        except Exception as e:
            self.logger.error(f"Error in parallel search: {e}")
            return []
    
    async def _weighted_fusion_search(self, query: str, config: HybridSearchConfig, 
                                    context_entities: List[str] = None) -> List[SearchResult]:
        """Weighted fusion search strategy"""
        try:
            # Get both vector and graph results
            vector_results = await self._vector_similarity_search(query, config)
            graph_results = await self._graph_traversal_search(query, config, context_entities)
            
            # Create unified entity set
            all_entities = set()
            vector_scores = {}
            graph_scores = {}
            
            # Process vector results
            for result in vector_results:
                entity_id = result["entity_id"]
                all_entities.add(entity_id)
                vector_scores[entity_id] = result["score"]
            
            # Process graph results
            for result in graph_results:
                entity_id = result["entity_id"]
                all_entities.add(entity_id)
                graph_scores[entity_id] = result["score"]
            
            # Compute weighted fusion scores
            fusion_results = []
            for entity_id in all_entities:
                vector_score = vector_scores.get(entity_id, 0.0)
                graph_score = graph_scores.get(entity_id, 0.0)
                
                # Weighted combination
                fusion_score = (config.vector_weight * vector_score + 
                              config.graph_weight * graph_score)
                
                # Skip if below thresholds
                if (vector_score < config.min_vector_threshold and 
                    graph_score < config.min_graph_threshold):
                    continue
                
                # Get entity data
                entity_data = await self.graph_engine.get_entity(entity_id)
                if entity_data:
                    search_result = SearchResult(
                        entity_id=entity_id,
                        entity_data=entity_data,
                        relevance_score=fusion_score,
                        vector_score=vector_score,
                        graph_score=graph_score,
                        reasoning_path=[f"weighted_fusion_v{config.vector_weight}_g{config.graph_weight}"],
                        search_strategy="weighted_fusion"
                    )
                    fusion_results.append(search_result)
            
            # Sort by fusion score
            fusion_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return fusion_results
            
        except Exception as e:
            self.logger.error(f"Error in weighted fusion search: {e}")
            return []
    
    async def _vector_similarity_search(self, query: str, 
                                      config: HybridSearchConfig) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        try:
            # Get all entities (in practice, this would be optimized with vector DB)
            # For now, we'll get a sample of entities
            entities = await self._get_entities_for_search(limit=1000)
            
            # Perform semantic search
            similar_entities = await self.embedding_service.semantic_search(
                query, entities, top_k=config.top_k * 2, 
                threshold=config.min_vector_threshold
            )
            
            # Convert to standard format
            results = []
            for entity in similar_entities:
                results.append({
                    "entity_id": entity["id"],
                    "entity_data": entity,
                    "score": entity.get("similarity_score", 0.0),
                    "method": "vector_similarity"
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in vector similarity search: {e}")
            return []
    
    async def _graph_traversal_search(self, query: str, config: HybridSearchConfig, 
                                    context_entities: List[str] = None) -> List[Dict[str, Any]]:
        """Perform graph traversal search"""
        try:
            results = []
            
            # If context entities provided, start from them
            if context_entities:
                start_entities = context_entities
            else:
                # Find starting entities using text search
                start_entities_data = await self.graph_engine.search_entities(
                    query, limit=10
                )
                start_entities = [e["id"] for e in start_entities_data]
            
            if not start_entities:
                return []
            
            # Perform multi-hop traversal
            visited = set()
            current_level = set(start_entities)
            
            for hop in range(config.max_hops):
                next_level = set()
                
                for entity_id in current_level:
                    if entity_id in visited:
                        continue
                    
                    visited.add(entity_id)
                    
                    # Get entity data
                    entity_data = await self.graph_engine.get_entity(entity_id)
                    if entity_data:
                        # Calculate graph-based relevance score
                        graph_score = await self._calculate_graph_relevance(
                            entity_id, query, hop, start_entities
                        )
                        
                        if graph_score >= config.min_graph_threshold:
                            results.append({
                                "entity_id": entity_id,
                                "entity_data": entity_data,
                                "score": graph_score,
                                "method": "graph_traversal",
                                "hop_distance": hop
                            })
                    
                    # Get neighbors for next hop
                    if hop < config.max_hops - 1:
                        relationships = await self.graph_engine.get_entity_relationships(
                            entity_id, direction="both"
                        )
                        
                        for rel in relationships:
                            neighbor_id = (rel["target_id"] if rel["source_id"] == entity_id 
                                         else rel["source_id"])
                            if neighbor_id not in visited:
                                next_level.add(neighbor_id)
                
                current_level = next_level
                if not current_level:
                    break
            
            # Sort by graph score
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in graph traversal search: {e}")
            return []
    
    async def _calculate_graph_relevance(self, entity_id: str, query: str, 
                                       hop_distance: int, start_entities: List[str]) -> float:
        """Calculate graph-based relevance score"""
        try:
            base_score = 1.0
            
            # Distance penalty
            distance_penalty = 0.8 ** hop_distance
            
            # Centrality bonus (simplified)
            relationships = await self.graph_engine.get_entity_relationships(entity_id)
            centrality_bonus = min(1.0, len(relationships) / 10.0) * 0.2
            
            # Connection strength to start entities
            connection_strength = 0.0
            for start_entity in start_entities:
                if start_entity != entity_id:
                    # Check if there's a direct relationship
                    direct_rels = await self.graph_engine.get_entity_relationships(
                        entity_id, direction="both"
                    )
                    for rel in direct_rels:
                        other_id = (rel["target_id"] if rel["source_id"] == entity_id 
                                  else rel["source_id"])
                        if other_id == start_entity:
                            connection_strength = max(connection_strength, rel.get("strength", 0.5))
            
            # Combine scores
            final_score = (base_score * distance_penalty + 
                          centrality_bonus + 
                          connection_strength * 0.3)
            
            return min(1.0, final_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating graph relevance: {e}")
            return 0.0
    
    async def _expand_with_graph_traversal(self, vector_results: List[Dict[str, Any]], 
                                         config: HybridSearchConfig, 
                                         context_entities: List[str] = None) -> List[Dict[str, Any]]:
        """Expand vector results with graph traversal"""
        try:
            expanded_results = []
            
            # Use top vector results as starting points
            start_entities = [r["entity_id"] for r in vector_results[:10]]
            
            # Perform limited graph traversal
            visited = set(start_entities)
            
            for entity_id in start_entities:
                relationships = await self.graph_engine.get_entity_relationships(
                    entity_id, direction="both"
                )
                
                for rel in relationships[:5]:  # Limit to top 5 relationships
                    neighbor_id = (rel["target_id"] if rel["source_id"] == entity_id 
                                 else rel["source_id"])
                    
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        
                        entity_data = await self.graph_engine.get_entity(neighbor_id)
                        if entity_data:
                            graph_score = rel.get("strength", 0.5) * 0.8  # Penalize by hop
                            
                            expanded_results.append({
                                "entity_id": neighbor_id,
                                "entity_data": entity_data,
                                "score": graph_score,
                                "method": "graph_expansion",
                                "via_entity": entity_id
                            })
            
            return expanded_results
            
        except Exception as e:
            self.logger.error(f"Error expanding with graph traversal: {e}")
            return []
    
    async def _enhance_with_vector_similarity(self, graph_results: List[Dict[str, Any]], 
                                            query: str, config: HybridSearchConfig) -> List[Dict[str, Any]]:
        """Enhance graph results with vector similarity"""
        try:
            enhanced_results = []
            
            # Get embeddings for query and entities
            query_embedding = await self.embedding_service.get_embedding(query)
            
            for result in graph_results:
                entity_data = result["entity_data"]
                entity_text = self.embedding_service._entity_to_text(entity_data)
                entity_embedding = await self.embedding_service.get_embedding(entity_text, "entity")
                
                # Calculate vector similarity
                vector_score = await self.embedding_service.compute_similarity(
                    query_embedding, entity_embedding
                )
                
                # Update result with vector information
                result["vector_score"] = vector_score
                enhanced_results.append(result)
            
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"Error enhancing with vector similarity: {e}")
            return graph_results
    
    async def _combine_vector_graph_results(self, vector_results: List[Dict[str, Any]], 
                                          graph_results: List[Dict[str, Any]], 
                                          config: HybridSearchConfig, 
                                          strategy: str) -> List[SearchResult]:
        """Combine vector and graph results"""
        try:
            combined_results = []
            entity_map = {}
            
            # Index all results by entity ID
            for result in vector_results + graph_results:
                entity_id = result["entity_id"]
                if entity_id not in entity_map:
                    entity_map[entity_id] = {
                        "entity_data": result["entity_data"],
                        "vector_score": 0.0,
                        "graph_score": 0.0,
                        "methods": []
                    }
                
                if result.get("method") == "vector_similarity":
                    entity_map[entity_id]["vector_score"] = result["score"]
                    entity_map[entity_id]["methods"].append("vector")
                elif result.get("method") in ["graph_traversal", "graph_expansion"]:
                    entity_map[entity_id]["graph_score"] = max(
                        entity_map[entity_id]["graph_score"], result["score"]
                    )
                    entity_map[entity_id]["methods"].append("graph")
            
            # Create SearchResult objects
            for entity_id, data in entity_map.items():
                # Calculate relevance score based on strategy
                if strategy == "vector_first":
                    relevance_score = data["vector_score"] + 0.3 * data["graph_score"]
                elif strategy == "graph_first":
                    relevance_score = data["graph_score"] + 0.3 * data["vector_score"]
                else:
                    relevance_score = (config.vector_weight * data["vector_score"] + 
                                     config.graph_weight * data["graph_score"])
                
                search_result = SearchResult(
                    entity_id=entity_id,
                    entity_data=data["entity_data"],
                    relevance_score=relevance_score,
                    vector_score=data["vector_score"],
                    graph_score=data["graph_score"],
                    reasoning_path=[f"{strategy}_combination", f"methods_{','.join(data['methods'])}"],
                    search_strategy=strategy
                )
                
                combined_results.append(search_result)
            
            # Sort by relevance score
            combined_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return combined_results
            
        except Exception as e:
            self.logger.error(f"Error combining results: {e}")
            return []
    
    async def _merge_parallel_results(self, vector_results: List[Dict[str, Any]], 
                                    graph_results: List[Dict[str, Any]], 
                                    config: HybridSearchConfig) -> List[SearchResult]:
        """Merge results from parallel search"""
        return await self._combine_vector_graph_results(
            vector_results, graph_results, config, "parallel"
        )
    
    async def _rerank_results(self, query: str, results: List[SearchResult], 
                            config: HybridSearchConfig) -> List[SearchResult]:
        """Rerank results using additional signals"""
        try:
            # Get query embedding for reranking
            query_embedding = await self.embedding_service.get_embedding(query)
            
            for result in results:
                # Calculate additional relevance signals
                entity_text = self.embedding_service._entity_to_text(result.entity_data)
                entity_embedding = await self.embedding_service.get_embedding(entity_text, "entity")
                
                # Fine-grained similarity
                fine_similarity = await self.embedding_service.compute_similarity(
                    query_embedding, entity_embedding
                )
                
                # Entity quality score (based on completeness)
                quality_score = self._calculate_entity_quality(result.entity_data)
                
                # Recency score
                recency_score = self._calculate_recency_score(result.entity_data)
                
                # Update relevance score with reranking
                rerank_boost = (fine_similarity * 0.4 + 
                              quality_score * 0.3 + 
                              recency_score * 0.3)
                
                result.relevance_score = (result.relevance_score * 0.8 + 
                                        rerank_boost * 0.2)
            
            # Re-sort after reranking
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error reranking results: {e}")
            return results
    
    async def _diversify_results(self, results: List[SearchResult], 
                               config: HybridSearchConfig) -> List[SearchResult]:
        """Diversify results to reduce redundancy"""
        try:
            if config.diversification_factor <= 0:
                return results
            
            diversified = []
            
            for i, result in enumerate(results):
                # Calculate diversity penalty
                diversity_penalty = 0.0
                
                for existing in diversified:
                    # Simple diversity based on entity type and properties
                    if result.entity_data.get("type") == existing.entity_data.get("type"):
                        diversity_penalty += 0.1
                    
                    # Could add more sophisticated diversity measures here
                
                # Apply diversity penalty
                adjusted_score = result.relevance_score - (diversity_penalty * config.diversification_factor)
                result.relevance_score = max(0.0, adjusted_score)
                
                diversified.append(result)
            
            # Re-sort after diversification
            diversified.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return diversified
            
        except Exception as e:
            self.logger.error(f"Error diversifying results: {e}")
            return results
    
    def _calculate_entity_quality(self, entity_data: Dict[str, Any]) -> float:
        """Calculate entity quality score"""
        try:
            score = 0.0
            
            # Completeness score
            properties = entity_data.get("properties", {})
            score += min(1.0, len(properties) / 10.0) * 0.5
            
            # Required fields
            if entity_data.get("name") or properties.get("name"):
                score += 0.2
            
            if entity_data.get("description") or properties.get("description"):
                score += 0.2
            
            # Recency
            if entity_data.get("updated_at"):
                score += 0.1
            
            return min(1.0, score)
            
        except Exception:
            return 0.5
    
    def _calculate_recency_score(self, entity_data: Dict[str, Any]) -> float:
        """Calculate recency score"""
        try:
            updated_at = entity_data.get("updated_at")
            if not updated_at:
                return 0.5
            
            # Simple recency calculation (could be improved)
            try:
                if isinstance(updated_at, str):
                    from datetime import datetime
                    update_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    days_old = (datetime.now() - update_time).days
                    return max(0.0, 1.0 - days_old / 365.0)  # Decay over a year
            except:
                pass
            
            return 0.5
            
        except Exception:
            return 0.5
    
    async def _get_entities_for_search(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get entities for search (would be optimized in production)"""
        try:
            # This is a simplified implementation
            # In production, this would use proper indexing/sampling
            return []  # Placeholder - would return actual entities
            
        except Exception as e:
            self.logger.error(f"Error getting entities for search: {e}")
            return []
    
    def _update_search_stats(self, num_results: int, search_time: float):
        """Update search statistics"""
        total_searches = self.stats["total_searches"]
        
        # Update average results
        current_avg_results = self.stats["average_results_returned"]
        self.stats["average_results_returned"] = (
            (current_avg_results * (total_searches - 1) + num_results) / total_searches
        )
        
        # Update average search time
        current_avg_time = self.stats["average_search_time"]
        self.stats["average_search_time"] = (
            (current_avg_time * (total_searches - 1) + search_time) / total_searches
        )
    
    async def get_search_statistics(self) -> Dict[str, Any]:
        """Get search statistics"""
        return self.stats.copy()
    
    async def shutdown(self):
        """Shutdown hybrid search service"""
        self.logger.info("Hybrid search service shutdown")