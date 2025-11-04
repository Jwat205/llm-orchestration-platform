"""
Async Neo4j adapter implementing transactional CRUD
and traversal operations with connection pooling.
"""

from typing import Any, Dict, List, Optional, Union
import neo4j
from neo4j import AsyncGraphDatabase, AsyncSession
import asyncio
from tenacity import retry, wait_fixed, stop_after_attempt
from dataclasses import asdict, is_dataclass
import json
from uuid import uuid4


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Turn dataclass/Pydantic/dict into a plain dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return obj.__dict__

Primitive = Union[str, bool, int, float]
JSONable = Union[Primitive, List[Primitive]]

def _clean_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Remove nested maps; JSON‑encode any lists/maps that aren't pure primitives."""
    cleaned: Dict[str, Any] = {}
    for k, v in props.items():
        if v is None:
            continue
        # primitives pass through
        if isinstance(v, (str, bool, int, float)):
            cleaned[k] = v
        # lists of primitives pass through; otherwise JSON‑encode
        elif isinstance(v, list):
            if all(isinstance(item, (str, bool, int, float)) for item in v):
                cleaned[k] = v
            else:
                cleaned[k] = json.dumps(v)
        # everything else (dict, object) → JSON‑encode
        else:
            cleaned[k] = json.dumps(v)
    return cleaned

class Neo4jAdapter:
    """
    Thread-safe Neo4j driver wrapper with automatic retries
    and connection health checks.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        max_pool_size: int = 50,
        max_retry_attempts: int = 3,
    ) -> None:
        self.driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=max_pool_size,
            connection_timeout=30,
        )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def connect(self):
        await self.driver.verify_connectivity()

    async def create_entity(self, entity: Any) -> str:
        data = _to_dict(entity)
        data["id"] = data.get("id") or f"entity_{uuid4().hex}"
        return await self._merge_entity(data)
    
    @staticmethod
    async def _merge_entity_tx(tx: AsyncSession, data: Dict[str, Any]):
        # clean out nested maps before passing to Cypher
        props = _clean_props(data)
        query = """
        MERGE (e:Entity {id: $id})
        SET e += $props, e.updated_at = datetime()
        RETURN $id AS id
        """
        result = await tx.run(query, id=data["id"], props=props)
        return await result.single()

    async def _merge_entity(self, data: Dict[str, Any]) -> str:
        async with self.driver.session() as session:
            rec = await session.execute_write(self._merge_entity_tx, data)
            return rec["id"]

    async def create_relationship(self, rel) -> str:
        raw = _to_dict(rel)
        raw["id"] = raw.get("id") or f"rel_{uuid4().hex}"
        raw["source_id"] = raw.get("source_id") or raw.get("source")
        raw["target_id"] = raw.get("target_id") or raw.get("target")
        props = _clean_props(raw)
        return await self._merge_rel({
            "id": raw["id"],
            "source_id": raw["source_id"],
            "target_id": raw["target_id"],
            "props": props
        })

    @staticmethod
    async def _merge_rel_tx(tx, data: Dict[str, Any]):
        query = """
        MATCH (src:Entity {id: $source_id}), (tgt:Entity {id: $target_id})
        MERGE (src)-[r:RELATIONSHIP {id: $id}]->(tgt)
        SET r += $props, r.updated_at = datetime()
        RETURN r.id AS id
        """
        result = await tx.run(query, **data)
        return await result.single()

    async def _merge_rel(self, data: Dict[str, Any]) -> str:
        async with self.driver.session() as session:
            rec = await session.execute_write(self._merge_rel_tx, data)
            return rec["id"]

    async def traverse(
        self,
        start_id: str,
        max_depth: int = 3,
        relationship_types: Optional[List[str]] = None,
        direction: str = "any",
    ) -> List[Dict[str, Any]]:
        async with self.driver.session() as session:
            rel_filter = (
                f"WHERE type(r) IN {relationship_types}"
                if relationship_types
                else ""
            )
            dir_clause = {
                "out": "-[*1..{}]->",
                "in": "<-[*1..{}]-",
                "any": "-[*1..{}]-",
            }[direction].format(max_depth)

            query = f"""
            MATCH path = (start {{id: $start_id}}){dir_clause}(connected)
            {rel_filter}
            UNWIND nodes(path) as n UNWIND relationships(path) as r
            RETURN collect(DISTINCT properties(n)) as nodes,
                   collect(DISTINCT properties(r)) as rels
            """
            result = await session.run(query, start_id=start_id)
            record = await result.single(raise_on_error=True)
            return [{"nodes": record["nodes"], "relationships": record["rels"]}]

    async def to_networkx(
        self, weight_attr: Optional[str] = None
    ) -> "networkx.Graph":  # type: ignore[name-defined]
        import networkx as nx

        async with self.driver.session() as session:
            query = """
            MATCH (n)
            RETURN properties(n) as props, id(n) as nid
            """
            nodes = await session.run(query)
            G = nx.MultiDiGraph()
            async for record in nodes:
                G.add_node(record["nid"], **record["props"])

            rel_query = f"""
            MATCH (a)-[r]->(b)
            RETURN id(a) as src, id(b) as dst, type(r) as type, properties(r) as props
            {f', r.{weight_attr} as weight' if weight_attr else ''}
            """
            rels = await session.run(rel_query)
            async for rec in rels:
                G.add_edge(
                    rec["src"],
                    rec["dst"],
                    key=rec["type"],
                    **rec["props"],
                    weight=rec.get("weight", 1.0),
                )
        return G

    async def close(self):
        """Close the driver connection."""
        await self.driver.close()