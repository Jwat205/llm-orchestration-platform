"""
Ontology Manager for Knowledge Graph
Manages ontologies, schemas, entity types, and relationship definitions
"""
import logging
from typing import Dict, List, Set, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import yaml
from pathlib import Path
from datetime import datetime
import networkx as nx
import asyncio
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Standard entity types"""
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    EVENT = "Event"
    CONCEPT = "Concept"
    DOCUMENT = "Document"
    PRODUCT = "Product"
    TIME = "Time"
    QUANTITY = "Quantity"
    MISCELLANEOUS = "Miscellaneous"


class RelationType(Enum):
    """Standard relationship types"""
    # Hierarchical
    IS_A = "isA"
    PART_OF = "partOf"
    HAS_PART = "hasPart"
    SUBCLASS_OF = "subClassOf"
    INSTANCE_OF = "instanceOf"
    
    # Spatial
    LOCATED_IN = "locatedIn"
    CONTAINS = "contains"
    NEAR = "near"
    ADJACENT_TO = "adjacentTo"
    
    # Temporal
    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    OVERLAPS = "overlaps"
    
    # Causal
    CAUSES = "causes"
    ENABLES = "enables"
    PREVENTS = "prevents"
    INFLUENCES = "influences"
    
    # Social
    KNOWS = "knows"
    WORKS_FOR = "worksFor"
    MEMBER_OF = "memberOf"
    RELATED_TO = "relatedTo"
    
    # Semantic
    SIMILAR_TO = "similarTo"
    DIFFERENT_FROM = "differentFrom"
    EQUIVALENT_TO = "equivalentTo"
    SYNONYMOUS_WITH = "synonymousWith"


@dataclass
class EntitySchema:
    """Schema definition for entity types"""
    name: str
    type: EntityType
    description: str
    properties: Dict[str, str] = field(default_factory=dict)  # property_name: data_type
    required_properties: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    parent_types: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class RelationshipSchema:
    """Schema definition for relationship types"""
    name: str
    type: RelationType
    description: str
    domain: List[str] = field(default_factory=list)  # Valid subject types
    range: List[str] = field(default_factory=list)   # Valid object types
    properties: Dict[str, str] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    inverse: Optional[str] = None
    symmetric: bool = False
    transitive: bool = False
    functional: bool = False

   

class OntologyManager:
    """
    Central manager for all ontology artifacts:
      – Entity schemas (sub-classing, properties, constraints)
      – Relationship schemas (domain/range, cardinality, inverse)
      – Runtime validation & inference helpers
      – Import / Export (YAML, JSON-LD, TTL, …)
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, strict_mode: bool = True):
        self.strict: bool = strict_mode
        self._entity_schemas: Dict[str, EntitySchema] = {}
        self._relation_schemas: Dict[str, RelationshipSchema] = {}
        self._inheritance_graph: nx.DiGraph = nx.DiGraph()  # for "is-a"/"sub-class-of"
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Entity Schemas
    # ------------------------------------------------------------------
    def add_entity_schema(self, schema: EntitySchema) -> None:
        """
        Register a new entity schema.
        Automatically builds inheritance edges for parent_types.
        """
        if schema.name in self._entity_schemas:
            if self.strict:
                raise ValueError(f"Entity schema '{schema.name}' already exists.")
            logger.warning("Overwriting entity schema '%s'", schema.name)

        self._entity_schemas[schema.name] = schema
        # Build inheritance DAG
        for parent in schema.parent_types:
            self._inheritance_graph.add_edge(schema.name, parent)

    def get_entity_schema(self, name: str) -> Optional[EntitySchema]:
        return self._entity_schemas.get(name)

    def list_entity_schemas(self) -> List[str]:
        return list(self._entity_schemas.keys())

    def remove_entity_schema(self, name: str) -> bool:
        if name not in self._entity_schemas:
            return False
        del self._entity_schemas[name]
        self._inheritance_graph.remove_node(name)
        return True

    # ------------------------------------------------------------------
    # Relationship Schemas
    # ------------------------------------------------------------------
    def add_relationship_schema(self, schema: RelationshipSchema) -> None:
        if schema.name in self._relation_schemas:
            if self.strict:
                raise ValueError(f"Relationship schema '{schema.name}' already exists.")
            logger.warning("Overwriting relationship schema '%s'", schema.name)

        self._relation_schemas[schema.name] = schema

    def get_relationship_schema(self, name: str) -> Optional[RelationshipSchema]:
        return self._relation_schemas.get(name)

    def list_relationship_schemas(self) -> List[str]:
        return list(self._relation_schemas.keys())

    def remove_relationship_schema(self, name: str) -> bool:
        return self._relation_schemas.pop(name, None) is not None

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def validate_entity(
        self,
        entity_type: str,
        properties: Dict[str, Any],
        raise_on_error: bool = True,
    ) -> bool:
        """
        Check if an instance of 'entity_type' satisfies its schema
        (required fields, data-types, constraints).
        """
        schema = self._entity_schemas.get(entity_type)
        if not schema:
            if raise_on_error:
                raise ValueError(f"Unknown entity type '{entity_type}'.")
            return False

        missing = set(schema.required_properties) - set(properties.keys())
        if missing:
            if raise_on_error:
                raise ValueError(f"Missing required properties: {missing}")
            return False

        # TODO: deep type & constraint checks
        return True

    def validate_relationship(
        self,
        rel_name: str,
        subject_type: str,
        object_type: str,
        raise_on_error: bool = True,
    ) -> bool:
        schema = self._relation_schemas.get(rel_name)
        if not schema:
            if raise_on_error:
                raise ValueError(f"Unknown relationship '{rel_name}'.")
            return False

        subject_ok = self._type_in_domain(subject_type, schema.domain)
        object_ok = self._type_in_range(object_type, schema.range)

        if not (subject_ok and object_ok):
            if raise_on_error:
                raise ValueError(
                    f"Invalid domain/range for '{rel_name}': "
                    f"subject={subject_type}, object={object_type}"
                )
            return False
        return True

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _type_in_domain(self, t: str, domain: List[str]) -> bool:
        return self._type_in_list(t, domain)

    def _type_in_range(self, t: str, range_: List[str]) -> bool:
        return self._type_in_list(t, range_)

    def _type_in_list(self, t: str, allowed: List[str]) -> bool:
        if not allowed:
            return True  # open world
        # Allow inheritance
        for a in allowed:
            if nx.has_path(self._inheritance_graph, t, a):
                return True
        return False

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def load_from_file(self, path: Union[str, Path], fmt: str = "yaml") -> None:
        """
        Load a complete ontology from YAML or JSON.
        Expects top-level keys: 'entities' and 'relationships'.
        """
        path = Path(path)
        with path.open("rt", encoding="utf-8") as fp:
            raw = yaml.safe_load(fp) if fmt.lower() in {"yaml", "yml"} else json.load(fp)

        for ent_def in raw.get("entities", []):
            self.add_entity_schema(EntitySchema(**ent_def))
        for rel_def in raw.get("relationships", []):
            self.add_relationship_schema(RelationshipSchema(**rel_def))

    def save_to_file(self, path: Union[str, Path], fmt: str = "yaml") -> None:
        """
        Dump the current ontology to YAML or JSON.
        """
        path = Path(path)
        data = {
            "entities": [self._asdict(es) for es in self._entity_schemas.values()],
            "relationships": [self._asdict(rs) for rs in self._relation_schemas.values()],
        }
        with path.open("wt", encoding="utf-8") as fp:
            if fmt.lower() in {"yaml", "yml"}:
                yaml.safe_dump(data, fp, sort_keys=False)
            else:
                json.dump(data, fp, indent=2, ensure_ascii=False)

    @staticmethod
    def _asdict(dc) -> Dict[str, Any]:
        # dataclasses.asdict is recursive; we use a shallow copy
        return {k: v for k, v in dc.__dict__.items()}

    # ------------------------------------------------------------------
    # Async context manager for safe concurrent updates
    # ------------------------------------------------------------------
    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()