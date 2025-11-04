"""
Centrality Measures for Knowledge Graphs
Implements various centrality algorithms including betweenness, closeness, eigenvector, and PageRank.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set
import logging
from dataclasses import dataclass
from enum import Enum
import numpy as np
from collections import defaultdict, deque
import networkx as nx

logger = logging.getLogger(__name__)

class CentralityType(Enum):
    DEGREE = "degree"
    BETWEENNESS = "betweenness"
    CLOSENESS = "closeness"
    EIGENVECTOR = "eigenvector"
    PAGERANK = "pagerank"
    KATZ = "katz"
    HARMONIC = "harmonic"

@dataclass
class CentralityConfig:
    centrality_type: CentralityType = CentralityType.BETWEENNESS
    normalized: bool = True
    weight_attribute: Optional[str] = None
    max_iterations: int = 100
    tolerance: float = 1e-6
    alpha: float = 0.85  # For PageRank
    beta: float = 0.1   # For Katz centrality
    node_filters: Optional[Dict[str, Any]] = None
    include_self_loops: bool = False

@dataclass
class CentralityResult:
    node_id: str
    centrality_score: float
    rank: int
    metadata: Dict[str, Any] = None

class CentralityCalculator:
    """Calculate various centrality measures for knowledge graphs"""
    
    def __init__(self, graph_engine=None):
        self.graph_engine = graph_engine
        self.logger = logging.getLogger(__name__)
    
    async def calculate(self, centrality_type: str = "betweenness", node_filter: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Calculate centrality measures"""
        try:
            config = CentralityConfig(
                centrality_type=CentralityType(centrality_type),
                node_filters=node_filter
            )
            
            if config.centrality_type == CentralityType.DEGREE:
                return await self.calculate_degree_centrality(config)
            elif config.centrality_type == CentralityType.BETWEENNESS:
                return await self.calculate_betweenness_centrality(config)
            elif config.centrality_type == CentralityType.CLOSENESS:
                return await self.calculate_closeness_centrality(config)
            elif config.centrality_type == CentralityType.EIGENVECTOR:
                return await self.calculate_eigenvector_centrality(config)
            elif config.centrality_type == CentralityType.PAGERANK:
                return await self.calculate_pagerank(config)
            elif config.centrality_type == CentralityType.KATZ:
                return await self.calculate_katz_centrality(config)
            elif config.centrality_type == CentralityType.HARMONIC:
                return await self.calculate_harmonic_centrality(config)
            else:
                self.logger.warning(f"Unknown centrality type: {centrality_type}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error calculating centrality: {e}")
            return {}
    
    async def calculate_degree_centrality(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate degree centrality"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            centrality_scores = {}
            total_nodes = len(graph_data["nodes"])
            
            for node_id in graph_data["nodes"]:
                # Count in-degree and out-degree
                in_degree = len([n for n in graph_data["adjacency"] if node_id in graph_data["adjacency"][n]])
                out_degree = len(graph_data["adjacency"].get(node_id, {}))
                degree = in_degree + out_degree
                
                if config.normalized and total_nodes > 1:
                    centrality_scores[node_id] = degree / (total_nodes - 1)
                else:
                    centrality_scores[node_id] = float(degree)
            
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating degree centrality: {e}")
            return {}
    
    async def calculate_betweenness_centrality(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate betweenness centrality using Brandes' algorithm"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            
            centrality_scores = {node: 0.0 for node in nodes}
            
            # Brandes' algorithm
            for source in nodes:
                # Initialize
                stack = []
                predecessors = {node: [] for node in nodes}
                distances = {node: -1 for node in nodes}
                sigma = {node: 0 for node in nodes}
                delta = {node: 0.0 for node in nodes}
                
                distances[source] = 0
                sigma[source] = 1
                queue = deque([source])
                
                # BFS to compute shortest paths
                while queue:
                    current = queue.popleft()
                    stack.append(current)
                    
                    for neighbor in adjacency.get(current, {}):
                        # First time we reach this neighbor?
                        if distances[neighbor] < 0:
                            queue.append(neighbor)
                            distances[neighbor] = distances[current] + 1
                        
                        # Shortest path to neighbor via current?
                        if distances[neighbor] == distances[current] + 1:
                            sigma[neighbor] += sigma[current]
                            predecessors[neighbor].append(current)
                
                # Accumulation
                while stack:
                    node = stack.pop()
                    for predecessor in predecessors[node]:
                        delta[predecessor] += (sigma[predecessor] / sigma[node]) * (1 + delta[node])
                    
                    if node != source:
                        centrality_scores[node] += delta[node]
            
            # Normalization
            if config.normalized:
                n = len(nodes)
                if n > 2:
                    normalization_factor = 2.0 / ((n - 1) * (n - 2))
                    for node in centrality_scores:
                        centrality_scores[node] *= normalization_factor
            
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating betweenness centrality: {e}")
            return {}
    
    async def calculate_closeness_centrality(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate closeness centrality"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            centrality_scores = {}
            
            for source in nodes:
                # BFS to compute shortest distances
                distances = {source: 0}
                queue = deque([source])
                
                while queue:
                    current = queue.popleft()
                    
                    for neighbor in adjacency.get(current, {}):
                        if neighbor not in distances:
                            distances[neighbor] = distances[current] + 1
                            queue.append(neighbor)
                
                # Calculate closeness
                total_distance = sum(distances.values())
                reachable_nodes = len(distances) - 1  # Exclude source itself
                
                if total_distance > 0 and reachable_nodes > 0:
                    closeness = reachable_nodes / total_distance
                    
                    if config.normalized:
                        closeness = closeness * reachable_nodes / (len(nodes) - 1)
                    
                    centrality_scores[source] = closeness
                else:
                    centrality_scores[source] = 0.0
            
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating closeness centrality: {e}")
            return {}
    
    async def calculate_eigenvector_centrality(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate eigenvector centrality using power iteration"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            n = len(nodes)
            
            if n == 0:
                return {}
            
            # Create adjacency matrix
            node_to_idx = {node: i for i, node in enumerate(nodes)}
            adj_matrix = np.zeros((n, n))
            
            for source, neighbors in adjacency.items():
                source_idx = node_to_idx[source]
                for target in neighbors:
                    target_idx = node_to_idx[target]
                    adj_matrix[source_idx][target_idx] = 1.0
            
            # Power iteration
            x = np.ones(n) / n
            
            for iteration in range(config.max_iterations):
                x_new = adj_matrix.T @ x
                
                # Normalize
                norm = np.linalg.norm(x_new)
                if norm > 0:
                    x_new = x_new / norm
                
                # Check convergence
                if np.allclose(x, x_new, atol=config.tolerance):
                    break
                
                x = x_new
            
            # Convert back to dictionary
            centrality_scores = {}
            for i, node in enumerate(nodes):
                centrality_scores[node] = float(x[i])
            
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating eigenvector centrality: {e}")
            return {}
    
    async def calculate_pagerank(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate PageRank"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            n = len(nodes)
            
            if n == 0:
                return {}
            
            # Initialize PageRank scores
            pagerank = {node: 1.0 / n for node in nodes}
            
            # Calculate out-degrees
            out_degrees = {}
            for node in nodes:
                out_degrees[node] = len(adjacency.get(node, {}))
            
            # Power iteration
            for iteration in range(config.max_iterations):
                new_pagerank = {}
                
                for node in nodes:
                    # Random walk component
                    new_score = (1 - config.alpha) / n
                    
                    # Link contribution
                    for source, neighbors in adjacency.items():
                        if node in neighbors and out_degrees[source] > 0:
                            new_score += config.alpha * pagerank[source] / out_degrees[source]
                    
                    new_pagerank[node] = new_score
                
                # Check convergence
                diff = sum(abs(new_pagerank[node] - pagerank[node]) for node in nodes)
                if diff < config.tolerance:
                    break
                
                pagerank = new_pagerank
            
            return pagerank
            
        except Exception as e:
            self.logger.error(f"Error calculating PageRank: {e}")
            return {}
    
    async def calculate_katz_centrality(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate Katz centrality"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            n = len(nodes)
            
            if n == 0:
                return {}
            
            # Create adjacency matrix
            node_to_idx = {node: i for i, node in enumerate(nodes)}
            adj_matrix = np.zeros((n, n))
            
            for source, neighbors in adjacency.items():
                source_idx = node_to_idx[source]
                for target in neighbors:
                    target_idx = node_to_idx[target]
                    adj_matrix[source_idx][target_idx] = 1.0
            
            # Katz centrality: (I - alpha * A^T)^-1 * beta
            identity = np.eye(n)
            try:
                katz_matrix = np.linalg.inv(identity - config.beta * adj_matrix.T)
                katz_scores = katz_matrix @ np.ones(n) * config.beta
            except np.linalg.LinAlgError:
                # Matrix is not invertible, use power iteration
                x = np.ones(n)
                for _ in range(config.max_iterations):
                    x_new = config.beta * (adj_matrix.T @ x) + config.beta
                    if np.allclose(x, x_new, atol=config.tolerance):
                        break
                    x = x_new
                katz_scores = x
            
            # Convert to dictionary
            centrality_scores = {}
            for i, node in enumerate(nodes):
                centrality_scores[node] = float(katz_scores[i])
            
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating Katz centrality: {e}")
            return {}
    
    async def calculate_harmonic_centrality(self, config: CentralityConfig) -> Dict[str, float]:
        """Calculate harmonic centrality"""
        try:
            graph_data = await self._build_graph_representation(config)
            
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            centrality_scores = {}
            
            for source in nodes:
                # BFS to compute shortest distances
                distances = {source: 0}
                queue = deque([source])
                
                while queue:
                    current = queue.popleft()
                    
                    for neighbor in adjacency.get(current, {}):
                        if neighbor not in distances:
                            distances[neighbor] = distances[current] + 1
                            queue.append(neighbor)
                
                # Calculate harmonic centrality
                harmonic_sum = 0.0
                for target, distance in distances.items():
                    if target != source and distance > 0:
                        harmonic_sum += 1.0 / distance
                
                if config.normalized and len(nodes) > 1:
                    harmonic_sum = harmonic_sum / (len(nodes) - 1)
                
                centrality_scores[source] = harmonic_sum
            
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating harmonic centrality: {e}")
            return {}
    
    async def _build_graph_representation(self, config: CentralityConfig) -> Optional[Dict[str, Any]]:
        """Build graph representation for centrality calculation"""
        try:
            if not self.graph_engine:
                return None
            
            # Get graph statistics to understand size
            stats = await self.graph_engine.get_statistics()
            
            # For large graphs, we might want to sample or use approximate methods
            # For now, try to get the full graph
            
            nodes = set()
            adjacency = defaultdict(set)
            
            # Get all entities (nodes)
            entities_filter = config.node_filters or {}
            entities = await self.graph_engine.find_entities(entities_filter, limit=10000)
            
            for entity in entities:
                node_id = entity.get("_id", entity.get("id", "")).split("/")[-1]
                nodes.add(node_id)
            
            # Get all relationships (edges)
            relationships = await self.graph_engine.find_relationships(limit=50000)
            
            for rel in relationships:
                source_id = rel.get("_from", rel.get("source_id", "")).split("/")[-1]
                target_id = rel.get("_to", rel.get("target_id", "")).split("/")[-1]
                
                if source_id in nodes and target_id in nodes:
                    adjacency[source_id].add(target_id)
                    
                    # For undirected graphs, add reverse edge
                    # adjacency[target_id].add(source_id)
            
            # Convert sets to lists for consistency
            adjacency_dict = {}
            for source, targets in adjacency.items():
                adjacency_dict[source] = list(targets)
            
            return {
                "nodes": list(nodes),
                "adjacency": adjacency_dict
            }
            
        except Exception as e:
            self.logger.error(f"Error building graph representation: {e}")
            return None
    
    async def get_top_central_nodes(self, centrality_scores: Dict[str, float], top_k: int = 10) -> List[CentralityResult]:
        """Get top-k nodes by centrality score"""
        try:
            # Sort by centrality score
            sorted_nodes = sorted(centrality_scores.items(), key=lambda x: x[1], reverse=True)
            
            results = []
            for rank, (node_id, score) in enumerate(sorted_nodes[:top_k], 1):
                result = CentralityResult(
                    node_id=node_id,
                    centrality_score=score,
                    rank=rank
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting top central nodes: {e}")
            return []
    
    async def compare_centrality_measures(self, node_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, float]]:
        """Compare different centrality measures for the same graph"""
        try:
            centrality_types = [
                CentralityType.DEGREE,
                CentralityType.BETWEENNESS,
                CentralityType.CLOSENESS,
                CentralityType.PAGERANK
            ]
            
            results = {}
            
            for centrality_type in centrality_types:
                config = CentralityConfig(
                    centrality_type=centrality_type,
                    node_filters=node_filters
                )
                
                scores = await self.calculate(centrality_type.value, node_filters)
                results[centrality_type.value] = scores
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error comparing centrality measures: {e}")
            return {}
    
    async def get_centrality_statistics(self, centrality_scores: Dict[str, float]) -> Dict[str, Any]:
        """Get statistics for centrality scores"""
        try:
            if not centrality_scores:
                return {}
            
            scores = list(centrality_scores.values())
            
            stats = {
                "count": len(scores),
                "min": min(scores),
                "max": max(scores),
                "mean": sum(scores) / len(scores),
                "median": sorted(scores)[len(scores) // 2],
                "std": np.std(scores) if len(scores) > 1 else 0.0
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculating centrality statistics: {e}")
            return {}
    
    async def shutdown(self):
        """Cleanup resources"""
        pass