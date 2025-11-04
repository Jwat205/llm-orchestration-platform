# shared/schemas/graph_schemas.py
from pydantic import BaseModel
from typing import List, Dict, Any

class GraphEntity(BaseModel):
    id: str
    type: str
    attributes: Dict[str, Any]

class GraphRelationship(BaseModel):
    subject: str
    predicate: str
    object: str

class GraphQuerySchema(BaseModel):
    query: str
    depth: int = 1

class GraphSearchRequest(BaseModel):
    query: str
    top_k: int = 10

class GraphSearchResponse(BaseModel):
    entities: List[GraphEntity]
    relationships: List[GraphRelationship]

class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    depth: int = 2

class EntityExtractionRequest(BaseModel):
    text: str

class RelationshipQuery(BaseModel):
    entity: str

class GraphAnalyticsRequest(BaseModel):
    metrics: List[str]