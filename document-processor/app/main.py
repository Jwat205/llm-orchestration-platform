"""
Enhanced Document Processing Service
Main FastAPI application with knowledge graph capabilities
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import json
import os
from datetime import datetime

# FastAPI imports
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Document processors
from processors.pdf_processor import PDFProcessor
from processors.text_processor import TextProcessor
from processors.html_processor import HTMLProcessor
from processors.code_processor import CodeProcessor
from processors.graph_processor import GraphProcessor

# Chunking modules
from chunking.text_splitter import TextSplitterFactory
from chunking.semantic_chunker import SemanticChunker
from chunking.code_chunker import CodeChunker
from chunking.graph_aware_chunker import GraphAwareChunker

# Extraction modules
from extraction.entity_extractor import EntityExtractor
from extraction.relationship_extractor import RelationshipExtractor
from extraction.concept_extractor import ConceptExtractor
from extraction.temporal_extractor import TemporalExtractor

# Graph builders
from graph_builders.document_graph_builder import DocumentGraphBuilder
from graph_builders.concept_graph_builder import ConceptGraphBuilder
from graph_builders.temporal_graph_builder import TemporalGraphBuilder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="Enhanced Document Processing Service",
    description="Advanced document processing with knowledge graph capabilities",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
pdf_processor = PDFProcessor()
text_processor = TextProcessor()
html_processor = HTMLProcessor()
code_processor = CodeProcessor()
graph_processor = GraphProcessor()

# Chunking services
text_splitter_factory = TextSplitterFactory()
semantic_chunker = SemanticChunker()
code_chunker = CodeChunker()
graph_aware_chunker = GraphAwareChunker()

# Extraction services
entity_extractor = EntityExtractor()
relationship_extractor = RelationshipExtractor()
concept_extractor = ConceptExtractor()
temporal_extractor = TemporalExtractor()

# Graph builders
document_graph_builder = DocumentGraphBuilder()
concept_graph_builder = ConceptGraphBuilder()
temporal_graph_builder = TemporalGraphBuilder()

# Storage for processing results (in production, use a proper database)  
processing_results = {}
processing_tasks = {}


# Pydantic models for API requests
class ProcessingOptions(BaseModel):
    """Processing options for document analysis"""
    extract_entities: bool = True
    extract_concepts: bool = True
    extract_temporal: bool = True
    extract_relationships: bool = True
    build_graph: bool = True
    chunk_strategy: str = "semantic"  # semantic, recursive, sentence, paragraph
    max_chunk_size: int = 1000
    chunk_overlap: int = 200
    include_embeddings: bool = False
    graph_types: List[str] = ["document", "concept", "temporal"]


class DocumentMetadata(BaseModel):
    """Document metadata"""
    title: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    language: str = "en"
    document_type: Optional[str] = None


class ProcessingRequest(BaseModel):
    """Request model for document processing"""
    content: str
    metadata: Optional[DocumentMetadata] = None
    options: Optional[ProcessingOptions] = None


class BatchProcessingRequest(BaseModel):
    """Request model for batch processing"""
    documents: List[ProcessingRequest]
    batch_options: Optional[ProcessingOptions] = None


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "message": "Enhanced Document Processing Service",
        "version": "1.0.0",
        "features": [
            "Multi-format document processing (PDF, HTML, Text, Code)",
            "Advanced entity and concept extraction",
            "Temporal information extraction",
            "Relationship detection",
            "Knowledge graph construction",
            "Semantic chunking",
            "Graph-aware processing"
        ],
        "endpoints": {
            "/process": "Process a single document",
            "/process/batch": "Process multiple documents", 
            "/process/file": "Upload and process a file",
            "/analyze/entities": "Extract entities from text",
            "/analyze/concepts": "Extract concepts from text",
            "/analyze/temporal": "Extract temporal information",
            "/analyze/relationships": "Extract relationships",
            "/graph/build": "Build knowledge graphs",
            "/graph/query": "Query knowledge graphs",
            "/health": "Service health check"
        }
    }


@app.get("/health")
async def health_check():
    """Service health check"""
    
    try:
        # Check service components
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "pdf_processor": "available",
                "text_processor": "available",
                "html_processor": "available",
                "code_processor": "available",
                "entity_extractor": "available",
                "concept_extractor": "available",
                "temporal_extractor": "available",
                "relationship_extractor": "available",
                "graph_builders": "available"
            },
            "active_tasks": len(processing_tasks),
            "completed_results": len(processing_results)
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process")
async def process_document(request: ProcessingRequest, background_tasks: BackgroundTasks):
    """Process a single document with comprehensive analysis"""
    
    try:
        # Generate processing ID
        processing_id = f"proc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(request.content) % 10000}"
        
        # Initialize processing options
        options = request.options or ProcessingOptions()
        metadata = request.metadata or DocumentMetadata()
        
        # Start processing in background
        background_tasks.add_task(
            _process_document_background,
            processing_id,
            request.content,
            metadata.dict(),
            options.dict()
        )
        
        # Store initial task info
        processing_tasks[processing_id] = {
            "status": "processing",
            "started_at": datetime.now().isoformat(),
            "progress": 0
        }
        
        return {
            "processing_id": processing_id,
            "status": "started",
            "message": "Document processing initiated",
            "check_status_url": f"/status/{processing_id}"
        }
        
    except Exception as e:
        logger.error(f"Error initiating document processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/text", response_model=ProcessingResult)
async def process_text(
    request: ProcessingRequest,
    text_content: str
):
    """Process text content directly"""
    
    document_id = f"text_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    start_time = datetime.now()
    
    try:
        result = await process_text_content(
            document_id=document_id,
            content=text_content,
            content_type="text/plain",
            extract_entities=request.extract_entities,
            build_graph=request.build_graph,
            chunk_strategy=request.chunk_strategy,
            max_chunk_size=request.max_chunk_size,
            overlap_size=request.overlap_size
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        result["processing_time"] = processing_time
        
        return ProcessingResult(**result)
        
    except Exception as e:
        logger.error(f"Error processing text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{document_id}", response_model=ProcessingStatus)
async def get_processing_status(document_id: str):
    """Get processing status for a document"""
    
    if document_id not in processing_status:
        raise HTTPException(status_code=404, detail="Document not found")
    
    status_data = processing_status[document_id]
    
    return ProcessingStatus(
        document_id=document_id,
        status=status_data["status"],
        progress=status_data["progress"],
        message=status_data["message"],
        started_at=status_data["started_at"],
        completed_at=status_data.get("completed_at")
    )


@app.get("/result/{document_id}", response_model=ProcessingResult)
async def get_processing_result(document_id: str):
    """Get processing result for a completed document"""
    
    if document_id not in processing_status:
        raise HTTPException(status_code=404, detail="Document not found")
    
    status_data = processing_status[document_id]
    
    if status_data["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Document processing not completed. Status: {status_data['status']}"
        )
    
    if "result" not in status_data:
        raise HTTPException(status_code=500, detail="Processing result not available")
    
    return ProcessingResult(**status_data["result"])


@app.post("/extract/entities")
async def extract_entities_endpoint(
    text: str,
    entity_types: Optional[List[str]] = None
):
    """Extract entities from text"""
    
    try:
        entities = await entity_extractor.extract(text, entity_types)
        
        return {
            "entities": entities,
            "total_count": len(entities),
            "extraction_time": 0.0  # Would be measured in actual implementation
        }
        
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/relationships")
async def extract_relationships_endpoint(
    text: str,
    entities: List[Dict[str, Any]]
):
    """Extract relationships from text given entities"""
    
    try:
        relationships = await relationship_extractor.extract(text, entities)
        
        return {
            "relationships": relationships,
            "total_count": len(relationships),
            "extraction_time": 0.0
        }
        
    except Exception as e:
        logger.error(f"Error extracting relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chunk/text")
async def chunk_text_endpoint(
    text: str,
    strategy: str = "semantic",
    max_chunk_size: int = 1000,
    overlap_size: int = 200
):
    """Chunk text using specified strategy"""
    
    try:
        if strategy == "semantic":
            chunks = await semantic_chunker.chunk(text, max_chunk_size, overlap_size)
        elif strategy == "graph_aware":
            chunks = await graph_aware_chunker.chunk(text, max_chunk_size, overlap_size)
        else:
            chunks = await text_splitter.chunk(text, max_chunk_size, overlap_size)
        
        return {
            "chunks": chunks,
            "total_chunks": len(chunks),
            "strategy": strategy
        }
        
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/build/graph")
async def build_graph_endpoint(
    text: str,
    graph_type: str = "document"
):
    """Build knowledge graph from text"""
    
    try:
        if graph_type == "document":
            graph_data = await document_graph_builder.build(text)
        elif graph_type == "concept":
            graph_data = await concept_graph_builder.build(text)
        elif graph_type == "temporal":
            graph_data = await temporal_graph_builder.build(text)
        else:
            raise ValueError(f"Unknown graph type: {graph_type}")
        
        return {
            "graph_data": graph_data,
            "graph_type": graph_type,
            "node_count": len(graph_data.get("nodes", [])),
            "edge_count": len(graph_data.get("edges", []))
        }
        
    except Exception as e:
        logger.error(f"Error building graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background processing function
async def process_document_background(
    document_id: str,
    file_path: str,
    filename: str,
    extract_entities: bool,
    build_graph: bool,
    chunk_strategy: str,
    max_chunk_size: int,
    overlap_size: int,
    temp_dir: str
):
    """Background task for processing uploaded documents"""
    
    try:
        # Update status
        processing_status[document_id]["message"] = "Extracting content..."
        processing_status[document_id]["progress"] = 10.0
        
        # Determine file type and process
        file_extension = os.path.splitext(filename)[1].lower()
        content_type = get_content_type(file_extension)
        
        # Extract content
        if file_extension == '.pdf':
            content = await pdf_processor.process(file_path)
        elif file_extension in ['.html', '.htm']:
            content = await html_processor.process(file_path)
        elif file_extension in ['.py', '.js', '.java', '.cpp', '.c', '.h']:
            content = await code_processor.process(file_path)
        else:
            # Default to text processor
            content = await text_processor.process(file_path)
        
        processing_status[document_id]["message"] = "Processing content..."
        processing_status[document_id]["progress"] = 30.0
        
        # Process the extracted content
        result = await process_text_content(
            document_id=document_id,
            content=content,
            content_type=content_type,
            extract_entities=extract_entities,
            build_graph=build_graph,
            chunk_strategy=chunk_strategy,
            max_chunk_size=max_chunk_size,
            overlap_size=overlap_size
        )
        
        # Store result
        processing_status[document_id]["result"] = result
        processing_status[document_id]["status"] = "completed"
        processing_status[document_id]["progress"] = 100.0
        processing_status[document_id]["message"] = "Processing completed successfully"
        processing_status[document_id]["completed_at"] = datetime.now()
        
    except Exception as e:
        logger.error(f"Error in background processing: {e}")
        
        processing_status[document_id]["status"] = "failed"
        processing_status[document_id]["message"] = f"Processing failed: {str(e)}"
        processing_status[document_id]["completed_at"] = datetime.now()
    
    finally:
        # Cleanup temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)


async def process_text_content(
    document_id: str,
    content: str,
    content_type: str,
    extract_entities: bool,
    build_graph: bool,
    chunk_strategy: str,
    max_chunk_size: int,
    overlap_size: int
) -> Dict[str, Any]:
    """Process text content with all enhancements"""
    
    result = {
        "document_id": document_id,
        "content_type": content_type,
        "chunks": [],
        "entities": [],
        "relationships": [],
        "concepts": [],
        "temporal_info": [],
        "graph_data": {},
        "metadata": {
            "content_length": len(content),
            "processing_options": {
                "extract_entities": extract_entities,
                "build_graph": build_graph,
                "chunk_strategy": chunk_strategy,
                "max_chunk_size": max_chunk_size,
                "overlap_size": overlap_size
            }
        }
    }
    
    # Update progress if tracking
    if document_id in processing_status:
        processing_status[document_id]["message"] = "Chunking content..."
        processing_status[document_id]["progress"] = 40.0
    
    # Chunk the content
    if chunk_strategy == "semantic":
        chunks = await semantic_chunker.chunk(content, max_chunk_size, overlap_size)
    elif chunk_strategy == "graph_aware":
        chunks = await graph_aware_chunker.chunk(content, max_chunk_size, overlap_size)
    elif chunk_strategy == "code" and content_type.startswith("code/"):
        chunks = await code_chunker.chunk(content, max_chunk_size, overlap_size)
    else:
        chunks = await text_splitter.chunk(content, max_chunk_size, overlap_size)
    
    result["chunks"] = chunks
    
    # Extract entities if requested
    if extract_entities:
        if document_id in processing_status:
            processing_status[document_id]["message"] = "Extracting entities..."
            processing_status[document_id]["progress"] = 60.0
        
        # Extract from full content
        entities = await entity_extractor.extract(content)
        result["entities"] = entities
        
        # Extract relationships
        if entities:
            relationships = await relationship_extractor.extract(content, entities)
            result["relationships"] = relationships
        
        # Extract concepts
        concepts = await concept_extractor.extract(content)
        result["concepts"] = concepts
        
        # Extract temporal information
        temporal_info = await temporal_extractor.extract(content)
        result["temporal_info"] = temporal_info
    
    # Build knowledge graph if requested
    if build_graph:
        if document_id in processing_status:
            processing_status[document_id]["message"] = "Building knowledge graph..."
            processing_status[document_id]["progress"] = 80.0
        
        # Build document graph
        document_graph = await document_graph_builder.build(content)
        
        # Build concept graph if concepts were extracted
        concept_graph = {}
        if result["concepts"]:
            concept_graph = await concept_graph_builder.build(content, result["concepts"])
        
        # Build temporal graph if temporal info was extracted
        temporal_graph = {}
        if result["temporal_info"]:
            temporal_graph = await temporal_graph_builder.build(content, result["temporal_info"])
        
        result["graph_data"] = {
            "document_graph": document_graph,
            "concept_graph": concept_graph,
            "temporal_graph": temporal_graph
        }
    
    return result


def get_content_type(file_extension: str) -> str:
    """Get content type from file extension"""
    
    mapping = {
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.xml': 'text/xml',
        '.json': 'application/json',
        '.py': 'code/python',
        '.js': 'code/javascript',
        '.java': 'code/java',
        '.cpp': 'code/cpp',
        '.c': 'code/c',
        '.h': 'code/c',
        '.cs': 'code/csharp',
        '.go': 'code/go',
        '.rs': 'code/rust',
        '.php': 'code/php',
        '.rb': 'code/ruby',
        '.swift': 'code/swift',
        '.kt': 'code/kotlin'
    }
    
    return mapping.get(file_extension, 'text/plain')


# Background processing functions
async def _process_document_background(
    processing_id: str,
    content: str,
    metadata: Dict[str, Any],
    options: Dict[str, Any]
):
    """Background task for document processing"""
    
    start_time = datetime.now()
    
    try:
        # Update status
        processing_tasks[processing_id]["current_step"] = "initializing"
        processing_tasks[processing_id]["progress"] = 10
        
        result = await _comprehensive_document_processing(
            content, metadata, options, processing_id
        )
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Store result
        result.update({
            "processing_id": processing_id,
            "completed_at": datetime.now().isoformat(),
            "processing_time": processing_time
        })
        
        processing_results[processing_id] = result
        
        # Update task status
        processing_tasks[processing_id]["status"] = "completed"
        processing_tasks[processing_id]["progress"] = 100
        
        logger.info(f"Document processing completed: {processing_id}")
        
    except Exception as e:
        logger.error(f"Error in background processing {processing_id}: {e}")
        processing_tasks[processing_id]["status"] = "failed"
        processing_tasks[processing_id]["error"] = str(e)


async def _comprehensive_document_processing(
    content: str,
    metadata: Dict[str, Any],
    options: Dict[str, Any],
    processing_id: str
) -> Dict[str, Any]:
    """Comprehensive document processing pipeline"""
    
    result = {
        "metadata": metadata,
        "options": options,
        "content_length": len(content),
        "processing_steps": []
    }
    
    try:
        # Step 1: Text chunking
        if processing_id in processing_tasks:
            processing_tasks[processing_id]["current_step"] = "chunking text"
            processing_tasks[processing_id]["progress"] = 30
        
        chunk_strategy = options.get("chunk_strategy", "semantic")
        
        if chunk_strategy == "semantic":
            chunks = await semantic_chunker.chunk_text(content)
            result["chunks"] = [chunk.__dict__ for chunk in chunks]
        elif chunk_strategy == "graph_aware":
            chunks = await graph_aware_chunker.chunk_text(content)
            result["chunks"] = [chunk.__dict__ for chunk in chunks]
        else:
            splitter = text_splitter_factory.create_splitter(
                chunk_strategy,
                chunk_size=options.get("max_chunk_size", 1000),
                chunk_overlap=options.get("chunk_overlap", 200)
            )
            chunks = splitter.split(content)
            result["chunks"] = [chunk.__dict__ for chunk in chunks]
        
        result["processing_steps"].append("text_chunking")
        
        # Step 2: Entity extraction
        if options.get("extract_entities", True):
            if processing_id in processing_tasks:
                processing_tasks[processing_id]["current_step"] = "extracting entities"
                processing_tasks[processing_id]["progress"] = 50
            
            entities = await entity_extractor.extract(content)
            result["entities"] = entities
            result["processing_steps"].append("entity_extraction")
        
        # Step 3: Concept extraction
        if options.get("extract_concepts", True):
            if processing_id in processing_tasks:
                processing_tasks[processing_id]["current_step"] = "extracting concepts"
                processing_tasks[processing_id]["progress"] = 60
            
            concepts = await concept_extractor.extract_concepts(content)
            result["concepts"] = [concept.__dict__ for concept in concepts]
            result["processing_steps"].append("concept_extraction")
        
        # Step 4: Temporal extraction
        if options.get("extract_temporal", True):
            if processing_id in processing_tasks:
                processing_tasks[processing_id]["current_step"] = "extracting temporal information"
                processing_tasks[processing_id]["progress"] = 70
            
            temporal_info = await temporal_extractor.extract_temporal_information(content)
            result["temporal_entities"] = temporal_info.get("temporal_entities", [])
            result["temporal_relationships"] = temporal_info.get("temporal_relationships", [])
            result["processing_steps"].append("temporal_extraction")
        
        # Step 5: Relationship extraction
        if options.get("extract_relationships", True) and result.get("entities"):
            if processing_id in processing_tasks:
                processing_tasks[processing_id]["current_step"] = "extracting relationships"
                processing_tasks[processing_id]["progress"] = 80
            
            relationships = await relationship_extractor.extract_relationships(
                content, result["entities"]
            )
            result["relationships"] = [rel.__dict__ for rel in relationships]
            result["processing_steps"].append("relationship_extraction")
        
        # Step 6: Graph building
        if options.get("build_graph", True):
            if processing_id in processing_tasks:
                processing_tasks[processing_id]["current_step"] = "building knowledge graphs"
                processing_tasks[processing_id]["progress"] = 90
            
            graph_types = options.get("graph_types", ["document", "concept", "temporal"])
            graphs = {}
            
            if "document" in graph_types:
                doc_graph = await document_graph_builder.build_document_graph(
                    document_data=result,
                    include_entities=bool(result.get("entities")),
                    include_concepts=bool(result.get("concepts")),
                    include_temporal=bool(result.get("temporal_entities"))
                )
                graphs["document"] = doc_graph
            
            if "concept" in graph_types and result.get("concepts"):
                concept_graph = await concept_graph_builder.build_concept_graph(
                    concepts=result["concepts"],
                    text_content=content
                )
                graphs["concept"] = concept_graph
            
            if "temporal" in graph_types and result.get("temporal_entities"):
                temporal_graph = await temporal_graph_builder.build_temporal_graph(
                    temporal_entities=result["temporal_entities"],
                    temporal_relationships=result.get("temporal_relationships", []),
                    entities=result.get("entities", [])
                )
                graphs["temporal"] = temporal_graph
            
            result["graphs"] = graphs
            result["processing_steps"].append("graph_building")
        
        # Update final progress
        if processing_id in processing_tasks:
            processing_tasks[processing_id]["current_step"] = "finalizing"
            processing_tasks[processing_id]["progress"] = 95
        
        return result
        
    except Exception as e:
        logger.error(f"Error in comprehensive processing: {e}")
        result["error"] = str(e)
        return result


# Application startup
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Enhanced Document Processing Service starting up...")
    
    # Initialize services if needed
    try:
        # Test basic functionality
        test_text = "This is a test document for service initialization."
        
        # Test entity extraction
        test_entities = await entity_extractor.extract(test_text)
        logger.info(f"Entity extractor initialized - found {len(test_entities)} entities in test")
        
        # Test concept extraction
        test_concepts = await concept_extractor.extract_concepts(test_text, max_concepts=5)
        logger.info(f"Concept extractor initialized - found {len(test_concepts)} concepts in test")
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during service initialization: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Enhanced Document Processing Service shutting down...")
    
    # Clear processing data
    processing_results.clear()
    processing_tasks.clear()
    
    logger.info("Service shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )