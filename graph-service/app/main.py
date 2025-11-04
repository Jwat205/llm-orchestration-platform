"""
Dedicated Knowledge Graph Service
Main FastAPI application for graph operations and management.
Enhanced with embeddings, vector search, temporal features, and GNN capabilities.
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

from core.graph_engine import GraphEngine
from core.query_processor import QueryProcessor
from core.inference_engine import InferenceEngine
from core.ontology_manager import OntologyManager

from services.embedding_service import EmbeddingService
from services.hybrid_search_service import HybridSearchService, HybridSearchConfig, SearchStrategy
from services.entity_resolution_service import EntityResolutionService, ResolutionConfig
from services.gnn_service import GNNService, GNNConfig, GNNTask, GNNModel
from services.temporal_graph_service import TemporalGraphService, TemporalQuery, TemporalQueryType, TemporalInterval

from extractors.spacy_extractor import SpacyExtractor
from extractors.transformer_extractor import TransformerExtractor
from extractors.custom_extractor import CustomExtractor

from builders.incremental_builder import IncrementalBuilder
from builders.batch_builder import BatchBuilder
from builders.streaming_builder import StreamingBuilder

from storage.neo4j_adapter import Neo4jAdapter
from storage.arangodb_adapter import ArangoDBAdapter
from storage.graph_cache import GraphCache

from algorithms.path_finding import PathFinder
from algorithms.centrality_measures import CentralityCalculator
from algorithms.community_detection import CommunityDetector
from algorithms.similarity_propagation import SimilarityPropagator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
graph_engine: GraphEngine = None
query_processor: QueryProcessor = None
inference_engine: InferenceEngine = None
ontology_manager: OntologyManager = None

# New enhanced services
embedding_service: EmbeddingService = None
hybrid_search_service: HybridSearchService = None
entity_resolution_service: EntityResolutionService = None
gnn_service: GNNService = None
temporal_service: TemporalGraphService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Graph Service...")
    await initialize_services()
    yield
    # Shutdown
    logger.info("Shutting down Graph Service...")
    await cleanup_services()

app = FastAPI(
    title="Knowledge Graph Service",
    description="Dedicated service for knowledge graph operations, entity extraction, and graph analytics",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def initialize_services():
    """Initialize all graph service components"""
    global graph_engine, query_processor, inference_engine, ontology_manager
    global embedding_service, hybrid_search_service, entity_resolution_service, gnn_service, temporal_service
    
    try:
        # Initialize storage adapters
        neo4j_adapter = Neo4jAdapter()
        arangodb_adapter = ArangoDBAdapter()
        graph_cache = GraphCache()
        
        # Initialize core services
        graph_engine = GraphEngine(
            primary_storage=neo4j_adapter,
            secondary_storage=arangodb_adapter,
            cache=graph_cache
        )
        
        query_processor = QueryProcessor(graph_engine)
        inference_engine = InferenceEngine(graph_engine)
        ontology_manager = OntologyManager(graph_engine)
        
        # Initialize enhanced services
        embedding_service = EmbeddingService()
        await embedding_service.initialize()
        
        hybrid_search_service = HybridSearchService(graph_engine, embedding_service)
        await hybrid_search_service.initialize()
        
        entity_resolution_service = EntityResolutionService(graph_engine, embedding_service)
        await entity_resolution_service.initialize()
        
        gnn_service = GNNService(graph_engine, embedding_service)
        await gnn_service.initialize()
        
        temporal_service = TemporalGraphService(graph_engine)
        await temporal_service.initialize()
        
        # Initialize extractors
        await graph_engine.register_extractor("spacy", SpacyExtractor())
        await graph_engine.register_extractor("transformer", TransformerExtractor())
        await graph_engine.register_extractor("custom", CustomExtractor())
        
        # Initialize builders
        await graph_engine.register_builder("incremental", IncrementalBuilder())
        await graph_engine.register_builder("batch", BatchBuilder())
        await graph_engine.register_builder("streaming", StreamingBuilder())
        
        # Initialize algorithms
        await graph_engine.register_algorithm("path_finding", PathFinder())
        await graph_engine.register_algorithm("centrality", CentralityCalculator())
        await graph_engine.register_algorithm("community", CommunityDetector())
        await graph_engine.register_algorithm("similarity", SimilarityPropagator())
        
        logger.info("Graph service initialization completed")
        
    except Exception as e:
        logger.error(f"Failed to initialize graph service: {e}")
        raise

async def cleanup_services():
    """Cleanup service resources"""
    global graph_engine, query_processor, inference_engine, ontology_manager
    global embedding_service, hybrid_search_service, entity_resolution_service, gnn_service, temporal_service
    
    if graph_engine:
        await graph_engine.shutdown()
    if query_processor:
        await query_processor.shutdown()
    if inference_engine:
        await inference_engine.shutdown()
    if ontology_manager:
        await ontology_manager.shutdown()
    
    # Shutdown enhanced services
    if embedding_service:
        await embedding_service.shutdown()
    if hybrid_search_service:
        await hybrid_search_service.shutdown()
    if entity_resolution_service:
        await entity_resolution_service.shutdown()
    if gnn_service:
        await gnn_service.shutdown()
    if temporal_service:
        await temporal_service.shutdown()

def get_graph_engine() -> GraphEngine:
    """Dependency to get graph engine instance"""
    if graph_engine is None:
        raise HTTPException(status_code=503, detail="Graph engine not initialized")
    return graph_engine

def get_query_processor() -> QueryProcessor:
    """Dependency to get query processor instance"""
    if query_processor is None:
        raise HTTPException(status_code=503, detail="Query processor not initialized")
    return query_processor

def get_inference_engine() -> InferenceEngine:
    """Dependency to get inference engine instance"""
    if inference_engine is None:
        raise HTTPException(status_code=503, detail="Inference engine not initialized")
    return inference_engine

def get_ontology_manager() -> OntologyManager:
    """Dependency to get ontology manager instance"""
    if ontology_manager is None:
        raise HTTPException(status_code=503, detail="Ontology manager not initialized")
    return ontology_manager

def get_embedding_service() -> EmbeddingService:
    """Dependency to get embedding service instance"""
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")
    return embedding_service

def get_hybrid_search_service() -> HybridSearchService:
    """Dependency to get hybrid search service instance"""
    if hybrid_search_service is None:
        raise HTTPException(status_code=503, detail="Hybrid search service not initialized")
    return hybrid_search_service

def get_entity_resolution_service() -> EntityResolutionService:
    """Dependency to get entity resolution service instance"""
    if entity_resolution_service is None:
        raise HTTPException(status_code=503, detail="Entity resolution service not initialized")
    return entity_resolution_service

def get_gnn_service() -> GNNService:
    """Dependency to get GNN service instance"""
    if gnn_service is None:
        raise HTTPException(status_code=503, detail="GNN service not initialized")
    return gnn_service

def get_temporal_service() -> TemporalGraphService:
    """Dependency to get temporal service instance"""
    if temporal_service is None:
        raise HTTPException(status_code=503, detail="Temporal service not initialized")
    return temporal_service

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "knowledge-graph-service",
        "version": "1.0.0",
        "components": {
            "graph_engine": graph_engine is not None,
            "query_processor": query_processor is not None,
            "inference_engine": inference_engine is not None,
            "ontology_manager": ontology_manager is not None
        }
    }

# Entity Management Endpoints
@app.post("/v1/entities")
async def create_entities(
    entities: List[Dict[str, Any]],
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Create new entities in the knowledge graph"""
    try:
        result = await engine.create_entities(entities)
        return {"success": True, "created_entities": result}
    except Exception as e:
        logger.error(f"Error creating entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Get entity by ID"""
    try:
        entity = await engine.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/v1/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    entity_data: Dict[str, Any],
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Update entity"""
    try:
        result = await engine.update_entity(entity_id, entity_data)
        return {"success": True, "updated_entity": result}
    except Exception as e:
        logger.error(f"Error updating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v1/entities/{entity_id}")
async def delete_entity(
    entity_id: str,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Delete entity"""
    try:
        result = await engine.delete_entity(entity_id)
        return {"success": True, "deleted": result}
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Relationship Management Endpoints
@app.post("/v1/relationships")
async def create_relationships(
    relationships: List[Dict[str, Any]],
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Create new relationships in the knowledge graph"""
    try:
        result = await engine.create_relationships(relationships)
        return {"success": True, "created_relationships": result}
    except Exception as e:
        logger.error(f"Error creating relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/relationships/{relationship_id}")
async def get_relationship(
    relationship_id: str,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Get relationship by ID"""
    try:
        relationship = await engine.get_relationship(relationship_id)
        if relationship is None:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return relationship
    except Exception as e:
        logger.error(f"Error getting relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Query Endpoints
@app.post("/v1/query")
async def execute_query(
    query_data: Dict[str, Any],
    processor: QueryProcessor = Depends(get_query_processor)
):
    """Execute graph query"""
    try:
        result = await processor.execute_query(query_data)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/query/cypher")
async def execute_cypher_query(
    cypher_query: str,
    parameters: Optional[Dict[str, Any]] = None,
    processor: QueryProcessor = Depends(get_query_processor)
):
    """Execute Cypher query"""
    try:
        result = await processor.execute_cypher(cypher_query, parameters or {})
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/query/sparql")
async def execute_sparql_query(
    sparql_query: str,
    processor: QueryProcessor = Depends(get_query_processor)
):
    """Execute SPARQL query"""
    try:
        result = await processor.execute_sparql(sparql_query)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error executing SPARQL query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Graph Analytics Endpoints
@app.post("/v1/analytics/centrality")
async def calculate_centrality(
    centrality_type: str = "betweenness",
    node_filter: Optional[Dict[str, Any]] = None,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Calculate centrality measures"""
    try:
        algorithm = await engine.get_algorithm("centrality")
        result = await algorithm.calculate(centrality_type, node_filter)
        return {"success": True, "centrality": result}
    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/analytics/community")
async def detect_communities(
    algorithm: str = "louvain",
    resolution: float = 1.0,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Detect communities in the graph"""
    try:
        detector = await engine.get_algorithm("community")
        result = await detector.detect(algorithm, resolution)
        return {"success": True, "communities": result}
    except Exception as e:
        logger.error(f"Error detecting communities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/analytics/path")
async def find_path(
    source_id: str,
    target_id: str,
    algorithm: str = "dijkstra",
    max_length: int = 10,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Find path between two entities"""
    try:
        path_finder = await engine.get_algorithm("path_finding")
        result = await path_finder.find_path(source_id, target_id, algorithm, max_length)
        return {"success": True, "path": result}
    except Exception as e:
        logger.error(f"Error finding path: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Entity Extraction Endpoints
@app.post("/v1/extract/entities")
async def extract_entities(
    text: str,
    extractor_type: str = "spacy",
    entity_types: Optional[List[str]] = None,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Extract entities from text"""
    try:
        extractor = await engine.get_extractor(extractor_type)
        result = await extractor.extract(text, entity_types)
        return {"success": True, "entities": result}
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/extract/relationships")
async def extract_relationships(
    text: str,
    entities: Optional[List[Dict[str, Any]]] = None,
    extractor_type: str = "transformer",
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Extract relationships from text"""
    try:
        extractor = await engine.get_extractor(extractor_type)
        result = await extractor.extract_relationships(text, entities)
        return {"success": True, "relationships": result}
    except Exception as e:
        logger.error(f"Error extracting relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Graph Building Endpoints
@app.post("/v1/build/incremental")
async def build_graph_incremental(
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    builder_config: Optional[Dict[str, Any]] = None,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Build graph incrementally"""
    try:
        builder = await engine.get_builder("incremental")
        task_id = await builder.start_build(data, builder_config or {})
        
        # Add background task to monitor build progress
        background_tasks.add_task(monitor_build_progress, task_id, builder)
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error starting incremental build: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/build/batch")
async def build_graph_batch(
    data_sources: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    builder_config: Optional[Dict[str, Any]] = None,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Build graph in batch mode"""
    try:
        builder = await engine.get_builder("batch")
        task_id = await builder.start_batch_build(data_sources, builder_config or {})
        
        # Add background task to monitor build progress
        background_tasks.add_task(monitor_build_progress, task_id, builder)
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error starting batch build: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/build/status/{task_id}")
async def get_build_status(
    task_id: str,
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Get build task status"""
    try:
        status = await engine.get_build_status(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return status
    except Exception as e:
        logger.error(f"Error getting build status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Ontology Management Endpoints
@app.get("/v1/ontology")
async def get_ontology(
    ontology_manager: OntologyManager = Depends(get_ontology_manager)
):
    """Get current ontology"""
    try:
        ontology = await ontology_manager.get_ontology()
        return {"success": True, "ontology": ontology}
    except Exception as e:
        logger.error(f"Error getting ontology: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/ontology/classes")
async def create_ontology_class(
    class_data: Dict[str, Any],
    ontology_manager: OntologyManager = Depends(get_ontology_manager)
):
    """Create ontology class"""
    try:
        result = await ontology_manager.create_class(class_data)
        return {"success": True, "class": result}
    except Exception as e:
        logger.error(f"Error creating ontology class: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/ontology/properties")
async def create_ontology_property(
    property_data: Dict[str, Any],
    ontology_manager: OntologyManager = Depends(get_ontology_manager)
):
    """Create ontology property"""
    try:
        result = await ontology_manager.create_property(property_data)
        return {"success": True, "property": result}
    except Exception as e:
        logger.error(f"Error creating ontology property: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Inference Endpoints
@app.post("/v1/inference/infer")
async def infer_relationships(
    entities: List[str],
    inference_type: str = "semantic",
    confidence_threshold: float = 0.7,
    inference_engine: InferenceEngine = Depends(get_inference_engine)
):
    """Infer new relationships"""
    try:
        result = await inference_engine.infer(
            entities, inference_type, confidence_threshold
        )
        return {"success": True, "inferred_relationships": result}
    except Exception as e:
        logger.error(f"Error in inference: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Graph Statistics Endpoints
@app.get("/v1/stats")
async def get_graph_statistics(
    engine: GraphEngine = Depends(get_graph_engine)
):
    """Get graph statistics"""
    try:
        stats = await engine.get_statistics()
        return {"success": True, "statistics": stats}
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task for monitoring build progress
async def monitor_build_progress(task_id: str, builder):
    """Monitor build progress in background"""
    try:
        while True:
            status = await builder.get_build_status(task_id)
            if status["status"] in ["completed", "failed", "cancelled"]:
                logger.info(f"Build task {task_id} finished with status: {status['status']}")
                break
            
            await asyncio.sleep(5)  # Check every 5 seconds
            
    except Exception as e:
        logger.error(f"Error monitoring build progress: {e}")

# ===== ENHANCED ENDPOINTS =====

# Embedding Service Endpoints
@app.get("/v1/embeddings/text")
async def get_text_embedding(
    text: str,
    embedding_type: str = "text",
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Get embedding for text"""
    try:
        embedding = await embedding_service.get_embedding(text, embedding_type)
        return {"success": True, "text": text, "embedding": embedding}
    except Exception as e:
        logger.error(f"Error getting text embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/embeddings/batch")
async def get_batch_embeddings(
    texts: List[str],
    embedding_type: str = "text",
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Get embeddings for multiple texts"""
    try:
        embeddings = await embedding_service.get_embeddings_batch(texts, embedding_type)
        return {"success": True, "embeddings": dict(zip(texts, embeddings))}
    except Exception as e:
        logger.error(f"Error getting batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/embeddings/similarity")
async def compute_similarity(
    embedding1: List[float],
    embedding2: List[float],
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Compute similarity between embeddings"""
    try:
        similarity = await embedding_service.compute_similarity(embedding1, embedding2)
        return {"success": True, "similarity": similarity}
    except Exception as e:
        logger.error(f"Error computing similarity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Hybrid Search Endpoints
@app.post("/v1/search/hybrid")
async def hybrid_search(
    query: str,
    strategy: str = "weighted_fusion",
    vector_weight: float = 0.6,
    graph_weight: float = 0.4,
    max_hops: int = 3,
    top_k: int = 20,
    context_entities: Optional[List[str]] = None,
    hybrid_service: HybridSearchService = Depends(get_hybrid_search_service)
):
    """Perform hybrid vector-graph search"""
    try:
        config = HybridSearchConfig(
            strategy=SearchStrategy(strategy),
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            max_hops=max_hops,
            top_k=top_k
        )
        
        results = await hybrid_service.search(query, config, context_entities)
        
        # Convert SearchResult objects to dictionaries
        result_dicts = []
        for result in results:
            result_dicts.append({
                "entity_id": result.entity_id,
                "entity_data": result.entity_data,
                "relevance_score": result.relevance_score,
                "vector_score": result.vector_score,
                "graph_score": result.graph_score,
                "reasoning_path": result.reasoning_path,
                "search_strategy": result.search_strategy
            })
        
        return {"success": True, "results": result_dicts}
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Entity Resolution Endpoints
@app.post("/v1/resolution/find-duplicates")
async def find_duplicate_entities(
    entity_ids: Optional[List[str]] = None,
    strategy: str = "hybrid",
    similarity_threshold: float = 0.8,
    require_type_match: bool = True,
    resolution_service: EntityResolutionService = Depends(get_entity_resolution_service)
):
    """Find duplicate entities"""
    try:
        config = ResolutionConfig(
            similarity_threshold=similarity_threshold,
            require_type_match=require_type_match
        )
        
        matches = await resolution_service.find_duplicate_entities(entity_ids, config)
        
        # Convert EntityMatch objects to dictionaries
        match_dicts = []
        for match in matches:
            match_dicts.append({
                "entity1_id": match.entity1_id,
                "entity2_id": match.entity2_id,
                "similarity_score": match.similarity_score,
                "confidence_level": match.confidence_level.value,
                "matching_features": match.matching_features,
                "resolution_method": match.resolution_method,
                "evidence": match.evidence
            })
        
        return {"success": True, "matches": match_dicts}
    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/resolution/resolve")
async def resolve_duplicates(
    matches: List[Dict[str, Any]],
    auto_merge: bool = False,
    resolution_service: EntityResolutionService = Depends(get_entity_resolution_service)
):
    """Resolve duplicate entities"""
    try:
        # Convert match dictionaries back to EntityMatch objects (simplified)
        from services.entity_resolution_service import EntityMatch, ConfidenceLevel
        
        entity_matches = []
        for match_data in matches:
            entity_match = EntityMatch(
                entity1_id=match_data["entity1_id"],
                entity2_id=match_data["entity2_id"],
                similarity_score=match_data["similarity_score"],
                confidence_level=ConfidenceLevel(match_data["confidence_level"]),
                matching_features=match_data["matching_features"],
                resolution_method=match_data["resolution_method"],
                evidence=match_data["evidence"]
            )
            entity_matches.append(entity_match)
        
        result = await resolution_service.resolve_entity_duplicates(entity_matches, auto_merge)
        return {"success": True, "resolution_result": result}
    except Exception as e:
        logger.error(f"Error resolving duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# GNN Service Endpoints
@app.post("/v1/gnn/train")
async def train_gnn_model(
    model_name: str,
    task: str,
    model_type: str = "gcn",
    hidden_dim: int = 128,
    num_layers: int = 2,
    learning_rate: float = 0.01,
    max_epochs: int = 100,
    training_data: Optional[Dict[str, Any]] = None,
    gnn_service: GNNService = Depends(get_gnn_service)
):
    """Train a GNN model"""
    try:
        config = GNNConfig(
            model_type=GNNModel(model_type),
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            learning_rate=learning_rate,
            max_epochs=max_epochs
        )
        
        result = await gnn_service.train_model(model_name, GNNTask(task), config, training_data)
        return result
    except Exception as e:
        logger.error(f"Error training GNN model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/gnn/embeddings/{model_name}")
async def generate_node_embeddings(
    model_name: str,
    node_ids: Optional[List[str]] = None,
    gnn_service: GNNService = Depends(get_gnn_service)
):
    """Generate node embeddings using GNN model"""
    try:
        embeddings = await gnn_service.generate_node_embeddings(model_name, node_ids)
        return {"success": True, "embeddings": embeddings}
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/gnn/predict-links/{model_name}")
async def predict_links(
    model_name: str,
    source_nodes: List[str],
    target_nodes: Optional[List[str]] = None,
    gnn_service: GNNService = Depends(get_gnn_service)
):
    """Predict links using GNN model"""
    try:
        predictions = await gnn_service.predict_links(model_name, source_nodes, target_nodes)
        return {"success": True, "predictions": predictions}
    except Exception as e:
        logger.error(f"Error predicting links: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Temporal Graph Endpoints
@app.post("/v1/temporal/entities")
async def create_temporal_entity(
    entity_data: Dict[str, Any],
    valid_start: Optional[str] = None,
    valid_end: Optional[str] = None,
    temporal_service: TemporalGraphService = Depends(get_temporal_service)
):
    """Create temporal entity"""
    try:
        valid_time = None
        if valid_start or valid_end:
            start_time = datetime.fromisoformat(valid_start) if valid_start else None
            end_time = datetime.fromisoformat(valid_end) if valid_end else None
            valid_time = TemporalInterval(start_time, end_time)
        
        entity_id = await temporal_service.create_temporal_entity(entity_data, valid_time)
        return {"success": True, "entity_id": entity_id}
    except Exception as e:
        logger.error(f"Error creating temporal entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/temporal/relationships")
async def create_temporal_relationship(
    source_id: str,
    target_id: str,
    relationship_type: str,
    properties: Optional[Dict[str, Any]] = None,
    strength: float = 1.0,
    valid_start: Optional[str] = None,
    valid_end: Optional[str] = None,
    temporal_service: TemporalGraphService = Depends(get_temporal_service)
):
    """Create temporal relationship"""
    try:
        valid_time = None
        if valid_start or valid_end:
            start_time = datetime.fromisoformat(valid_start) if valid_start else None
            end_time = datetime.fromisoformat(valid_end) if valid_end else None
            valid_time = TemporalInterval(start_time, end_time)
        
        rel_id = await temporal_service.create_temporal_relationship(
            source_id, target_id, relationship_type, properties, valid_time, strength=strength
        )
        return {"success": True, "relationship_id": rel_id}
    except Exception as e:
        logger.error(f"Error creating temporal relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/temporal/query")
async def execute_temporal_query(
    query_type: str,
    target_time: Optional[str] = None,
    time_range_start: Optional[str] = None,
    time_range_end: Optional[str] = None,
    entity_ids: Optional[List[str]] = None,
    relationship_types: Optional[List[str]] = None,
    temporal_service: TemporalGraphService = Depends(get_temporal_service)
):
    """Execute temporal query"""
    try:
        # Build temporal query
        query = TemporalQuery(query_type=TemporalQueryType(query_type))
        
        if target_time:
            query.target_time = datetime.fromisoformat(target_time)
        
        if time_range_start or time_range_end:
            start_time = datetime.fromisoformat(time_range_start) if time_range_start else None
            end_time = datetime.fromisoformat(time_range_end) if time_range_end else None
            query.time_range = TemporalInterval(start_time, end_time)
        
        query.entity_ids = entity_ids
        query.relationship_types = relationship_types
        
        result = await temporal_service.execute_temporal_query(query)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error executing temporal query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Service Statistics Endpoints
@app.get("/v1/stats/embedding")
async def get_embedding_stats(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Get embedding service statistics"""
    try:
        stats = await embedding_service.get_statistics()
        return {"success": True, "statistics": stats}
    except Exception as e:
        logger.error(f"Error getting embedding stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/stats/gnn")
async def get_gnn_stats(
    gnn_service: GNNService = Depends(get_gnn_service)
):
    """Get GNN service statistics"""
    try:
        stats = await gnn_service.get_gnn_statistics()
        return {"success": True, "statistics": stats}
    except Exception as e:
        logger.error(f"Error getting GNN stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/stats/temporal")
async def get_temporal_stats(
    temporal_service: TemporalGraphService = Depends(get_temporal_service)
):
    """Get temporal graph statistics"""
    try:
        stats = await temporal_service.get_temporal_statistics()
        return {"success": True, "statistics": stats}
    except Exception as e:
        logger.error(f"Error getting temporal stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)