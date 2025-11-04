"""
Graph-aware document processor
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import networkx as nx
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class GraphProcessor:
    """Graph-aware document processor that enhances processing with graph context"""
    
    def __init__(self):
        self.knowledge_graph = None  # Would be injected in real implementation
        self.entity_cache = {}
        self.relationship_cache = {}
    
    async def process_with_graph_context(
        self,
        content: str,
        content_type: str,
        existing_entities: List[Dict[str, Any]] = None,
        graph_depth: int = 2
    ) -> Dict[str, Any]:
        """Process document with graph context enhancement"""
        
        result = {
            "enhanced_content": content,
            "graph_context": {},
            "entity_enrichment": {},
            "relationship_enhancement": {},
            "semantic_expansion": {},
            "processing_metadata": {}
        }
        
        start_time = datetime.now()
        
        try:
            # Step 1: Identify entities in content
            if existing_entities:
                entities = existing_entities
            else:
                entities = await self._extract_basic_entities(content)
            
            # Step 2: Get graph context for entities
            if entities:
                graph_context = await self._get_graph_context(entities, graph_depth)
                result["graph_context"] = graph_context
                
                # Step 3: Enrich entities with graph information
                enriched_entities = await self._enrich_entities_with_graph(entities, graph_context)
                result["entity_enrichment"] = enriched_entities
                
                # Step 4: Enhance relationships with graph knowledge
                enhanced_relationships = await self._enhance_relationships_with_graph(
                    content, entities, graph_context
                )
                result["relationship_enhancement"] = enhanced_relationships
                
                # Step 5: Semantic expansion using graph
                semantic_expansion = await self._expand_semantics_with_graph(
                    content, graph_context
                )
                result["semantic_expansion"] = semantic_expansion
                
                # Step 6: Generate enhanced content
                enhanced_content = await self._generate_enhanced_content(
                    content, enriched_entities, enhanced_relationships, semantic_expansion
                )
                result["enhanced_content"] = enhanced_content
            
            # Processing metadata
            processing_time = (datetime.now() - start_time).total_seconds()
            result["processing_metadata"] = {
                "processing_time": processing_time,
                "entities_processed": len(entities) if entities else 0,
                "graph_depth": graph_depth,
                "enhancement_applied": len(result["graph_context"]) > 0
            }
            
        except Exception as e:
            logger.error(f"Error in graph-aware processing: {e}")
            result["processing_metadata"]["error"] = str(e)
        
        return result
    
    async def analyze_document_structure_with_graph(
        self,
        content: str,
        content_type: str
    ) -> Dict[str, Any]:
        """Analyze document structure using graph insights"""
        
        analysis = {
            "structural_elements": {},
            "entity_distribution": {},
            "relationship_patterns": {},
            "concept_hierarchy": {},
            "information_flow": {}
        }
        
        try:
            # Extract structural elements
            structural_elements = await self._extract_structural_elements(content, content_type)
            analysis["structural_elements"] = structural_elements
            
            # Analyze entity distribution across structure
            entity_distribution = await self._analyze_entity_distribution(
                content, structural_elements
            )
            analysis["entity_distribution"] = entity_distribution
            
            # Identify relationship patterns
            relationship_patterns = await self._identify_relationship_patterns(
                content, structural_elements
            )
            analysis["relationship_patterns"] = relationship_patterns
            
            # Build concept hierarchy
            concept_hierarchy = await self._build_concept_hierarchy(content)
            analysis["concept_hierarchy"] = concept_hierarchy
            
            # Analyze information flow
            information_flow = await self._analyze_information_flow(
                content, structural_elements, entity_distribution
            )
            analysis["information_flow"] = information_flow
            
        except Exception as e:
            logger.error(f"Error in document structure analysis: {e}")
            analysis["error"] = str(e)
        
        return analysis
    
    async def identify_key_concepts_with_graph(
        self,
        content: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """Identify key concepts using graph-based analysis"""
        
        try:
            # Extract entities and relationships
            entities = await self._extract_basic_entities(content)
            relationships = await self._extract_basic_relationships(content, entities)
            
            # Build local concept graph
            concept_graph = await self._build_local_concept_graph(entities, relationships)
            
            # Calculate concept importance using graph metrics
            concept_scores = await self._calculate_concept_importance(
                concept_graph, entities, content
            )
            
            # Rank and return top concepts
            top_concepts = sorted(
                concept_scores.items(), 
                key=lambda x: x[1]["total_score"], 
                reverse=True
            )[:top_k]
            
            key_concepts = []
            for concept_name, scores in top_concepts:
                concept_info = {
                    "name": concept_name,
                    "type": scores.get("type", "CONCEPT"),
                    "importance_score": scores["total_score"],
                    "centrality_score": scores.get("centrality", 0.0),
                    "frequency_score": scores.get("frequency", 0.0),
                    "context_score": scores.get("context", 0.0),
                    "mentions": scores.get("mentions", []),
                    "related_concepts": scores.get("related", [])
                }
                key_concepts.append(concept_info)
            
            return key_concepts
            
        except Exception as e:
            logger.error(f"Error identifying key concepts: {e}")
            return []
    
    async def generate_content_summary_with_graph(
        self,
        content: str,
        summary_length: int = 3,
        focus_entities: List[str] = None
    ) -> Dict[str, Any]:
        """Generate content summary using graph-based insights"""
        
        summary_result = {
            "summary": "",
            "key_points": [],
            "important_entities": [],
            "relationship_insights": [],
            "structure_analysis": {}
        }
        
        try:
            # Extract key information
            entities = await self._extract_basic_entities(content)
            key_concepts = await self.identify_key_concepts_with_graph(content, top_k=10)
            
            # Focus on specific entities if provided
            if focus_entities:
                entities = [e for e in entities if e["name"] in focus_entities]
                key_concepts = [c for c in key_concepts if c["name"] in focus_entities]
            
            # Generate summary sentences
            summary_sentences = await self._generate_summary_sentences(
                content, entities, key_concepts, summary_length
            )
            summary_result["summary"] = " ".join(summary_sentences)
            
            # Extract key points
            key_points = await self._extract_key_points(content, entities, key_concepts)
            summary_result["key_points"] = key_points
            
            # Important entities
            summary_result["important_entities"] = [
                {
                    "name": concept["name"],
                    "type": concept["type"],
                    "importance": concept["importance_score"]
                }
                for concept in key_concepts[:5]
            ]
            
            # Relationship insights
            relationship_insights = await self._generate_relationship_insights(
                content, entities
            )
            summary_result["relationship_insights"] = relationship_insights
            
            # Structure analysis
            structure_analysis = await self._analyze_content_structure(content)
            summary_result["structure_analysis"] = structure_analysis
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            summary_result["error"] = str(e)
        
        return summary_result
    
    # Helper methods
    async def _extract_basic_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract basic entities from content"""
        # Simplified entity extraction - would use NLP models in practice
        
        # Common entity patterns
        import re
        
        entities = []
        
        # Person names (capitalized words)
        person_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
        persons = re.findall(person_pattern, content)
        for person in set(persons):
            entities.append({
                "name": person,
                "type": "PERSON",
                "confidence": 0.7,
                "positions": [m.start() for m in re.finditer(re.escape(person), content)]
            })
        
        # Organizations (words ending with Inc, Corp, Ltd, etc.)
        org_pattern = r'\b[A-Z][a-zA-Z\s]+(Inc|Corp|Ltd|LLC|Company|Organization)\b'
        orgs = re.findall(org_pattern, content)
        for org in set(orgs):
            entities.append({
                "name": org,
                "type": "ORGANIZATION",
                "confidence": 0.8,
                "positions": [m.start() for m in re.finditer(re.escape(org), content)]
            })
        
        # Dates
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'
        dates = re.findall(date_pattern, content)
        for date in set(dates):
            entities.append({
                "name": date,
                "type": "DATE",
                "confidence": 0.9,
                "positions": [m.start() for m in re.finditer(re.escape(date), content)]
            })
        
        return entities
    
    async def _extract_basic_relationships(
        self, 
        content: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract basic relationships between entities"""
        
        relationships = []
        
        # Simple pattern-based relationship extraction
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Check if entities co-occur in the same sentence
                sentences = content.split('.')
                
                for sentence in sentences:
                    if entity1["name"] in sentence and entity2["name"] in sentence:
                        # Determine relationship type based on context
                        rel_type = "RELATED_TO"  # Default
                        
                        if "works for" in sentence.lower() or "employee of" in sentence.lower():
                            rel_type = "WORKS_FOR"
                        elif "located in" in sentence.lower() or "based in" in sentence.lower():
                            rel_type = "LOCATED_IN"
                        elif "part of" in sentence.lower() or "division of" in sentence.lower():
                            rel_type = "PART_OF"
                        
                        relationships.append({
                            "source": entity1["name"],
                            "target": entity2["name"],
                            "type": rel_type,
                            "confidence": 0.6,
                            "context": sentence.strip()
                        })
                        break
        
        return relationships
    
    async def _get_graph_context(
        self, 
        entities: List[Dict[str, Any]], 
        depth: int
    ) -> Dict[str, Any]:
        """Get graph context for entities"""
        
        # Simulate graph context retrieval
        context = {
            "related_entities": [],
            "relationship_patterns": {},
            "domain_knowledge": {},
            "semantic_associations": {}
        }
        
        # For each entity, simulate finding related entities
        for entity in entities[:5]:  # Limit for performance
            entity_name = entity["name"]
            
            # Simulate related entities
            related = await self._find_related_entities(entity_name, depth)
            context["related_entities"].extend(related)
            
            # Simulate relationship patterns
            patterns = await self._find_relationship_patterns(entity_name)
            context["relationship_patterns"][entity_name] = patterns
            
            # Simulate domain knowledge
            domain_info = await self._get_domain_knowledge(entity_name, entity["type"])
            context["domain_knowledge"][entity_name] = domain_info
        
        return context
    
    async def _find_related_entities(self, entity_name: str, depth: int) -> List[Dict[str, Any]]:
        """Find entities related to the given entity"""
        
        # Simulate finding related entities
        related_entities = []
        
        # Simple simulation based on entity type/name
        if "Company" in entity_name or "Corp" in entity_name:
            related_entities.extend([
                {"name": "Technology Sector", "type": "CONCEPT", "relationship": "PART_OF"},
                {"name": "Business Market", "type": "CONCEPT", "relationship": "OPERATES_IN"}
            ])
        
        if any(name_part in entity_name for name_part in ["John", "Mary", "David", "Sarah"]):
            related_entities.extend([
                {"name": "Professional Network", "type": "CONCEPT", "relationship": "MEMBER_OF"},
                {"name": "Industry Expert", "type": "CONCEPT", "relationship": "CLASSIFIED_AS"}
            ])
        
        return related_entities
    
    async def _find_relationship_patterns(self, entity_name: str) -> Dict[str, Any]:
        """Find common relationship patterns for entity"""
        
        patterns = {
            "common_relationships": ["RELATED_TO", "ASSOCIATED_WITH"],
            "typical_contexts": ["business", "professional", "organizational"],
            "strength_indicators": ["frequently mentioned", "central role"]
        }
        
        return patterns
    
    async def _get_domain_knowledge(self, entity_name: str, entity_type: str) -> Dict[str, Any]:
        """Get domain-specific knowledge about entity"""
        
        domain_info = {
            "category": entity_type,
            "common_attributes": [],
            "typical_relationships": [],
            "domain_context": ""
        }
        
        if entity_type == "PERSON":
            domain_info.update({
                "common_attributes": ["name", "role", "organization", "expertise"],
                "typical_relationships": ["WORKS_FOR", "COLLABORATES_WITH", "REPORTS_TO"],
                "domain_context": "Professional and personal networks"
            })
        elif entity_type == "ORGANIZATION":
            domain_info.update({
                "common_attributes": ["name", "industry", "size", "location"],
                "typical_relationships": ["OWNS", "PARTNERS_WITH", "COMPETES_WITH"],
                "domain_context": "Business and organizational structures"
            })
        
        return domain_info
    
    async def _enrich_entities_with_graph(
        self, 
        entities: List[Dict[str, Any]], 
        graph_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich entities with graph information"""
        
        enriched = {}
        
        for entity in entities:
            entity_name = entity["name"]
            
            enrichment = {
                "original_entity": entity,
                "graph_associations": graph_context.get("related_entities", []),
                "domain_context": graph_context.get("domain_knowledge", {}).get(entity_name, {}),
                "relationship_context": graph_context.get("relationship_patterns", {}).get(entity_name, {}),
                "confidence_boost": 0.1  # Graph context increases confidence
            }
            
            # Update confidence based on graph context
            if len(enrichment["graph_associations"]) > 0:
                enrichment["confidence_boost"] += 0.2
            
            enriched[entity_name] = enrichment
        
        return enriched
    
    async def _enhance_relationships_with_graph(
        self,
        content: str,
        entities: List[Dict[str, Any]],
        graph_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance relationships using graph knowledge"""
        
        enhanced_relationships = {
            "inferred_relationships": [],
            "strengthened_relationships": [],
            "context_relationships": []
        }
        
        # Infer relationships based on graph patterns
        for entity in entities:
            entity_name = entity["name"]
            related_entities = graph_context.get("related_entities", [])
            
            for related in related_entities:
                if related["name"] != entity_name:
                    enhanced_relationships["inferred_relationships"].append({
                        "source": entity_name,
                        "target": related["name"],
                        "type": related["relationship"],
                        "confidence": 0.5,
                        "inference_method": "graph_context"
                    })
        
        return enhanced_relationships
    
    async def _expand_semantics_with_graph(
        self,
        content: str,
        graph_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Expand semantic understanding using graph"""
        
        expansion = {
            "semantic_concepts": [],
            "contextual_meanings": {},
            "domain_specific_terms": [],
            "concept_relationships": []
        }
        
        # Extract semantic concepts from graph context
        related_entities = graph_context.get("related_entities", [])
        for entity in related_entities:
            if entity["type"] == "CONCEPT":
                expansion["semantic_concepts"].append({
                    "concept": entity["name"],
                    "relevance": 0.7,
                    "source": "graph_context"
                })
        
        return expansion
    
    async def _generate_enhanced_content(
        self,
        original_content: str,
        enriched_entities: Dict[str, Any],
        enhanced_relationships: Dict[str, Any],
        semantic_expansion: Dict[str, Any]
    ) -> str:
        """Generate enhanced content with graph insights"""
        
        # For now, return original content with metadata
        # In practice, this would generate enriched content
        
        enhancements = []
        
        # Add entity enhancements
        if enriched_entities:
            enhancements.append(f"[ENTITY_ENRICHMENT: {len(enriched_entities)} entities enriched with graph context]")
        
        # Add relationship enhancements
        inferred_count = len(enhanced_relationships.get("inferred_relationships", []))
        if inferred_count > 0:
            enhancements.append(f"[RELATIONSHIP_ENHANCEMENT: {inferred_count} relationships inferred from graph]")
        
        # Add semantic expansions
        concept_count = len(semantic_expansion.get("semantic_concepts", []))
        if concept_count > 0:
            enhancements.append(f"[SEMANTIC_EXPANSION: {concept_count} concepts added from graph]")
        
        # Combine with original content
        if enhancements:
            enhanced_content = original_content + "\n\n" + "\n".join(enhancements)
        else:
            enhanced_content = original_content
        
        return enhanced_content
    
    async def _extract_structural_elements(
        self, 
        content: str, 
        content_type: str
    ) -> Dict[str, Any]:
        """Extract structural elements from content"""
        
        elements = {
            "paragraphs": [],
            "sections": [],
            "headings": [],
            "lists": [],
            "tables": []
        }
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        elements["paragraphs"] = [{"index": i, "content": p, "length": len(p)} for i, p in enumerate(paragraphs)]
        
        # Identify headings (lines that are short and end without punctuation)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if line and len(line) < 100 and not line.endswith(('.', '!', '?', ',')):
                if line.isupper() or (line[0].isupper() and not any(c.islower() for c in line[:20])):
                    elements["headings"].append({
                        "index": i,
                        "content": line,
                        "level": 1  # Simplified - would determine actual level
                    })
        
        return elements
    
    async def _analyze_entity_distribution(
        self,
        content: str,
        structural_elements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze how entities are distributed across document structure"""
        
        distribution = {
            "entity_by_section": {},
            "entity_density": {},
            "entity_concentration": []
        }
        
        # Extract entities
        entities = await self._extract_basic_entities(content)
        
        # Map entities to paragraphs
        paragraphs = structural_elements.get("paragraphs", [])
        
        for paragraph in paragraphs:
            para_content = paragraph["content"]
            para_entities = [e for e in entities if e["name"] in para_content]
            
            distribution["entity_by_section"][paragraph["index"]] = {
                "entity_count": len(para_entities),
                "entities": [e["name"] for e in para_entities],
                "entity_types": list(set(e["type"] for e in para_entities))
            }
            
            # Calculate entity density
            if paragraph["length"] > 0:
                density = len(para_entities) / paragraph["length"] * 1000  # per 1000 chars
                distribution["entity_density"][paragraph["index"]] = density
        
        return distribution
    
    async def _identify_relationship_patterns(
        self,
        content: str,
        structural_elements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify relationship patterns in document structure"""
        
        patterns = {
            "co_occurrence_patterns": {},
            "sequential_patterns": [],
            "hierarchical_patterns": []
        }
        
        # Extract entities and relationships
        entities = await self._extract_basic_entities(content)
        relationships = await self._extract_basic_relationships(content, entities)
        
        # Analyze co-occurrence patterns
        entity_pairs = defaultdict(int)
        for rel in relationships:
            pair = tuple(sorted([rel["source"], rel["target"]]))
            entity_pairs[pair] += 1
        
        patterns["co_occurrence_patterns"] = {
            f"{pair[0]} - {pair[1]}": count 
            for pair, count in entity_pairs.items() if count > 1
        }
        
        return patterns
    
    async def _build_concept_hierarchy(self, content: str) -> Dict[str, Any]:
        """Build concept hierarchy from content"""
        
        hierarchy = {
            "root_concepts": [],
            "concept_tree": {},
            "concept_relationships": []
        }
        
        # Extract key concepts
        key_concepts = await self.identify_key_concepts_with_graph(content, top_k=15)
        
        # Group concepts by importance
        high_importance = [c for c in key_concepts if c["importance_score"] > 0.8]
        medium_importance = [c for c in key_concepts if 0.5 < c["importance_score"] <= 0.8]
        low_importance = [c for c in key_concepts if c["importance_score"] <= 0.5]
        
        hierarchy["root_concepts"] = [c["name"] for c in high_importance]
        hierarchy["concept_tree"] = {
            "high_importance": [c["name"] for c in high_importance],
            "medium_importance": [c["name"] for c in medium_importance],
            "low_importance": [c["name"] for c in low_importance]
        }
        
        return hierarchy
    
    async def _analyze_information_flow(
        self,
        content: str,
        structural_elements: Dict[str, Any],
        entity_distribution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze information flow through document"""
        
        flow_analysis = {
            "flow_direction": "linear",  # Simplified
            "information_density_curve": [],
            "topic_transitions": [],
            "entity_introduction_order": []
        }
        
        # Calculate information density across sections
        paragraphs = structural_elements.get("paragraphs", [])
        
        for para in paragraphs:
            para_index = para["index"]
            entity_count = entity_distribution.get("entity_by_section", {}).get(para_index, {}).get("entity_count", 0)
            content_length = para["length"]
            
            density = entity_count / max(content_length, 1) * 1000
            flow_analysis["information_density_curve"].append({
                "section": para_index,
                "density": density,
                "entity_count": entity_count
            })
        
        return flow_analysis
    
    async def _build_local_concept_graph(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> nx.Graph:
        """Build local concept graph from entities and relationships"""
        
        G = nx.Graph()
        
        # Add entity nodes
        for entity in entities:
            G.add_node(entity["name"], **entity)
        
        # Add relationship edges
        for rel in relationships:
            if rel["source"] in G.nodes and rel["target"] in G.nodes:
                G.add_edge(rel["source"], rel["target"], **rel)
        
        return G
    
    async def _calculate_concept_importance(
        self,
        concept_graph: nx.Graph,
        entities: List[Dict[str, Any]],
        content: str
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate importance scores for concepts"""
        
        concept_scores = {}
        
        for entity in entities:
            entity_name = entity["name"]
            
            # Frequency score
            frequency = content.lower().count(entity_name.lower())
            frequency_score = min(frequency / 10.0, 1.0)  # Normalize
            
            # Centrality score (if in graph)
            centrality_score = 0.0
            if entity_name in concept_graph.nodes:
                try:
                    centrality = nx.degree_centrality(concept_graph)[entity_name]
                    centrality_score = centrality
                except:
                    centrality_score = 0.0
            
            # Context score (based on position in text)
            context_score = 0.5  # Default
            first_occurrence = content.lower().find(entity_name.lower())
            if first_occurrence >= 0:
                # Earlier mentions get higher context score
                relative_position = first_occurrence / len(content)
                context_score = 1.0 - relative_position
            
            # Combined score
            total_score = (frequency_score * 0.4 + centrality_score * 0.4 + context_score * 0.2)
            
            concept_scores[entity_name] = {
                "type": entity["type"],
                "frequency": frequency_score,
                "centrality": centrality_score,
                "context": context_score,
                "total_score": total_score,
                "mentions": frequency,
                "related": list(concept_graph.neighbors(entity_name)) if entity_name in concept_graph.nodes else []
            }
        
        return concept_scores
    
    async def _generate_summary_sentences(
        self,
        content: str,
        entities: List[Dict[str, Any]],
        key_concepts: List[Dict[str, Any]],
        summary_length: int
    ) -> List[str]:
        """Generate summary sentences based on entities and concepts"""
        
        sentences = content.split('.')
        
        # Score sentences based on entity/concept presence
        sentence_scores = []
        
        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            score = 0.0
            
            # Score based on entity presence
            for entity in entities:
                if entity["name"] in sentence:
                    score += 1.0
            
            # Score based on key concept presence
            for concept in key_concepts:
                if concept["name"] in sentence:
                    score += concept["importance_score"]
            
            # Boost for position (earlier sentences often important)
            position_boost = max(0, 1.0 - (i / len(sentences)))
            score += position_boost * 0.5
            
            sentence_scores.append((sentence.strip(), score))
        
        # Sort by score and take top sentences
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        
        summary_sentences = [s[0] for s in sentence_scores[:summary_length]]
        
        return summary_sentences
    
    async def _extract_key_points(
        self,
        content: str,
        entities: List[Dict[str, Any]],
        key_concepts: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract key points from content"""
        
        key_points = []
        
        # Look for sentences with high entity/concept density
        sentences = content.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue
            
            entity_count = sum(1 for entity in entities if entity["name"] in sentence)
            concept_count = sum(1 for concept in key_concepts if concept["name"] in sentence)
            
            if entity_count >= 2 or concept_count >= 2:
                key_points.append(sentence)
            
            if len(key_points) >= 5:  # Limit key points
                break
        
        return key_points
    
    async def _generate_relationship_insights(
        self,
        content: str,
        entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate insights about relationships in content"""
        
        insights = []
        
        relationships = await self._extract_basic_relationships(content, entities)
        
        if relationships:
            # Count relationship types
            rel_types = Counter(rel["type"] for rel in relationships)
            
            for rel_type, count in rel_types.most_common(3):
                insights.append(f"Found {count} {rel_type} relationships")
            
            # Find most connected entities
            entity_connections = Counter()
            for rel in relationships:
                entity_connections[rel["source"]] += 1
                entity_connections[rel["target"]] += 1
            
            if entity_connections:
                most_connected = entity_connections.most_common(1)[0]
                insights.append(f"'{most_connected[0]}' is the most connected entity with {most_connected[1]} relationships")
        
        return insights
    
    async def _analyze_content_structure(self, content: str) -> Dict[str, Any]:
        """Analyze overall content structure"""
        
        structure = {
            "total_length": len(content),
            "paragraph_count": len([p for p in content.split('\n\n') if p.strip()]),
            "sentence_count": len([s for s in content.split('.') if s.strip()]),
            "average_sentence_length": 0,
            "complexity_score": 0.5
        }
        
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        if sentences:
            total_length = sum(len(s) for s in sentences)
            structure["average_sentence_length"] = total_length / len(sentences)
            
            # Simple complexity score based on sentence length variation
            lengths = [len(s) for s in sentences]
            if len(lengths) > 1:
                import statistics
                length_std = statistics.stdev(lengths)
                structure["complexity_score"] = min(length_std / 100, 1.0)
        
        return structure