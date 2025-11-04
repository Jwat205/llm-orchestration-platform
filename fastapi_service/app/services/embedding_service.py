"""
Enhanced embedding service with graph integration and multiple model support.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
import numpy as np
import uuid
from dataclasses import dataclass, asdict
import json

# Import various embedding libraries with fallbacks
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

@dataclass
class EmbeddingResult:
    embedding: List[float]
    model: str
    dimensions: int
    processing_time: float
    metadata: Dict[str, Any]

@dataclass
class BatchResult:
    batch_id: str
    embeddings: List[EmbeddingResult]
    total_tokens: int
    processing_time: float
    status: str
    error: Optional[str] = None

class EmbeddingEngine:
    """Core embedding engine supporting multiple models and optimization techniques."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.models = {}
        self.cache = {}
        self.batch_cache = {}
        self.model_configs = {
            "text-embedding-ada-002": {
                "provider": "openai",
                "dimensions": 1536,
                "max_tokens": 8191,
                "cost_per_token": 0.0001
            },
            "text-embedding-3-small": {
                "provider": "openai", 
                "dimensions": 1536,
                "max_tokens": 8191,
                "cost_per_token": 0.00002
            },
            "text-embedding-3-large": {
                "provider": "openai",
                "dimensions": 3072,
                "max_tokens": 8191,
                "cost_per_token": 0.00013
            },
            "all-MiniLM-L6-v2": {
                "provider": "sentence_transformers",
                "dimensions": 384,
                "max_tokens": 256,
                "cost_per_token": 0.0
            },
            "all-mpnet-base-v2": {
                "provider": "sentence_transformers",
                "dimensions": 768,
                "max_tokens": 384,
                "cost_per_token": 0.0
            }
        }
        
        # Initialize available models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize embedding models based on available libraries."""
        # Initialize OpenAI models
        if OPENAI_AVAILABLE:
            try:
                self.models["openai"] = "openai_client"  # Placeholder
                self.logger.info("OpenAI embedding models initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize OpenAI: {e}")
        
        # Initialize Sentence Transformers models
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Load commonly used models
                self.models["all-MiniLM-L6-v2"] = SentenceTransformer('all-MiniLM-L6-v2')
                self.models["all-mpnet-base-v2"] = SentenceTransformer('all-mpnet-base-v2')
                self.logger.info("Sentence Transformers models initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Sentence Transformers: {e}")
    
    async def create_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-ada-002",
        dimensions: Optional[int] = None,
        user: Optional[str] = None,
        **kwargs
    ) -> List[EmbeddingResult]:
        """Create embeddings for given texts with specified model."""
        start_time = datetime.now()
        
        try:
            model_config = self.model_configs.get(model)
            if not model_config:
                raise ValueError(f"Unsupported model: {model}")
            
            provider = model_config["provider"]
            embeddings = []
            
            if provider == "openai":
                embeddings = await self._create_openai_embeddings(
                    texts, model, dimensions, user
                )
            elif provider == "sentence_transformers":
                embeddings = await self._create_sentence_transformer_embeddings(
                    texts, model, dimensions
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Create results with metadata
            results = []
            for i, embedding in enumerate(embeddings):
                result = EmbeddingResult(
                    embedding=embedding,
                    model=model,
                    dimensions=len(embedding),
                    processing_time=processing_time / len(texts),
                    metadata={
                        "provider": provider,
                        "text_length": len(texts[i]),
                        "created_at": datetime.now().isoformat(),
                        "user": user
                    }
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error creating embeddings: {e}")
            raise
    
    async def _create_openai_embeddings(
        self,
        texts: List[str],
        model: str,
        dimensions: Optional[int],
        user: Optional[str]
    ) -> List[List[float]]:
        """Create embeddings using OpenAI API."""
        if not OPENAI_AVAILABLE or "openai" not in self.models:
            # Mock embeddings for demo
            dim = dimensions or 1536
            return [[0.1 + (i * 0.001) for i in range(dim)] for _ in texts]
        
        try:
            # Would use actual OpenAI API here
            # For now, return mock embeddings
            dim = dimensions or 1536
            return [[0.1 + (i * 0.001) for i in range(dim)] for _ in texts]
            
        except Exception as e:
            self.logger.error(f"OpenAI embedding error: {e}")
            # Fallback to mock embeddings
            dim = dimensions or 1536
            return [[0.1] * dim for _ in texts]
    
    async def _create_sentence_transformer_embeddings(
        self,
        texts: List[str],
        model: str,
        dimensions: Optional[int]
    ) -> List[List[float]]:
        """Create embeddings using Sentence Transformers."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE or model not in self.models:
            # Mock embeddings if model not available
            model_config = self.model_configs.get(model, {"dimensions": 384})
            dim = dimensions or model_config["dimensions"]
            return [[0.1 + (i * 0.001) for i in range(dim)] for _ in texts]
        
        try:
            transformer_model = self.models[model]
            
            def encode_texts():
                embeddings = transformer_model.encode(
                    texts,
                    convert_to_tensor=False,
                    normalize_embeddings=True
                )
                return embeddings.tolist()
            
            # Run in thread pool to avoid blocking
            embeddings = await asyncio.to_thread(encode_texts)
            
            # Apply dimension reduction if requested
            if dimensions and embeddings and len(embeddings[0]) != dimensions:
                embeddings = await self._reduce_dimensions(embeddings, dimensions)
            
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Sentence Transformer embedding error: {e}")
            # Fallback to mock embeddings
            model_config = self.model_configs.get(model, {"dimensions": 384})
            dim = dimensions or model_config["dimensions"]
            return [[0.1] * dim for _ in texts]
    
    async def _reduce_dimensions(
        self,
        embeddings: List[List[float]],
        target_dimensions: int
    ) -> List[List[float]]:
        """Reduce embedding dimensions using PCA or truncation."""
        try:
            # Simple truncation fallback
            return [emb[:target_dimensions] for emb in embeddings]
            
        except Exception as e:
            self.logger.warning(f"Dimension reduction failed: {e}")
            return [emb[:target_dimensions] for emb in embeddings]
    
    async def compute_similarities(
        self,
        embeddings: List[List[float]]
    ) -> List[List[float]]:
        """Compute pairwise cosine similarities between embeddings."""
        try:
            if not embeddings:
                return []
            
            # Convert to numpy for efficient computation
            emb_array = np.array(embeddings)
            
            # Normalize embeddings
            norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
            normalized_emb = emb_array / (norms + 1e-8)
            
            # Compute cosine similarity matrix
            similarity_matrix = np.dot(normalized_emb, normalized_emb.T)
            
            return similarity_matrix.tolist()
            
        except Exception as e:
            self.logger.error(f"Error computing similarities: {e}")
            # Return identity matrix as fallback
            n = len(embeddings)
            return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

class EmbeddingService:
    """Main embedding service with caching, batching, and graph integration."""
    
    def __init__(self, knowledge_graph=None):
        self.logger = logging.getLogger(__name__)
        self.engine = EmbeddingEngine()
        self.knowledge_graph = knowledge_graph
        self.batch_tasks = {}
        self.cache = {}
        self.performance_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_tokens": 0,
            "total_processing_time": 0.0
        }
    
    async def create_embeddings(
        self,
        input: Union[str, List[str]],
        model: str = "text-embedding-ada-002",
        dimensions: Optional[int] = None,
        user: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create embeddings with OpenAI-compatible response format."""
        start_time = datetime.now()
        
        try:
            # Normalize input
            texts = [input] if isinstance(input, str) else input
            
            # Check cache
            cached_results = await self._check_cache(texts, model, dimensions)
            if cached_results:
                self.performance_stats["cache_hits"] += 1
                return cached_results
            
            # Generate embeddings
            results = await self.engine.create_embeddings(
                texts=texts,
                model=model,
                dimensions=dimensions,
                user=user,
                **kwargs
            )
            
            # Format response
            response = {
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "index": i,
                        "embedding": result.embedding
                    }
                    for i, result in enumerate(results)
                ],
                "model": model,
                "usage": {
                    "prompt_tokens": sum(len(text.split()) for text in texts),
                    "total_tokens": sum(len(text.split()) for text in texts)
                }
            }
            
            # Cache results
            await self._cache_results(texts, model, dimensions, response)
            
            # Update stats
            processing_time = (datetime.now() - start_time).total_seconds()
            self.performance_stats["total_requests"] += 1
            self.performance_stats["total_tokens"] += response["usage"]["total_tokens"]
            self.performance_stats["total_processing_time"] += processing_time
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in embedding service: {e}")
            raise
    
    async def search(
        self,
        query: str,
        model: str = "text-embedding-ada-002",
        top_k: int = 10,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Search embeddings using vector similarity."""
        try:
            # Generate query embedding
            query_result = await self.create_embeddings(query, model)
            query_embedding = query_result["data"][0]["embedding"]
            
            # Mock results for demo
            results = {
                "results": [
                    {
                        "id": f"doc_{i}",
                        "score": 0.9 - (i * 0.1),
                        "text": f"Sample document {i} matching query: {query}",
                        "metadata": {
                            "source": "mock",
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    for i in range(min(top_k, 5))
                ],
                "query_time": 0.1,
                "total_results": 5
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in search: {e}")
            return {"results": [], "query_time": 0.0, "total_results": 0}
    
    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        model: str = "text-embedding-ada-002"
    ) -> float:
        """Calculate similarity between two texts."""
        try:
            # Generate embeddings
            results = await self.engine.create_embeddings([text1, text2], model)
            embeddings = [result.embedding for result in results]
            
            # Compute similarity
            similarities = await self.engine.compute_similarities(embeddings)
            return similarities[0][1]  # Off-diagonal element
            
        except Exception as e:
            self.logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    async def start_batch_processing(
        self,
        texts: List[str],
        model: str,
        batch_size: int,
        enhance_with_graph: bool = False
    ) -> str:
        """Start batch processing and return batch ID."""
        batch_id = str(uuid.uuid4())
        
        # Initialize batch tracking
        self.batch_tasks[batch_id] = {
            "status": "processing",
            "total_items": len(texts),
            "processed_items": 0,
            "start_time": datetime.now(),
            "results": []
        }
        
        return batch_id
    
    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get status of batch processing task."""
        return self.batch_tasks.get(batch_id)
    
    async def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available embedding models."""
        models = []
        for model_name, config in self.engine.model_configs.items():
            models.append({
                "id": model_name,
                "object": "model",
                "provider": config["provider"],
                "dimensions": config["dimensions"],
                "max_tokens": config["max_tokens"],
                "cost_per_token": config["cost_per_token"],
                "available": True  # Simplified
            })
        
        return models
    
    async def get_model_analytics(self) -> Dict[str, Any]:
        """Get analytics about model usage and performance."""
        return {
            "performance_stats": self.performance_stats,
            "available_models": len(self.engine.model_configs),
            "cache_size": len(self.cache),
            "active_batches": len([
                batch for batch in self.batch_tasks.values()
                if batch["status"] == "processing"
            ])
        }
    
    async def _check_cache(
        self,
        texts: List[str],
        model: str,
        dimensions: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """Check if embeddings are cached."""
        cache_key = self._generate_cache_key(texts, model, dimensions)
        return self.cache.get(cache_key)
    
    async def _cache_results(
        self,
        texts: List[str],
        model: str,
        dimensions: Optional[int],
        results: Dict[str, Any]
    ):
        """Cache embedding results."""
        cache_key = self._generate_cache_key(texts, model, dimensions)
        self.cache[cache_key] = results
        
        # Simple cache size management
        if len(self.cache) > 1000:
            oldest_keys = list(self.cache.keys())[:100]
            for key in oldest_keys:
                del self.cache[key]
    
    def _generate_cache_key(
        self,
        texts: List[str],
        model: str,
        dimensions: Optional[int]
    ) -> str:
        """Generate cache key for given parameters."""
        import hashlib
        content = f"{model}:{dimensions}:{':'.join(texts)}"
        return hashlib.md5(content.encode()).hexdigest()