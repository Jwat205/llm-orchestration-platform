"""
Semantic chunker that groups text based on semantic similarity and coherence.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering
import logging

logger = logging.getLogger(__name__)

@dataclass
class SemanticChunk:
    """Represents a semantically coherent chunk"""
    content: str
    sentences: List[str]
    start_index: int
    end_index: int
    chunk_id: str
    coherence_score: float
    semantic_tags: List[str]
    embedding: Optional[List[float]] = None

class SemanticChunker:
    """Chunker that creates semantically coherent chunks"""
    
    def __init__(self,
                 model_name: str = "all-MiniLM-L6-v2",
                 similarity_threshold: float = 0.7,
                 max_chunk_size: int = 1000,
                 min_chunk_size: int = 100):
        """
        Initialize semantic chunker
        
        Args:
            model_name: Sentence transformer model name
            similarity_threshold: Minimum similarity for grouping sentences
            max_chunk_size: Maximum characters per chunk
            min_chunk_size: Minimum characters per chunk
        """
        self.similarity_threshold = similarity_threshold
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.warning(f"Could not load model {model_name}: {str(e)}")
            self.model = None
    
    async def chunk_text(self, text: str) -> List[SemanticChunk]:
        """
        Create semantic chunks from text
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of semantic chunks
        """
        if not self.model:
            # Fallback to simple sentence-based chunking
            return await self._fallback_chunking(text)
        
        try:
            # Split into sentences
            sentences = self._split_into_sentences(text)
            
            if len(sentences) <= 1:
                return await self._create_single_chunk(text, sentences)
            
            # Generate embeddings for sentences
            sentence_embeddings = await self._generate_embeddings(sentences)
            
            # Calculate similarity matrix
            similarity_matrix = cosine_similarity(sentence_embeddings)
            
            # Group sentences by semantic similarity
            sentence_groups = await self._group_sentences_by_similarity(
                sentences, similarity_matrix
            )
            
            # Create chunks from groups
            chunks = await self._create_chunks_from_groups(
                text, sentences, sentence_groups, sentence_embeddings
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error in semantic chunking: {str(e)}")
            return await self._fallback_chunking(text)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        import re
        
        # Enhanced sentence splitting pattern
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        
        # Clean and filter sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # Filter very short sentences
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    async def _generate_embeddings(self, sentences: List[str]) -> np.ndarray:
        """Generate embeddings for sentences"""
        try:
            embeddings = self.model.encode(sentences, convert_to_tensor=False)
            return np.array(embeddings)
        except Exception as e:
            logger.warning(f"Error generating embeddings: {str(e)}")
            # Return random embeddings as fallback
            return np.random.rand(len(sentences), 384)
    
    async def _group_sentences_by_similarity(self, 
                                           sentences: List[str],
                                           similarity_matrix: np.ndarray) -> List[List[int]]:
        """Group sentences by semantic similarity"""
        try:
            # Use agglomerative clustering to group similar sentences
            n_clusters = max(1, len(sentences) // 3)  # Rough heuristic
            
            # Convert similarity to distance matrix
            distance_matrix = 1 - similarity_matrix
            
            clustering = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='precomputed',
                linkage='average'
            )
            
            cluster_labels = clustering.fit_predict(distance_matrix)
            
            # Group sentence indices by cluster
            groups = {}
            for i, label in enumerate(cluster_labels):
                if label not in groups:
                    groups[label] = []
                groups[label].append(i)
            
            # Sort groups by first sentence index to maintain order
            sorted_groups = sorted(groups.values(), key=lambda group: group[0])
            
            return sorted_groups
            
        except Exception as e:
            logger.warning(f"Error in clustering: {str(e)}")
            # Fallback: create sequential groups
            group_size = max(2, len(sentences) // 5)
            groups = []
            for i in range(0, len(sentences), group_size):
                groups.append(list(range(i, min(i + group_size, len(sentences)))))
            return groups
    
    async def _create_chunks_from_groups(self,
                                       text: str,
                                       sentences: List[str],
                                       sentence_groups: List[List[int]],
                                       sentence_embeddings: np.ndarray) -> List[SemanticChunk]:
        """Create semantic chunks from sentence groups"""
        chunks = []
        chunk_id = 0
        
        for group_indices in sentence_groups:
            group_sentences = [sentences[i] for i in group_indices]
            chunk_content = " ".join(group_sentences)
            
            # Check size constraints
            if len(chunk_content) > self.max_chunk_size:
                # Split large groups
                sub_chunks = await self._split_large_group(
                    group_sentences, group_indices, sentence_embeddings, chunk_id
                )
                chunks.extend(sub_chunks)
                chunk_id += len(sub_chunks)
            elif len(chunk_content) < self.min_chunk_size and chunks:
                # Merge with previous chunk if too small
                prev_chunk = chunks[-1]
                merged_chunk = await self._merge_chunks(prev_chunk, group_sentences, text)
                if merged_chunk:
                    chunks[-1] = merged_chunk
                else:
                    chunks.append(await self._create_chunk(
                        chunk_content, group_sentences, text, chunk_id
                    ))
                    chunk_id += 1
            else:
                chunks.append(await self._create_chunk(
                    chunk_content, group_sentences, text, chunk_id
                ))
                chunk_id += 1
        
        return chunks
    
    async def _create_chunk(self,
                          content: str,
                          sentences: List[str],
                          full_text: str,
                          chunk_id: int) -> SemanticChunk:
        """Create a semantic chunk"""
        # Find start and end positions in full text
        start_index = full_text.find(sentences[0]) if sentences else 0
        end_index = start_index + len(content)
        
        # Calculate coherence score
        coherence_score = await self._calculate_coherence_score(sentences)
        
        # Generate semantic tags
        semantic_tags = await self._generate_semantic_tags(content)
        
        # Generate chunk embedding if model is available
        embedding = None
        if self.model:
            try:
                embedding = self.model.encode(content, convert_to_tensor=False).tolist()
            except Exception as e:
                logger.warning(f"Error generating chunk embedding: {str(e)}")
        
        return SemanticChunk(
            content=content,
            sentences=sentences,
            start_index=start_index,
            end_index=end_index,
            chunk_id=f"semantic_chunk_{chunk_id:04d}",
            coherence_score=coherence_score,
            semantic_tags=semantic_tags,
            embedding=embedding
        )
    
    async def _calculate_coherence_score(self, sentences: List[str]) -> float:
        """Calculate semantic coherence score for sentences"""
        if len(sentences) <= 1:
            return 1.0
        
        try:
            if self.model:
                embeddings = await self._generate_embeddings(sentences)
                similarities = []
                
                for i in range(len(embeddings) - 1):
                    sim = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
                    similarities.append(sim)
                
                return float(np.mean(similarities))
            else:
                # Simple heuristic based on word overlap
                word_overlap_scores = []
                for i in range(len(sentences) - 1):
                    words1 = set(sentences[i].lower().split())
                    words2 = set(sentences[i + 1].lower().split())
                    
                    if len(words1.union(words2)) > 0:
                        overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                        word_overlap_scores.append(overlap)
                
                return float(np.mean(word_overlap_scores)) if word_overlap_scores else 0.5
                
        except Exception as e:
            logger.warning(f"Error calculating coherence: {str(e)}")
            return 0.5
    
    async def _generate_semantic_tags(self, content: str) -> List[str]:
        """Generate semantic tags for content"""
        tags = []
        content_lower = content.lower()
        
        # Simple keyword-based tagging
        tag_keywords = {
            "technical": ["system", "technology", "software", "algorithm", "data", "process"],
            "business": ["company", "market", "revenue", "customer", "strategy", "product"],
            "academic": ["research", "study", "analysis", "theory", "method", "result"],
            "narrative": ["story", "experience", "journey", "happened", "then", "finally"],
            "descriptive": ["description", "features", "characteristics", "appearance", "details"],
            "analytical": ["analyze", "compare", "evaluate", "assess", "examine", "consider"]
        }
        
        for tag, keywords in tag_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                tags.append(tag)
        
        # Add length-based tags
        if len(content) > 800:
            tags.append("detailed")
        elif len(content) < 200:
            tags.append("brief")
        
        return tags[:5]  # Limit to top 5 tags
    
    async def _split_large_group(self,
                               sentences: List[str],
                               indices: List[int],
                               embeddings: np.ndarray,
                               base_chunk_id: int) -> List[SemanticChunk]:
        """Split a large sentence group into smaller chunks"""
        chunks = []
        current_sentences = []
        current_content = ""
        chunk_id = base_chunk_id
        
        for sentence in sentences:
            if len(current_content + sentence) <= self.max_chunk_size:
                current_sentences.append(sentence)
                current_content += sentence + " "
            else:
                if current_sentences:
                    chunks.append(await self._create_chunk(
                        current_content.strip(), current_sentences, "", chunk_id
                    ))
                    chunk_id += 1
                
                current_sentences = [sentence]
                current_content = sentence + " "
        
        # Add final chunk
        if current_sentences:
            chunks.append(await self._create_chunk(
                current_content.strip(), current_sentences, "", chunk_id
            ))
        
        return chunks
    
    async def _merge_chunks(self,
                          prev_chunk: SemanticChunk,
                          new_sentences: List[str],
                          full_text: str) -> Optional[SemanticChunk]:
        """Merge a small chunk with the previous chunk"""
        new_content = " ".join(new_sentences)
        merged_content = prev_chunk.content + " " + new_content
        
        # Check if merged chunk is too large
        if len(merged_content) > self.max_chunk_size:
            return None
        
        merged_sentences = prev_chunk.sentences + new_sentences
        
        return await self._create_chunk(
            merged_content,
            merged_sentences,
            full_text,
            int(prev_chunk.chunk_id.split('_')[-1])
        )
    
    async def _create_single_chunk(self, text: str, sentences: List[str]) -> List[SemanticChunk]:
        """Create a single chunk when there's only one sentence or very short text"""
        chunk = await self._create_chunk(text, sentences, text, 0)
        return [chunk]
    
    async def _fallback_chunking(self, text: str) -> List[SemanticChunk]:
        """Fallback chunking when semantic analysis fails"""
        sentences = self._split_into_sentences(text)
        
        if not sentences:
            return [await self._create_chunk(text, [text], text, 0)]
        
        chunks = []
        chunk_id = 0
        current_sentences = []
        current_content = ""
        
        for sentence in sentences:
            if len(current_content + sentence) <= self.max_chunk_size:
                current_sentences.append(sentence)
                current_content += sentence + " "
            else:
                if current_sentences:
                    chunks.append(await self._create_chunk(
                        current_content.strip(), current_sentences, text, chunk_id
                    ))
                    chunk_id += 1
                
                current_sentences = [sentence]
                current_content = sentence + " "
        
        # Add final chunk
        if current_sentences:
            chunks.append(await self._create_chunk(
                current_content.strip(), current_sentences, text, chunk_id
            ))
        
        return chunks
    
    async def analyze_chunk_quality(self, chunks: List[SemanticChunk]) -> Dict[str, Any]:
        """Analyze the quality of semantic chunking"""
        if not chunks:
            return {"error": "No chunks to analyze"}
        
        coherence_scores = [chunk.coherence_score for chunk in chunks]
        chunk_sizes = [len(chunk.content) for chunk in chunks]
        
        analysis = {
            "total_chunks": len(chunks),
            "average_coherence": np.mean(coherence_scores),
            "min_coherence": np.min(coherence_scores),
            "max_coherence": np.max(coherence_scores),
            "average_chunk_size": np.mean(chunk_sizes),
            "size_distribution": {
                "min": np.min(chunk_sizes),
                "max": np.max(chunk_sizes),
                "std": np.std(chunk_sizes)
            },
            "semantic_tag_distribution": {}
        }
        
        # Analyze semantic tags
        all_tags = []
        for chunk in chunks:
            all_tags.extend(chunk.semantic_tags)
        
        from collections import Counter
        tag_counts = Counter(all_tags)
        analysis["semantic_tag_distribution"] = dict(tag_counts.most_common(10))
        
        return analysis