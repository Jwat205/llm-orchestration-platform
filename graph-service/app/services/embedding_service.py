"""
Embedding Service for Knowledge Graph.
Handles vector embeddings for entities, relationships, and semantic search.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from datetime import datetime
import json
import hashlib

try:
    import sentence_transformers
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

class EmbeddingService:
    """Service for generating and managing embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_size: int = 10000):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.model = None
        self.embedding_cache = {}
        self.cache_size = cache_size
        self.embedding_dim = 384  # Default for MiniLM
        
        # Statistics
        self.stats = {
            "embeddings_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0
        }
    
    async def initialize(self):
        """Initialize embedding service"""
        try:
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.model = SentenceTransformer(self.model_name)
                self.embedding_dim = self.model.get_sentence_embedding_dimension()
                self.logger.info(f"Loaded SentenceTransformer model: {self.model_name}")
            else:
                self.logger.warning("SentenceTransformers not available, using mock embeddings")
            
            self.logger.info("Embedding service initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing embedding service: {e}")
            raise
    
    async def get_embedding(self, text: str, embedding_type: str = "text") -> List[float]:
        """Get embedding for text"""
        try:
            self.stats["total_requests"] += 1
            
            # Check cache
            cache_key = self._get_cache_key(text, embedding_type)
            if cache_key in self.embedding_cache:
                self.stats["cache_hits"] += 1
                return self.embedding_cache[cache_key]
            
            self.stats["cache_misses"] += 1
            
            # Generate embedding
            if embedding_type == "text":
                embedding = await self._generate_text_embedding(text)
            elif embedding_type == "entity":
                embedding = await self._generate_entity_embedding(text)
            elif embedding_type == "relationship":
                embedding = await self._generate_relationship_embedding(text)
            else:
                embedding = await self._generate_text_embedding(text)
            
            # Cache embedding
            self._cache_embedding(cache_key, embedding)
            
            self.stats["embeddings_generated"] += 1
            return embedding
            
        except Exception as e:
            self.logger.error(f"Error getting embedding: {e}")
            return self._get_zero_embedding()
    
    async def get_embeddings_batch(self, texts: List[str], 
                                 embedding_type: str = "text") -> List[List[float]]:
        """Get embeddings for multiple texts efficiently"""
        try:
            embeddings = []
            uncached_texts = []
            uncached_indices = []
            
            # Check cache for each text
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text, embedding_type)
                if cache_key in self.embedding_cache:
                    embeddings.append(self.embedding_cache[cache_key])
                    self.stats["cache_hits"] += 1
                else:
                    embeddings.append(None)  # Placeholder
                    uncached_texts.append(text)
                    uncached_indices.append(i)
                    self.stats["cache_misses"] += 1
            
            # Generate embeddings for uncached texts
            if uncached_texts:
                if embedding_type == "text":
                    batch_embeddings = await self._generate_text_embeddings_batch(uncached_texts)
                elif embedding_type == "entity":
                    batch_embeddings = await self._generate_entity_embeddings_batch(uncached_texts)
                else:
                    batch_embeddings = await self._generate_text_embeddings_batch(uncached_texts)
                
                # Fill in the embeddings and cache them
                for i, embedding in enumerate(batch_embeddings):
                    idx = uncached_indices[i]
                    embeddings[idx] = embedding
                    
                    # Cache embedding
                    cache_key = self._get_cache_key(uncached_texts[i], embedding_type)
                    self._cache_embedding(cache_key, embedding)
            
            self.stats["total_requests"] += len(texts)
            self.stats["embeddings_generated"] += len(uncached_texts)
            
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Error getting batch embeddings: {e}")
            return [self._get_zero_embedding() for _ in texts]
    
    async def _generate_text_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            if self.model and SENTENCE_TRANSFORMERS_AVAILABLE:
                # Use SentenceTransformer
                embedding = self.model.encode(text, convert_to_tensor=False)
                return embedding.tolist()
            
            elif OPENAI_AVAILABLE and openai.api_key:
                # Use OpenAI embeddings
                response = await openai.Embedding.acreate(
                    model="text-embedding-ada-002",
                    input=text
                )
                return response['data'][0]['embedding']
            
            else:
                # Generate mock embedding based on text hash
                return self._generate_mock_embedding(text)
                
        except Exception as e:
            self.logger.error(f"Error generating text embedding: {e}")
            return self._generate_mock_embedding(text)
    
    async def _generate_text_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            if self.model and SENTENCE_TRANSFORMERS_AVAILABLE:
                # Use SentenceTransformer batch processing
                embeddings = self.model.encode(texts, convert_to_tensor=False, batch_size=32)
                return [emb.tolist() for emb in embeddings]
            
            elif OPENAI_AVAILABLE and openai.api_key:
                # Use OpenAI batch processing
                response = await openai.Embedding.acreate(
                    model="text-embedding-ada-002",
                    input=texts
                )
                return [item['embedding'] for item in response['data']]
            
            else:
                # Generate mock embeddings
                return [self._generate_mock_embedding(text) for text in texts]
                
        except Exception as e:
            self.logger.error(f"Error generating batch embeddings: {e}")
            return [self._generate_mock_embedding(text) for text in texts]
    
    async def _generate_entity_embedding(self, entity_data: str) -> List[float]:
        """Generate specialized embedding for entity"""
        try:
            # Parse entity data if it's JSON
            if isinstance(entity_data, str) and entity_data.startswith('{'):
                entity = json.loads(entity_data)
                # Create text representation for entity
                text_repr = self._entity_to_text(entity)
            else:
                text_repr = str(entity_data)
            
            # Generate base embedding
            base_embedding = await self._generate_text_embedding(text_repr)
            
            # Add entity-specific modifications (could be learned)
            # For now, just apply a simple transformation
            entity_embedding = [x * 1.1 for x in base_embedding]  # Simple scaling
            
            return entity_embedding
            
        except Exception as e:
            self.logger.error(f"Error generating entity embedding: {e}")
            return self._generate_mock_embedding(entity_data)
    
    async def _generate_entity_embeddings_batch(self, entities: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple entities"""
        embeddings = []
        for entity in entities:
            embedding = await self._generate_entity_embedding(entity)
            embeddings.append(embedding)
        return embeddings
    
    async def _generate_relationship_embedding(self, relationship_data: str) -> List[float]:
        """Generate specialized embedding for relationship"""
        try:
            # Parse relationship data if it's JSON
            if isinstance(relationship_data, str) and relationship_data.startswith('{'):
                relationship = json.loads(relationship_data)
                # Create text representation for relationship
                text_repr = self._relationship_to_text(relationship)
            else:
                text_repr = str(relationship_data)
            
            # Generate base embedding
            base_embedding = await self._generate_text_embedding(text_repr)
            
            # Add relationship-specific modifications
            relationship_embedding = [x * 0.9 for x in base_embedding]  # Simple scaling
            
            return relationship_embedding
            
        except Exception as e:
            self.logger.error(f"Error generating relationship embedding: {e}")
            return self._generate_mock_embedding(relationship_data)
    
    def _entity_to_text(self, entity: Dict[str, Any]) -> str:
        """Convert entity to text representation"""
        parts = []
        
        # Add type
        if "type" in entity:
            parts.append(f"Type: {entity['type']}")
        
        # Add properties
        if "properties" in entity:
            for key, value in entity["properties"].items():
                parts.append(f"{key}: {value}")
        
        # Add name if available
        if "name" in entity:
            parts.insert(0, f"Name: {entity['name']}")
        elif "properties" in entity and "name" in entity["properties"]:
            parts.insert(0, f"Name: {entity['properties']['name']}")
        
        return " | ".join(parts)
    
    def _relationship_to_text(self, relationship: Dict[str, Any]) -> str:
        """Convert relationship to text representation"""
        parts = []
        
        # Add relationship type
        if "type" in relationship:
            parts.append(f"Relationship: {relationship['type']}")
        
        # Add source and target if available
        if "source_id" in relationship and "target_id" in relationship:
            parts.append(f"From: {relationship['source_id']} To: {relationship['target_id']}")
        
        # Add properties
        if "properties" in relationship:
            for key, value in relationship["properties"].items():
                parts.append(f"{key}: {value}")
        
        return " | ".join(parts)
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding based on text"""
        # Use hash to generate consistent embeddings
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Convert hash to numbers
        numbers = []
        for i in range(0, len(text_hash), 2):
            hex_byte = text_hash[i:i+2]
            numbers.append(int(hex_byte, 16) / 255.0 - 0.5)  # Normalize to [-0.5, 0.5]
        
        # Extend or truncate to desired dimension
        while len(numbers) < self.embedding_dim:
            numbers.extend(numbers[:min(len(numbers), self.embedding_dim - len(numbers))])
        
        return numbers[:self.embedding_dim]
    
    def _get_zero_embedding(self) -> List[float]:
        """Get zero embedding as fallback"""
        return [0.0] * self.embedding_dim
    
    def _get_cache_key(self, text: str, embedding_type: str) -> str:
        """Generate cache key"""
        return f"{embedding_type}:{hashlib.md5(text.encode()).hexdigest()}"
    
    def _cache_embedding(self, cache_key: str, embedding: List[float]):
        """Cache embedding with size management"""
        if len(self.embedding_cache) >= self.cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.embedding_cache.keys())[:len(self.embedding_cache) // 4]
            for key in oldest_keys:
                del self.embedding_cache[key]
        
        self.embedding_cache[cache_key] = embedding
    
    async def compute_similarity(self, embedding1: List[float], 
                               embedding2: List[float]) -> float:
        """Compute cosine similarity between embeddings"""
        try:
            # Convert to numpy arrays for efficient computation
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            magnitude1 = np.linalg.norm(vec1)
            magnitude2 = np.linalg.norm(vec2)
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            similarity = dot_product / (magnitude1 * magnitude2)
            return float(similarity)
            
        except Exception as e:
            self.logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    async def find_similar_embeddings(self, query_embedding: List[float], 
                                    candidate_embeddings: List[Tuple[str, List[float]]], 
                                    top_k: int = 10, 
                                    threshold: float = 0.5) -> List[Tuple[str, float]]:
        """Find most similar embeddings"""
        try:
            similarities = []
            
            for entity_id, embedding in candidate_embeddings:
                similarity = await self.compute_similarity(query_embedding, embedding)
                if similarity >= threshold:
                    similarities.append((entity_id, similarity))
            
            # Sort by similarity and return top k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            self.logger.error(f"Error finding similar embeddings: {e}")
            return []
    
    async def semantic_search(self, query: str, entities: List[Dict[str, Any]], 
                            top_k: int = 10, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Perform semantic search over entities"""
        try:
            # Get query embedding
            query_embedding = await self.get_embedding(query, "text")
            
            # Get entity embeddings
            entity_texts = []
            entity_ids = []
            
            for entity in entities:
                entity_text = self._entity_to_text(entity)
                entity_texts.append(entity_text)
                entity_ids.append(entity["id"])
            
            entity_embeddings = await self.get_embeddings_batch(entity_texts, "entity")
            
            # Find similar entities
            candidate_embeddings = list(zip(entity_ids, entity_embeddings))
            similar_entities = await self.find_similar_embeddings(
                query_embedding, candidate_embeddings, top_k, threshold
            )
            
            # Return entities with similarity scores
            results = []
            entity_map = {e["id"]: e for e in entities}
            
            for entity_id, similarity in similar_entities:
                if entity_id in entity_map:
                    result = entity_map[entity_id].copy()
                    result["similarity_score"] = similarity
                    results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in semantic search: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get embedding service statistics"""
        cache_hit_rate = (self.stats["cache_hits"] / max(1, self.stats["total_requests"])) * 100
        
        return {
            **self.stats,
            "cache_hit_rate": cache_hit_rate,
            "cache_size": len(self.embedding_cache),
            "embedding_dimension": self.embedding_dim,
            "model_name": self.model_name
        }
    
    async def clear_cache(self):
        """Clear embedding cache"""
        self.embedding_cache.clear()
        self.logger.info("Embedding cache cleared")
    
    async def shutdown(self):
        """Shutdown embedding service"""
        self.embedding_cache.clear()
        self.logger.info("Embedding service shutdown")