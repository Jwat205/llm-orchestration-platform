"""
Parallel centrality computation using NetworkX & async off-loading.
"""

from typing import Dict
import networkx as nx


class CentralityMeasures:
    def __init__(self, storage):
        self.storage = storage

    """
    Async wrappers for:
      - Betweenness
      - Closeness
      - Eigenvector
      - PageRank
    """

    @staticmethod
    async def betweenness(
        normalized: bool = True, weight_attr: str = "weight"
    ) -> Dict[str, float]:
        from app.core.graph_engine import GraphEngine
        nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
        centrality = nx.betweenness_centrality(nxg, normalized=normalized, weight=weight_attr)
        return centrality

    @staticmethod
    async def closeness(weight_attr: str = "weight") -> Dict[str, float]:
        from app.core.graph_engine import GraphEngine
        nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
        return nx.closeness_centrality(nxg, distance=weight_attr)

    @staticmethod
    async def eigenvector(weight_attr: str = "weight", max_iter: int = 100) -> Dict[str, float]:
        from app.core.graph_engine import GraphEngine
        nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
        return nx.eigenvector_centrality(nxg, max_iter=max_iter, weight=weight_attr)

    @staticmethod
    async def pagerank(weight_attr: str = "weight", alpha: float = 0.85) -> Dict[str, float]:
        from app.core.graph_engine import GraphEngine
        nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
        return nx.pagerank(nxg, alpha=alpha, weight=weight_attr)