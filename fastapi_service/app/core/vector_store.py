"""
Enhanced vector database with multiple backend support and graph integration.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np
import json
import uuid
from abc import ABC, abstractmethod

# Import vector database libraries with fallbacks
try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

@dataclass
class VectorDocument:
    id: str
    vector: List[float]
    metadata: Dict[str, Any]
    text: Optional[str] = None
    namespace: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class SearchResult:
    id: str
    score: float
    metadata: Dict[str, Any]
    text: Optional[str] = None
    vector: Optional[List[float]] = None

class VectorStoreInterface(ABC):
    """Abstract interface for vector store implementations."""
    
    @abstractmethod
    async def upsert(self, documents: List[VectorDocument]) -> Dict[str, Any]:
        """Insert or update documents in the vector store."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> bool:
        """Delete documents by IDs."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        pass

class PineconeStore(VectorStoreInterface):
    """Pinecone vector store implementation."""
    
    def __init__(self, api_key: str, environment: str, index_name: str):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        self.index = None
        
        if not PINECONE_AVAILABLE:
            self.logger.warning("Pinecone not available, using mock implementation")
    
    async def initialize(self):
        """Initialize Pinecone connection."""
        if not PINECONE_AVAILABLE:
            return
        
        try:
            pinecone.init(api_key=self.api_key, environment=self.environment)
            self.index = pinecone.Index(self.index_name)
            self.logger.info(f"Pinecone index '{self.index_name}' initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Pinecone: {e}")
    
    async def upsert(self, documents: List[VectorDocument]) -> Dict[str, Any]:
        """Insert or update documents in Pinecone."""
        if not PINECONE_AVAILABLE or not self.index:
            return {"upserted_count": len(documents), "status": "mock"}
        
        try:
            vectors = []
            for doc in documents:
                vector_data = {
                    "id": doc.id,
                    "values": doc.vector,
                    "metadata": doc.metadata
                }
                if doc.namespace:
                    vector_data["namespace"] = doc.namespace
                vectors.append(vector_data)
            
            response = self.index.upsert(vectors=vectors)
            return {"upserted_count": response.upserted_count}
            
        except Exception as e:
            self.logger.error(f"Pinecone upsert error: {e}")
            return {"upserted_count": 0, "error": str(e)}
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search vectors in Pinecone."""
        if not PINECONE_AVAILABLE or not self.index:
            # Mock search results
            return [
                SearchResult(
                    id=f"mock_{i}",
                    score=0.9 - (i * 0.1),
                    metadata={"source": "mock", "index": i},
                    text=f"Mock document {i}"
                )
                for i in range(min(top_k, 3))
            ]
        
        try:
            query_params = {
                "vector": query_vector,
                "top_k": top_k,
                "include_metadata": True
            }
            
            if filters:
                query_params["filter"] = filters
            if namespace:
                query_params["namespace"] = namespace
            
            response = self.index.query(**query_params)
            
            results = []
            for match in response.matches:
                results.append(SearchResult(
                    id=match.id,
                    score=match.score,
                    metadata=match.metadata or {},
                    vector=match.values if hasattr(match, 'values') else None
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Pinecone search error: {e}")
            return []
    
    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> bool:
        """Delete vectors from Pinecone."""
        if not PINECONE_AVAILABLE or not self.index:
            return True
        
        try:
            delete_params = {"ids": ids}
            if namespace:
                delete_params["namespace"] = namespace
            
            self.index.delete(**delete_params)
            return True
            
        except Exception as e:
            self.logger.error(f"Pinecone delete error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Pinecone index statistics."""
        if not PINECONE_AVAILABLE or not self.index:
            return {"total_vectors": 1000, "dimensions": 1536, "index_fullness": 0.1}
        
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimensions": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": stats.namespaces
            }
        except Exception as e:
            self.logger.error(f"Pinecone stats error: {e}")
            return {}

class ChromaStore(VectorStoreInterface):
    """Chroma vector store implementation."""
    
    def __init__(self, collection_name: str = "default", persist_directory: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        
        if not CHROMA_AVAILABLE:
            self.logger.warning("Chroma not available, using mock implementation")
    
    async def initialize(self):
        """Initialize Chroma client."""
        if not CHROMA_AVAILABLE:
            return
        
        try:
            if self.persist_directory:
                self.client = chromadb.PersistentClient(path=self.persist_directory)
            else:
                self.client = chromadb.Client()
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self.logger.info(f"Chroma collection '{self.collection_name}' initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Chroma: {e}")
    
    async def upsert(self, documents: List[VectorDocument]) -> Dict[str, Any]:
        """Insert documents into Chroma."""
        if not CHROMA_AVAILABLE or not self.collection:
            return {"upserted_count": len(documents), "status": "mock"}
        
        try:
            ids = [doc.id for doc in documents]
            embeddings = [doc.vector for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            documents_text = [doc.text or "" for doc in documents]
            
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents_text
            )
            
            return {"upserted_count": len(documents)}
            
        except Exception as e:
            self.logger.error(f"Chroma upsert error: {e}")
            return {"upserted_count": 0, "error": str(e)}
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search vectors in Chroma."""
        if not CHROMA_AVAILABLE or not self.collection:
            # Mock search results
            return [
                SearchResult(
                    id=f"chroma_mock_{i}",
                    score=0.8 - (i * 0.1),
                    metadata={"source": "chroma_mock", "index": i},
                    text=f"Chroma mock document {i}"
                )
                for i in range(min(top_k, 3))
            ]
        
        try:
            query_params = {
                "query_embeddings": [query_vector],
                "n_results": top_k,
                "include": ["metadatas", "documents", "distances"]
            }
            
            if filters:
                query_params["where"] = filters
            
            results = self.collection.query(**query_params)
            
            search_results = []
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"][0]):
                    score = 1.0 - results["distances"][0][i]  # Convert distance to similarity
                    search_results.append(SearchResult(
                        id=doc_id,
                        score=score,
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        text=results["documents"][0][i] if results["documents"] else None
                    ))
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"Chroma search error: {e}")
            return []
    
    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> bool:
        """Delete documents from Chroma."""
        if not CHROMA_AVAILABLE or not self.collection:
            return True
        
        try:
            self.collection.delete(ids=ids)
            return True
        except Exception as e:
            self.logger.error(f"Chroma delete error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Chroma collection statistics."""
        if not CHROMA_AVAILABLE or not self.collection:
            return {"total_vectors": 500, "collection_name": self.collection_name}
        
        try:
            count = self.collection.count()
            return {
                "total_vectors": count,
                "collection_name": self.collection_name
            }
        except Exception as e:
            self.logger.error(f"Chroma stats error: {e}")
            return {}

class FAISSStore(VectorStoreInterface):
    """FAISS vector store implementation."""
    
    def __init__(self, dimension: int = 1536, index_type: str = "IndexFlatIP"):
        self.logger = logging.getLogger(__name__)
        self.dimension = dimension
        self.index_type = index_type
        self.index = None
        self.id_map = {}  # Map FAISS indices to document IDs
        self.document_store = {}  # Store document metadata
        
        if not FAISS_AVAILABLE:
            self.logger.warning("FAISS not available, using mock implementation")
    
    async def initialize(self):
        """Initialize FAISS index."""
        if not FAISS_AVAILABLE:
            return
        
        try:
            if self.index_type == "IndexFlatIP":
                self.index = faiss.IndexFlatIP(self.dimension)
            elif self.index_type == "IndexIVFFlat":
                quantizer = faiss.IndexFlatIP(self.dimension)
                self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            else:
                self.index = faiss.IndexFlatL2(self.dimension)
            
            self.logger.info(f"FAISS index initialized with type {self.index_type}")
        except Exception as e:
            self.logger.error(f"Failed to initialize FAISS: {e}")
    
    async def upsert(self, documents: List[VectorDocument]) -> Dict[str, Any]:
        """Insert documents into FAISS."""
        if not FAISS_AVAILABLE or not self.index:
            return {"upserted_count": len(documents), "status": "mock"}
        
        try:
            vectors = np.array([doc.vector for doc in documents], dtype=np.float32)
            
            # Get current index size for ID mapping
            start_idx = self.index.ntotal
            
            # Add vectors to index
            self.index.add(vectors)
            
            # Update ID mappings and document store
            for i, doc in enumerate(documents):
                faiss_idx = start_idx + i
                self.id_map[doc.id] = faiss_idx
                self.document_store[doc.id] = {
                    "metadata": doc.metadata,
                    "text": doc.text,
                    "created_at": doc.created_at or datetime.now()
                }
            
            return {"upserted_count": len(documents)}
            
        except Exception as e:
            self.logger.error(f"FAISS upsert error: {e}")
            return {"upserted_count": 0, "error": str(e)}
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search vectors in FAISS."""
        if not FAISS_AVAILABLE or not self.index:
            # Mock search results
            return [
                SearchResult(
                    id=f"faiss_mock_{i}",
                    score=0.85 - (i * 0.05),
                    metadata={"source": "faiss_mock", "index": i},
                    text=f"FAISS mock document {i}"
                )
                for i in range(min(top_k, 3))
            ]
        
        try:
            query_array = np.array([query_vector], dtype=np.float32)
            scores, indices = self.index.search(query_array, top_k)
            
            results = []
            reverse_id_map = {v: k for k, v in self.id_map.items()}
            
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx == -1:  # Invalid index
                    continue
                
                doc_id = reverse_id_map.get(idx)
                if not doc_id:
                    continue
                
                doc_data = self.document_store.get(doc_id, {})
                
                # Apply filters if specified
                if filters and not self._matches_filters(doc_data.get("metadata", {}), filters):
                    continue
                
                results.append(SearchResult(
                    id=doc_id,
                    score=float(score),
                    metadata=doc_data.get("metadata", {}),
                    text=doc_data.get("text")
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"FAISS search error: {e}")
            return []
    
    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if metadata matches the given filters."""
        for key, value in filters.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True
    
    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> bool:
        """Delete documents from FAISS (limited support)."""
        if not FAISS_AVAILABLE or not self.index:
            return True
        
        # FAISS doesn't support direct deletion, so we remove from our mappings
        try:
            for doc_id in ids:
                if doc_id in self.id_map:
                    del self.id_map[doc_id]
                if doc_id in self.document_store:
                    del self.document_store[doc_id]
            return True
        except Exception as e:
            self.logger.error(f"FAISS delete error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get FAISS index statistics."""
        if not FAISS_AVAILABLE or not self.index:
            return {"total_vectors": 750, "dimensions": self.dimension}
        
        try:
            return {
                "total_vectors": self.index.ntotal,
                "dimensions": self.dimension,
                "index_type": self.index_type,
                "is_trained": self.index.is_trained
            }
        except Exception as e:
            self.logger.error(f"FAISS stats error: {e}")
            return {}

class VectorStore:
    """Main vector store with multiple backend support and graph integration."""
    
    def __init__(self, backend: str = "chroma", **backend_config):
        self.logger = logging.getLogger(__name__)
        self.backend = backend
        self.store = None
        self.graph_service = None
        
        # Initialize the appropriate backend
        if backend == "pinecone":
            self.store = PineconeStore(**backend_config)
        elif backend == "chroma":
            self.store = ChromaStore(**backend_config)
        elif backend == "faiss":
            self.store = FAISSStore(**backend_config)
        else:
            raise ValueError(f"Unsupported backend: {backend}")
    
    async def initialize(self, graph_service=None):
        """Initialize vector store and optional graph service."""
        await self.store.initialize()
        self.graph_service = graph_service
        if graph_service:
            self.logger.info("Graph service integration enabled")
    
    async def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        namespace: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Enhanced similarity search with optional graph enrichment."""
        try:
            # Perform vector search
            results = await self.store.search(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters,
                namespace=namespace
            )
            
            # Convert to dict format
            search_results = []
            for result in results:
                result_dict = {
                    "id": result.id,
                    "score": result.score,
                    "text": result.text,
                }
                
                if include_metadata:
                    result_dict["metadata"] = result.metadata
                
                search_results.append(result_dict)
            
            # Enhance with graph information if available
            if self.graph_service and search_results:
                enhanced_results = await self._enhance_with_graph_context(search_results)
                return enhanced_results
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"Error in similarity search: {e}")
            return []
    
    async def hybrid_search(
        self,
        query_vector: List[float],
        graph_entities: List[str],
        top_k: int = 10,
        vector_weight: float = 0.7,
        graph_weight: float = 0.3,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining vector similarity and graph traversal."""
        try:
            # Vector search
            vector_results = await self.similarity_search(
                query_vector=query_vector,
                top_k=top_k * 2,  # Get more candidates
                **kwargs
            )
            
            # Graph search (if graph service available)
            graph_results = []
            if self.graph_service and graph_entities:
                graph_results = await self.graph_service.search_by_entities(
                    entities=graph_entities,
                    max_results=top_k * 2
                )
            
            # Combine and re-rank results
            combined_results = await self._combine_search_results(
                vector_results=vector_results,
                graph_results=graph_results,
                vector_weight=vector_weight,
                graph_weight=graph_weight
            )
            
            return combined_results[:top_k]
            
        except Exception as e:
            self.logger.error(f"Error in hybrid search: {e}")
            return []
    
    async def upsert_documents(
        self,
        documents: List[Dict[str, Any]],
        extract_entities: bool = False,
        build_graph: bool = False
    ) -> Dict[str, Any]:
        """Insert/update documents with optional graph enhancement."""
        try:
            # Convert to VectorDocument objects
            vector_docs = []
            for doc in documents:
                vector_doc = VectorDocument(
                    id=doc.get("id", str(uuid.uuid4())),
                    vector=doc["vector"],
                    metadata=doc.get("metadata", {}),
                    text=doc.get("text"),
                    namespace=doc.get("namespace"),
                    created_at=datetime.now()
                )
                vector_docs.append(vector_doc)
            
            # Insert into vector store
            result = await self.store.upsert(vector_docs)
            
            # Enhance with graph processing if requested
            if self.graph_service and (extract_entities or build_graph):
                graph_result = await self._process_documents_for_graph(
                    documents, extract_entities, build_graph
                )
                result["graph_processing"] = graph_result
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error upserting documents: {e}")
            return {"upserted_count": 0, "error": str(e)}
    
    async def delete_documents(
        self,
        ids: List[str],
        namespace: Optional[str] = None,
        cleanup_graph: bool = False
    ) -> bool:
        """Delete documents and optionally clean up graph data."""
        try:
            # Delete from vector store
            success = await self.store.delete(ids, namespace)
            
            # Clean up graph data if requested
            if success and cleanup_graph and self.graph_service:
                await self.graph_service.cleanup_document_entities(ids)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error deleting documents: {e}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive vector store statistics."""
        try:
            stats = await self.store.get_stats()
            stats["backend"] = self.backend
            stats["graph_integration"] = self.graph_service is not None
            
            if self.graph_service:
                graph_stats = await self.graph_service.get_statistics()
                stats["graph_stats"] = graph_stats
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    async def _enhance_with_graph_context(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enhance search results with graph context."""
        if not self.graph_service:
            return search_results
        
        try:
            enhanced_results = []
            
            for result in search_results:
                # Extract entities from result text
                text = result.get("text", "")
                if text:
                    entities = await self.graph_service.extract_entities(text)
                    if entities:
                        # Get graph context for entities
                        graph_context = await self.graph_service.get_entity_context(entities)
                        result["graph_context"] = graph_context
                        result["entities"] = entities
                
                enhanced_results.append(result)
            
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"Error enhancing with graph context: {e}")
            return search_results
    
    async def _combine_search_results(
        self,
        vector_results: List[Dict[str, Any]],
        graph_results: List[Dict[str, Any]],
        vector_weight: float,
        graph_weight: float
    ) -> List[Dict[str, Any]]:
        """Combine vector and graph search results with weighted scoring."""
        try:
            # Create a combined results dictionary
            combined = {}
            
            # Add vector results
            for result in vector_results:
                doc_id = result["id"]
                combined[doc_id] = result.copy()
                combined[doc_id]["vector_score"] = result["score"]
                combined[doc_id]["graph_score"] = 0.0
                combined[doc_id]["combined_score"] = result["score"] * vector_weight
            
            # Add graph results
            for result in graph_results:
                doc_id = result["id"]
                graph_score = result.get("score", 0.5)
                
                if doc_id in combined:
                    # Update existing result
                    combined[doc_id]["graph_score"] = graph_score
                    combined[doc_id]["combined_score"] = (
                        combined[doc_id]["vector_score"] * vector_weight +
                        graph_score * graph_weight
                    )
                else:
                    # Add new result
                    combined[doc_id] = result.copy()
                    combined[doc_id]["vector_score"] = 0.0
                    combined[doc_id]["graph_score"] = graph_score
                    combined[doc_id]["combined_score"] = graph_score * graph_weight
            
            # Sort by combined score
            sorted_results = sorted(
                combined.values(),
                key=lambda x: x["combined_score"],
                reverse=True
            )
            
            # Update final scores
            for result in sorted_results:
                result["score"] = result["combined_score"]
            
            return sorted_results
            
        except Exception as e:
            self.logger.error(f"Error combining search results: {e}")
            return vector_results
    
    async def _process_documents_for_graph(
        self,
        documents: List[Dict[str, Any]],
        extract_entities: bool,
        build_graph: bool
    ) -> Dict[str, Any]:
        """Process documents for graph enhancement."""
        if not self.graph_service:
            return {"status": "no_graph_service"}
        
        try:
            result = {"entities": [], "relationships": []}
            
            if extract_entities:
                texts = [doc.get("text", "") for doc in documents if doc.get("text")]
                entities = await self.graph_service.extract_entities_batch(texts)
                result["entities"] = entities
            
            if build_graph:
                # Build relationships between documents
                relationships = await self.graph_service.build_document_graph(documents)
                result["relationships"] = relationships
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing documents for graph: {e}")
            return {"error": str(e)}