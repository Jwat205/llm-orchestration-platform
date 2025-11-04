"""
Async ArangoDB adapter using python-arango.
Provides multi-model support (graph, document, KV).
"""

from typing import Any, Dict, List, Optional
import aioarango
from aioarango import ArangoClient


class ArangoAdapter:
    """
    Production-grade ArangoDB adapter with
    connection pooling and automatic collection creation.
    """

    def __init__(
        self,
        hosts: str,
        user: str,
        password: str,
        db_name: str,
        max_connections: int = 20,
    ) -> None:
        self.client = ArangoClient(hosts=hosts, max_connections=max_connections)
        self.db_name = db_name
        self.user = user
        self.password = password
        self.db: Optional[aioarango.database.StandardDatabase] = None

    async def connect(self) -> None:
        sys_db = await self.client.db("_system", username=self.user, password=self.password)
        if not await sys_db.has_database(self.db_name):
            await sys_db.create_database(self.db_name)

        self.db = await self.client.db(self.db_name, username=self.user, password=self.password)

        # Ensure collections & graph exist
        if self.db and not await self.db.has_graph("knowledge"):
            await self.db.create_graph("knowledge")

        if self.db and not await self.db.has_collection("entities"):
            await self.db.create_collection("entities")

        if self.db and not await self.db.has_collection("relationships"):
            await self.db.create_edge_collection("relationships")

    async def close(self) -> None:
        await self.client.close()

    async def upsert_entity(self, entity: Dict[str, Any]) -> str:
        assert self.db is not None
        col = self.db.collection("entities")
        meta = await col.insert(entity, overwrite=True, return_new=True)
        return str(meta["_key"])

    async def upsert_relationship(self, rel: Dict[str, Any]) -> str:
        assert self.db is not None
        col = self.db.collection("relationships")
        rel["_from"] = f"entities/{rel['source']}"
        rel["_to"] = f"entities/{rel['target']}"
        meta = await col.insert(rel, overwrite=True, return_new=True)
        return str(meta["_key"])

    async def traverse(
        self,
        start_id: str,
        max_depth: int = 3,
        relationship_types: Optional[List[str]] = None,
        direction: str = "any",
    ) -> List[Dict[str, Any]]:
        assert self.db is not None
        filter_clause = (
            f"AND e.type IN {relationship_types}" if relationship_types else ""
        )
        dir_clause = {"out": "OUTBOUND", "in": "INBOUND", "any": "ANY"}[direction]

        aql = f"""
        FOR v, e, p IN 1..{max_depth} {dir_clause} @start
          GRAPH 'knowledge'
          {filter_clause}
          RETURN {{nodes: p.vertices, relationships: p.edges}}
        """
        cursor = await self.db.aql.execute(aql, bind_vars={"start": f"entities/{start_id}"})
        return [doc async for doc in cursor]

    async def to_networkx(
        self, weight_attr: Optional[str] = None
    ) -> "networkx.Graph":  # type: ignore[name-defined]
        import networkx as nx

        assert self.db is not None
        nodes = [doc async for doc in self.db.collection("entities").all()]
        G = nx.MultiDiGraph()
        for n in nodes:
            G.add_node(n["_key"], **{k: v for k, v in n.items() if k not in ("_key", "_id")})

        edges = [doc async for doc in self.db.collection("relationships").all()]
        for e in edges:
            G.add_edge(
                e["_from"].split("/", 1)[1],
                e["_to"].split("/", 1)[1],
                key=e.get("type", "edge"),
                **{k: v for k, v in e.items() if k not in ("_from", "_to", "_key", "_id")},
                weight=e.get(weight_attr, 1.0),
            )
        return G