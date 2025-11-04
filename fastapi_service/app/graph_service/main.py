"""
Graph Service - Main Application
FastAPI service for knowledge graph construction and querying
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from typing import List, Dict, Any, Optional
import logging

from app.config import settings
from app.graph_service.core.graph_engine import GraphEngine
from app.graph_service.core.query_processor import QueryProcessor
from app.graph_service.core.inference_engine import InferenceEngine
from app.graph_service.core.ontology_manager import OntologyManager
from app.graph_service.storage.neo4j_adapter import Neo4jAdapter
from app.graph_service.storage.graph_cache import GraphCache
from ..shared.schemas.graph_schemas import (
    GraphEntity, GraphRelationship, GraphQuerySchema, 
    GraphSearchRequest, GraphSearchResponse,
    EntityExtractionRequest, RelationshipQuery,
    GraphAnalyticsRequest, HybridSearchRequest
)
from dotenv import load_dotenv

load_dotenv()  # Load PYTHONPATH from .env
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
graph_router = APIRouter(prefix="/graph_service/graph", tags=["graph"])
# Global instances
graph_engine: Optional[GraphEngine] = None
query_processor: Optional[QueryProcessor] = None
inference_engine: Optional[InferenceEngine] = None
ontology_manager: Optional[OntologyManager] = None
 

async def init_graph_service(app: FastAPI):
    logger.info("Initializing Graph Service components...")
    neo4j = Neo4jAdapter(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    cache = GraphCache()

    ge = GraphEngine(neo4j, cache,
                     uri=settings.neo4j_uri,
                     user=settings.neo4j_user,
                     password=settings.neo4j_password)
    qp = QueryProcessor(ge)
    om = OntologyManager(ge)
    ie = InferenceEngine(ge,om)

    app.state.neo4j = neo4j
    app.state.graph_cache = cache
    app.state.graph_engine = ge
    app.state.query_processor = qp
    app.state.inference_engine = ie
    app.state.ontology_manager = om
    
async def shutdown_graph_service(app: FastAPI):
    logger.info("Shutting down Graph Service...")
    await app.state.neo4j.close()
    await app.state.graph_cache.close()

def _get(req: Request, name: str):
    obj = getattr(req.app.state, name, None)
    if obj is None:
        raise HTTPException(503, f"{name} not initialized")
    return obj

def get_graph_engine(req: Request) -> GraphEngine:
    return _get(req, "graph_engine")

def get_query_processor(req: Request) -> QueryProcessor:
    return _get(req, "query_processor")

def get_inference_engine(req: Request) -> InferenceEngine:
    return _get(req, "inference_engine")

router = APIRouter(prefix="/v1/graph", tags=["graph"])

@router.get("/healthz")
async def health(req: Request):
    return {"ok": True, "graph_engine": hasattr(req.app.state, "graph_engine")}
# API Endpoints

@graph_router.post("/v1/entities", response_model=GraphEntity)
async def create_entity(
    entity_data: Dict[str, Any],
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Create a new entity in the knowledge graph"""
    try:
        entity = await engine.create_entity(entity_data)
        return entity
    except Exception as e:
        logger.error(f"Error creating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/relationships", response_model=GraphRelationship)
async def create_relationship(
    relationship_data: Dict[str, Any],
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Create a new relationship in the knowledge graph"""
    try:
        relationship = await engine.create_relationship(relationship_data)
        return relationship
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/extract/entities", response_model=List[GraphEntity])
async def extract_entities(
    request: EntityExtractionRequest,
    background_tasks: BackgroundTasks,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Extract entities from text using various NLP models"""
    try:
        # Run entity extraction
        entities = await engine.extract_entities(
            text=request.text,
            extractors=request.extractors,
            confidence_threshold=request.confidence_threshold
        )
        
        # Optionally add to graph in background
        if request.add_to_graph:
            background_tasks.add_task(
                engine.add_entities_to_graph, 
                entities
            )
        
        return entities
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/extract/relationships", response_model=List[GraphRelationship])
async def extract_relationships(
    text: str,
    entities: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Extract relationships from text"""
    try:
        relationships = await engine.extract_relationships(
            text=text,
            entities=entities
        )
        
        if background_tasks:
            background_tasks.add_task(
                engine.add_relationships_to_graph,
                relationships
            )
        
        return relationships
    except Exception as e:
        logger.error(f"Error extracting relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/search/graph", response_model=GraphSearchResponse)
async def search_graph(
    request: GraphSearchRequest,
    processor: QueryProcessor = Depends(get_query_processor)
):
    """Search the knowledge graph using various query types"""
    try:
        results = await processor.search_graph(request)
        return results
    except Exception as e:
        logger.error(f"Error searching graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/search/hybrid")
async def hybrid_search(
    request: HybridSearchRequest,
    processor: QueryProcessor = Depends(get_query_processor)
):
    """Perform hybrid search combining vector similarity and graph traversal"""
    try:
        results = await processor.hybrid_search(request)
        return results
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/query/relationships")
async def query_relationships(
    query: RelationshipQuery,
    processor: QueryProcessor = Depends(get_query_processor)
):
    """Query relationships in the knowledge graph"""
    try:
        relationships = await processor.query_relationships(query)
        return relationships
    except Exception as e:
        logger.error(f"Error querying relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/analytics/graph")
async def graph_analytics(
    request: GraphAnalyticsRequest,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Perform graph analytics and return insights"""
    try:
        analytics_results = await engine.perform_analytics(request)
        return analytics_results
    except Exception as e:
        logger.error(f"Error in graph analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/inference/reasoning")
async def perform_reasoning(
    query: str,
    context: Optional[Dict[str, Any]] = None,
    inference: InferenceEngine = Depends(get_inference_engine)
):
    """Perform reasoning over the knowledge graph"""
    try:
        reasoning_results = await inference.reason(query, context)
        return reasoning_results
    except Exception as e:
        logger.error(f"Error in reasoning: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.get("/v1/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    include_relationships: bool = False,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Get entity by ID with optional relationships"""
    try:
        entity = await engine.get_entity(entity_id, include_relationships)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.get("/v1/graph/stats")
async def get_graph_statistics(
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Get knowledge graph statistics"""
    try:
        stats = await engine.get_graph_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting graph statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.post("/v1/graph/build")
async def build_graph_from_document(
    document_text: str,
    document_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Build knowledge graph from document text"""
    try:
        if background_tasks:
            background_tasks.add_task(
                engine.build_graph_from_document,
                document_text,
                document_id
            )
            return {"message": "Graph building started in background", "document_id": document_id}
        else:
            result = await engine.build_graph_from_document(document_text, document_id)
            return result
    except Exception as e:
        logger.error(f"Error building graph from document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@graph_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "knowledge-graph-service",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )