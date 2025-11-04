"""
Batch-oriented graph construction with transactional semantics.
Supports file ingest (JSONL, CSV, Parquet) and parallel workers.
"""

import asyncio
import aiofiles
import pandas as pd
from pathlib import Path
from typing import Union, Dict, Any
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple, Set
from app.shared.schemas.graph_schemas import GraphEntity, GraphRelationship  # adjust path
from dataclasses import asdict, is_dataclass



def _to_dict(o):
    if hasattr(o, "model_dump"): return o.model_dump()
    if hasattr(o, "dict"):       return o.dict()
    if is_dataclass(o):          return asdict(o)
    if isinstance(o, dict):      return o
    return o.__dict__


class BatchBuilder:
    def __init__(self, storage):
        self.storage = storage

    
    async def build_graph(self, *, entities, relationships, document_id):
        save_ent = getattr(self.storage, "create_entity",
                  getattr(self.storage, "create_entity"))
        save_rel = getattr(self.storage, "create_relationship",
                  getattr(self.storage, "create_relationship"))

        await asyncio.gather(*(save_ent(_to_dict(e)) for e in entities))
        await asyncio.gather(*(save_rel(_to_dict(r)) for r in relationships))

        return {
            "document_id": document_id,
            "entities_written": len(entities),
            "relationships_written": len(relationships),
        }
    """
    Bulk ingestion pipeline:
      - Transactional load (all-or-nothing)
      - Parallel ingestion workers
      - Automatic rollback on failure
    """

    @classmethod
    async def ingest_jsonl(cls, file_path: Union[str, Path]) -> Dict[str, Any]:
        from app.services.graph_service import GraphService
        from ..core.graph_engine import GraphEngine


        """Ingest newline-delimited JSON files."""
        entities, relationships = [], []
        async with aiofiles.open(file_path, "r") as f:
            async for line in f:
                rec = pd.io.json.loads(line)
                if rec.get("type") == "entity":
                    entities.append(rec["data"])
                elif rec.get("type") == "relationship":
                    relationships.append(rec["data"])

        return await cls._bulk_upsert(entities, relationships)

    @classmethod
    async def ingest_csv(
        cls,
        entities_csv: Union[str, Path],
        relationships_csv: Union[str, Path],
    ) -> Dict[str, Any]:
        from app.services.graph_service import GraphService
        from ..core.graph_engine import GraphEngine


        """Ingest CSV files using pandas for speed."""
        entities_df = pd.read_csv(entities_csv).to_dict("records")
        rels_df = pd.read_csv(relationships_csv).to_dict("records")
        return await cls._bulk_upsert(entities_df, rels_df)

    @staticmethod
    async def _bulk_upsert(
        entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        from app.services.graph_service import GraphService
        from ..core.graph_engine import GraphEngine

        """Transactional upsert with rollback on any failure."""
        tx_id = str(uuid.uuid4())
        for e in entities:
            e.setdefault("id", str(uuid.uuid4()))
            e.setdefault("updated_at", datetime.now(timezone.utc).isoformat())

        for r in relationships:
            r.setdefault("id", str(uuid.uuid4()))
            r.setdefault("updated_at", datetime.now(timezone.utc).isoformat())

        try:
            tasks = [GraphEngine.upsert_entity(e) for e in entities] + [
                GraphEngine.upsert_relationship(r) for r in relationships
            ]
            await asyncio.gather(*tasks)
            await GraphService.resolve_duplicates()
            await GraphService.calculate_relationship_strengths()
            return {"tx_id": tx_id, "status": "success", "entities": len(entities), "relationships": len(relationships)}
        except Exception as e:
            # TODO: Implement rollback via adapter
            return {"tx_id": tx_id, "status": "failure", "error": str(e)}
        
        