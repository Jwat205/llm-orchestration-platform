"""
Graph-based similarity propagation using label-spreading & node2vec replacement via SentenceTransformer.
"""
from typing import Dict, List
import networkx as nx
import random

from sentence_transformers import SentenceTransformer
from app.graph_service.core.graph_engine import GraphEngine


class SimilarityPropagation:
    def __init__(self, storage):
        self.storage = storage
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    @staticmethod
    async def _generate_random_walks(graph: nx.Graph, walk_length: int, num_walks: int) -> List[str]:
        """
        Perform random walks and return each walk as a string (sentence).
        """
        def walk_from_node(start_node: str) -> List[str]:
            walk = [start_node]
            for _ in range(walk_length - 1):
                cur = walk[-1]
                neighbors = list(graph.neighbors(cur))
                if neighbors:
                    walk.append(random.choice(neighbors))
                else:
                    break
            return walk

        walks = []
        nodes = list(graph.nodes())
        for _ in range(num_walks):
            random.shuffle(nodes)
            for node in nodes:
                walk = walk_from_node(str(node))
                sentence = " ".join(walk)
                walks.append(sentence)
        return walks

    async def node2vec_embeddings(
        self,
        dimensions: int = 64,
        walk_length: int = 30,
        num_walks: int = 200
    ) -> Dict[str, List[float]]:
        """
        Learn node embeddings by encoding random walk "sentences" using a SentenceTransformer.
        Returns: {node_id: embedding_vector}
        """
        nxg = await GraphEngine._adapter.to_networkx()
        walk_sentences = await self._generate_random_walks(nxg, walk_length, num_walks)

        # SentenceTransformer will embed each walk (sentence)
        walk_embeddings = self.model.encode(walk_sentences)

        # Average embeddings of walks that contain each node
        node_vectors: Dict[str, List[List[float]]] = {str(node): [] for node in nxg.nodes()}
        for walk, emb in zip(walk_sentences, walk_embeddings):
            for node in walk.split():
                node_vectors[node].append(emb)

        # Average the vectors per node
        averaged_node_embeddings: Dict[str, List[float]] = {}
        for node, vecs in node_vectors.items():
            if vecs:
                avg_vec = [float(sum(x) / len(x)) for x in zip(*vecs)]
                averaged_node_embeddings[node] = avg_vec
            else:
                averaged_node_embeddings[node] = [0.0] * dimensions  # fallback

        return averaged_node_embeddings
