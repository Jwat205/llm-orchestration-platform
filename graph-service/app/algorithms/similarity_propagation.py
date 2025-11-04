"""
Similarity Propagation Algorithms for Knowledge Graphs
Implements similarity propagation, influence maximization, and trust propagation algorithms.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict, deque
import random
import math

logger = logging.getLogger(__name__)

class PropagationType(Enum):
    SIMILARITY = "similarity"
    TRUST = "trust"
    INFLUENCE = "influence"
    PERSONALIZED_PAGERANK = "personalized_pagerank"
    RANDOM_WALK = "random_walk"
    LABEL_SPREADING = "label_spreading"

@dataclass
class PropagationConfig:
    propagation_type: PropagationType = PropagationType.SIMILARITY
    alpha: float = 0.85  # Damping factor
    beta: float = 0.15   # Restart probability
    max_iterations: int = 100
    tolerance: float = 1e-6
    initial_scores: Optional[Dict[str, float]] = None
    seed_nodes: Optional[List[str]] = None
    weight_attribute: Optional[str] = None
    direction: str = "both"  # outbound, inbound, both
    normalize: bool = True
    decay_factor: float = 0.9

@dataclass
class PropagationResult:
    node_scores: Dict[str, float]
    iterations: int
    converged: bool
    execution_time: float
    algorithm_used: str
    seed_nodes: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

class SimilarityPropagator:
    """Propagate similarity, trust, and influence through knowledge graphs"""
    
    def __init__(self, graph_engine=None):
        self.graph_engine = graph_engine
        self.logger = logging.getLogger(__name__)
    
    async def propagate(self, seed_nodes: List[str], propagation_type: str = "similarity", 
                       alpha: float = 0.85) -> Dict[str, float]:
        """Propagate scores from seed nodes"""
        try:
            config = PropagationConfig(
                propagation_type=PropagationType(propagation_type),
                alpha=alpha,
                seed_nodes=seed_nodes
            )
            
            if config.propagation_type == PropagationType.SIMILARITY:
                return await self.similarity_propagation(config)
            elif config.propagation_type == PropagationType.TRUST:
                return await self.trust_propagation(config)
            elif config.propagation_type == PropagationType.INFLUENCE:
                return await self.influence_propagation(config)
            elif config.propagation_type == PropagationType.PERSONALIZED_PAGERANK:
                return await self.personalized_pagerank(config)
            elif config.propagation_type == PropagationType.RANDOM_WALK:
                return await self.random_walk_propagation(config)
            elif config.propagation_type == PropagationType.LABEL_SPREADING:
                return await self.label_spreading(config)
            else:
                self.logger.warning(f"Unknown propagation type: {propagation_type}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error in propagation: {e}")
            return {}
    
    async def similarity_propagation(self, config: PropagationConfig) -> Dict[str, float]:
        """Propagate similarity scores through the graph"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            weights = graph_data.get("weights", {})
            
            # Initialize scores
            scores = {node: 0.0 for node in nodes}
            
            # Set initial scores for seed nodes
            if config.seed_nodes:
                seed_score = 1.0 / len(config.seed_nodes)
                for seed in config.seed_nodes:
                    if seed in scores:
                        scores[seed] = seed_score
            
            if config.initial_scores:
                scores.update(config.initial_scores)
            
            # Normalize transition matrix
            transition_matrix = await self._build_transition_matrix(adjacency, weights, config.normalize)
            
            # Power iteration
            converged = False
            iteration = 0
            
            while iteration < config.max_iterations and not converged:
                new_scores = {node: 0.0 for node in nodes}
                
                # Propagation step
                for node in nodes:
                    # Random restart component
                    restart_score = (1 - config.alpha) * (scores[node] if node in config.seed_nodes else 0.0)
                    
                    # Propagation component
                    prop_score = 0.0
                    for source in transition_matrix:
                        if node in transition_matrix[source]:
                            prop_score += config.alpha * scores[source] * transition_matrix[source][node]
                    
                    new_scores[node] = restart_score + prop_score
                
                # Check convergence
                diff = sum(abs(new_scores[node] - scores[node]) for node in nodes)
                if diff < config.tolerance:
                    converged = True
                
                scores = new_scores
                iteration += 1
            
            execution_time = time.time() - start_time
            
            result = PropagationResult(
                node_scores=scores,
                iterations=iteration,
                converged=converged,
                execution_time=execution_time,
                algorithm_used="similarity_propagation",
                seed_nodes=config.seed_nodes or []
            )
            
            return await self._format_propagation_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in similarity propagation: {e}")
            return {}
    
    async def trust_propagation(self, config: PropagationConfig) -> Dict[str, float]:
        """Propagate trust scores with decay"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            weights = graph_data.get("weights", {})
            
            # Initialize trust scores
            trust_scores = {node: 0.0 for node in nodes}
            
            # Set initial trust for seed nodes
            if config.seed_nodes:
                for seed in config.seed_nodes:
                    if seed in trust_scores:
                        trust_scores[seed] = 1.0
            
            # BFS-based trust propagation with decay
            for seed in config.seed_nodes or []:
                if seed not in nodes:
                    continue
                
                visited = set()
                queue = deque([(seed, 1.0, 0)])  # (node, trust_value, depth)
                
                while queue:
                    current_node, current_trust, depth = queue.popleft()
                    
                    if current_node in visited:
                        continue
                    
                    visited.add(current_node)
                    
                    # Update trust score (take maximum)
                    trust_scores[current_node] = max(trust_scores[current_node], current_trust)
                    
                    # Propagate to neighbors with decay
                    if depth < 10:  # Limit propagation depth
                        for neighbor in adjacency.get(current_node, []):
                            if neighbor not in visited:
                                # Calculate trust propagation
                                edge_weight = weights.get(current_node, {}).get(neighbor, 1.0)
                                propagated_trust = current_trust * config.decay_factor * edge_weight
                                
                                if propagated_trust > config.tolerance:
                                    queue.append((neighbor, propagated_trust, depth + 1))
            
            execution_time = time.time() - start_time
            
            result = PropagationResult(
                node_scores=trust_scores,
                iterations=1,  # BFS is single-pass
                converged=True,
                execution_time=execution_time,
                algorithm_used="trust_propagation",
                seed_nodes=config.seed_nodes or []
            )
            
            return await self._format_propagation_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in trust propagation: {e}")
            return {}
    
    async def influence_propagation(self, config: PropagationConfig) -> Dict[str, float]:
        """Propagate influence using Independent Cascade Model"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            weights = graph_data.get("weights", {})
            
            # Initialize influence scores
            influence_scores = {node: 0.0 for node in nodes}
            
            # Run multiple simulations for Monte Carlo estimation
            num_simulations = 100
            
            for simulation in range(num_simulations):
                # Initialize active set with seed nodes
                active = set(config.seed_nodes or [])
                newly_active = set(config.seed_nodes or [])
                
                # Cascade process
                while newly_active:
                    next_active = set()
                    
                    for active_node in newly_active:
                        for neighbor in adjacency.get(active_node, []):
                            if neighbor not in active:
                                # Calculate activation probability
                                edge_weight = weights.get(active_node, {}).get(neighbor, 0.5)
                                activation_prob = min(edge_weight, 1.0)
                                
                                # Random activation
                                if random.random() < activation_prob:
                                    next_active.add(neighbor)
                                    active.add(neighbor)
                    
                    newly_active = next_active
                
                # Update influence scores
                for node in active:
                    influence_scores[node] += 1.0 / num_simulations
            
            execution_time = time.time() - start_time
            
            result = PropagationResult(
                node_scores=influence_scores,
                iterations=num_simulations,
                converged=True,
                execution_time=execution_time,
                algorithm_used="influence_propagation",
                seed_nodes=config.seed_nodes or []
            )
            
            return await self._format_propagation_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in influence propagation: {e}")
            return {}
    
    async def personalized_pagerank(self, config: PropagationConfig) -> Dict[str, float]:
        """Calculate Personalized PageRank from seed nodes"""
        try:
            import time
            start_time = time.time()
            
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
            
            # Create personalization vector
            personalization = {node: 0.0 for node in nodes}
            if config.seed_nodes:
                seed_weight = 1.0 / len(config.seed_nodes)
                for seed in config.seed_nodes:
                    if seed in personalization:
                        personalization[seed] = seed_weight
            else:
                # Uniform personalization
                for node in nodes:
                    personalization[node] = 1.0 / n
            
            # Calculate out-degrees
            out_degrees = {}
            for node in nodes:
                out_degrees[node] = len(adjacency.get(node, []))
            
            # Power iteration
            converged = False
            iteration = 0
            
            while iteration < config.max_iterations and not converged:
                new_pagerank = {}
                
                for node in nodes:
                    # Personalization component
                    new_score = (1 - config.alpha) * personalization[node]
                    
                    # Link contribution
                    for source in adjacency:
                        if node in adjacency[source] and out_degrees[source] > 0:
                            new_score += config.alpha * pagerank[source] / out_degrees[source]
                    
                    new_pagerank[node] = new_score
                
                # Check convergence
                diff = sum(abs(new_pagerank[node] - pagerank[node]) for node in nodes)
                if diff < config.tolerance:
                    converged = True
                
                pagerank = new_pagerank
                iteration += 1
            
            execution_time = time.time() - start_time
            
            result = PropagationResult(
                node_scores=pagerank,
                iterations=iteration,
                converged=converged,
                execution_time=execution_time,
                algorithm_used="personalized_pagerank",
                seed_nodes=config.seed_nodes or []
            )
            
            return await self._format_propagation_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in personalized PageRank: {e}")
            return {}
    
    async def random_walk_propagation(self, config: PropagationConfig) -> Dict[str, float]:
        """Propagate using random walk with restart"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            
            # Initialize visit counts
            visit_counts = {node: 0.0 for node in nodes}
            
            # Perform random walks from each seed node
            num_walks = 1000
            walk_length = 20
            
            for seed in config.seed_nodes or []:
                if seed not in nodes:
                    continue
                
                for walk in range(num_walks):
                    current_node = seed
                    
                    for step in range(walk_length):
                        visit_counts[current_node] += 1.0
                        
                        # Random restart
                        if random.random() < config.beta:
                            current_node = seed
                            continue
                        
                        # Move to random neighbor
                        neighbors = adjacency.get(current_node, [])
                        if neighbors:
                            current_node = random.choice(neighbors)
                        else:
                            # Dead end - restart
                            current_node = seed
            
            # Normalize visit counts
            total_visits = sum(visit_counts.values())
            if total_visits > 0:
                for node in visit_counts:
                    visit_counts[node] /= total_visits
            
            execution_time = time.time() - start_time
            
            result = PropagationResult(
                node_scores=visit_counts,
                iterations=num_walks,
                converged=True,
                execution_time=execution_time,
                algorithm_used="random_walk_propagation",
                seed_nodes=config.seed_nodes or []
            )
            
            return await self._format_propagation_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in random walk propagation: {e}")
            return {}
    
    async def label_spreading(self, config: PropagationConfig) -> Dict[str, float]:
        """Spread labels from seed nodes"""
        try:
            import time
            start_time = time.time()
            
            graph_data = await self._build_graph_representation(config)
            if not graph_data:
                return {}
            
            nodes = graph_data["nodes"]
            adjacency = graph_data["adjacency"]
            weights = graph_data.get("weights", {})
            
            # Initialize label scores
            labels = {node: 0.0 for node in nodes}
            
            # Set seed labels
            if config.seed_nodes:
                for seed in config.seed_nodes:
                    if seed in labels:
                        labels[seed] = 1.0
            
            # Build normalized adjacency matrix
            transition_matrix = await self._build_transition_matrix(adjacency, weights, True)
            
            # Label spreading iteration
            converged = False
            iteration = 0
            
            while iteration < config.max_iterations and not converged:
                new_labels = {}
                
                for node in nodes:
                    if node in config.seed_nodes:
                        # Keep seed labels fixed
                        new_labels[node] = 1.0
                    else:
                        # Spread from neighbors
                        spread_score = 0.0
                        for source in transition_matrix:
                            if node in transition_matrix[source]:
                                spread_score += labels[source] * transition_matrix[source][node]
                        
                        new_labels[node] = config.alpha * spread_score
                
                # Check convergence
                diff = sum(abs(new_labels[node] - labels[node]) for node in nodes)
                if diff < config.tolerance:
                    converged = True
                
                labels = new_labels
                iteration += 1
            
            execution_time = time.time() - start_time
            
            result = PropagationResult(
                node_scores=labels,
                iterations=iteration,
                converged=converged,
                execution_time=execution_time,
                algorithm_used="label_spreading",
                seed_nodes=config.seed_nodes or []
            )
            
            return await self._format_propagation_result(result)
            
        except Exception as e:
            self.logger.error(f"Error in label spreading: {e}")
            return {}
    
    async def _build_graph_representation(self, config: PropagationConfig) -> Optional[Dict[str, Any]]:
        """Build graph representation for propagation"""
        try:
            if not self.graph_engine:
                return None
            
            nodes = set()
            adjacency = defaultdict(list)
            weights = defaultdict(dict)
            
            # Get entities (nodes)
            entities = await self.graph_engine.find_entities({}, limit=10000)
            
            for entity in entities:
                node_id = entity.get("_id", entity.get("id", "")).split("/")[-1]
                nodes.add(node_id)
            
            # Get relationships (edges)
            relationships = await self.graph_engine.find_relationships(limit=50000)
            
            for rel in relationships:
                source_id = rel.get("_from", rel.get("source_id", "")).split("/")[-1]
                target_id = rel.get("_to", rel.get("target_id", "")).split("/")[-1]
                
                if source_id in nodes and target_id in nodes:
                    # Handle direction
                    if config.direction in ["outbound", "both"]:
                        adjacency[source_id].append(target_id)
                    
                    if config.direction in ["inbound", "both"]:
                        adjacency[target_id].append(source_id)
                    
                    # Extract weight
                    weight = 1.0
                    if config.weight_attribute and config.weight_attribute in rel:
                        weight = float(rel[config.weight_attribute])
                    
                    weights[source_id][target_id] = weight
                    if config.direction == "both":
                        weights[target_id][source_id] = weight
            
            return {
                "nodes": list(nodes),
                "adjacency": dict(adjacency),
                "weights": dict(weights)
            }
            
        except Exception as e:
            self.logger.error(f"Error building graph representation: {e}")
            return None
    
    async def _build_transition_matrix(self, adjacency: Dict[str, List[str]], 
                                     weights: Dict[str, Dict[str, float]], normalize: bool) -> Dict[str, Dict[str, float]]:
        """Build transition matrix for propagation"""
        try:
            transition_matrix = defaultdict(dict)
            
            for source, neighbors in adjacency.items():
                if not neighbors:
                    continue
                
                # Calculate normalization factor
                if normalize:
                    total_weight = sum(weights.get(source, {}).get(neighbor, 1.0) for neighbor in neighbors)
                else:
                    total_weight = 1.0
                
                # Build transition probabilities
                for neighbor in neighbors:
                    edge_weight = weights.get(source, {}).get(neighbor, 1.0)
                    transition_matrix[source][neighbor] = edge_weight / total_weight if total_weight > 0 else 0.0
            
            return dict(transition_matrix)
            
        except Exception as e:
            self.logger.error(f"Error building transition matrix: {e}")
            return {}
    
    async def _format_propagation_result(self, result: PropagationResult) -> Dict[str, float]:
        """Format propagation result for API response"""
        try:
            # Sort by score and return top results
            sorted_scores = dict(sorted(result.node_scores.items(), key=lambda x: x[1], reverse=True))
            return sorted_scores
            
        except Exception as e:
            self.logger.error(f"Error formatting propagation result: {e}")
            return {}
    
    async def find_influential_nodes(self, k: int = 10, propagation_type: str = "influence") -> List[Tuple[str, float]]:
        """Find top-k influential nodes using influence maximization"""
        try:
            # Greedy algorithm for influence maximization
            all_nodes = await self._get_all_nodes()
            
            if not all_nodes:
                return []
            
            selected_seeds = []
            
            for i in range(min(k, len(all_nodes))):
                best_node = None
                best_influence = 0.0
                
                # Evaluate marginal influence for each candidate
                for candidate in all_nodes:
                    if candidate in selected_seeds:
                        continue
                    
                    # Calculate influence with current seeds + candidate
                    test_seeds = selected_seeds + [candidate]
                    config = PropagationConfig(
                        propagation_type=PropagationType(propagation_type),
                        seed_nodes=test_seeds
                    )
                    
                    scores = await self.propagate(test_seeds, propagation_type)
                    total_influence = sum(scores.values())
                    
                    if total_influence > best_influence:
                        best_influence = total_influence
                        best_node = candidate
                
                if best_node:
                    selected_seeds.append(best_node)
            
            # Calculate final influences
            result = []
            for seed in selected_seeds:
                config = PropagationConfig(
                    propagation_type=PropagationType(propagation_type),
                    seed_nodes=[seed]
                )
                scores = await self.propagate([seed], propagation_type)
                influence = sum(scores.values())
                result.append((seed, influence))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error finding influential nodes: {e}")
            return []
    
    async def _get_all_nodes(self) -> List[str]:
        """Get all nodes in the graph"""
        try:
            if not self.graph_engine:
                return []
            
            entities = await self.graph_engine.find_entities({}, limit=1000)
            nodes = []
            
            for entity in entities:
                node_id = entity.get("_id", entity.get("id", "")).split("/")[-1]
                nodes.append(node_id)
            
            return nodes
            
        except Exception as e:
            self.logger.error(f"Error getting all nodes: {e}")
            return []
    
    async def calculate_similarity_matrix(self, nodes: List[str]) -> Dict[str, Dict[str, float]]:
        """Calculate pairwise similarity matrix between nodes"""
        try:
            similarity_matrix = defaultdict(dict)
            
            for i, node1 in enumerate(nodes):
                for j, node2 in enumerate(nodes[i:], i):
                    if i == j:
                        similarity_matrix[node1][node2] = 1.0
                    else:
                        # Calculate similarity using propagation
                        config = PropagationConfig(seed_nodes=[node1])
                        scores = await self.similarity_propagation(config)
                        similarity = scores.get(node2, 0.0)
                        
                        similarity_matrix[node1][node2] = similarity
                        similarity_matrix[node2][node1] = similarity
            
            return dict(similarity_matrix)
            
        except Exception as e:
            self.logger.error(f"Error calculating similarity matrix: {e}")
            return {}
    
    async def shutdown(self):
        """Cleanup resources"""
        pass