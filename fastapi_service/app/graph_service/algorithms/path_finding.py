"""
Fast path-finding algorithms on top of graph adapters.
Supports weighted edges & multi-criteria constraints.
"""

from typing import List, Dict, Any, Optional
import heapq
import networkx as nx


class PathFinding:
    def __init__(self, storage):
        self.storage = storage

    """
    High-performance wrappers for:
      - Shortest path (Dijkstra / A*)
      - K-shortest paths
      - All-pairs shortest paths (Floyd-Warshall)
    """

    @staticmethod
    async def shortest_path(
        source: str,
        target: str,
        weight_attr: str = "weight",
        max_hops: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        from ..core.graph_engine import GraphEngine

        """
        Returns list of nodes in the shortest path.
        """
        adapter = GraphEngine._adapter
        nxg = await adapter.to_networkx(weight_attr=weight_attr)
        try:
            path = nx.shortest_path(nxg, source, target, weight=weight_attr)
            return [{"id": n} for n in path]
        except nx.NetworkXNoPath:
            return []

    @staticmethod
    async def k_shortest_paths(
        source: str,
        target: str,
        k: int = 3,
        weight_attr: str = "weight",
    ) -> List[List[Dict[str, Any]]]:
        from ..core.graph_engine import GraphEngine

        nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
        paths_gen = nx.shortest_simple_paths(nxg, source, target, weight=weight_attr)
        paths = []
        for path in heapq.nsmallest(k, paths_gen, key=lambda p: nx.path_weight(nxg, p, weight=weight_attr)):
            paths.append([{"id": n} for n in path])
        return paths