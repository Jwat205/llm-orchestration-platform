"""
Enhanced relationship extractor for identifying relationships between entities
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
import json

# NLP libraries (with fallbacks)
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """Types of relationships between entities"""
    WORKS_FOR = "WORKS_FOR"
    LOCATED_IN = "LOCATED_IN"
    PART_OF = "PART_OF"
    OWNS = "OWNS"
    FOUNDED = "FOUNDED"
    ACQUIRED = "ACQUIRED"
    COMPETITOR = "COMPETITOR"
    PARTNER = "PARTNER"
    RELATED_TO = "RELATED_TO"
    TEMPORAL = "TEMPORAL"
    CAUSAL = "CAUSAL"
    SIMILAR_TO = "SIMILAR_TO"
    OPPOSITE_OF = "OPPOSITE_OF"
    MEMBER_OF = "MEMBER_OF"
    CREATES = "CREATES"
    USES = "USES"
    INFLUENCES = "INFLUENCES"


@dataclass
class Relationship:
    """Represents a relationship between two entities"""
    source_entity: str
    target_entity: str
    relationship_type: RelationshipType
    confidence: float
    evidence_text: str
    start_position: int
    end_position: int
    extraction_method: str
    metadata: Dict[str, Any]
    context: Optional[str] = None


class RelationshipExtractor:
    """Enhanced relationship extractor using multiple methods"""
    
    def __init__(self):
        self.spacy_model = None
        self.relation_classifier = None
        self.dependency_patterns = self._load_dependency_patterns()
        self.lexical_patterns = self._load_lexical_patterns()
        self.min_confidence = 0.3
        
        # Initialize models
        self._initialize_models()
        
        # Common relationship indicators
        self.relationship_indicators = {
            RelationshipType.WORKS_FOR: [
                "works for", "employed by", "employee of", "staff at",
                "works at", "job at", "position at", "role at"
            ],
            RelationshipType.LOCATED_IN: [
                "located in", "based in", "situated in", "found in",
                "headquarters in", "office in", "branch in"
            ],
            RelationshipType.PART_OF: [
                "part of", "division of", "subsidiary of", "unit of",
                "department of", "branch of", "member of"
            ],
            RelationshipType.OWNS: [
                "owns", "owner of", "belongs to", "property of",
                "possession of", "acquired", "purchased"
            ],
            RelationshipType.FOUNDED: [
                "founded", "established", "created", "started",
                "launched", "initiated", "formed"
            ],
            RelationshipType.PARTNER: [
                "partner", "partnership", "collaboration", "alliance",
                "joint venture", "cooperation", "works with"
            ],
            RelationshipType.COMPETITOR: [
                "competitor", "competes with", "rival", "competing",
                "versus", "against", "alternative to"
            ]
        }
    
    def _initialize_models(self):
        """Initialize NLP models for relationship extraction"""
        
        if SPACY_AVAILABLE:
            try:
                self.spacy_model = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded for relationship extraction")
            except OSError:
                logger.warning("spaCy model not found for relationship extraction")
                self.spacy_model = None
        
        if TRANSFORMERS_AVAILABLE:
            try:
                # Initialize relation classification pipeline if available
                # This would be a more sophisticated model in practice
                logger.info("Transformers available for relationship extraction")
            except Exception as e:
                logger.warning(f"Failed to load transformer model: {e}")
    
    async def extract_relationships(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None,
        use_dependency_parsing: bool = True,
        use_pattern_matching: bool = True,
        use_coreference: bool = True
    ) -> List[Relationship]:
        """Extract relationships between entities in text"""
        
        all_relationships = []
        
        try:
            # Method 1: Dependency parsing based extraction
            if use_dependency_parsing and self.spacy_model:
                dep_relationships = await self._extract_with_dependency_parsing(
                    text, entities, relationship_types
                )
                all_relationships.extend(dep_relationships)
            
            # Method 2: Pattern-based extraction
            if use_pattern_matching:
                pattern_relationships = await self._extract_with_patterns(
                    text, entities, relationship_types
                )
                all_relationships.extend(pattern_relationships)
            
            # Method 3: Co-occurrence and proximity based
            proximity_relationships = await self._extract_with_proximity(
                text, entities, relationship_types
            )
            all_relationships.extend(proximity_relationships)
            
            # Method 4: Coreference resolution enhanced extraction
            if use_coreference and self.spacy_model:
                coref_relationships = await self._extract_with_coreference(
                    text, entities, relationship_types
                )
                all_relationships.extend(coref_relationships)
            
            # Merge and deduplicate relationships
            merged_relationships = await self._merge_relationships(all_relationships)
            
            # Filter and validate
            filtered_relationships = self._filter_relationships(
                merged_relationships, relationship_types
            )
            
            return filtered_relationships
            
        except Exception as e:
            logger.error(f"Error in relationship extraction: {e}")
            return []
    
    async def extract_relationship_graph(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        relationships: Optional[List[Relationship]] = None
    ) -> Dict[str, Any]:
        """Extract relationships and build a graph representation"""
        
        if relationships is None:
            relationships = await self.extract_relationships(text, entities)
        
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available for graph construction")
            return {"error": "NetworkX not available"}
        
        # Create directed graph
        graph = nx.DiGraph()
        
        # Add entities as nodes
        for entity in entities:
            graph.add_node(
                entity["name"],
                entity_type=entity["type"],
                confidence=entity["confidence"],
                **entity.get("metadata", {})
            )
        
        # Add relationships as edges
        for rel in relationships:
            graph.add_edge(
                rel.source_entity,
                rel.target_entity,
                relationship_type=rel.relationship_type.value,
                confidence=rel.confidence,
                evidence=rel.evidence_text,
                extraction_method=rel.extraction_method,
                **rel.metadata
            )
        
        # Calculate graph metrics
        metrics = {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "density": nx.density(graph),
            "connected_components": nx.number_weakly_connected_components(graph)
        }
        
        # Find central entities
        if graph.number_of_nodes() > 0:
            try:
                centrality = nx.degree_centrality(graph)
                top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
                metrics["top_central_entities"] = top_central
            except:
                pass
        
        return {
            "graph": graph,
            "metrics": metrics,
            "relationships": [self._relationship_to_dict(rel) for rel in relationships]
        }
    
    async def analyze_relationship_patterns(
        self,
        relationships: List[Relationship]
    ) -> Dict[str, Any]:
        """Analyze patterns in extracted relationships"""
        
        if not relationships:
            return {"error": "No relationships to analyze"}
        
        analysis = {
            "total_relationships": len(relationships),
            "relationship_types": {},
            "confidence_distribution": {},
            "extraction_methods": {},
            "entity_connectivity": {},
            "relationship_strength": {}
        }
        
        # Relationship type distribution
        type_counts = Counter(rel.relationship_type.value for rel in relationships)
        analysis["relationship_types"] = dict(type_counts.most_common())
        
        # Confidence distribution
        confidences = [rel.confidence for rel in relationships]
        analysis["confidence_distribution"] = {
            "high": len([c for c in confidences if c >= 0.8]),
            "medium": len([c for c in confidences if 0.5 <= c < 0.8]),
            "low": len([c for c in confidences if c < 0.5]),
            "average": sum(confidences) / len(confidences),
            "min": min(confidences),
            "max": max(confidences)
        }
        
        # Extraction method distribution
        method_counts = Counter(rel.extraction_method for rel in relationships)
        analysis["extraction_methods"] = dict(method_counts)
        
        # Entity connectivity analysis
        entity_connections = defaultdict(int)
        for rel in relationships:
            entity_connections[rel.source_entity] += 1
            entity_connections[rel.target_entity] += 1
        
        analysis["entity_connectivity"] = dict(
            sorted(entity_connections.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        # Relationship strength analysis
        relationship_strength = defaultdict(list)
        for rel in relationships:
            pair = tuple(sorted([rel.source_entity, rel.target_entity]))
            relationship_strength[pair].append(rel.confidence)
        
        strong_relationships = {}
        for pair, confidences in relationship_strength.items():
            avg_confidence = sum(confidences) / len(confidences)
            if avg_confidence >= 0.7:
                strong_relationships[f"{pair[0]} <-> {pair[1]}"] = {
                    "average_confidence": avg_confidence,
                    "relationship_count": len(confidences)
                }
        
        analysis["relationship_strength"] = strong_relationships
        
        return analysis
    
    # Extraction method implementations
    async def _extract_with_dependency_parsing(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Relationship]:
        """Extract relationships using dependency parsing"""
        
        if not self.spacy_model:
            return []
        
        def extract():
            doc = self.spacy_model(text)
            relationships = []
            
            # Create entity lookup
            entity_spans = {}
            for entity in entities:
                if "start" in entity and "end" in entity:
                    entity_spans[(entity["start"], entity["end"])] = entity
            
            # Process sentences
            for sent in doc.sents:
                sent_relationships = self._extract_sentence_relationships(
                    sent, entity_spans, relationship_types
                )
                relationships.extend(sent_relationships)
            
            return relationships
        
        return await asyncio.to_thread(extract)
    
    def _extract_sentence_relationships(
        self,
        sent,
        entity_spans: Dict[Tuple[int, int], Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Relationship]:
        """Extract relationships from a single sentence using dependency parsing"""
        
        relationships = []
        
        # Find entities in this sentence
        sent_entities = []
        for (start, end), entity in entity_spans.items():
            if sent.start_char <= start < sent.end_char:
                sent_entities.append(entity)
        
        if len(sent_entities) < 2:
            return relationships
        
        # Apply dependency patterns
        for pattern_info in self.dependency_patterns:
            matches = self._match_dependency_pattern(sent, pattern_info, sent_entities)
            relationships.extend(matches)
        
        return relationships
    
    def _match_dependency_pattern(
        self,
        sent,
        pattern_info: Dict[str, Any],
        entities: List[Dict[str, Any]]
    ) -> List[Relationship]:
        """Match dependency patterns in sentence"""
        
        relationships = []
        pattern = pattern_info["pattern"]
        rel_type = pattern_info["relationship_type"]
        confidence = pattern_info["confidence"]
        
        # This is a simplified pattern matching
        # In practice, this would use more sophisticated dependency pattern matching
        for token in sent:
            if token.lemma_ in pattern.get("verbs", []):
                # Find subject and object
                subject = None
                obj = None
                
                for child in token.children:
                    if child.dep_ in ["nsubj", "nsubjpass"]:
                        subject = self._find_entity_for_token(child, entities)
                    elif child.dep_ in ["dobj", "pobj"]:
                        obj = self._find_entity_for_token(child, entities)
                
                if subject and obj and subject != obj:
                    relationship = Relationship(
                        source_entity=subject["name"],
                        target_entity=obj["name"],
                        relationship_type=rel_type,
                        confidence=confidence,
                        evidence_text=sent.text,
                        start_position=sent.start_char,
                        end_position=sent.end_char,
                        extraction_method="dependency_parsing",
                        metadata={
                            "verb": token.lemma_,
                            "dependency_pattern": pattern_info["name"]
                        }
                    )
                    relationships.append(relationship)
        
        return relationships
    
    def _find_entity_for_token(self, token, entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find entity that contains or matches the given token"""
        
        for entity in entities:
            if token.text in entity["name"] or entity["name"] in token.text:
                return entity
            
            # Check if token is part of entity span
            if "start" in entity and "end" in entity:
                if entity["start"] <= token.idx < entity["end"]:
                    return entity
        
        return None
    
    async def _extract_with_patterns(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Relationship]:
        """Extract relationships using lexical patterns"""
        
        relationships = []
        
        # Create entity name lookup
        entity_names = {entity["name"]: entity for entity in entities}
        
        for rel_type, patterns in self.lexical_patterns.items():
            if relationship_types and rel_type not in relationship_types:
                continue
            
            for pattern_info in patterns:
                pattern = pattern_info["pattern"]
                confidence = pattern_info["confidence"]
                
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Extract entities from the match
                    matched_text = match.group()
                    
                    # Find entities in the matched text
                    matched_entities = []
                    for entity_name, entity in entity_names.items():
                        if entity_name.lower() in matched_text.lower():
                            matched_entities.append(entity)
                    
                    # Create relationships between matched entities
                    if len(matched_entities) >= 2:
                        for i in range(len(matched_entities) - 1):
                            source = matched_entities[i]
                            target = matched_entities[i + 1]
                            
                            relationship = Relationship(
                                source_entity=source["name"],
                                target_entity=target["name"],
                                relationship_type=rel_type,
                                confidence=confidence,
                                evidence_text=matched_text,
                                start_position=match.start(),
                                end_position=match.end(),
                                extraction_method="pattern_matching",
                                metadata={
                                    "pattern_name": pattern_info["name"],
                                    "full_match": matched_text
                                }
                            )
                            relationships.append(relationship)
        
        return relationships
    
    async def _extract_with_proximity(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None,
        max_distance: int = 100
    ) -> List[Relationship]:
        """Extract relationships based on entity proximity"""
        
        relationships = []
        
        # Sort entities by position
        positioned_entities = [
            e for e in entities if "start" in e and "end" in e
        ]
        positioned_entities.sort(key=lambda x: x["start"])
        
        # Find entities within proximity
        for i, entity1 in enumerate(positioned_entities):
            for entity2 in positioned_entities[i + 1:]:
                distance = entity2["start"] - entity1["end"]
                
                if distance > max_distance:
                    break  # Too far, and subsequent entities will be even farther
                
                # Calculate confidence based on distance and context
                confidence = max(0.1, 1.0 - (distance / max_distance))
                
                # Extract context between entities
                context_start = entity1["end"]
                context_end = entity2["start"]
                context = text[context_start:context_end].strip()
                
                # Determine relationship type from context
                rel_type = self._infer_relationship_type_from_context(
                    context, entity1, entity2
                )
                
                if rel_type and confidence >= self.min_confidence:
                    relationship = Relationship(
                        source_entity=entity1["name"],
                        target_entity=entity2["name"],
                        relationship_type=rel_type,
                        confidence=confidence,
                        evidence_text=text[entity1["start"]:entity2["end"]],
                        start_position=entity1["start"],
                        end_position=entity2["end"],
                        extraction_method="proximity",
                        metadata={
                            "distance": distance,
                            "context": context
                        }
                    )
                    relationships.append(relationship)
        
        return relationships
    
    def _infer_relationship_type_from_context(
        self,
        context: str,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> Optional[RelationshipType]:
        """Infer relationship type from context between entities"""
        
        context_lower = context.lower()
        
        # Check for explicit relationship indicators
        for rel_type, indicators in self.relationship_indicators.items():
            for indicator in indicators:
                if indicator in context_lower:
                    return rel_type
        
        # Infer based on entity types
        type1, type2 = entity1["type"], entity2["type"]
        
        if type1 == "PERSON" and type2 == "ORGANIZATION":
            return RelationshipType.WORKS_FOR
        elif type1 == "ORGANIZATION" and type2 == "LOCATION":
            return RelationshipType.LOCATED_IN
        elif type1 == "PERSON" and type2 == "LOCATION":
            return RelationshipType.LOCATED_IN
        elif type1 == "ORGANIZATION" and type2 == "ORGANIZATION":
            if any(word in context_lower for word in ["partner", "collaboration"]):
                return RelationshipType.PARTNER
            elif any(word in context_lower for word in ["compete", "rival"]):
                return RelationshipType.COMPETITOR
            else:
                return RelationshipType.RELATED_TO
        
        return RelationshipType.RELATED_TO
    
    async def _extract_with_coreference(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Relationship]:
        """Extract relationships using coreference resolution"""
        
        # This is a simplified version
        # In practice, this would use more sophisticated coreference resolution
        relationships = []
        
        # Simple pronoun resolution
        pronouns = ["he", "she", "it", "they", "his", "her", "its", "their"]
        
        sentences = text.split('.')
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            for pronoun in pronouns:
                if pronoun in sentence_lower:
                    # Find nearest entity that could be the antecedent
                    antecedent = self._find_pronoun_antecedent(
                        sentence, pronoun, entities, text
                    )
                    
                    if antecedent:
                        # Look for other entities in the sentence
                        sentence_entities = [
                            e for e in entities 
                            if e["name"].lower() in sentence_lower and e != antecedent
                        ]
                        
                        for other_entity in sentence_entities:
                            rel_type = self._infer_relationship_type_from_context(
                                sentence, antecedent, other_entity
                            )
                            
                            if rel_type:
                                relationship = Relationship(
                                    source_entity=antecedent["name"],
                                    target_entity=other_entity["name"],
                                    relationship_type=rel_type,
                                    confidence=0.6,  # Lower confidence due to inference
                                    evidence_text=sentence,
                                    start_position=text.find(sentence),
                                    end_position=text.find(sentence) + len(sentence),
                                    extraction_method="coreference",
                                    metadata={
                                        "pronoun": pronoun,
                                        "coreference_resolution": True
                                    }
                                )
                                relationships.append(relationship)
        
        return relationships
    
    def _find_pronoun_antecedent(
        self,
        sentence: str,
        pronoun: str,
        entities: List[Dict[str, Any]],
        full_text: str
    ) -> Optional[Dict[str, Any]]:
        """Find the antecedent entity for a pronoun"""
        
        # Simple heuristic: find the nearest person/organization entity before the pronoun
        sentence_start = full_text.find(sentence)
        pronoun_pos = sentence.lower().find(pronoun) + sentence_start
        
        candidates = []
        for entity in entities:
            if entity["type"] in ["PERSON", "ORGANIZATION"] and "start" in entity:
                if entity["start"] < pronoun_pos:
                    distance = pronoun_pos - entity["start"]
                    candidates.append((entity, distance))
        
        if candidates:
            # Return the closest entity
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]
        
        return None
    
    async def _merge_relationships(
        self,
        relationships: List[Relationship]
    ) -> List[Relationship]:
        """Merge duplicate and overlapping relationships"""
        
        if not relationships:
            return []
        
        # Group relationships by entity pair and type
        relationship_groups = defaultdict(list)
        
        for rel in relationships:
            key = (rel.source_entity, rel.target_entity, rel.relationship_type)
            relationship_groups[key].append(rel)
        
        merged_relationships = []
        
        for group in relationship_groups.values():
            if len(group) == 1:
                merged_relationships.append(group[0])
            else:
                # Merge multiple relationships
                merged_rel = self._merge_relationship_group(group)
                merged_relationships.append(merged_rel)
        
        return merged_relationships
    
    def _merge_relationship_group(self, group: List[Relationship]) -> Relationship:
        """Merge a group of similar relationships"""
        
        # Use the highest confidence relationship as base
        base_rel = max(group, key=lambda x: x.confidence)
        
        # Average confidence
        avg_confidence = sum(rel.confidence for rel in group) / len(group)
        
        # Combine evidence
        evidence_texts = [rel.evidence_text for rel in group]
        combined_evidence = " | ".join(set(evidence_texts))
        
        # Combine extraction methods
        methods = list(set(rel.extraction_method for rel in group))
        combined_method = "+".join(methods)
        
        # Create merged relationship
        merged_rel = Relationship(
            source_entity=base_rel.source_entity,
            target_entity=base_rel.target_entity,
            relationship_type=base_rel.relationship_type,
            confidence=min(avg_confidence * 1.1, 1.0),  # Slight boost for consensus
            evidence_text=combined_evidence,
            start_position=min(rel.start_position for rel in group),
            end_position=max(rel.end_position for rel in group),
            extraction_method=combined_method,
            metadata={
                "merged_from": len(group),
                "original_confidences": [rel.confidence for rel in group],
                "extraction_methods": methods
            }
        )
        
        return merged_rel
    
    def _filter_relationships(
        self,
        relationships: List[Relationship],
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Relationship]:
        """Filter relationships by confidence and type"""
        
        filtered = []
        
        for rel in relationships:
            # Filter by confidence
            if rel.confidence < self.min_confidence:
                continue
            
            # Filter by type
            if relationship_types and rel.relationship_type not in relationship_types:
                continue
            
            # Filter out self-relationships
            if rel.source_entity == rel.target_entity:
                continue
            
            filtered.append(rel)
        
        return filtered
    
    def _relationship_to_dict(self, relationship: Relationship) -> Dict[str, Any]:
        """Convert relationship to dictionary representation"""
        
        return {
            "source_entity": relationship.source_entity,
            "target_entity": relationship.target_entity,
            "relationship_type": relationship.relationship_type.value,
            "confidence": relationship.confidence,
            "evidence_text": relationship.evidence_text,
            "start_position": relationship.start_position,
            "end_position": relationship.end_position,
            "extraction_method": relationship.extraction_method,
            "metadata": relationship.metadata,
            "context": relationship.context
        }
    
    def _load_dependency_patterns(self) -> List[Dict[str, Any]]:
        """Load dependency parsing patterns for relationship extraction"""
        
        return [
            {
                "name": "works_for_pattern",
                "pattern": {"verbs": ["work", "employ"]},
                "relationship_type": RelationshipType.WORKS_FOR,
                "confidence": 0.8
            },
            {
                "name": "located_in_pattern",
                "pattern": {"verbs": ["locate", "base", "situate"]},
                "relationship_type": RelationshipType.LOCATED_IN,
                "confidence": 0.8
            },
            {
                "name": "own_pattern",
                "pattern": {"verbs": ["own", "possess", "acquire"]},
                "relationship_type": RelationshipType.OWNS,
                "confidence": 0.8
            },
            {
                "name": "found_pattern",
                "pattern": {"verbs": ["found", "establish", "create", "start"]},
                "relationship_type": RelationshipType.FOUNDED,
                "confidence": 0.8
            }
        ]
    
    def _load_lexical_patterns(self) -> Dict[RelationshipType, List[Dict[str, Any]]]:
        """Load lexical patterns for relationship extraction"""
        
        return {
            RelationshipType.WORKS_FOR: [
                {
                    "name": "employment_pattern",
                    "pattern": r'(\w+(?:\s+\w+)*)\s+(?:works\s+(?:for|at)|employed\s+by|job\s+at)\s+(\w+(?:\s+\w+)*)',
                    "confidence": 0.8
                }
            ],
            RelationshipType.LOCATED_IN: [
                {
                    "name": "location_pattern",
                    "pattern": r'(\w+(?:\s+\w+)*)\s+(?:located\s+in|based\s+in|situated\s+in)\s+(\w+(?:\s+\w+)*)',
                    "confidence": 0.8
                }
            ],
            RelationshipType.FOUNDED: [
                {
                    "name": "founding_pattern",
                    "pattern": r'(\w+(?:\s+\w+)*)\s+(?:founded|established|created)\s+(\w+(?:\s+\w+)*)',
                    "confidence": 0.8
                }
            ],
            RelationshipType.OWNS: [
                {
                    "name": "ownership_pattern",
                    "pattern": r'(\w+(?:\s+\w+)*)\s+(?:owns|acquired|purchased)\s+(\w+(?:\s+\w+)*)',
                    "confidence": 0.8
                }
            ]
        }