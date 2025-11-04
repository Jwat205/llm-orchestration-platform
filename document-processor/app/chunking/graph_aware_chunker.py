"""
Graph-aware chunking that considers entity boundaries and relationships
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
import re
from collections import defaultdict
import networkx as nx

logger = logging.getLogger(__name__)


class GraphAwareChunker:
    """Chunker that considers entity boundaries and relationships when splitting text"""
    
    def __init__(self):
        self.entity_boundary_weight = 0.3
        self.relationship_continuity_weight = 0.4
        self.semantic_coherence_weight = 0.3
        self.min_chunk_size = 100
        self.overlap_sentences = 1
    
    async def chunk(
        self,
        text: str,
        max_chunk_size: int = 1000,
        overlap_size: int = 200,
        preserve_entities: bool = True,
        maintain_relationships: bool = True
    ) -> List[Dict[str, Any]]:
        """Chunk text while preserving entity boundaries and relationships"""
        
        chunks = []
        
        try:
            # Step 1: Extract entities and relationships
            entities = await self._extract_entities(text)
            relationships = await self._extract_relationships(text, entities)
            
            # Step 2: Analyze text structure
            sentences = await self._split_into_sentences(text)
            paragraphs = await self._identify_paragraphs(text)
            
            # Step 3: Build entity-sentence mapping
            entity_sentence_map = await self._map_entities_to_sentences(entities, sentences)
            
            # Step 4: Calculate chunk boundaries using graph awareness
            chunk_boundaries = await self._calculate_graph_aware_boundaries(
                sentences,
                entities,
                relationships,
                entity_sentence_map,
                max_chunk_size,
                preserve_entities,
                maintain_relationships
            )
            
            # Step 5: Create chunks with overlap
            chunks = await self._create_chunks_with_overlap(
                sentences,
                chunk_boundaries,
                overlap_size,
                entities,
                relationships
            )
            
            # Step 6: Validate and optimize chunks
            chunks = await self._validate_and_optimize_chunks(chunks, max_chunk_size)
            
        except Exception as e:
            logger.error(f"Error in graph-aware chunking: {e}")
            # Fallback to simple sentence-based chunking
            chunks = await self._fallback_chunking(text, max_chunk_size, overlap_size)
        
        return chunks
    
    async def analyze_chunking_quality(
        self,
        text: str,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze the quality of graph-aware chunking"""
        
        analysis = {
            "total_chunks": len(chunks),
            "entity_preservation": {},
            "relationship_continuity": {},
            "semantic_coherence": {},
            "size_distribution": {},
            "overlap_analysis": {}
        }
        
        try:
            # Extract original entities and relationships
            original_entities = await self._extract_entities(text)
            original_relationships = await self._extract_relationships(text, original_entities)
            
            # Analyze entity preservation
            entity_preservation = await self._analyze_entity_preservation(
                chunks, original_entities
            )
            analysis["entity_preservation"] = entity_preservation
            
            # Analyze relationship continuity
            relationship_continuity = await self._analyze_relationship_continuity(
                chunks, original_relationships
            )
            analysis["relationship_continuity"] = relationship_continuity
            
            # Analyze semantic coherence
            semantic_coherence = await self._analyze_semantic_coherence(chunks)
            analysis["semantic_coherence"] = semantic_coherence
            
            # Analyze size distribution
            sizes = [len(chunk["content"]) for chunk in chunks]
            analysis["size_distribution"] = {
                "min_size": min(sizes) if sizes else 0,
                "max_size": max(sizes) if sizes else 0,
                "avg_size": sum(sizes) / len(sizes) if sizes else 0,
                "size_variance": self._calculate_variance(sizes)
            }
            
            # Analyze overlap
            overlap_analysis = await self._analyze_overlap_quality(chunks)
            analysis["overlap_analysis"] = overlap_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing chunking quality: {e}")
            analysis["error"] = str(e)
        
        return analysis
    
    async def optimize_chunks_for_graph(
        self,
        chunks: List[Dict[str, Any]],
        optimization_criteria: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """Optimize chunks based on graph-based criteria"""
        
        if optimization_criteria is None:
            optimization_criteria = {
                "entity_completeness": 0.4,
                "relationship_preservation": 0.3,
                "semantic_coherence": 0.2,
                "size_consistency": 0.1
            }
        
        optimized_chunks = []
        
        try:
            for chunk in chunks:
                optimized_chunk = await self._optimize_single_chunk(
                    chunk, optimization_criteria
                )
                optimized_chunks.append(optimized_chunk)
            
            # Post-processing: merge small chunks, split large ones
            optimized_chunks = await self._post_process_chunks(optimized_chunks)
            
        except Exception as e:
            logger.error(f"Error optimizing chunks: {e}")
            optimized_chunks = chunks  # Return original on error
        
        return optimized_chunks
    
    # Helper methods
    async def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        entities = []
        
        # Simple pattern-based entity extraction
        # In practice, this would use more sophisticated NLP models
        
        # Person names
        person_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
        for match in re.finditer(person_pattern, text):
            entities.append({
                "name": match.group(),
                "type": "PERSON",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.7
            })
        
        # Organizations
        org_pattern = r'\b[A-Z][a-zA-Z\s]+(Inc|Corp|Ltd|LLC|Company)\b'
        for match in re.finditer(org_pattern, text):
            entities.append({
                "name": match.group(),
                "type": "ORGANIZATION",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.8
            })
        
        # Dates
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'
        for match in re.finditer(date_pattern, text):
            entities.append({
                "name": match.group(),
                "type": "DATE",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
        
        # Remove overlapping entities (keep highest confidence)
        entities = self._remove_overlapping_entities(entities)
        
        return entities
    
    async def _extract_relationships(
        self, 
        text: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relationships between entities"""
        relationships = []
        
        # Find relationships by co-occurrence in sentences
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence_entities = [
                e for e in entities 
                if e["start"] <= len(text) - len(sentence.strip()) + sentence.find(e["name"]) <= e["end"]
                if e["name"] in sentence
            ]
            
            # Create relationships between entities in the same sentence
            for i, entity1 in enumerate(sentence_entities):
                for entity2 in sentence_entities[i+1:]:
                    rel_type = self._determine_relationship_type(sentence, entity1, entity2)
                    
                    relationships.append({
                        "source": entity1["name"],
                        "target": entity2["name"],
                        "type": rel_type,
                        "context": sentence.strip(),
                        "confidence": 0.6
                    })
        
        return relationships
    
    async def _split_into_sentences(self, text: str) -> List[Dict[str, Any]]:
        """Split text into sentences with metadata"""
        sentences = []
        
        # Simple sentence splitting (would use better approach in practice)
        sentence_texts = re.split(r'(?<=[.!?])\s+', text)
        
        current_pos = 0
        for i, sentence_text in enumerate(sentence_texts):
            sentence_text = sentence_text.strip()
            if not sentence_text:
                continue
            
            start_pos = text.find(sentence_text, current_pos)
            end_pos = start_pos + len(sentence_text)
            
            sentences.append({
                "index": i,
                "content": sentence_text,
                "start": start_pos,
                "end": end_pos,
                "length": len(sentence_text)
            })
            
            current_pos = end_pos
        
        return sentences
    
    async def _identify_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """Identify paragraph boundaries"""
        paragraphs = []
        
        paragraph_texts = text.split('\n\n')
        current_pos = 0
        
        for i, para_text in enumerate(paragraph_texts):
            para_text = para_text.strip()
            if not para_text:
                continue
            
            start_pos = text.find(para_text, current_pos)
            end_pos = start_pos + len(para_text)
            
            paragraphs.append({
                "index": i,
                "content": para_text,
                "start": start_pos,
                "end": end_pos,
                "sentence_count": len([s for s in para_text.split('.') if s.strip()])
            })
            
            current_pos = end_pos
        
        return paragraphs
    
    async def _map_entities_to_sentences(
        self, 
        entities: List[Dict[str, Any]], 
        sentences: List[Dict[str, Any]]
    ) -> Dict[str, List[int]]:
        """Map entities to sentences that contain them"""
        entity_sentence_map = defaultdict(list)
        
        for entity in entities:
            entity_name = entity["name"]
            
            for sentence in sentences:
                if entity_name in sentence["content"]:
                    entity_sentence_map[entity_name].append(sentence["index"])
        
        return dict(entity_sentence_map)
    
    async def _calculate_graph_aware_boundaries(
        self,
        sentences: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        entity_sentence_map: Dict[str, List[int]],
        max_chunk_size: int,
        preserve_entities: bool,
        maintain_relationships: bool
    ) -> List[int]:
        """Calculate optimal chunk boundaries considering graph structure"""
        
        boundaries = [0]  # Start with first sentence
        current_chunk_start = 0
        current_chunk_size = 0
        
        i = 0
        while i < len(sentences):
            sentence = sentences[i]
            sentence_size = sentence["length"]
            
            # Check if adding this sentence would exceed max size
            if current_chunk_size + sentence_size > max_chunk_size and current_chunk_size > self.min_chunk_size:
                # Find optimal boundary around this position
                optimal_boundary = await self._find_optimal_boundary(
                    sentences,
                    current_chunk_start,
                    i,
                    entities,
                    relationships,
                    entity_sentence_map,
                    preserve_entities,
                    maintain_relationships
                )
                
                if optimal_boundary > current_chunk_start:
                    boundaries.append(optimal_boundary)
                    current_chunk_start = optimal_boundary
                    current_chunk_size = sum(
                        sentences[j]["length"] 
                        for j in range(optimal_boundary, i + 1)
                        if j < len(sentences)
                    )
                else:
                    boundaries.append(i)
                    current_chunk_start = i
                    current_chunk_size = sentence_size
            else:
                current_chunk_size += sentence_size
            
            i += 1
        
        # Add final boundary if needed
        if len(sentences) not in boundaries:
            boundaries.append(len(sentences))
        
        return boundaries
    
    async def _find_optimal_boundary(
        self,
        sentences: List[Dict[str, Any]],
        start_idx: int,
        end_idx: int,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        entity_sentence_map: Dict[str, List[int]],
        preserve_entities: bool,
        maintain_relationships: bool
    ) -> int:
        """Find optimal boundary within a range considering graph factors"""
        
        best_boundary = end_idx
        best_score = -1
        
        # Evaluate potential boundaries in the range
        for candidate in range(start_idx + 1, min(end_idx + 3, len(sentences))):
            score = await self._evaluate_boundary_score(
                candidate,
                sentences,
                entities,
                relationships,
                entity_sentence_map,
                preserve_entities,
                maintain_relationships
            )
            
            if score > best_score:
                best_score = score
                best_boundary = candidate
        
        return best_boundary
    
    async def _evaluate_boundary_score(
        self,
        boundary_idx: int,
        sentences: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        entity_sentence_map: Dict[str, List[int]],
        preserve_entities: bool,
        maintain_relationships: bool
    ) -> float:
        """Evaluate how good a boundary position is based on graph factors"""
        
        score = 0.0
        
        # Entity boundary preservation score
        if preserve_entities:
            entity_score = self._calculate_entity_boundary_score(
                boundary_idx, entities, entity_sentence_map
            )
            score += entity_score * self.entity_boundary_weight
        
        # Relationship continuity score
        if maintain_relationships:
            relationship_score = self._calculate_relationship_continuity_score(
                boundary_idx, relationships, entity_sentence_map
            )
            score += relationship_score * self.relationship_continuity_weight
        
        # Semantic coherence score (simplified)
        semantic_score = self._calculate_semantic_coherence_score(
            boundary_idx, sentences
        )
        score += semantic_score * self.semantic_coherence_weight
        
        return score
    
    def _calculate_entity_boundary_score(
        self,
        boundary_idx: int,
        entities: List[Dict[str, Any]],
        entity_sentence_map: Dict[str, List[int]]
    ) -> float:
        """Calculate score based on entity boundary preservation"""
        
        split_entities = 0
        total_entities = 0
        
        for entity_name, sentence_indices in entity_sentence_map.items():
            total_entities += 1
            
            # Check if entity spans across boundary
            before_boundary = any(idx < boundary_idx for idx in sentence_indices)
            after_boundary = any(idx >= boundary_idx for idx in sentence_indices)
            
            if before_boundary and after_boundary:
                split_entities += 1
        
        if total_entities == 0:
            return 1.0
        
        # Higher score for fewer split entities
        return 1.0 - (split_entities / total_entities)
    
    def _calculate_relationship_continuity_score(
        self,
        boundary_idx: int,
        relationships: List[Dict[str, Any]],
        entity_sentence_map: Dict[str, List[int]]
    ) -> float:
        """Calculate score based on relationship continuity"""
        
        broken_relationships = 0
        total_relationships = 0
        
        for relationship in relationships:
            total_relationships += 1
            
            source_sentences = entity_sentence_map.get(relationship["source"], [])
            target_sentences = entity_sentence_map.get(relationship["target"], [])
            
            # Check if relationship entities are split across boundary
            source_before = any(idx < boundary_idx for idx in source_sentences)
            source_after = any(idx >= boundary_idx for idx in source_sentences)
            target_before = any(idx < boundary_idx for idx in target_sentences)
            target_after = any(idx >= boundary_idx for idx in target_sentences)
            
            if ((source_before and target_after) or (source_after and target_before)):
                broken_relationships += 1
        
        if total_relationships == 0:
            return 1.0
        
        # Higher score for fewer broken relationships
        return 1.0 - (broken_relationships / total_relationships)
    
    def _calculate_semantic_coherence_score(
        self,
        boundary_idx: int,
        sentences: List[Dict[str, Any]]
    ) -> float:
        """Calculate semantic coherence score (simplified)"""
        
        if boundary_idx >= len(sentences):
            return 0.0
        
        # Simple heuristic: prefer boundaries at paragraph breaks
        if boundary_idx > 0:
            current_sentence = sentences[boundary_idx - 1]["content"]
            next_sentence = sentences[boundary_idx]["content"] if boundary_idx < len(sentences) else ""
            
            # Check for paragraph indicators
            if (current_sentence.endswith('.') and 
                next_sentence and 
                (next_sentence[0].isupper() or next_sentence.startswith(('    ', '\t')))):
                return 0.8
        
        return 0.5  # Neutral score
    
    async def _create_chunks_with_overlap(
        self,
        sentences: List[Dict[str, Any]],
        boundaries: List[int],
        overlap_size: int,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create chunks with appropriate overlap"""
        
        chunks = []
        
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i + 1]
            
            # Calculate overlap
            overlap_start = start_idx
            overlap_end = end_idx
            
            if i > 0:  # Add overlap from previous chunk
                overlap_sentences = min(self.overlap_sentences, start_idx)
                overlap_start = max(0, start_idx - overlap_sentences)
            
            if i < len(boundaries) - 2:  # Add overlap to next chunk
                remaining_sentences = len(sentences) - end_idx
                overlap_sentences = min(self.overlap_sentences, remaining_sentences)
                overlap_end = min(len(sentences), end_idx + overlap_sentences)
            
            # Build chunk content
            chunk_sentences = sentences[overlap_start:overlap_end]
            chunk_content = ' '.join(s["content"] for s in chunk_sentences)
            
            # Find entities and relationships in this chunk
            chunk_entities = self._find_entities_in_range(
                entities, overlap_start, overlap_end, sentences
            )
            chunk_relationships = self._find_relationships_in_chunk(
                relationships, chunk_entities
            )
            
            chunk = {
                "index": i,
                "content": chunk_content,
                "start_sentence": overlap_start,
                "end_sentence": overlap_end,
                "core_start": start_idx,
                "core_end": end_idx,
                "length": len(chunk_content),
                "sentence_count": len(chunk_sentences),
                "entities": chunk_entities,
                "relationships": chunk_relationships,
                "metadata": {
                    "has_overlap": overlap_start < start_idx or overlap_end > end_idx,
                    "overlap_start": overlap_start < start_idx,
                    "overlap_end": overlap_end > end_idx
                }
            }
            
            chunks.append(chunk)
        
        return chunks
    
    def _find_entities_in_range(
        self,
        entities: List[Dict[str, Any]],
        start_sentence_idx: int,
        end_sentence_idx: int,
        sentences: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find entities that appear in the given sentence range"""
        
        chunk_entities = []
        
        # Get text range
        if start_sentence_idx < len(sentences) and end_sentence_idx <= len(sentences):
            range_start = sentences[start_sentence_idx]["start"] if start_sentence_idx < len(sentences) else 0
            range_end = sentences[end_sentence_idx - 1]["end"] if end_sentence_idx > 0 and end_sentence_idx <= len(sentences) else len(sentences[-1]["content"]) if sentences else 0
            
            for entity in entities:
                # Check if entity overlaps with sentence range
                if (entity["start"] < range_end and entity["end"] > range_start):
                    chunk_entities.append(entity.copy())
        
        return chunk_entities
    
    def _find_relationships_in_chunk(
        self,
        relationships: List[Dict[str, Any]],
        chunk_entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find relationships where both entities are in the chunk"""
        
        chunk_entity_names = set(e["name"] for e in chunk_entities)
        chunk_relationships = []
        
        for relationship in relationships:
            if (relationship["source"] in chunk_entity_names and 
                relationship["target"] in chunk_entity_names):
                chunk_relationships.append(relationship.copy())
        
        return chunk_relationships
    
    async def _validate_and_optimize_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_chunk_size: int
    ) -> List[Dict[str, Any]]:
        """Validate and optimize chunks"""
        
        optimized_chunks = []
        
        for chunk in chunks:
            # Check if chunk is too large
            if chunk["length"] > max_chunk_size * 1.2:  # Allow 20% tolerance
                # Split large chunk
                sub_chunks = await self._split_large_chunk(chunk, max_chunk_size)
                optimized_chunks.extend(sub_chunks)
            elif chunk["length"] < self.min_chunk_size and optimized_chunks:
                # Merge with previous chunk if too small
                prev_chunk = optimized_chunks[-1]
                merged_chunk = await self._merge_chunks(prev_chunk, chunk)
                
                if merged_chunk["length"] <= max_chunk_size * 1.2:
                    optimized_chunks[-1] = merged_chunk
                else:
                    optimized_chunks.append(chunk)
            else:
                optimized_chunks.append(chunk)
        
        # Renumber chunks
        for i, chunk in enumerate(optimized_chunks):
            chunk["index"] = i
        
        return optimized_chunks
    
    async def _split_large_chunk(
        self,
        chunk: Dict[str, Any],
        max_size: int
    ) -> List[Dict[str, Any]]:
        """Split a chunk that's too large"""
        
        # Simple approach: split at sentence boundaries
        sentences = chunk["content"].split('.')
        sub_chunks = []
        current_content = ""
        current_entities = []
        current_relationships = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_content + sentence) > max_size and current_content:
                # Create sub-chunk
                sub_chunk = {
                    "index": len(sub_chunks),
                    "content": current_content.strip(),
                    "length": len(current_content),
                    "entities": current_entities.copy(),
                    "relationships": current_relationships.copy(),
                    "metadata": {"split_from_large_chunk": True}
                }
                sub_chunks.append(sub_chunk)
                
                current_content = sentence + ". "
                current_entities = []
                current_relationships = []
            else:
                current_content += sentence + ". "
        
        # Add remaining content
        if current_content.strip():
            sub_chunk = {
                "index": len(sub_chunks),
                "content": current_content.strip(),
                "length": len(current_content),
                "entities": current_entities,
                "relationships": current_relationships,
                "metadata": {"split_from_large_chunk": True}
            }
            sub_chunks.append(sub_chunk)
        
        return sub_chunks if sub_chunks else [chunk]
    
    async def _merge_chunks(
        self,
        chunk1: Dict[str, Any],
        chunk2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two chunks"""
        
        merged_content = chunk1["content"] + " " + chunk2["content"]
        merged_entities = chunk1.get("entities", []) + chunk2.get("entities", [])
        merged_relationships = chunk1.get("relationships", []) + chunk2.get("relationships", [])
        
        # Remove duplicate entities and relationships
        unique_entities = []
        seen_entities = set()
        for entity in merged_entities:
            entity_key = (entity["name"], entity["type"])
            if entity_key not in seen_entities:
                unique_entities.append(entity)
                seen_entities.add(entity_key)
        
        unique_relationships = []
        seen_relationships = set()
        for rel in merged_relationships:
            rel_key = (rel["source"], rel["target"], rel["type"])
            if rel_key not in seen_relationships:
                unique_relationships.append(rel)
                seen_relationships.add(rel_key)
        
        merged_chunk = {
            "index": chunk1["index"],
            "content": merged_content,
            "length": len(merged_content),
            "entities": unique_entities,
            "relationships": unique_relationships,
            "metadata": {
                "merged_from_chunks": [chunk1.get("index"), chunk2.get("index")],
                "original_lengths": [chunk1["length"], chunk2["length"]]
            }
        }
        
        return merged_chunk
    
    async def _fallback_chunking(
        self,
        text: str,
        max_chunk_size: int,
        overlap_size: int
    ) -> List[Dict[str, Any]]:
        """Fallback to simple sentence-based chunking"""
        
        sentences = text.split('.')
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_size = len(sentence)
            
            if current_size + sentence_size > max_chunk_size and current_chunk:
                chunks.append({
                    "index": len(chunks),
                    "content": current_chunk.strip(),
                    "length": len(current_chunk),
                    "entities": [],
                    "relationships": [],
                    "metadata": {"fallback_chunking": True}
                })
                
                current_chunk = sentence + ". "
                current_size = sentence_size
            else:
                current_chunk += sentence + ". "
                current_size += sentence_size
        
        # Add remaining content
        if current_chunk.strip():
            chunks.append({
                "index": len(chunks),
                "content": current_chunk.strip(),
                "length": len(current_chunk),
                "entities": [],
                "relationships": [],
                "metadata": {"fallback_chunking": True}
            })
        
        return chunks
    
    # Additional helper methods
    def _remove_overlapping_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove overlapping entities, keeping highest confidence ones"""
        
        entities.sort(key=lambda x: x["confidence"], reverse=True)
        filtered_entities = []
        
        for entity in entities:
            overlaps = False
            for existing in filtered_entities:
                if (entity["start"] < existing["end"] and entity["end"] > existing["start"]):
                    overlaps = True
                    break
            
            if not overlaps:
                filtered_entities.append(entity)
        
        return filtered_entities
    
    def _determine_relationship_type(
        self,
        sentence: str,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> str:
        """Determine relationship type between entities based on context"""
        
        sentence_lower = sentence.lower()
        
        if any(pattern in sentence_lower for pattern in ["works for", "employee of", "employed by"]):
            return "WORKS_FOR"
        elif any(pattern in sentence_lower for pattern in ["located in", "based in", "headquarters in"]):
            return "LOCATED_IN"
        elif any(pattern in sentence_lower for pattern in ["part of", "division of", "subsidiary of"]):
            return "PART_OF"
        elif any(pattern in sentence_lower for pattern in ["collaborated with", "partnered with", "worked with"]):
            return "COLLABORATES_WITH"
        else:
            return "RELATED_TO"
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    async def _analyze_entity_preservation(
        self,
        chunks: List[Dict[str, Any]],
        original_entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze how well entities are preserved in chunks"""
        
        analysis = {
            "total_entities": len(original_entities),
            "entities_in_chunks": 0,
            "entities_split_across_chunks": 0,
            "preservation_rate": 0.0
        }
        
        entity_chunk_map = defaultdict(list)
        
        # Map entities to chunks
        for chunk_idx, chunk in enumerate(chunks):
            for entity in chunk.get("entities", []):
                entity_chunk_map[entity["name"]].append(chunk_idx)
        
        analysis["entities_in_chunks"] = len(entity_chunk_map)
        
        # Count split entities
        for entity_name, chunk_indices in entity_chunk_map.items():
            if len(chunk_indices) > 1:
                analysis["entities_split_across_chunks"] += 1
        
        if analysis["total_entities"] > 0:
            analysis["preservation_rate"] = analysis["entities_in_chunks"] / analysis["total_entities"]
        
        return analysis
    
    async def _analyze_relationship_continuity(
        self,
        chunks: List[Dict[str, Any]],
        original_relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze relationship continuity across chunks"""
        
        analysis = {
            "total_relationships": len(original_relationships),
            "relationships_preserved": 0,
            "relationships_broken": 0,
            "continuity_rate": 0.0
        }
        
        for relationship in original_relationships:
            source = relationship["source"]
            target = relationship["target"]
            
            # Check if both entities appear in the same chunk
            preserved = False
            for chunk in chunks:
                chunk_entity_names = set(e["name"] for e in chunk.get("entities", []))
                if source in chunk_entity_names and target in chunk_entity_names:
                    preserved = True
                    break
            
            if preserved:
                analysis["relationships_preserved"] += 1
            else:
                analysis["relationships_broken"] += 1
        
        if analysis["total_relationships"] > 0:
            analysis["continuity_rate"] = analysis["relationships_preserved"] / analysis["total_relationships"]
        
        return analysis
    
    async def _analyze_semantic_coherence(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze semantic coherence of chunks"""
        
        analysis = {
            "avg_entity_density": 0.0,
            "avg_relationship_density": 0.0,
            "coherence_score": 0.0
        }
        
        if not chunks:
            return analysis
        
        entity_densities = []
        relationship_densities = []
        
        for chunk in chunks:
            entity_count = len(chunk.get("entities", []))
            relationship_count = len(chunk.get("relationships", []))
            content_length = chunk.get("length", 1)
            
            entity_density = entity_count / content_length * 1000  # per 1000 chars
            relationship_density = relationship_count / content_length * 1000
            
            entity_densities.append(entity_density)
            relationship_densities.append(relationship_density)
        
        analysis["avg_entity_density"] = sum(entity_densities) / len(entity_densities)
        analysis["avg_relationship_density"] = sum(relationship_densities) / len(relationship_densities)
        
        # Simple coherence score based on consistency of densities
        entity_variance = self._calculate_variance(entity_densities)
        relationship_variance = self._calculate_variance(relationship_densities)
        
        # Lower variance indicates better coherence
        analysis["coherence_score"] = max(0, 1.0 - (entity_variance + relationship_variance) / 10)
        
        return analysis
    
    async def _analyze_overlap_quality(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze quality of overlap between chunks"""
        
        analysis = {
            "chunks_with_overlap": 0,
            "avg_overlap_entity_count": 0.0,
            "overlap_effectiveness": 0.0
        }
        
        overlapping_chunks = [c for c in chunks if c.get("metadata", {}).get("has_overlap", False)]
        analysis["chunks_with_overlap"] = len(overlapping_chunks)
        
        if overlapping_chunks:
            overlap_entity_counts = [len(c.get("entities", [])) for c in overlapping_chunks]
            analysis["avg_overlap_entity_count"] = sum(overlap_entity_counts) / len(overlap_entity_counts)
            
            # Effectiveness based on entity preservation in overlaps
            analysis["overlap_effectiveness"] = min(analysis["avg_overlap_entity_count"] / 5.0, 1.0)
        
        return analysis
    
    async def _optimize_single_chunk(
        self,
        chunk: Dict[str, Any],
        criteria: Dict[str, float]
    ) -> Dict[str, Any]:
        """Optimize a single chunk based on criteria"""
        
        # For now, return the chunk as-is
        # In practice, this would apply various optimization techniques
        
        optimized_chunk = chunk.copy()
        optimized_chunk["metadata"] = chunk.get("metadata", {}).copy()
        optimized_chunk["metadata"]["optimized"] = True
        
        return optimized_chunk
    
    async def _post_process_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process chunks for final optimization"""
        
        # Simple post-processing: ensure minimum chunk sizes
        processed_chunks = []
        
        i = 0
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # If chunk is too small and not the last one, try to merge
            if (current_chunk["length"] < self.min_chunk_size and 
                i < len(chunks) - 1 and 
                current_chunk["length"] + chunks[i + 1]["length"] < 1500):
                
                merged_chunk = await self._merge_chunks(current_chunk, chunks[i + 1])
                processed_chunks.append(merged_chunk)
                i += 2  # Skip next chunk as it's been merged
            else:
                processed_chunks.append(current_chunk)
                i += 1
        
        # Renumber chunks
        for idx, chunk in enumerate(processed_chunks):
            chunk["index"] = idx
        
        return processed_chunks