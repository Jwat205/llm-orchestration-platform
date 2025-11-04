"""
Community Detection Algorithms for Knowledge Graphs
Implements various community detection algorithms including Louvain, Leiden, and modularity-based methods.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict, deque
import random
import networkx as nx

logger = logging.getLogger(__name__)

class CommunityAlgorithm(Enum):
    LOUVAIN = "louvain"
    LEIDEN = "leiden"
    LABEL_PROPAGATION = "label_propagation"
    GIRVAN_NEWMAN = "girvan_newman"
    MODULARITY_MAXIMIZATION = "modularity_maximization"
    WALKTRAP = "walktrap"
    INFOMAP = "infomap"

@dataclass
class CommunityDetectionConfig:
    algorithm: CommunityAlgorithm = CommunityAlgorithm.LOUVAIN
    resolution: float = 1.0
    max_iterations: int = 100
    tolerance: float = 1e-6
    random_seed: Optional[int] = None
    weight_attribute: Optional[str] = None
    min_community_size: int = 2
    max_communities: Optional[int] = None
    node_filters: Optional[Dict[str, Any]] = None

@dataclass
class Community:
    community_id: str
    nodes: Set[str]
    size: int
    internal_edges: int
    external_edges: int
    modularity_contribution: float
    density: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CommunityDetectionResult:
    communities: List[Community]
    modularity: float
    num_communities: int
    coverage: float
    performance: float
    algorithm_used: str
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

class CommunityDetector:
    """Detect communities in knowledge graphs using various algorithms"""
    
    def __init__(self, graph_engine=None):
        self.graph_engine = graph_engine
        self.logger = logging.getLogger(__name__)
    
    async def detect(self, algorithm: str = "louvain", resolution: float = 1.0) -> Dict[str, Any]:
        """Detect communities using specified algorithm"""
        try:
            config = CommunityDetectionConfig(
                algorithm=CommunityAlgorithm(algorithm),
                resolution=resolution
            )
            
            if config.algorithm == CommunityAlgorithm.LOUVAIN:
                return await self.detect_louvain(config)
            elif config.algorithm == CommunityAlgorithm.LEIDEN:
                return await self.detect_leiden(config)
            elif config.algorithm == CommunityAlgorithm.LABEL_PROPAGATION:
                return await self.detect_label_propagation(config)
            elif config.algorithm == CommunityAlgorithm.GIRVAN_NEWMAN:
                return await self.detect_girvan_newman(config)
            elif config.algorithm == CommunityAlgorithm.MODULARITY_MAXIMIZATION:
                return await self.detect_modularity_maximization(config)
            else:
                self.logger.warning(f"Unknown algorithm: {algorithm}")
                return await self.detect_louvain(config)
                
        except Exception as e:
            self.logger.error(f"Error detecting communities: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def detect_louvain(self, config: CommunityDetectionConfig) -> Dict[str, Any]:
        """Detect communities using Louvain algorithm"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {"communities": [], "modularity": 0.0}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            weights = graph_data.get("weights", {})
            
            # Initialize each node as its own community
            node_to_community = {node: i for i, node in enumerate(nodes)}
            community_to_nodes = {i: {node} for i, node in enumerate(nodes)}
            
            # Calculate initial modularity
            total_weight = sum(sum(weights.get(source, {}).values()) for source in adjacency)
            if total_weight == 0:
                total_weight = sum(len(neighbors) for neighbors in adjacency.values())
            
            improved = True
            iteration = 0
            
            while improved and iteration < config.max_iterations:
                improved = False
                iteration += 1
                
                # Randomize node order
                random_nodes = nodes.copy()
                if config.random_seed:
                    random.seed(config.random_seed + iteration)
                random.shuffle(random_nodes)
                
                for node in random_nodes:
                    current_community = node_to_community[node]
                    
                    # Calculate modularity change for moving to each neighbor's community
                    best_community = current_community
                    best_gain = 0.0
                    
                    neighbor_communities = set()
                    for neighbor in adjacency.get(node, []):
                        neighbor_communities.add(node_to_community[neighbor])
                    
                    for target_community in neighbor_communities:
                        if target_community == current_community:
                            continue
                        
                        # Calculate modularity gain
                        gain = await self._calculate_modularity_gain(
                            node, current_community, target_community,
                            node_to_community, adjacency, weights, total_weight, config.resolution
                        )
                        
                        if gain > best_gain:
                            best_gain = gain
                            best_community = target_community
                    
                    # Move node if beneficial
                    if best_community != current_community and best_gain > config.tolerance:
                        # Remove from current community
                        community_to_nodes[current_community].remove(node)
                        if not community_to_nodes[current_community]:
                            del community_to_nodes[current_community]
                        
                        # Add to new community
                        if best_community not in community_to_nodes:
                            community_to_nodes[best_community] = set()
                        community_to_nodes[best_community].add(node)
                        
                        node_to_community[node] = best_community
                        improved = True
                
                self.logger.debug(f"Louvain iteration {iteration}: {len(community_to_nodes)} communities")
            
            # Convert to Community objects
            communities = []
            for comm_id, comm_nodes in community_to_nodes.items():
                if len(comm_nodes) >= config.min_community_size:
                    community = await self._create_community_object(
                        str(comm_id), comm_nodes, adjacency, weights
                    )
                    communities.append(community)
            
            # Calculate final modularity
            modularity = await self._calculate_modularity(
                node_to_community, adjacency, weights, total_weight, config.resolution
            )
            
            execution_time = time.time() - start_time
            
            result = CommunityDetectionResult(
                communities=communities,
                modularity=modularity,
                num_communities=len(communities),
                coverage=await self._calculate_coverage(communities, nodes),
                performance=await self._calculate_performance(communities, adjacency),
                algorithm_used="louvain",
                execution_time=execution_time
            )
            
            return await self._format_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in Louvain detection: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def detect_leiden(self, config: CommunityDetectionConfig) -> Dict[str, Any]:
        """Detect communities using Leiden algorithm (improved Louvain)"""
        try:
            # Leiden algorithm is more complex - for now, use Louvain as base
            # In practice, would implement the refinement step
            self.logger.info("Using Louvain as Leiden base implementation")
            return await self.detect_louvain(config)
            
        except Exception as e:
            self.logger.error(f"Error in Leiden detection: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def detect_label_propagation(self, config: CommunityDetectionConfig) -> Dict[str, Any]:
        """Detect communities using Label Propagation Algorithm"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {"communities": [], "modularity": 0.0}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            
            # Initialize each node with its own label
            labels = {node: i for i, node in enumerate(nodes)}
            
            # Iteratively update labels
            for iteration in range(config.max_iterations):
                changed = False
                
                # Randomize node order
                random_nodes = nodes.copy()
                if config.random_seed:
                    random.seed(config.random_seed + iteration)
                random.shuffle(random_nodes)
                
                for node in random_nodes:
                    # Count neighbor labels
                    neighbor_labels = defaultdict(int)
                    for neighbor in adjacency.get(node, []):
                        neighbor_labels[labels[neighbor]] += 1
                    
                    if neighbor_labels:
                        # Choose most frequent label (random tie-breaking)
                        max_count = max(neighbor_labels.values())
                        best_labels = [label for label, count in neighbor_labels.items() if count == max_count]
                        new_label = random.choice(best_labels)
                        
                        if new_label != labels[node]:
                            labels[node] = new_label
                            changed = True
                
                if not changed:
                    break
            
            # Group nodes by label
            label_to_nodes = defaultdict(set)
            for node, label in labels.items():
                label_to_nodes[label].add(node)
            
            # Convert to Community objects
            communities = []
            for label, comm_nodes in label_to_nodes.items():
                if len(comm_nodes) >= config.min_community_size:
                    community = await self._create_community_object(
                        str(label), comm_nodes, adjacency, {}
                    )
                    communities.append(community)
            
            # Calculate modularity
            modularity = await self._calculate_modularity(
                labels, adjacency, {}, sum(len(neighbors) for neighbors in adjacency.values()), config.resolution
            )
            
            execution_time = time.time() - start_time
            
            result = CommunityDetectionResult(
                communities=communities,
                modularity=modularity,
                num_communities=len(communities),
                coverage=await self._calculate_coverage(communities, nodes),
                performance=await self._calculate_performance(communities, adjacency),
                algorithm_used="label_propagation",
                execution_time=execution_time
            )
            
            return await self._format_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in label propagation: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def detect_girvan_newman(self, config: CommunityDetectionConfig) -> Dict[str, Any]:
        """Detect communities using Girvan-Newman algorithm"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {"communities": [], "modularity": 0.0}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            
            # Start with all nodes in one component
            current_adjacency = {node: set(neighbors) for node, neighbors in adjacency.items()}
            
            best_modularity = -1.0
            best_communities = []
            
            # Iteratively remove edges with highest betweenness
            for iteration in range(min(len(nodes), config.max_iterations)):
                # Calculate edge betweenness
                edge_betweenness = await self._calculate_edge_betweenness(current_adjacency)
                
                if not edge_betweenness:
                    break
                
                # Remove edge with highest betweenness
                max_betweenness = max(edge_betweenness.values())
                edges_to_remove = [edge for edge, btw in edge_betweenness.items() if btw == max_betweenness]
                
                # Remove one edge (random if tie)
                edge_to_remove = random.choice(edges_to_remove)
                source, target = edge_to_remove
                
                current_adjacency[source].discard(target)
                current_adjacency[target].discard(source)
                
                # Find connected components
                components = await self._find_connected_components(current_adjacency)
                
                # Calculate modularity for current partition
                node_to_community = {}
                for comm_id, component in enumerate(components):
                    for node in component:
                        node_to_community[node] = comm_id
                
                modularity = await self._calculate_modularity(
                    node_to_community, adjacency, {}, 
                    sum(len(neighbors) for neighbors in adjacency.values()), config.resolution
                )
                
                if modularity > best_modularity:
                    best_modularity = modularity
                    best_communities = components.copy()
            
            # Convert to Community objects
            communities = []
            for comm_id, comm_nodes in enumerate(best_communities):
                if len(comm_nodes) >= config.min_community_size:
                    community = await self._create_community_object(
                        str(comm_id), comm_nodes, adjacency, {}
                    )
                    communities.append(community)
            
            execution_time = time.time() - start_time
            
            result = CommunityDetectionResult(
                communities=communities,
                modularity=best_modularity,
                num_communities=len(communities),
                coverage=await self._calculate_coverage(communities, nodes),
                performance=await self._calculate_performance(communities, adjacency),
                algorithm_used="girvan_newman",
                execution_time=execution_time
            )
            
            return await self._format_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in Girvan-Newman detection: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def detect_modularity_maximization(self, config: CommunityDetectionConfig) -> Dict[str, Any]:
        """Detect communities using direct modularity maximization"""
        try:
            # This is computationally expensive for large graphs
            # For now, use Louvain which is a modularity optimization algorithm
            self.logger.info("Using Louvain for modularity maximization")
            return await self.detect_louvain(config)
            
        except Exception as e:
            self.logger.error(f"Error in modularity maximization: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def _build_graph_representation(self, config: CommunityDetectionConfig) -> Optional[Dict[str, Any]]:
        """Build graph representation for community detection"""
        try:
            if not self.graph_engine:
                return None
            
            nodes = set()
            adjacency = defaultdict(list)
            weights = defaultdict(dict)
            
            # Get entities (nodes)
            entities_filter = config.node_filters or {}
            entities = await self.graph_engine.find_entities(entities_filter, limit=10000)
            
            for entity in entities:
                node_id = entity.get("_id", entity.get("id", "")).split("/")[-1]
                nodes.add(node_id)
            
            # Get relationships (edges)
            relationships = await self.graph_engine.find_relationships(limit=50000)
            
            for rel in relationships:
                source_id = rel.get("_from", rel.get("source_id", "")).split("/")[-1]
                target_id = rel.get("_to", rel.get("target_id", "")).split("/")[-1]
                
                if source_id in nodes and target_id in nodes:
                    adjacency[source_id].append(target_id)
                    adjacency[target_id].append(source_id)  # Undirected
                    
                    # Extract weight if specified
                    weight = 1.0
                    if config.weight_attribute and config.weight_attribute in rel:
                        weight = float(rel[config.weight_attribute])
                    
                    weights[source_id][target_id] = weight
                    weights[target_id][source_id] = weight
            
            return {
                "nodes": list(nodes),
                "adjacency": dict(adjacency),
                "weights": dict(weights)
            }
            
        except Exception as e:
            self.logger.error(f"Error building graph representation: {e}")
            return None
    
    async def _calculate_modularity_gain(self, node: str, current_comm: int, target_comm: int,
                                       node_to_community: Dict[str, int], adjacency: Dict[str, List[str]],
                                       weights: Dict[str, Dict[str, float]], total_weight: float,
                                       resolution: float) -> float:
        """Calculate modularity gain for moving a node between communities"""
        try:
            # Simplified modularity gain calculation
            ki = sum(weights.get(node, {}).values()) or len(adjacency.get(node, []))
            
            # Edges to current community
            ki_in_current = 0
            for neighbor in adjacency.get(node, []):
                if node_to_community[neighbor] == current_comm:
                    ki_in_current += weights.get(node, {}).get(neighbor, 1.0)
            
            # Edges to target community
            ki_in_target = 0
            for neighbor in adjacency.get(node, []):
                if node_to_community[neighbor] == target_comm:
                    ki_in_target += weights.get(node, {}).get(neighbor, 1.0)
            
            # Community weights
            sigma_in_current = sum(
                sum(weights.get(n, {}).values()) or len(adjacency.get(n, []))
                for n in node_to_community if node_to_community[n] == current_comm
            )
            
            sigma_in_target = sum(
                sum(weights.get(n, {}).values()) or len(adjacency.get(n, []))
                for n in node_to_community if node_to_community[n] == target_comm
            )
            
            # Modularity gain approximation
            gain = (ki_in_target - ki_in_current) / total_weight
            gain -= resolution * ki * (sigma_in_target - sigma_in_current + ki) / (2 * total_weight * total_weight)
            
            return gain
            
        except Exception as e:
            self.logger.error(f"Error calculating modularity gain: {e}")
            return 0.0
    
    async def _calculate_modularity(self, node_to_community: Dict[str, int], adjacency: Dict[str, List[str]],
                                  weights: Dict[str, Dict[str, float]], total_weight: float,
                                  resolution: float) -> float:
        """Calculate modularity of a partition"""
        try:
            if total_weight == 0:
                return 0.0
            
            modularity = 0.0
            
            # Calculate community degrees
            community_degrees = defaultdict(float)
            for node, community in node_to_community.items():
                degree = sum(weights.get(node, {}).values()) or len(adjacency.get(node, []))
                community_degrees[community] += degree
            
            # Calculate modularity
            for source in adjacency:
                for target in adjacency[source]:
                    if node_to_community[source] == node_to_community[target]:
                        # Internal edge
                        edge_weight = weights.get(source, {}).get(target, 1.0)
                        modularity += edge_weight
            
            # Subtract expected edges
            for community, degree_sum in community_degrees.items():
                modularity -= resolution * (degree_sum * degree_sum) / (2 * total_weight)
            
            return modularity / total_weight
            
        except Exception as e:
            self.logger.error(f"Error calculating modularity: {e}")
            return 0.0
    
    async def _calculate_edge_betweenness(self, adjacency: Dict[str, Set[str]]) -> Dict[Tuple[str, str], float]:
        """Calculate betweenness centrality for edges"""
        try:
            edge_betweenness = defaultdict(float)
            nodes = list(adjacency.keys())
            
            for source in nodes:
                # BFS to find shortest paths
                stack = []
                predecessors = defaultdict(list)
                distances = {node: -1 for node in nodes}
                sigma = {node: 0 for node in nodes}
                
                distances[source] = 0
                sigma[source] = 1
                queue = deque([source])
                
                while queue:
                    current = queue.popleft()
                    stack.append(current)
                    
                    for neighbor in adjacency.get(current, set()):
                        if distances[neighbor] < 0:
                            queue.append(neighbor)
                            distances[neighbor] = distances[current] + 1
                        
                        if distances[neighbor] == distances[current] + 1:
                            sigma[neighbor] += sigma[current]
                            predecessors[neighbor].append(current)
                
                # Calculate edge betweenness
                delta = {node: 0.0 for node in nodes}
                
                while stack:
                    node = stack.pop()
                    for predecessor in predecessors[node]:
                        edge_contribution = (sigma[predecessor] / sigma[node]) * (1 + delta[node])
                        delta[predecessor] += edge_contribution
                        
                        # Add to edge betweenness
                        edge = tuple(sorted([predecessor, node]))
                        edge_betweenness[edge] += edge_contribution
            
            return dict(edge_betweenness)
            
        except Exception as e:
            self.logger.error(f"Error calculating edge betweenness: {e}")
            return {}
    
    async def _find_connected_components(self, adjacency: Dict[str, Set[str]]) -> List[Set[str]]:
        """Find connected components in graph"""
        try:
            visited = set()
            components = []
            
            for node in adjacency:
                if node not in visited:
                    # BFS to find component
                    component = set()
                    queue = deque([node])
                    
                    while queue:
                        current = queue.popleft()
                        if current not in visited:
                            visited.add(current)
                            component.add(current)
                            
                            for neighbor in adjacency.get(current, set()):
                                if neighbor not in visited:
                                    queue.append(neighbor)
                    
                    components.append(component)
            
            return components
            
        except Exception as e:
            self.logger.error(f"Error finding connected components: {e}")
            return []
    
    async def _create_community_object(self, community_id: str, nodes: Set[str],
                                     adjacency: Dict[str, List[str]], weights: Dict[str, Dict[str, float]]) -> Community:
        """Create Community object from nodes"""
        try:
            internal_edges = 0
            external_edges = 0
            
            for node in nodes:
                for neighbor in adjacency.get(node, []):
                    if neighbor in nodes:
                        internal_edges += 1
                    else:
                        external_edges += 1
            
            # Account for double counting
            internal_edges //= 2
            
            # Calculate density
            n = len(nodes)
            max_internal_edges = n * (n - 1) // 2
            density = internal_edges / max_internal_edges if max_internal_edges > 0 else 0.0
            
            return Community(
                community_id=community_id,
                nodes=nodes,
                size=len(nodes),
                internal_edges=internal_edges,
                external_edges=external_edges,
                modularity_contribution=0.0,  # Would calculate actual contribution
                density=density
            )
            
        except Exception as e:
            self.logger.error(f"Error creating community object: {e}")
            return Community(
                community_id=community_id,
                nodes=nodes,
                size=len(nodes),
                internal_edges=0,
                external_edges=0,
                modularity_contribution=0.0,
                density=0.0
            )
    
    async def _calculate_coverage(self, communities: List[Community], all_nodes: List[str]) -> float:
        """Calculate coverage of communities"""
        try:
            covered_nodes = set()
            for community in communities:
                covered_nodes.update(community.nodes)
            
            return len(covered_nodes) / len(all_nodes) if all_nodes else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating coverage: {e}")
            return 0.0
    
    async def _calculate_performance(self, communities: List[Community], adjacency: Dict[str, List[str]]) -> float:
        """Calculate performance metric"""
        try:
            total_edges = sum(len(neighbors) for neighbors in adjacency.values()) // 2
            if total_edges == 0:
                return 0.0
            
            correct_edges = sum(community.internal_edges for community in communities)
            return correct_edges / total_edges
            
        except Exception as e:
            self.logger.error(f"Error calculating performance: {e}")
            return 0.0
    
    async def _format_result(self, result: CommunityDetectionResult) -> Dict[str, Any]:
        """Format result for API response"""
        try:
            communities_data = []
            for community in result.communities:
                comm_data = {
                    "id": community.community_id,
                    "nodes": list(community.nodes),
                    "size": community.size,
                    "internal_edges": community.internal_edges,
                    "external_edges": community.external_edges,
                    "density": community.density,
                    "modularity_contribution": community.modularity_contribution
                }
                communities_data.append(comm_data)
            
            return {
                "communities": communities_data,
                "modularity": result.modularity,
                "num_communities": result.num_communities,
                "coverage": result.coverage,
                "performance": result.performance,
                "algorithm": result.algorithm_used,
                "execution_time": result.execution_time,
                "metadata": result.metadata
            }
            
        except Exception as e:
            self.logger.error(f"Error formatting result: {e}")
            return {"communities": [], "modularity": 0.0}
    
    async def compare_algorithms(self, algorithms: List[str], config: CommunityDetectionConfig) -> Dict[str, Any]:
        """Compare different community detection algorithms"""
        try:
            results = {}
            
            for algorithm in algorithms:
                config.algorithm = CommunityAlgorithm(algorithm)
                result = await self.detect(algorithm, config.resolution)
                results[algorithm] = result
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error comparing algorithms: {e}")
            return {}
    
    async def get_community_statistics(self, communities: List[Community]) -> Dict[str, Any]:
        """Get statistics for detected communities"""
        try:
            if not communities:
                return {}
            
            sizes = [comm.size for comm in communities]
            densities = [comm.density for comm in communities]
            
            stats = {
                "num_communities": len(communities),
                "total_nodes": sum(sizes),
                "avg_community_size": sum(sizes) / len(sizes),
                "min_community_size": min(sizes),
                "max_community_size": max(sizes),
                "avg_density": sum(densities) / len(densities),
                "min_density": min(densities),
                "max_density": max(densities)
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculating community statistics: {e}")
            return {}
    
    async def shutdown(self):
        """Cleanup resources"""
        pass