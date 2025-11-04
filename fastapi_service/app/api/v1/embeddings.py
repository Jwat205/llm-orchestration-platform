"""
Enhanced embeddings endpoints with knowledge graph integration
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from uuid import uuid4
import asyncio
import logging

from ...services.embedding_service import EmbeddingService
from ...services.graph_service import GraphService
from ...core.vector_store import VectorStore
from ...core.knowledge_graph import KnowledgeGraph
from ...models.graph_models import (
    GraphSearchResult,
    HybridSearchResult,
    EntityExtractionResult,
    RelationshipExtractionResult
)
from ...core.dependencies import get_embedding_service, get_graph_service
from ...core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/embeddings", tags=["embeddings"])


# Request Models
class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]] = Field(..., description="Text to embed")
    model: str = Field(default="text-embedding-ada-002", description="Embedding model to use")
    encoding_format: Optional[str] = Field(default="float", description="Encoding format")
    dimensions: Optional[int] = Field(default=None, description="Number of dimensions")
    user: Optional[str] = Field(default=None, description="User identifier")
    
    # Graph enhancement options
    extract_entities: bool = Field(default=False, description="Extract entities during embedding")
    build_graph: bool = Field(default=False, description="Build knowledge graph from text")
    context_expansion: bool = Field(default=False, description="Expand context using existing graph")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    model: str = Field(default="text-embedding-ada-002", description="Embedding model")
    top_k: int = Field(default=10, description="Number of results to return")
    threshold: float = Field(default=0.0, description="Similarity threshold")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")
    namespace: Optional[str] = Field(default=None, description="Vector namespace")
    
    # Graph enhancement options
    use_graph_context: bool = Field(default=False, description="Use graph context for search")
    expand_entities: bool = Field(default=False, description="Expand search using related entities")
    relationship_boost: float = Field(default=1.0, description="Boost factor for related entities")


class SimilarityRequest(BaseModel):
    text1: str = Field(..., description="First text")
    text2: str = Field(..., description="Second text")
    model: str = Field(default="text-embedding-ada-002", description="Embedding model")
    use_graph_similarity: bool = Field(default=False, description="Include graph-based similarity")


class GraphSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    search_type: str = Field(default="hybrid", description="Type of search: vector, graph, or hybrid")
    top_k: int = Field(default=10, description="Number of results")
    graph_depth: int = Field(default=2, description="Graph traversal depth")
    entity_types: Optional[List[str]] = Field(default=None, description="Filter by entity types")
    relationship_types: Optional[List[str]] = Field(default=None, description="Filter by relationship types")
    boost_entities: Optional[List[str]] = Field(default=None, description="Entities to boost in ranking")
    temporal_filter: Optional[Dict[str, Any]] = Field(default=None, description="Temporal constraints")


class EntitySearchRequest(BaseModel):
    entity_name: str = Field(..., description="Entity name to search")
    entity_type: Optional[str] = Field(default=None, description="Entity type filter")
    include_relationships: bool = Field(default=True, description="Include entity relationships")
    relationship_depth: int = Field(default=1, description="Depth of relationships to include")
    context_expansion: bool = Field(default=False, description="Expand with vector similarity")


class RelationshipSearchRequest(BaseModel):
    source_entity: Optional[str] = Field(default=None, description="Source entity")
    target_entity: Optional[str] = Field(default=None, description="Target entity")
    relationship_type: Optional[str] = Field(default=None, description="Relationship type")
    min_strength: float = Field(default=0.0, description="Minimum relationship strength")
    max_hops: int = Field(default=3, description="Maximum relationship hops")
    include_context: bool = Field(default=True, description="Include surrounding context")


class BatchEmbeddingRequest(BaseModel):
    inputs: List[str] = Field(..., description="List of texts to embed")
    model: str = Field(default="text-embedding-ada-002", description="Embedding model")
    batch_size: int = Field(default=100, description="Batch processing size")
    parallel_processing: bool = Field(default=True, description="Enable parallel processing")
    
    # Graph options
    extract_entities: bool = Field(default=False, description="Extract entities from all texts")
    build_relationships: bool = Field(default=False, description="Build relationships between texts")


# Response Models
class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: Dict[str, int]
    
    # Graph enhancement data
    entities: Optional[List[Dict[str, Any]]] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    graph_stats: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]
    
    # Graph enhancement
    entities: Optional[List[Dict[str, Any]]] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    graph_context: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_count: int
    query_time: float
    
    # Graph analytics
    graph_insights: Optional[Dict[str, Any]] = None
    entity_summary: Optional[Dict[str, Any]] = None


# Endpoints
@router.post("/", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Create embeddings with optional graph enhancement"""
    try:
        # Generate embeddings
        embeddings_result = await embedding_service.create_embeddings(
            input=request.input,
            model=request.model,
            dimensions=request.dimensions,
            user=request.user or current_user.id
        )
        
        response_data = {
            "object": "list",
            "data": embeddings_result["data"],
            "model": request.model,
            "usage": embeddings_result["usage"]
        }
        
        # Graph enhancements
        if request.extract_entities or request.build_graph:
            texts = request.input if isinstance(request.input, list) else [request.input]
            
            if request.extract_entities:
                entities = await graph_service.extract_entities_batch(texts)
                response_data["entities"] = entities
            
            if request.build_graph:
                graph_result = await graph_service.build_graph_from_texts(
                    texts, 
                    extract_relationships=True
                )
                response_data["relationships"] = graph_result.get("relationships", [])
                response_data["graph_stats"] = graph_result.get("stats", {})
        
        if request.context_expansion:
            # Expand embeddings with graph context
            expanded_embeddings = await embedding_service.expand_with_graph_context(
                embeddings_result["data"],
                graph_service
            )
            response_data["data"] = expanded_embeddings
        
        return EmbeddingResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error creating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_embeddings(
    request: SearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Search embeddings with optional graph enhancement"""
    try:
        # Standard vector search
        search_results = await embedding_service.search(
            query=request.query,
            model=request.model,
            top_k=request.top_k,
            threshold=request.threshold,
            filters=request.filters,
            namespace=request.namespace
        )
        
        results = []
        for result in search_results["results"]:
            search_result = SearchResult(
                id=result["id"],
                score=result["score"],
                text=result["text"],
                metadata=result["metadata"]
            )
            
            # Add graph enhancements
            if request.use_graph_context:
                graph_context = await graph_service.get_context_for_text(
                    result["text"],
                    depth=2
                )
                search_result.graph_context = graph_context
            
            if request.expand_entities:
                entities = await graph_service.extract_entities(result["text"])
                search_result.entities = entities
                
                # Boost results with related entities
                if entities and request.relationship_boost > 1.0:
                    search_result.score *= request.relationship_boost
            
            results.append(search_result)
        
        # Re-sort if we modified scores
        if request.expand_entities and request.relationship_boost > 1.0:
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[:request.top_k]
        
        # Generate graph insights
        graph_insights = None
        entity_summary = None
        
        if request.use_graph_context or request.expand_entities:
            all_entities = []
            for result in results:
                if result.entities:
                    all_entities.extend(result.entities)
            
            if all_entities:
                entity_summary = await graph_service.summarize_entities(all_entities)
                graph_insights = await graph_service.analyze_search_patterns(
                    request.query, 
                    all_entities
                )
        
        return SearchResponse(
            results=results,
            total_count=len(results),
            query_time=search_results.get("query_time", 0.0),
            graph_insights=graph_insights,
            entity_summary=entity_summary
        )
        
    except Exception as e:
        logger.error(f"Error searching embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similarity")
async def calculate_similarity(
    request: SimilarityRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Calculate similarity between two texts with optional graph enhancement"""
    try:
        # Vector similarity
        vector_similarity = await embedding_service.calculate_similarity(
            text1=request.text1,
            text2=request.text2,
            model=request.model
        )
        
        result = {
            "vector_similarity": vector_similarity,
            "overall_similarity": vector_similarity
        }
        
        if request.use_graph_similarity:
            # Graph-based similarity
            graph_similarity = await graph_service.calculate_graph_similarity(
                request.text1,
                request.text2
            )
            
            # Combined similarity (weighted average)
            combined_similarity = (vector_similarity * 0.7) + (graph_similarity * 0.3)
            
            result.update({
                "graph_similarity": graph_similarity,
                "overall_similarity": combined_similarity,
                "similarity_breakdown": {
                    "vector_weight": 0.7,
                    "graph_weight": 0.3,
                    "vector_score": vector_similarity,
                    "graph_score": graph_similarity
                }
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating similarity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph-search", response_model=Dict[str, Any])
async def graph_enhanced_search(
    request: GraphSearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Perform graph-enhanced search combining vector similarity and graph traversal"""
    try:
        if request.search_type == "vector":
            # Pure vector search
            results = await embedding_service.search(
                query=request.query,
                top_k=request.top_k
            )
            
        elif request.search_type == "graph":
            # Pure graph search
            results = await graph_service.graph_search(
                query=request.query,
                depth=request.graph_depth,
                entity_types=request.entity_types,
                relationship_types=request.relationship_types,
                top_k=request.top_k
            )
            
        else:  # hybrid
            # Hybrid search
            results = await graph_service.hybrid_search(
                query=request.query,
                vector_weight=0.6,
                graph_weight=0.4,
                top_k=request.top_k,
                graph_depth=request.graph_depth,
                entity_types=request.entity_types,
                relationship_types=request.relationship_types,
                boost_entities=request.boost_entities,
                temporal_filter=request.temporal_filter
            )
        
        return {
            "search_type": request.search_type,
            "results": results,
            "query_time": results.get("query_time", 0.0),
            "graph_statistics": results.get("graph_stats", {}),
            "search_insights": results.get("insights", {})
        }
        
    except Exception as e:
        logger.error(f"Error in graph search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entity-search", response_model=Dict[str, Any])
async def entity_based_search(
    request: EntitySearchRequest,
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Search for entities and their relationships"""
    try:
        results = await graph_service.search_entities(
            entity_name=request.entity_name,
            entity_type=request.entity_type,
            include_relationships=request.include_relationships,
            relationship_depth=request.relationship_depth
        )
        
        if request.context_expansion:
            # Expand results with vector similarity
            expanded_results = await graph_service.expand_entity_context(
                results,
                include_similar_entities=True
            )
            results = expanded_results
        
        return {
            "entity": request.entity_name,
            "results": results,
            "relationship_count": len(results.get("relationships", [])),
            "entity_network": results.get("network_stats", {}),
            "context_summary": results.get("context", {})
        }
        
    except Exception as e:
        logger.error(f"Error in entity search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relationship-search", response_model=Dict[str, Any])
async def relationship_based_search(
    request: RelationshipSearchRequest,
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Search for relationships between entities"""
    try:
        results = await graph_service.search_relationships(
            source_entity=request.source_entity,
            target_entity=request.target_entity,
            relationship_type=request.relationship_type,
            min_strength=request.min_strength,
            max_hops=request.max_hops
        )
        
        if request.include_context:
            # Add contextual information
            context_results = await graph_service.get_relationship_context(
                results,
                include_surrounding_entities=True
            )
            results["context"] = context_results
        
        return {
            "search_criteria": {
                "source": request.source_entity,
                "target": request.target_entity,
                "type": request.relationship_type
            },
            "relationships": results.get("relationships", []),
            "paths": results.get("paths", []),
            "statistics": results.get("stats", {}),
            "context": results.get("context", {})
        }
        
    except Exception as e:
        logger.error(f"Error in relationship search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=Dict[str, Any])
async def batch_embeddings(
    request: BatchEmbeddingRequest,
    background_tasks: BackgroundTasks,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Process batch embeddings with optional graph construction"""
    try:
        batch_id = str(uuid4())
        
        # Start batch processing
        task_result = await embedding_service.process_batch_embeddings(
            inputs=request.inputs,
            model=request.model,
            batch_size=request.batch_size,
            parallel_processing=request.parallel_processing,
            batch_id=batch_id
        )
        
        result = {
            "batch_id": batch_id,
            "status": "processing",
            "total_items": len(request.inputs),
            "estimated_time": task_result.get("estimated_time", 0),
            "embeddings": task_result.get("embeddings", [])
        }
        
        # Add graph processing if requested
        if request.extract_entities or request.build_relationships:
            background_tasks.add_task(
                process_batch_graph_operations,
                request.inputs,
                batch_id,
                request.extract_entities,
                request.build_relationships,
                graph_service
            )
            result["graph_processing"] = "scheduled"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    current_user = Depends(get_current_user)
):
    """Get batch processing status"""
    try:
        status = await embedding_service.get_batch_status(batch_id)
        return status
        
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task for graph processing
async def process_batch_graph_operations(
    texts: List[str],
    batch_id: str,
    extract_entities: bool,
    build_relationships: bool,
    graph_service: GraphService
):
    """Background task for processing graph operations on batch data"""
    try:
        logger.info(f"Starting graph processing for batch {batch_id}")
        
        if extract_entities:
            entities = await graph_service.extract_entities_batch(texts)
            logger.info(f"Extracted {len(entities)} entities for batch {batch_id}")
        
        if build_relationships:
            relationships = await graph_service.build_relationships_batch(texts)
            logger.info(f"Built {len(relationships)} relationships for batch {batch_id}")
        
        # Update batch status
        await graph_service.update_batch_graph_status(
            batch_id, 
            "completed",
            {"entities_count": len(entities) if extract_entities else 0,
             "relationships_count": len(relationships) if build_relationships else 0}
        )
        
    except Exception as e:
        logger.error(f"Error in batch graph processing: {e}")
        await graph_service.update_batch_graph_status(batch_id, "failed", {"error": str(e)})


# Analytics endpoints
@router.get("/analytics/models")
async def get_model_analytics(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    current_user = Depends(get_current_user)
):
    """Get analytics about embedding model usage"""
    try:
        analytics = await embedding_service.get_model_analytics()
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting model analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/graph")
async def get_graph_analytics(
    graph_service: GraphService = Depends(get_graph_service),
    current_user = Depends(get_current_user)
):
    """Get analytics about knowledge graph usage"""
    try:
        analytics = await graph_service.get_graph_analytics()
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting graph analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))