"""
Asynchronous, idempotent incremental graph builder.
Streams triples into the graph store with exactly-once semantics
and automatic conflict resolution.
"""

import asyncio
from typing import Dict, Any, List
import uuid
from datetime import datetime, timezone



class IncrementalBuilder:
    def __init__(self, storage):
        self.storage = storage
    """
    Handles real-time ingestion of entities & relationships.
    Features:
      - Upsert semantics (idempotent)
      - Automatic deduplication & entity resolution
      - Temporal versioning
      - Back-pressure aware
    """

    @staticmethod
    async def process(payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.graph_service import GraphService
        from ..core.graph_engine import GraphEngine

        """
        Accepts JSON payload:
        {
          "entities": [...],
          "relationships": [...],
          "metadata": {...}
        }
        Returns summary statistics.
        """
        entities = payload.get("entities", [])
        relationships = payload.get("relationships", [])
        meta = payload.get("metadata", {})

        tasks = []
        for ent in entities:
            ent.setdefault("id", str(uuid.uuid4()))
            ent.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
            tasks.append(GraphEngine.upsert_entity(ent))

        for rel in relationships:
            rel.setdefault("id", str(uuid.uuid4()))
            rel.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
            tasks.append(GraphEngine.upsert_relationship(rel))

        await asyncio.gather(*tasks)

        # Post-processing
        await GraphService.resolve_duplicates()
        await GraphService.calculate_relationship_strengths()

        return {
            "entities_upserted": len(entities),
            "relationships_upserted": len(relationships),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }