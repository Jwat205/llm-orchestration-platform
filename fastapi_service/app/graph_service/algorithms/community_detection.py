"""
Louvain & Leiden community detection with async bridges.
"""

from typing import Dict, List
import networkx as nx
from community import community_louvain


class CommunityDetection:
    def __init__(self, storage):
        self.storage = storage
    """
    Detect densely connected subgraphs (communities).
    """

    @staticmethod
    async def louvain(
        resolution: float = 1.0, weight_attr: str = "weight"
    ) -> Dict[str, int]:
        from ..core.graph_engine import GraphEngine

        """
        Returns dict {node_id: community_id}.
        """
        nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
        partition = community_louvain.best_partition(nxg, resolution=resolution, weight=weight_attr)
        return partition

    @staticmethod
    async def leiden(
        resolution: float = 1.0, weight_attr: str = "weight"
    ) -> Dict[str, int]:
        from ..core.graph_engine import GraphEngine

        """
        Uses `leidenalg` if installed; falls back to Louvain otherwise.
        """
        try:
            import leidenalg
            import igraph as ig

            nxg = await GraphEngine._adapter.to_networkx(weight_attr=weight_attr)
            g_ig = ig.Graph.from_networkx(nxg)
            partition = leidenalg.find_partition(
                g_ig,
                leidenalg.ModularityVertexPartition,
                weights=g_ig.es[weight_attr],
                resolution_parameter=resolution,
            )
            return {g_ig.vs[i]["_nx_name"]: cid for i, cid in enumerate(partition.membership)}
        except ImportError:
            return await CommunityDetection.louvain(resolution=resolution, weight_attr=weight_attr)