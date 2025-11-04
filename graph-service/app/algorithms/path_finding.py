"""
Path Finding Algorithms for Knowledge Graphs
Implements various path finding algorithms including shortest path, all paths, and weighted paths.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from dataclasses import dataclass
from enum import Enum
import heapq
from collections import deque, defaultdict
import networkx as nx

logger = logging.getLogger(__name__)

class PathType(Enum):
    SHORTEST = "shortest"
    ALL_SIMPLE = "all_simple"
    K_SHORTEST = "k_shortest"
    WEIGHTED_SHORTEST = "weighted_shortest"

@dataclass
class Path:
    nodes: List[str]
    edges: List[Dict[str, Any]]
    length: int
    weight: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class PathFindingConfig:
    max_depth: int = 6
    max_paths: int = 100
    weight_property: str = "weight"
    direction: str = "outbound"  # outbound, inbound, both
    relationship_types: Optional[List[str]] = None
    node_filters: Optional[Dict[str, Any]] = None
    edge_filters: Optional[Dict[str, Any]] = None

class PathFinder:
    """Path finding algorithms for knowledge graphs"""
    
    def __init__(self, graph_engine=None):
        self.graph_engine = graph_engine
        self.logger = logging.getLogger(__name__)
    
    async def find_path(self, source_id: str, target_id: str, algorithm: str = "dijkstra", max_length: int = 10) -> Optional[Path]:
        """Find path between two nodes"""
        try:
            config = PathFindingConfig(max_depth=max_length)
            
            if algorithm == "dijkstra":
                return await self.find_shortest_path(source_id, target_id, config)
            elif algorithm == "bfs":
                return await self.find_shortest_path_bfs(source_id, target_id, config)
            elif algorithm == "dfs":
                return await self.find_path_dfs(source_id, target_id, config)
            else:
                self.logger.warning(f"Unknown algorithm: {algorithm}")
                return await self.find_shortest_path(source_id, target_id, config)
                
        except Exception as e:
            self.logger.error(f"Error finding path: {e}")
            return None
    
    async def find_shortest_path(self, source_id: str, target_id: str, config: PathFindingConfig) -> Optional[Path]:
        """Find shortest path using Dijkstra's algorithm"""
        try:
            if not self.graph_engine:
                return None
            
            # Get graph data
            graph_data = await self._build_graph_representation(source_id, target_id, config)
            
            if not graph_data:
                return None
            
            # Run Dijkstra's algorithm
            distances = {source_id: 0.0}
            previous = {}
            unvisited = set(graph_data["nodes"])
            
            while unvisited:
                # Get node with minimum distance
                current = min(unvisited, key=lambda x: distances.get(x, float('inf')))
                
                if distances.get(current, float('inf')) == float('inf'):
                    break  # No path exists
                
                if current == target_id:
                    # Reconstruct path
                    path_nodes = []
                    node = target_id
                    
                    while node in previous:
                        path_nodes.append(node)
                        node = previous[node]
                    path_nodes.append(source_id)
                    path_nodes.reverse()
                    
                    # Get edges for the path
                    path_edges = await self._get_path_edges(path_nodes, graph_data)
                    
                    return Path(
                        nodes=path_nodes,
                        edges=path_edges,
                        length=len(path_nodes) - 1,
                        weight=distances[current]
                    )
                
                unvisited.remove(current)
                
                # Update distances to neighbors
                for neighbor_id, edge_data in graph_data["adjacency"].get(current, {}).items():
                    if neighbor_id in unvisited:
                        weight = edge_data.get(config.weight_property, 1.0)
                        new_distance = distances[current] + weight
                        
                        if new_distance < distances.get(neighbor_id, float('inf')):
                            distances[neighbor_id] = new_distance
                            previous[neighbor_id] = current
            
            return None  # No path found
            
        except Exception as e:
            self.logger.error(f"Error in shortest path finding: {e}")
            return None
    
    async def find_shortest_path_bfs(self, source_id: str, target_id: str, config: PathFindingConfig) -> Optional[Path]:
        """Find shortest path using BFS (unweighted)"""
        try:
            if not self.graph_engine:
                return None
            
            graph_data = await self._build_graph_representation(source_id, target_id, config)
            
            if not graph_data:
                return None
            
            # BFS
            queue = deque([(source_id, [source_id])])
            visited = {source_id}
            
            while queue:
                current_node, path = queue.popleft()
                
                if len(path) > config.max_depth:
                    continue
                
                if current_node == target_id:
                    # Get edges for the path
                    path_edges = await self._get_path_edges(path, graph_data)
                    
                    return Path(
                        nodes=path,
                        edges=path_edges,
                        length=len(path) - 1,
                        weight=len(path) - 1
                    )
                
                # Explore neighbors
                for neighbor_id in graph_data["adjacency"].get(current_node, {}):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, path + [neighbor_id]))
            
            return None  # No path found
            
        except Exception as e:
            self.logger.error(f"Error in BFS path finding: {e}")
            return None
    
    async def find_path_dfs(self, source_id: str, target_id: str, config: PathFindingConfig) -> Optional[Path]:
        """Find path using DFS"""
        try:
            if not self.graph_engine:
                return None
            
            graph_data = await self._build_graph_representation(source_id, target_id, config)
            
            if not graph_data:
                return None
            
            # DFS with recursion limit
            visited = set()
            path = []
            
            if await self._dfs_recursive(source_id, target_id, visited, path, graph_data, config):
                # Get edges for the path
                path_edges = await self._get_path_edges(path, graph_data)
                
                return Path(
                    nodes=path.copy(),
                    edges=path_edges,
                    length=len(path) - 1,
                    weight=len(path) - 1
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in DFS path finding: {e}")
            return None
    
    async def _dfs_recursive(self, current: str, target: str, visited: Set[str], path: List[str], 
                           graph_data: Dict[str, Any], config: PathFindingConfig) -> bool:
        """Recursive DFS helper"""
        if len(path) >= config.max_depth:
            return False
        
        visited.add(current)
        path.append(current)
        
        if current == target:
            return True
        
        # Explore neighbors
        for neighbor_id in graph_data["adjacency"].get(current, {}):
            if neighbor_id not in visited:
                if await self._dfs_recursive(neighbor_id, target, visited, path, graph_data, config):
                    return True
        
        # Backtrack
        visited.remove(current)
        path.pop()
        
        return False
    
    async def find_all_simple_paths(self, source_id: str, target_id: str, config: PathFindingConfig) -> List[Path]:
        """Find all simple paths between two nodes"""
        try:
            if not self.graph_engine:
                return []
            
            graph_data = await self._build_graph_representation(source_id, target_id, config)
            
            if not graph_data:
                return []
            
            paths = []
            
            def dfs_all_paths(current: str, target: str, visited: Set[str], path: List[str]):
                if len(path) > config.max_depth or len(paths) >= config.max_paths:
                    return
                
                if current == target:
                    paths.append(path.copy())
                    return
                
                visited.add(current)
                
                for neighbor_id in graph_data["adjacency"].get(current, {}):
                    if neighbor_id not in visited:
                        path.append(neighbor_id)
                        dfs_all_paths(neighbor_id, target, visited, path)
                        path.pop()
                
                visited.remove(current)
            
            # Start DFS
            dfs_all_paths(source_id, target_id, set(), [source_id])
            
            # Convert to Path objects
            result_paths = []
            for path_nodes in paths:
                path_edges = await self._get_path_edges(path_nodes, graph_data)
                result_paths.append(Path(
                    nodes=path_nodes,
                    edges=path_edges,
                    length=len(path_nodes) - 1,
                    weight=len(path_nodes) - 1
                ))
            
            return result_paths
            
        except Exception as e:
            self.logger.error(f"Error finding all paths: {e}")
            return []
    
    async def find_k_shortest_paths(self, source_id: str, target_id: str, k: int, config: PathFindingConfig) -> List[Path]:
        """Find k shortest paths using Yen's algorithm"""
        try:
            if not self.graph_engine:
                return []
            
            # First, find the shortest path
            shortest_path = await self.find_shortest_path(source_id, target_id, config)
            
            if not shortest_path:
                return []
            
            paths = [shortest_path]
            candidates = []
            
            for i in range(1, k):
                # Generate candidate paths
                for j in range(len(paths[i-1].nodes) - 1):
                    spur_node = paths[i-1].nodes[j]
                    root_path = paths[i-1].nodes[:j+1]
                    
                    # Remove edges that are part of previous paths
                    removed_edges = set()
                    for path in paths:
                        if path.nodes[:j+1] == root_path and j+1 < len(path.nodes):
                            edge = (path.nodes[j], path.nodes[j+1])
                            removed_edges.add(edge)
                    
                    # Find path from spur node to target avoiding removed edges
                    spur_path = await self._find_path_avoiding_edges(spur_node, target_id, removed_edges, config)
                    
                    if spur_path:
                        # Combine root path and spur path
                        total_path = root_path[:-1] + spur_path.nodes
                        total_weight = (j * 1.0) + spur_path.weight  # Simplified weight calculation
                        
                        candidate_path = Path(
                            nodes=total_path,
                            edges=[],  # Would need to reconstruct
                            length=len(total_path) - 1,
                            weight=total_weight
                        )
                        
                        # Add to candidates if not already there
                        if not any(c.nodes == candidate_path.nodes for c in candidates):
                            candidates.append(candidate_path)
                
                if not candidates:
                    break
                
                # Get the shortest candidate
                candidates.sort(key=lambda x: x.weight)
                paths.append(candidates.pop(0))
            
            return paths
            
        except Exception as e:
            self.logger.error(f"Error finding k shortest paths: {e}")
            return []
    
    async def _find_path_avoiding_edges(self, source_id: str, target_id: str, avoided_edges: Set[Tuple[str, str]], 
                                      config: PathFindingConfig) -> Optional[Path]:
        """Find path while avoiding specific edges"""
        try:
            # This is a simplified implementation
            # In practice, you'd modify the graph representation to exclude avoided edges
            return await self.find_shortest_path(source_id, target_id, config)
        except Exception as e:
            self.logger.error(f"Error finding path avoiding edges: {e}")
            return None
    
    async def _build_graph_representation(self, source_id: str, target_id: str, config: PathFindingConfig) -> Optional[Dict[str, Any]]:
        """Build graph representation for pathfinding"""
        try:
            if not self.graph_engine:
                return None
            
            # Get subgraph around source and target
            nodes = set()
            adjacency = defaultdict(dict)
            
            # BFS to collect relevant nodes and edges
            queue = deque([source_id, target_id])
            visited = set()
            depth = 0
            
            while queue and depth < config.max_depth:
                level_size = len(queue)
                
                for _ in range(level_size):
                    current_node = queue.popleft()
                    
                    if current_node in visited:
                        continue
                    
                    visited.add(current_node)
                    nodes.add(current_node)
                    
                    # Get neighbors
                    neighbors = await self._get_node_neighbors(current_node, config)
                    
                    for neighbor_data in neighbors:
                        neighbor_id = neighbor_data["node_id"]
                        edge_data = neighbor_data["edge"]
                        
                        # Add to adjacency list
                        adjacency[current_node][neighbor_id] = edge_data
                        
                        # Add neighbor to queue for next level
                        if neighbor_id not in visited:
                            queue.append(neighbor_id)
                            nodes.add(neighbor_id)
                
                depth += 1
            
            return {
                "nodes": list(nodes),
                "adjacency": dict(adjacency)
            }
            
        except Exception as e:
            self.logger.error(f"Error building graph representation: {e}")
            return None
    
    async def _get_node_neighbors(self, node_id: str, config: PathFindingConfig) -> List[Dict[str, Any]]:
        """Get neighbors of a node"""
        try:
            if not self.graph_engine:
                return []
            
            # Use graph engine to get neighbors
            neighbors_data = await self.graph_engine.get_entity_neighbors(
                node_id, 
                direction=config.direction, 
                max_depth=1
            )
            
            neighbors = []
            for neighbor_info in neighbors_data:
                neighbor = {
                    "node_id": neighbor_info.get("vertex", {}).get("_id", "").split("/")[-1],
                    "edge": neighbor_info.get("edge", {})
                }
                neighbors.append(neighbor)
            
            return neighbors
            
        except Exception as e:
            self.logger.error(f"Error getting node neighbors: {e}")
            return []
    
    async def _get_path_edges(self, path_nodes: List[str], graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get edge information for a path"""
        edges = []
        
        try:
            for i in range(len(path_nodes) - 1):
                source = path_nodes[i]
                target = path_nodes[i + 1]
                
                # Get edge data from adjacency
                edge_data = graph_data["adjacency"].get(source, {}).get(target, {})
                edges.append(edge_data)
            
            return edges
            
        except Exception as e:
            self.logger.error(f"Error getting path edges: {e}")
            return []
    
    async def find_paths_with_pattern(self, pattern: Dict[str, Any], config: PathFindingConfig) -> List[Path]:
        """Find paths matching a specific pattern"""
        try:
            # This would implement pattern-based path finding
            # For now, return empty list
            self.logger.info("Pattern-based path finding not yet implemented")
            return []
            
        except Exception as e:
            self.logger.error(f"Error finding paths with pattern: {e}")
            return []
    
    async def get_path_statistics(self, paths: List[Path]) -> Dict[str, Any]:
        """Get statistics for a set of paths"""
        try:
            if not paths:
                return {}
            
            lengths = [path.length for path in paths]
            weights = [path.weight for path in paths]
            
            stats = {
                "count": len(paths),
                "min_length": min(lengths),
                "max_length": max(lengths),
                "avg_length": sum(lengths) / len(lengths),
                "min_weight": min(weights),
                "max_weight": max(weights),
                "avg_weight": sum(weights) / len(weights)
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculating path statistics: {e}")
            return {}
    
    async def shutdown(self):
        """Cleanup resources"""
        pass