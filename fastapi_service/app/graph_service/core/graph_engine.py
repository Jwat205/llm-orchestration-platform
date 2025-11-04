"""
Enhanced Graph Engine - Improved relationship creation and node connectivity
Maintains existing names while adding better relationship extraction capabilities
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import asyncio
import uuid
from datetime import datetime
import logging
import inspect
import re
from dataclasses import dataclass
from collections import defaultdict, Counter
import spacy
from ..storage.neo4j_adapter import Neo4jAdapter
from ..storage.graph_cache import GraphCache
from ..extractors.spacy_extractors import SpacyExtractor
from ..extractors.transformer_extractor import TransformerExtractor
from ..extractors.multi_modal_extractor import MultiModalExtractor
from ..extractors.custom_extractor import CustomExtractor
from ..builders.incremental_builder import IncrementalBuilder
from ..builders.batch_builder import BatchBuilder
from app.graph_service.extractors.custom_extractor import EntityMatch
from ...main import settings
from app.graph_service.extractors.custom_extractor import EntityMatch, normalize_entity, RelationshipMatch

logger = logging.getLogger(__name__)

@dataclass
class GraphStats:
    """Graph statistics data class"""
    total_entities: int
    total_relationships: int
    entity_types: Dict[str, int]
    relationship_types: Dict[str, int]
    avg_degree: float
    max_degree: int
    connected_components: int

@dataclass
class RelationshipPattern:
    """Enhanced relationship pattern matching"""
    pattern: str
    relationship_type: str
    confidence: float
    direction: str = "forward"  # forward, backward, bidirectional
    context_words: List[str] = None
    entity_constraints: Dict[str, List[str]] = None  # entity type constraints

class GraphEngine:
    from ..algorithms.path_finding import PathFinding
    from ..algorithms.centrality_measures import CentralityMeasures
    from ..algorithms.community_detection import CommunityDetection
    from ...shared.schemas.graph_schemas import GraphEntity, GraphRelationship

    """Enhanced core graph engine for knowledge graph operations"""
    
    def __init__(self, storage_adapter, cache, uri: str, user: str, password: str):
        self.storage = storage_adapter
        self.cache = cache
        self.extractors = self._initialize_extractors()
        self.builders = self._initialize_builders()
        self.algorithms = self._initialize_algorithms()
        self.entity_id_counter = 0
        self.relationship_id_counter = 0
        self.uri = settings.neo4j_uri
        self.user = settings.neo4j_user
        self.password = settings.neo4j_password
        
        # Enhanced relationship patterns
        self.relationship_patterns = self._initialize_relationship_patterns()
        
        # Entity similarity threshold for linking
        self.entity_similarity_threshold = 0.85
        
        # Relationship confidence threshold
        self.relationship_confidence_threshold = 0.6
        
        # Initialize NLP model for better text processing
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("SpaCy model not found, using basic text processing")
            self.nlp = None

    def _entity_name(self, e: Any) -> str:
        # prefer GraphEntity.name, else fallback to extractor Entity.text/canonical_form
        return getattr(e, "name", getattr(e, "text", getattr(e, "canonical_form", "")))
    
    def _to_entity_match(self, e, text: str) -> EntityMatch:
        # Already correct type
        if isinstance(e, EntityMatch):
            return e

        # Your GraphEntity schema
        if hasattr(e, "name"):
            props = getattr(e, "properties", {}) or {}
            return EntityMatch(
                text=e.name or props.get("text", ""),
                entity_type=getattr(e, "type", "UNKNOWN"),
                start=props.get("start", -1),
                end=props.get("end", -1),
                confidence=getattr(e, "confidence", 1.0),
                attributes=props,
                context=""
            )

        # Fallback: plain string – compute positions from the text
        if isinstance(e, str):
            idx = text.lower().find(e.lower())
            if idx == -1:
                return EntityMatch(e, "UNKNOWN", -1, -1, 0.5, {}, "")
            return EntityMatch(e, "UNKNOWN", idx, idx + len(e), 0.5, {}, "")

        # Dict?
        if isinstance(e, dict):
            return EntityMatch(
                text=e.get("text", ""),
                entity_type=e.get("label", "UNKNOWN"),
                start=int(e.get("start", -1)),
                end=int(e.get("end", -1)),
                confidence=float(e.get("confidence", 1.0)),
                attributes=e.get("attributes", {}),
                context=e.get("context", "")
            )

        # Last resort
        return EntityMatch(str(e), "UNKNOWN", -1, -1, 0.5, {}, "")

    def _initialize_relationship_patterns(self) -> List[RelationshipPattern]:
        """Initialize comprehensive relationship patterns"""
        patterns = [
            # Causal relationships
            RelationshipPattern(
                pattern=r"\b(?:causes?|leads?\s+to|results?\s+in|triggers?|brings?\s+about)\b",
                relationship_type="CAUSES",
                confidence=0.85,
                context_words=["because", "due to", "resulting", "leading"]
            ),
            
            # Hierarchical relationships
            RelationshipPattern(
                pattern=r"\b(?:is\s+a|are|type\s+of|kind\s+of|subclass\s+of|instance\s+of)\b",
                relationship_type="IS_A",
                confidence=0.9,
                context_words=["classified", "categorized", "belongs"]
            ),
            
            # Part-whole relationships
            RelationshipPattern(
                pattern=r"\b(?:part\s+of|contains?|includes?|comprises?|consists?\s+of|has)\b",
                relationship_type="PART_OF",
                confidence=0.8,
                context_words=["component", "element", "portion"]
            ),
            
            # Temporal relationships
            RelationshipPattern(
                pattern=r"\b(?:before|after|during|while|when|then|next|follows?|precedes?)\b",
                relationship_type="TEMPORAL",
                confidence=0.75,
                context_words=["time", "sequence", "order", "chronological"]
            ),
            
            # Spatial relationships
            RelationshipPattern(
                pattern=r"\b(?:in|on|at|near|inside|outside|above|below|beside|next\s+to)\b",
                relationship_type="LOCATED_IN",
                confidence=0.7,
                context_words=["location", "position", "place", "situated"]
            ),
            
            # Association relationships
            RelationshipPattern(
                pattern=r"\b(?:related\s+to|associated\s+with|connected\s+to|linked\s+to|similar\s+to)\b",
                relationship_type="RELATED_TO",
                confidence=0.65,
                context_words=["correlation", "connection", "association"]
            ),
            
            # Ownership/Possession
            RelationshipPattern(
                pattern=r"\b(?:owns?|belongs?\s+to|possesses?|has|holds?)\b",
                relationship_type="OWNS",
                confidence=0.8,
                context_words=["property", "possession", "ownership"]
            ),
            
            # Action relationships
            RelationshipPattern(
                pattern=r"\b(?:performs?|does|executes?|carries?\s+out|conducts?)\b",
                relationship_type="PERFORMS",
                confidence=0.75,
                context_words=["action", "activity", "task", "function"]
            ),
            
            # Negation relationships
            RelationshipPattern(
                pattern=r"\b(?:not|never|opposite\s+of|different\s+from|contrary\s+to)\b",
                relationship_type="OPPOSITE_OF",
                confidence=0.7,
                context_words=["contrast", "difference", "negation"]
            ),
            
            # Dependency relationships
            RelationshipPattern(
                pattern=r"\b(?:depends\s+on|requires?|needs?|relies\s+on|based\s+on)\b",
                relationship_type="DEPENDS_ON",
                confidence=0.8,
                context_words=["dependency", "requirement", "prerequisite"]
            )
        ]
        
        return patterns
        
    def _initialize_extractors(self) -> Dict[str, Any]:
        """Initialize all extractors with enhanced configuration"""
        config = {
            "patterns": {
                "PERSON": [
                    {"pattern": r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", "confidence": 0.9},
                    {"pattern": r"\b(?:Dr|Mr|Mrs|Ms|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", "confidence": 0.95}
                ],
                "ORGANIZATION": [
                    {"pattern": r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|LLC|Ltd|Company|Organization)\b", "confidence": 0.9}
                ],
                "LOCATION": [
                    {"pattern": r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:City|State|Country|Street|Avenue|Road)\b", "confidence": 0.85}
                ],
                "DISEASE": [
                    {"pattern": r"\b(?:diabetes|hypertension|cancer|pneumonia|influenza)\b", "confidence": 0.8}
                ],
                "MEDICATION": [
                    {"pattern": r"\b(?:aspirin|insulin|antibiotics|vaccine)\b", "confidence": 0.8}
                ]
            },
            "keywords": {
                "DISEASE": ["diabetes", "hypertension", "cancer", "illness", "condition"],
                "TREATMENT": ["treatment", "therapy", "medication", "surgery", "procedure"],
                "SYMPTOM": ["symptom", "sign", "manifestation", "indication"]
            },
            "rules": [
                {
                    "name": "causal_rule",
                    "entity_type": "CAUSE",
                    "pattern": r"caused by|results in|leads to"
                },
                {
                    "name": "treatment_rule", 
                    "entity_type": "TREATMENT",
                    "pattern": r"treated with|therapy for|medication for"
                }
            ],
            "entity_filters": {
                "exclude_labels": ["DATE", "TIME", "CARDINAL"],
                "min_length": 2
            },
            "relationship_filters": {
                "min_confidence": 0.6,
                "max_distance": 50  # max word distance between entities
            }
        }

        return {
            "custom": CustomExtractor(config),
            "spacy": SpacyExtractor(),
            "transformer": TransformerExtractor(),
            "multi_modal": MultiModalExtractor()
        }

    def _initialize_builders(self):
        """Initialize graph builders"""
        return {
            'incremental': IncrementalBuilder(self.storage),
            'batch': BatchBuilder(self.storage)
        }
    
    def _initialize_algorithms(self):
        from ..algorithms.path_finding import PathFinding
        from ..algorithms.centrality_measures import CentralityMeasures
        from ..algorithms.community_detection import CommunityDetection
        from ...shared.schemas.graph_schemas import GraphEntity, GraphRelationship
        """Initialize graph algorithms"""
        return {
            'path_finder': PathFinding(self.storage),
            'centrality': CentralityMeasures(self.storage),
            'community': CommunityDetection(self.storage)
        }
    
    async def create_entity(self, entity_data: Dict[str, Any]) -> 'GraphEntity':
        from ...shared.schemas.graph_schemas import GraphEntity, GraphRelationship

        """Create a new entity in the knowledge graph with enhanced linking"""
        try:
            # Generate unique ID if not provided
            entity_id = entity_data.get('id', f"entity_{uuid.uuid4().hex}")
            
            # Check for similar existing entities
            similar_entities = await self._find_similar_entities(entity_data)
            
            if similar_entities:
                # Link to most similar entity instead of creating duplicate
                most_similar = max(similar_entities, key=lambda x: x['similarity'])
                if most_similar['similarity'] > self.entity_similarity_threshold:
                    logger.info(f"Linking to existing similar entity: {most_similar['entity'].id}")
                    return most_similar['entity']
            
            # Create entity object
            entity = GraphEntity(
                id=entity_id,
                type=entity_data.get('type', 'Unknown'),
                name=entity_data.get('name', ''),
                properties=entity_data.get('properties', {}),
                confidence=entity_data.get('confidence', 1.0),
                source=entity_data.get('source', 'manual'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Store in graph database
            await self.storage.create_entity(entity)
            
            # Cache entity
            await self.cache.cache_entity(entity)
            
            logger.info(f"Created entity: {entity_id} ({entity.type})")
            return entity
            
        except Exception as e:
            logger.error(f"Error creating entity: {e}")
            raise
    
    async def create_relationship(self, relationship_data: Dict[str, Any]) -> 'GraphRelationship':
        from ...shared.schemas.graph_schemas import GraphEntity, GraphRelationship

        """Create a new relationship in the knowledge graph with validation"""
        try:
            # Generate unique ID if not provided
            rel_id = relationship_data.get('id', f"rel_{uuid.uuid4().hex}")
            
            # Create relationship object
            relationship = GraphRelationship(
                id=rel_id,
                source_id=relationship_data['source_id'],
                target_id=relationship_data['target_id'],
                type=relationship_data['type'],
                properties=relationship_data.get('properties', {}),
                confidence=relationship_data.get('confidence', 1.0),
                weight=relationship_data.get('weight', 1.0),
                source=relationship_data.get('source', 'manual'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Verify entities exist
            source_entity = await self.get_entity(relationship.source_id)
            target_entity = await self.get_entity(relationship.target_id)
            
            if not source_entity or not target_entity:
                raise ValueError("Source or target entity not found")
            
            # Check for duplicate relationships
            existing_rel = await self._check_existing_relationship(
                relationship.source_id, 
                relationship.target_id, 
                relationship.type
            )
            
            if existing_rel:
                # Update confidence and properties instead of creating duplicate
                await self._update_relationship_confidence(existing_rel, relationship)
                return existing_rel
            
            # Store in graph database
            await self.storage.create_relationship(relationship)
            
            # Cache relationship
            await self.cache.cache_relationship(relationship)
            
            logger.info(f"Created relationship: {rel_id} ({relationship.type})")
            return relationship
            
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            raise
    
    async def extract_entities(
        self,
        text: str,
        extractors: List[str] | None = None,
        confidence_threshold: float = 0.5,
    ) -> List["GraphEntity"]:
        """Extract entities from text using available extractors with enhanced processing"""
        try:
            if extractors is None:
                extractors = list(self.extractors.keys())

            # Preprocess text for better extraction
            processed_text = self._preprocess_text(text)
            
            loop = asyncio.get_running_loop()
            tasks = []

            for name in extractors:
                extractor = self.extractors.get(name)
                if not extractor:
                    continue

                if not hasattr(extractor, "extract_entities"):
                    logger.debug("Skipping %s: no extract_entities()", name)
                    continue

                fn = getattr(extractor, "extract_entities")

                if inspect.iscoroutinefunction(fn):
                    tasks.append(fn(processed_text, confidence_threshold))
                else:
                    tasks.append(loop.run_in_executor(None, fn, processed_text, confidence_threshold))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_entities: list["GraphEntity"] = []
            for res in results:
                if isinstance(res, Exception):
                    logger.exception("Extractor failed", exc_info=res)
                    continue
                all_entities.extend(res)

            # Enhanced entity processing
            filtered_entities = self._filter_entities(all_entities)
            merged = await self._merge_duplicate_entities(filtered_entities)
            
            logger.info("Extracted %d entities from text", len(merged))
            return merged

        except Exception as e:
            logger.error("Error extracting entities: %s", e)
            raise
        
    async def extract_relationships(
        self,
        text: str,
        entities: Optional[List[Any]] = None,
        use_patterns: bool = True,
        use_dependency_parsing: bool = True
    ) -> List[RelationshipMatch]:
        """Enhanced relationship extraction with multiple methods"""
        
        try:
            # Get entities if not provided
            raw_entities = await self.extract_entities(text) if entities is None else entities
            entity_matches = [normalize_entity(e, text) for e in raw_entities]

            all_relationships: List[RelationshipMatch] = []
            
            # Method 1: Use existing extractors
            for name, extractor in self.extractors.items():
                if not hasattr(extractor, "extract_relationships"):
                    continue
                res = extractor.extract_relationships(text, entity_matches)
                if inspect.isawaitable(res):
                    res = await res
                all_relationships.extend(res)

            # Method 2: Pattern-based extraction
            if use_patterns:
                pattern_relationships = self._extract_relationships_by_patterns(text, entity_matches)
                all_relationships.extend(pattern_relationships)
            
            # Method 3: Dependency parsing (if spaCy available)
            if use_dependency_parsing and self.nlp:
                dependency_relationships = self._extract_relationships_by_dependency(text, entity_matches)
                all_relationships.extend(dependency_relationships)
            
            # Method 4: Context-based extraction
            context_relationships = self._extract_relationships_by_context(text, entity_matches)
            all_relationships.extend(context_relationships)
            
            # Filter and deduplicate
            filtered_relationships = self._filter_relationships(all_relationships)
            unique_relationships = self._deduplicate_relationship_matches(filtered_relationships)
            
            logger.info(f"Extracted {len(unique_relationships)} relationships from text")
            return unique_relationships
            
        except Exception as e:
            logger.error("Error extracting relationships: %s", e)
            raise

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for better extraction"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Fix common punctuation issues
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        text = re.sub(r'([,.!?;:])\s*([A-Z])', r'\1 \2', text)
        
        return text

    def _filter_entities(self, entities: List['GraphEntity']) -> List['GraphEntity']:
        """Filter entities based on quality criteria"""
        filtered = []
        
        for entity in entities:
            entity_name = getattr(entity, 'name', '')
            entity_confidence = getattr(entity, 'confidence', 0.0)
            
            # Filter by minimum length
            if len(entity_name.strip()) < 2:
                continue
                
            # Filter by confidence
            if entity_confidence < 0.3:
                continue
                
            # Filter out common stop words as entities
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            if entity_name.lower() in stop_words:
                continue
                
            filtered.append(entity)
            
        return filtered

    def _extract_relationships_by_patterns(self, text: str, entities: List[EntityMatch]) -> List[RelationshipMatch]:
        """Extract relationships using predefined patterns"""
        relationships = []
        
        if len(entities) < 2:
            return relationships
        
        # Sort entities by position in text
        sorted_entities = sorted(entities, key=lambda x: x.start if x.start >= 0 else 0)
        
        for i, entity1 in enumerate(sorted_entities):
            for j, entity2 in enumerate(sorted_entities[i+1:], i+1):
                # Get text between entities
                start_pos = entity1.end if entity1.end >= 0 else 0
                end_pos = entity2.start if entity2.start >= 0 else len(text)
                
                if start_pos >= end_pos:
                    continue
                    
                between_text = text[start_pos:end_pos].strip()
                
                # Skip if too far apart
                if len(between_text) > 200:
                    continue
                
                # Check patterns
                for pattern in self.relationship_patterns:
                    if re.search(pattern.pattern, between_text, re.IGNORECASE):
                        # Check context words for confidence boost
                        confidence = pattern.confidence
                        if pattern.context_words:
                            for context_word in pattern.context_words:
                                if context_word in between_text.lower():
                                    confidence += 0.1
                                    break
                        
                        confidence = min(confidence, 1.0)
                        
                        if confidence >= self.relationship_confidence_threshold:
                            relationships.append(RelationshipMatch(
                                source_entity=entity1.text,
                                target_entity=entity2.text,
                                relationship_type=pattern.relationship_type,
                                confidence=confidence,
                                context=between_text,
                                source_start=entity1.start,
                                source_end=entity1.end,
                                target_start=entity2.start,
                                target_end=entity2.end
                            ))
        
        return relationships

    def _extract_relationships_by_dependency(self, text: str, entities: List[EntityMatch]) -> List[RelationshipMatch]:
        """Extract relationships using dependency parsing"""
        relationships = []
        
        if not self.nlp or len(entities) < 2:
            return relationships
        
        try:
            doc = self.nlp(text)
            
            # Create entity position map
            entity_tokens = {}
            for entity in entities:
                if entity.start >= 0 and entity.end >= 0:
                    for token in doc:
                        if token.idx >= entity.start and token.idx < entity.end:
                            entity_tokens[token.i] = entity
            
            # Extract relationships based on dependencies
            for token in doc:
                if token.i in entity_tokens:
                    entity1 = entity_tokens[token.i]
                    
                    # Check verb relationships
                    if token.dep_ in ['nsubj', 'dobj', 'pobj']:
                        head = token.head
                        if head.pos_ == 'VERB':
                            # Find other entities related to this verb
                            for child in head.children:
                                if child.i in entity_tokens and child.i != token.i:
                                    entity2 = entity_tokens[child.i]
                                    
                                    # Determine relationship type based on dependency
                                    rel_type = self._dependency_to_relationship_type(token.dep_, child.dep_, head.lemma_)
                                    
                                    relationships.append(RelationshipMatch(
                                        source_entity=entity1.text,
                                        target_entity=entity2.text,
                                        relationship_type=rel_type,
                                        confidence=0.75,
                                        context=f"{entity1.text} {head.lemma_} {entity2.text}",
                                        source_start=entity1.start,
                                        source_end=entity1.end,
                                        target_start=entity2.start,
                                        target_end=entity2.end
                                    ))
        
        except Exception as e:
            logger.error(f"Error in dependency parsing: {e}")
        
        return relationships

    def _dependency_to_relationship_type(self, dep1: str, dep2: str, verb: str) -> str:
        """Map dependency relations to relationship types"""
        verb_mapping = {
            'cause': 'CAUSES',
            'lead': 'LEADS_TO',
            'result': 'RESULTS_IN',
            'contain': 'CONTAINS',
            'have': 'HAS',
            'own': 'OWNS',
            'use': 'USES',
            'perform': 'PERFORMS',
            'create': 'CREATES',
            'destroy': 'DESTROYS'
        }
        
        return verb_mapping.get(verb.lower(), 'RELATED_TO')

    def _extract_relationships_by_context(self, text: str, entities: List[EntityMatch]) -> List[RelationshipMatch]:
        """Extract relationships based on contextual clues"""
        relationships = []
        
        # Co-occurrence patterns
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence_entities = [e for e in entities 
                               if e.start >= 0 and sentence.find(e.text) >= 0]
            
            if len(sentence_entities) >= 2:
                # Entities in same sentence are likely related
                for i, entity1 in enumerate(sentence_entities):
                    for entity2 in sentence_entities[i+1:]:
                        # Determine relationship strength based on distance
                        distance = abs(sentence.find(entity1.text) - sentence.find(entity2.text))
                        confidence = max(0.5, 1.0 - (distance / len(sentence)))
                        
                        if confidence >= self.relationship_confidence_threshold:
                            relationships.append(RelationshipMatch(
                                source_entity=entity1.text,
                                target_entity=entity2.text,
                                relationship_type='CO_OCCURS',
                                confidence=confidence,
                                context=sentence.strip(),
                                source_start=entity1.start,
                                source_end=entity1.end,
                                target_start=entity2.start,
                                target_end=entity2.end
                            ))
        
        return relationships

    def _filter_relationships(self, relationships: List[RelationshipMatch]) -> List[RelationshipMatch]:
        """Filter relationships based on quality criteria"""
        filtered = []
        
        for rel in relationships:
            # Filter by confidence
            if rel.confidence < self.relationship_confidence_threshold:
                continue
                
            # Filter out self-relationships
            if rel.source_entity.lower() == rel.target_entity.lower():
                continue
                
            # Filter out very short entities
            if len(rel.source_entity.strip()) < 2 or len(rel.target_entity.strip()) < 2:
                continue
                
            filtered.append(rel)
        
        return filtered

    def _deduplicate_relationship_matches(self, relationships: List[RelationshipMatch]) -> List[RelationshipMatch]:
        """Remove duplicate relationship matches"""
        seen = set()
        unique = []
        
        for rel in relationships:
            # Create key for deduplication
            key = (
                rel.source_entity.lower().strip(),
                rel.target_entity.lower().strip(),
                rel.relationship_type
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(rel)
            else:
                # If duplicate, keep the one with higher confidence
                existing_idx = next(i for i, r in enumerate(unique) 
                                  if (r.source_entity.lower().strip(),
                                     r.target_entity.lower().strip(),
                                     r.relationship_type) == key)
                if rel.confidence > unique[existing_idx].confidence:
                    unique[existing_idx] = rel
        
        return unique

    async def _find_similar_entities(self, entity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar entities in the graph"""
        similar_entities = []
        
        try:
            entity_name = entity_data.get('name', '').lower().strip()
            entity_type = entity_data.get('type', '')
            
            if not entity_name:
                return similar_entities
            
            # Search for entities with similar names
            if hasattr(self.storage, 'search_entities_by_name'):
                candidates = await self.storage.search_entities_by_name(entity_name, entity_type)
                
                for candidate in candidates:
                    similarity = self._calculate_entity_similarity(entity_data, candidate)
                    if similarity > 0.5:  # Minimum similarity threshold
                        similar_entities.append({
                            'entity': candidate,
                            'similarity': similarity
                        })
        
        except Exception as e:
            logger.error(f"Error finding similar entities: {e}")
        
        return similar_entities

    def _calculate_entity_similarity(self, entity1: Dict[str, Any], entity2: 'GraphEntity') -> float:
        """Calculate similarity between entities"""
        name1 = entity1.get('name', '').lower().strip()
        name2 = getattr(entity2, 'name', '').lower().strip()
        type1 = entity1.get('type', '')
        type2 = getattr(entity2, 'type', '')
        
        # Name similarity (using simple string matching)
        name_similarity = self._string_similarity(name1, name2)
        
        # Type similarity
        type_similarity = 1.0 if type1 == type2 else 0.0
        
        # Combined similarity
        return (name_similarity * 0.7) + (type_similarity * 0.3)

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using simple method"""
        if not s1 or not s2:
            return 0.0
        
        if s1 == s2:
            return 1.0
        
        # Simple Jaccard similarity with character n-grams
        def get_ngrams(text, n=2):
            return set(text[i:i+n] for i in range(len(text)-n+1))
        
        ngrams1 = get_ngrams(s1)
        ngrams2 = get_ngrams(s2)
        
        if not ngrams1 and not ngrams2:
            return 1.0
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0

    async def _check_existing_relationship(self, source_id: str, target_id: str, rel_type: str) -> Optional['GraphRelationship']:
        """Check if relationship already exists"""
        try:
            if hasattr(self.storage, 'get_relationship'):
                return await self.storage.get_relationship(source_id, target_id, rel_type)
            return None
        except Exception as e:
            logger.error(f"Error checking existing relationship: {e}")
            return None

    async def _update_relationship_confidence(self, existing_rel: 'GraphRelationship', new_rel: 'GraphRelationship'):
        """Update existing relationship with new confidence and properties"""
        try:
            # Take the higher confidence
            if new_rel.confidence > existing_rel.confidence:
                existing_rel.confidence = new_rel.confidence
            
            # Merge properties
            if hasattr(existing_rel, 'properties') and hasattr(new_rel, 'properties'):
                existing_props = existing_rel.properties or {}
                new_props = new_rel.properties or {}
                existing_props.update(new_props)
                existing_rel.properties = existing_props
            
            # Update timestamp
            existing_rel.updated_at = datetime.utcnow()
            
            # Update in storage
            if hasattr(self.storage, 'update_relationship'):
                await self.storage.update_relationship(existing_rel)
            
        except Exception as e:
            logger.error(f"Error updating relationship confidence: {e}")

    async def get_entity(
        self,
        entity_id: str,
        include_relationships: bool = False
    ) -> Optional['GraphEntity']:
        """Get entity by ID with enhanced caching"""
        try:
            # Check cache first
            entity = await self.cache.get_entity(entity_id)
            
            if entity is None:
                # Fetch from storage
                entity = await self.storage.get_entity(entity_id)
                
                if entity:
                    # Cache for future requests
                    await self.cache.cache_entity(entity)
            
            if entity and include_relationships:
                relationships = await self.storage.get_entity_relationships(entity_id)
                entity.relationships = relationships
            
            return entity
            
        except Exception as e:
            logger.error(f"Error getting entity {entity_id}: {e}")
            raise

    async def build_graph_from_document(
        self,
        document_text: str,
        document_id: Optional[str] = None,
        enable_entity_linking: bool = True,
        enable_relationship_inference: bool = True
    ) -> Dict[str, Any]:
        """Build knowledge graph from document text with enhanced processing"""
        try:
            document_id = document_id or f"doc_{uuid.uuid4().hex}"
            
            # Extract entities with enhanced processing
            entities = await self.extract_entities(document_text)
            
            # Extract relationships with multiple methods
            relationships = await self.extract_relationships(
                document_text, 
                entities,
                use_patterns=True,
                use_dependency_parsing=True
            )
            
            # Convert relationship matches to graph relationships
            graph_entities = []
            graph_relationships = []
            entity_id_map = {}
            
            # Process entities
            for entity in entities:
                if enable_entity_linking:
                    # Try to link to existing entities
                    graph_entity = await self.create_entity({
                        'name': self._entity_name(entity),
                        'type': getattr(entity, 'type', 'UNKNOWN'),
                        'properties': {
                            'confidence': getattr(entity, 'confidence', 1.0),
                            'source': document_id,
                            'original_text': getattr(entity, 'text', ''),
                            **getattr(entity, 'properties', {})
                        },
                        'confidence': getattr(entity, 'confidence', 1.0),
                        'source': document_id
                    })
                else:
                    # Create new entity without linking
                    entity_id = f"entity_{uuid.uuid4().hex}"
                    graph_entity = await self.create_entity({
                        'id': entity_id,
                        'name': self._entity_name(entity),
                        'type': getattr(entity, 'type', 'UNKNOWN'),
                        'properties': {
                            'confidence': getattr(entity, 'confidence', 1.0),
                            'source': document_id,
                            'original_text': getattr(entity, 'text', ''),
                            **getattr(entity, 'properties', {})
                        },
                        'confidence': getattr(entity, 'confidence', 1.0),
                        'source': document_id
                    })
                
                graph_entities.append(graph_entity)
                entity_id_map[self._entity_name(entity)] = graph_entity.id
            
            # Process relationships
            for rel_match in relationships:
                source_name = rel_match.source_entity
                target_name = rel_match.target_entity
                
                if source_name in entity_id_map and target_name in entity_id_map:
                    source_id = entity_id_map[source_name]
                    target_id = entity_id_map[target_name]
                    
                    graph_relationship = await self.create_relationship({
                        'source_id': source_id,
                        'target_id': target_id,
                        'type': rel_match.relationship_type,
                        'properties': {
                            'context': rel_match.context,
                            'source': document_id,
                            'extraction_method': 'pattern_based'
                        },
                        'confidence': rel_match.confidence,
                        'source': document_id
                    })
                    
                    graph_relationships.append(graph_relationship)
            
            # Enhanced relationship inference
            if enable_relationship_inference:
                inferred_relationships = await self._infer_additional_relationships(
                    graph_entities, graph_relationships, document_text
                )
                graph_relationships.extend(inferred_relationships)
            
            # Use batch builder for efficiency
            batch_builder = self.builders['batch']
            result = await batch_builder.build_graph(
                entities=graph_entities,
                relationships=graph_relationships,
                document_id=document_id
            )
            
            logger.info(f"Built graph from document {document_id}: "
                       f"{len(graph_entities)} entities, {len(graph_relationships)} relationships")
            
            return {
                'document_id': document_id,
                'entities_created': len(graph_entities),
                'relationships_created': len(graph_relationships),
                'inferred_relationships': len(graph_relationships) - len(relationships) if enable_relationship_inference else 0,
                'build_stats': result,
                'entity_types': Counter(getattr(e, 'type', 'UNKNOWN') for e in graph_entities),
                'relationship_types': Counter(getattr(r, 'type', 'UNKNOWN') for r in graph_relationships)
            }
            
        except Exception as e:
            logger.error(f"Error building graph from document: {e}")
            raise

    async def _infer_additional_relationships(
        self, 
        entities: List['GraphEntity'], 
        relationships: List['GraphRelationship'],
        context_text: str
    ) -> List['GraphRelationship']:
        """Infer additional relationships based on context and domain knowledge"""
        inferred_relationships = []
        
        try:
            # Domain-specific inference rules
            domain_rules = {
                'medical': self._medical_inference_rules,
                'business': self._business_inference_rules,
                'academic': self._academic_inference_rules
            }
            
            # Detect domain
            domain = self._detect_domain(context_text)
            
            if domain in domain_rules:
                domain_inferences = domain_rules[domain](entities, relationships, context_text)
                inferred_relationships.extend(domain_inferences)
            
            # General co-occurrence inference
            cooccurrence_inferences = await self._infer_cooccurrence_relationships(entities, context_text)
            inferred_relationships.extend(cooccurrence_inferences)
            
            # Hierarchical inference
            hierarchical_inferences = await self._infer_hierarchical_relationships(entities, context_text)
            inferred_relationships.extend(hierarchical_inferences)
            
        except Exception as e:
            logger.error(f"Error in relationship inference: {e}")
        
        return inferred_relationships

    def _detect_domain(self, text: str) -> str:
        """Detect the domain of the text"""
        domain_keywords = {
            'medical': ['patient', 'disease', 'treatment', 'diagnosis', 'symptoms', 'medicine', 'doctor', 'hospital'],
            'business': ['company', 'market', 'revenue', 'profit', 'investment', 'strategy', 'customer', 'product'],
            'academic': ['research', 'study', 'analysis', 'theory', 'methodology', 'findings', 'conclusion', 'hypothesis']
        }
        
        text_lower = text.lower()
        domain_scores = {}
        
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            domain_scores[domain] = score
        
        return max(domain_scores, key=domain_scores.get) if domain_scores else 'general'

    def _medical_inference_rules(self, entities: List['GraphEntity'], relationships: List['GraphRelationship'], text: str) -> List['GraphRelationship']:
        """Medical domain inference rules"""
        inferred = []
        
        # Find medical entities
        diseases = [e for e in entities if getattr(e, 'type', '') in ['DISEASE', 'CONDITION']]
        symptoms = [e for e in entities if getattr(e, 'type', '') == 'SYMPTOM']
        treatments = [e for e in entities if getattr(e, 'type', '') in ['TREATMENT', 'MEDICATION']]
        
        # Infer disease-symptom relationships
        for disease in diseases:
            for symptom in symptoms:
                if self._entities_cooccur_in_sentence(disease, symptom, text):
                    inferred.append(self._create_inferred_relationship(
                        disease.id, symptom.id, 'HAS_SYMPTOM', 0.7
                    ))
        
        # Infer disease-treatment relationships
        for disease in diseases:
            for treatment in treatments:
                if self._entities_cooccur_in_sentence(disease, treatment, text):
                    inferred.append(self._create_inferred_relationship(
                        treatment.id, disease.id, 'TREATS', 0.75
                    ))
        
        return inferred

    def _business_inference_rules(self, entities: List['GraphEntity'], relationships: List['GraphRelationship'], text: str) -> List['GraphRelationship']:
        """Business domain inference rules"""
        inferred = []
        
        companies = [e for e in entities if getattr(e, 'type', '') == 'ORGANIZATION']
        products = [e for e in entities if getattr(e, 'type', '') == 'PRODUCT']
        people = [e for e in entities if getattr(e, 'type', '') == 'PERSON']
        
        # Infer company-product relationships
        for company in companies:
            for product in products:
                if self._entities_cooccur_in_sentence(company, product, text):
                    inferred.append(self._create_inferred_relationship(
                        company.id, product.id, 'PRODUCES', 0.7
                    ))
        
        # Infer person-company relationships
        for person in people:
            for company in companies:
                if self._entities_cooccur_in_sentence(person, company, text):
                    inferred.append(self._create_inferred_relationship(
                        person.id, company.id, 'WORKS_FOR', 0.6
                    ))
        
        return inferred

    def _academic_inference_rules(self, entities: List['GraphEntity'], relationships: List['GraphRelationship'], text: str) -> List['GraphRelationship']:
        """Academic domain inference rules"""
        inferred = []
        
        concepts = [e for e in entities if getattr(e, 'type', '') in ['CONCEPT', 'THEORY']]
        methods = [e for e in entities if getattr(e, 'type', '') == 'METHOD']
        authors = [e for e in entities if getattr(e, 'type', '') == 'PERSON']
        
        # Infer concept relationships
        for i, concept1 in enumerate(concepts):
            for concept2 in concepts[i+1:]:
                if self._entities_cooccur_in_sentence(concept1, concept2, text):
                    inferred.append(self._create_inferred_relationship(
                        concept1.id, concept2.id, 'RELATED_TO', 0.6
                    ))
        
        return inferred

    async def _infer_cooccurrence_relationships(self, entities: List['GraphEntity'], text: str) -> List['GraphRelationship']:
        """Infer relationships based on co-occurrence patterns"""
        inferred = []
        
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence_entities = []
            for entity in entities:
                if getattr(entity, 'name', '') in sentence:
                    sentence_entities.append(entity)
            
            # Create co-occurrence relationships
            for i, entity1 in enumerate(sentence_entities):
                for entity2 in sentence_entities[i+1:]:
                    # Calculate confidence based on sentence length and entity distance
                    confidence = min(0.8, 1.0 - (len(sentence) / 200))
                    
                    if confidence >= 0.5:
                        inferred.append(self._create_inferred_relationship(
                            entity1.id, entity2.id, 'CO_OCCURS_WITH', confidence
                        ))
        
        return inferred

    async def _infer_hierarchical_relationships(self, entities: List['GraphEntity'], text: str) -> List['GraphRelationship']:
        """Infer hierarchical relationships based on linguistic patterns"""
        inferred = []
        
        hierarchy_patterns = [
            r'(\w+)\s+(?:is\s+a|are)\s+(?:type\s+of\s+)?(\w+)',
            r'(\w+)\s+(?:includes?|contains?|comprises?)\s+(\w+)',
            r'(\w+)\s+(?:such\s+as|like|including)\s+(\w+)'
        ]
        
        entity_names = {getattr(e, 'name', ''): e for e in entities}
        
        for pattern in hierarchy_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                parent_name = match.group(2)
                child_name = match.group(1)
                
                if parent_name in entity_names and child_name in entity_names:
                    parent_entity = entity_names[parent_name]
                    child_entity = entity_names[child_name]
                    
                    inferred.append(self._create_inferred_relationship(
                        child_entity.id, parent_entity.id, 'IS_A', 0.8
                    ))
        
        return inferred

    def _entities_cooccur_in_sentence(self, entity1: 'GraphEntity', entity2: 'GraphEntity', text: str) -> bool:
        """Check if two entities co-occur in the same sentence"""
        sentences = re.split(r'[.!?]+', text)
        entity1_name = getattr(entity1, 'name', '')
        entity2_name = getattr(entity2, 'name', '')
        
        for sentence in sentences:
            if entity1_name in sentence and entity2_name in sentence:
                return True
        
        return False

    def _create_inferred_relationship(self, source_id: str, target_id: str, rel_type: str, confidence: float) -> 'GraphRelationship':
        """Create an inferred relationship"""
        from ...shared.schemas.graph_schemas import GraphRelationship
        
        return GraphRelationship(
            id=f"inferred_{uuid.uuid4().hex}",
            source_id=source_id,
            target_id=target_id,
            type=rel_type,
            properties={
                'inferred': True,
                'inference_method': 'domain_rules'
            },
            confidence=confidence,
            weight=confidence,
            source='inference_engine',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    async def add_entities_to_graph(self, entities: List['GraphEntity']) -> None:
        """Add multiple entities to the graph with batch processing"""
        try:
            # Process in batches to avoid overwhelming the system
            batch_size = 50
            for i in range(0, len(entities), batch_size):
                batch = entities[i:i + batch_size]
                
                tasks = [self.storage.create_entity(entity) for entity in batch]
                await asyncio.gather(*tasks)
                
                # Cache entities
                cache_tasks = [self.cache.cache_entity(entity) for entity in batch]
                await asyncio.gather(*cache_tasks)
                
                logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} entities")
            
            logger.info(f"Added {len(entities)} entities to graph")
            
        except Exception as e:
            logger.error(f"Error adding entities to graph: {e}")
            raise

    async def add_relationships_to_graph(self, relationships: List['GraphRelationship']) -> None:
        """Add multiple relationships to the graph with batch processing"""
        try:
            # Process in batches
            batch_size = 100
            for i in range(0, len(relationships), batch_size):
                batch = relationships[i:i + batch_size]
                
                tasks = [self.storage.create_relationship(rel) for rel in batch]
                await asyncio.gather(*tasks)
                
                # Cache relationships
                cache_tasks = [self.cache.cache_relationship(rel) for rel in batch]
                await asyncio.gather(*cache_tasks)
                
                logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} relationships")
            
            logger.info(f"Added {len(relationships)} relationships to graph")
            
        except Exception as e:
            logger.error(f"Error adding relationships to graph: {e}")
            raise

    async def get_graph_statistics(self) -> GraphStats:
        """Get comprehensive graph statistics"""
        try:
            # Get basic counts
            entity_count = await self.storage.count_entities()
            relationship_count = await self.storage.count_relationships()
            
            # Get type distributions
            entity_types = await self.storage.get_entity_type_distribution()
            relationship_types = await self.storage.get_relationship_type_distribution()
            
            # Calculate degree statistics
            degree_stats = await self.storage.get_degree_statistics()
            
            # Count connected components
            components = await self.algorithms['community'].count_connected_components()
            
            stats = GraphStats(
                total_entities=entity_count,
                total_relationships=relationship_count,
                entity_types=entity_types,
                relationship_types=relationship_types,
                avg_degree=degree_stats.get('avg_degree', 0),
                max_degree=degree_stats.get('max_degree', 0),
                connected_components=components
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting graph statistics: {e}")
            raise

    async def perform_analytics(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Perform graph analytics based on request"""
        try:
            analytics_type = request.get('type', 'centrality')
            params = request.get('parameters', {})
            
            results = {}
            
            if analytics_type == 'centrality':
                centrality_calc = self.algorithms['centrality']
                results['centrality'] = await centrality_calc.calculate_centrality(
                    measure=params.get('measure', 'betweenness')
                )
            
            elif analytics_type == 'community':
                community_detector = self.algorithms['community']
                results['communities'] = await community_detector.detect_communities(
                    algorithm=params.get('algorithm', 'louvain')
                )
            
            elif analytics_type == 'paths':
                path_finder = self.algorithms['path_finder']
                results['paths'] = await path_finder.find_shortest_paths(
                    source=params.get('source'),
                    target=params.get('target'),
                    max_length=params.get('max_length', 5)
                )
            
            elif analytics_type == 'relationship_analysis':
                results['relationship_analysis'] = await self._analyze_relationship_patterns()
            
            elif analytics_type == 'entity_importance':
                results['entity_importance'] = await self._calculate_entity_importance()
            
            else:
                raise ValueError(f"Unknown analytics type: {analytics_type}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error performing analytics: {e}")
            raise

    async def _analyze_relationship_patterns(self) -> Dict[str, Any]:
        """Analyze relationship patterns in the graph"""
        try:
            # Get all relationships
            if hasattr(self.storage, 'get_all_relationships'):
                relationships = await self.storage.get_all_relationships()
            else:
                relationships = []
            
            # Analyze patterns
            type_counts = Counter()
            confidence_distribution = []
            
            for rel in relationships:
                rel_type = getattr(rel, 'type', 'UNKNOWN')
                confidence = getattr(rel, 'confidence', 0.0)
                
                type_counts[rel_type] += 1
                confidence_distribution.append(confidence)
            
            return {
                'total_relationships': len(relationships),
                'type_distribution': dict(type_counts),
                'avg_confidence': sum(confidence_distribution) / len(confidence_distribution) if confidence_distribution else 0,
                'most_common_types': type_counts.most_common(10)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing relationship patterns: {e}")
            return {}

    async def _calculate_entity_importance(self) -> Dict[str, Any]:
        """Calculate entity importance based on connectivity and other factors"""
        try:
            # Get entity degree information
            if hasattr(self.storage, 'get_entity_degrees'):
                entity_degrees = await self.storage.get_entity_degrees()
            else:
                entity_degrees = {}
            
            # Calculate importance scores
            importance_scores = {}
            for entity_id, degree in entity_degrees.items():
                # Simple importance based on degree
                importance_scores[entity_id] = degree
            
            # Sort by importance
            sorted_entities = sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)
            
            return {
                'entity_importance': dict(sorted_entities[:50]),  # Top 50
                'avg_degree': sum(entity_degrees.values()) / len(entity_degrees) if entity_degrees else 0,
                'max_degree': max(entity_degrees.values()) if entity_degrees else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating entity importance: {e}")
            return {}

    async def _merge_duplicate_entities(self, entities: List['GraphEntity']) -> List['GraphEntity']:
        """Merge duplicate entities based on enhanced similarity"""
        try:
            # Group entities by type for more efficient processing
            entities_by_type = defaultdict(list)
            for entity in entities:
                entity_type = getattr(entity, 'type', 'UNKNOWN')
                entities_by_type[entity_type].append(entity)
            
            merged_entities = []
            
            for entity_type, type_entities in entities_by_type.items():
                # Merge within each type
                type_merged = self._merge_entities_of_same_type(type_entities)
                merged_entities.extend(type_merged)
            
            return merged_entities
            
        except Exception as e:
            logger.error(f"Error merging duplicate entities: {e}")
            return entities

    def _merge_entities_of_same_type(self, entities: List['GraphEntity']) -> List['GraphEntity']:
        """Merge entities of the same type"""
        if len(entities) <= 1:
            return entities
        
        merged = []
        used_indices = set()
        
        for i, entity1 in enumerate(entities):
            if i in used_indices:
                continue
            
            # Find similar entities
            similar_indices = [i]
            entity1_name = getattr(entity1, 'name', '').lower().strip()
            
            for j, entity2 in enumerate(entities[i+1:], i+1):
                if j in used_indices:
                    continue
                
                entity2_name = getattr(entity2, 'name', '').lower().strip()
                similarity = self._string_similarity(entity1_name, entity2_name)
                
                if similarity > self.entity_similarity_threshold:
                    similar_indices.append(j)
            
            # Merge similar entities
            if len(similar_indices) > 1:
                merged_entity = self._merge_entity_group([entities[idx] for idx in similar_indices])
                merged.append(merged_entity)
                used_indices.update(similar_indices)
            else:
                merged.append(entity1)
                used_indices.add(i)
        
        return merged

    def _merge_entity_group(self, entity_group: List['GraphEntity']) -> 'GraphEntity':
        """Merge a group of similar entities"""
        # Take the entity with highest confidence as base
        base_entity = max(entity_group, key=lambda e: getattr(e, 'confidence', 0.0))
        
        # Merge properties from all entities
        merged_properties = {}
        all_names = set()
        total_confidence = 0
        
        for entity in entity_group:
            # Collect all names
            entity_name = getattr(entity, 'name', '')
            if entity_name:
                all_names.add(entity_name)
            
            # Merge properties
            entity_props = getattr(entity, 'properties', {}) or {}
            merged_properties.update(entity_props)
            
            # Sum confidences
            total_confidence += getattr(entity, 'confidence', 0.0)
        
        # Update base entity
        base_entity.properties = merged_properties
        base_entity.properties['alternative_names'] = list(all_names)
        base_entity.confidence = min(1.0, total_confidence / len(entity_group))
        base_entity.updated_at = datetime.utcnow()
        
        return base_entity

    async def _deduplicate_relationships(
        self, 
        relationships: List['GraphRelationship']
    ) -> List['GraphRelationship']:
        """Remove duplicate relationships with enhanced logic"""
        try:
            relationship_map = {}
            
            for rel in relationships:
                # Create key for deduplication
                key = (rel.source_id, rel.target_id, rel.type)
                
                if key in relationship_map:
                    # Keep the one with higher confidence
                    existing = relationship_map[key]
                    if rel.confidence > existing.confidence:
                        relationship_map[key] = rel
                    else:
                        # Merge properties
                        existing_props = getattr(existing, 'properties', {}) or {}
                        rel_props = getattr(rel, 'properties', {}) or {}
                        existing_props.update(rel_props)
                        existing.properties = existing_props
                else:
                    relationship_map[key] = rel
            
            return list(relationship_map.values())
            
        except Exception as e:
            logger.error(f"Error deduplicating relationships: {e}")
            return relationships

    async def optimize_graph_connectivity(self) -> Dict[str, Any]:
        """Optimize graph connectivity by adding missing relationships"""
        try:
            optimization_results = {
                'relationships_added': 0,
                'isolated_nodes_connected': 0,
                'optimization_time': 0
            }
            
            start_time = datetime.utcnow()
            
            # Find isolated nodes
            if hasattr(self.storage, 'get_isolated_entities'):
                isolated_entities = await self.storage.get_isolated_entities()
                
                # Try to connect isolated nodes based on similarity
                for entity in isolated_entities:
                    similar_entities = await self._find_similar_entities({
                        'name': getattr(entity, 'name', ''),
                        'type': getattr(entity, 'type', '')
                    })
                    
                    for similar in similar_entities[:3]:  # Connect to top 3 similar entities
                        if similar['similarity'] > 0.7:
                            await self.create_relationship({
                                'source_id': entity.id,
                                'target_id': similar['entity'].id,
                                'type': 'SIMILAR_TO',
                                'confidence': similar['similarity'],
                                'source': 'optimization'
                            })
                            optimization_results['relationships_added'] += 1
                    
                    optimization_results['isolated_nodes_connected'] += 1
            
            end_time = datetime.utcnow()
            optimization_results['optimization_time'] = (end_time - start_time).total_seconds()
            
            logger.info(f"Graph optimization completed: {optimization_results}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing graph connectivity: {e}")
            return {'error': str(e)}