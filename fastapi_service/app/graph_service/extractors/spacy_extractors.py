"""
SpaCy-based entity and relationship extraction for knowledge graph construction.
"""
import spacy
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from collections import defaultdict
import re

logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """Represents an extracted entity."""
    text: str
    label: str
    start: int
    end: int
    confidence: float
    attributes: Dict[str, Any]
    canonical_form: str = None

@dataclass
class Relationship:
    """Represents an extracted relationship between entities."""
    subject: Entity
    predicate: str
    object: Entity
    confidence: float
    context: str
    attributes: Dict[str, Any]

class SpacyExtractor:
    """SpaCy-based extractor for entities and relationships."""
    
    def __init__(self, model_name: str = "en_core_web_sm", custom_patterns: Dict = None):
        """
        Initialize the SpaCy extractor.
        
        Args:
            model_name: SpaCy model to use
            custom_patterns: Custom entity patterns to add
        """
        self.model_name = model_name
        self.nlp = None
        self.custom_patterns = custom_patterns or {}
        self._load_model()
        
    def _load_model(self):
        """Load the SpaCy model with custom configurations."""
        try:
            self.nlp = spacy.load(self.model_name)
            
            # Add custom entity patterns if provided
            if self.custom_patterns:
                self._add_custom_patterns()
                
            # Configure pipeline
            self._configure_pipeline()
            
        except OSError as e:
            logger.error(f"Failed to load SpaCy model {self.model_name}: {e}")
            raise
    
    def _add_custom_patterns(self):
        """Add custom entity patterns to the NER pipeline."""
        if "entity_ruler" not in self.nlp.pipe_names:
            ruler = self.nlp.add_pipe("entity_ruler")
        else:
            ruler = self.nlp.get_pipe("entity_ruler")
            
        patterns = []
        for label, pattern_list in self.custom_patterns.items():
            for pattern in pattern_list:
                patterns.append({"label": label, "pattern": pattern})
                
        ruler.add_patterns(patterns)
    
    def _configure_pipeline(self):
        """Configure the SpaCy pipeline for optimal performance."""
        # Disable unnecessary components for performance
        disable = []
        if "lemmatizer" in self.nlp.pipe_names and not self._needs_lemmatizer():
            disable.append("lemmatizer")
            
        if disable:
            self.nlp.disable_pipes(*disable)
    
    def _needs_lemmatizer(self) -> bool:
        """Check if lemmatizer is needed for current configuration."""
        return True  # Keep lemmatizer for canonical forms
    
    def extract_entities(self, text: str, min_confidence: float = 0.5) -> List[Entity]:
        """
        Extract entities from text using SpaCy NER.
        
        Args:
            text: Input text
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of extracted entities
        """
        if not text or not text.strip():
            return []
            
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            # Calculate confidence based on entity properties
            confidence = self._calculate_entity_confidence(ent, doc)
            
            if confidence >= min_confidence:
                # Create canonical form
                canonical_form = self._create_canonical_form(ent)
                
                # Extract entity attributes
                attributes = self._extract_entity_attributes(ent, doc)
                
                entity = Entity(
                    text=ent.text.strip(),
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=confidence,
                    attributes=attributes,
                    canonical_form=canonical_form
                )
                entities.append(entity)
        
        # Remove overlapping entities
        entities = self._remove_overlapping_entities(entities)
        
        return entities
    
    def extract_relationships(self, text: str, entities: List[Entity] = None, 
                           min_confidence: float = 0.3) -> List[Relationship]:
        """
        Extract relationships between entities using dependency parsing.
        
        Args:
            text: Input text
            entities: Pre-extracted entities (optional)
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of extracted relationships
        """
        if not text or not text.strip():
            return []
            
        doc = self.nlp(text)
        
        # Use provided entities or extract them
        if entities is None:
            entities = self.extract_entities(text, min_confidence=0.3)
        
        # Create entity mapping for quick lookup
        entity_map = self._create_entity_mapping(entities, doc)
        
        relationships = []
        
        # Extract relationships using dependency parsing
        dep_relationships = self._extract_dependency_relationships(doc, entity_map)
        relationships.extend(dep_relationships)
        
        # Extract relationships using pattern matching
        pattern_relationships = self._extract_pattern_relationships(doc, entity_map)
        relationships.extend(pattern_relationships)
        
        # Filter by confidence
        relationships = [rel for rel in relationships if rel.confidence >= min_confidence]
        
        return relationships
    
    def _calculate_entity_confidence(self, ent, doc) -> float:
        """Calculate confidence score for an entity."""
        confidence = 0.7  # Base confidence for SpaCy entities
        
        # Boost confidence for certain entity types
        high_confidence_types = {"PERSON", "ORG", "GPE", "DATE", "MONEY"}
        if ent.label_ in high_confidence_types:
            confidence += 0.2
            
        # Boost confidence for proper nouns
        if any(token.pos_ == "PROPN" for token in ent):
            confidence += 0.1
            
        # Reduce confidence for very short entities
        if len(ent.text.strip()) < 3:
            confidence -= 0.2
            
        # Reduce confidence for all lowercase entities (except certain types)
        if ent.text.islower() and ent.label_ not in {"DATE", "TIME", "PERCENT"}:
            confidence -= 0.1
            
        return min(max(confidence, 0.0), 1.0)
    
    def _create_canonical_form(self, ent) -> str:
        """Create canonical form of an entity."""
        # Use lemmatized form for common nouns
        if ent.label_ in {"PERSON", "ORG", "GPE"}:
            return ent.text.strip()
        else:
            return " ".join([token.lemma_.lower() for token in ent]).strip()
    
    def _extract_entity_attributes(self, ent, doc) -> Dict[str, Any]:
        """Extract additional attributes for an entity."""
        attributes = {
            "pos_tags": [token.pos_ for token in ent],
            "dependency_labels": [token.dep_ for token in ent],
            "is_title": ent.text.istitle(),
            "is_upper": ent.text.isupper(),
            "token_count": len(ent),
            "char_count": len(ent.text)
        }
        
        # Add entity-specific attributes
        if ent.label_ == "PERSON":
            attributes["person_type"] = self._classify_person_type(ent)
        elif ent.label_ == "ORG":
            attributes["org_type"] = self._classify_org_type(ent)
        elif ent.label_ == "DATE":
            attributes["date_type"] = self._classify_date_type(ent)
            
        return attributes
    
    def _classify_person_type(self, ent) -> str:
        """Classify type of person entity."""
        text_lower = ent.text.lower()
        if any(title in text_lower for title in ["dr.", "prof.", "professor"]):
            return "academic"
        elif any(title in text_lower for title in ["mr.", "mrs.", "ms."]):
            return "formal"
        else:
            return "general"
    
    def _classify_org_type(self, ent) -> str:
        """Classify type of organization entity."""
        text_lower = ent.text.lower()
        if any(suffix in text_lower for suffix in ["inc", "corp", "ltd", "llc"]):
            return "company"
        elif any(suffix in text_lower for suffix in ["university", "college", "school"]):
            return "educational"
        elif any(suffix in text_lower for suffix in ["hospital", "clinic"]):
            return "medical"
        else:
            return "general"
    
    def _classify_date_type(self, ent) -> str:
        """Classify type of date entity."""
        text_lower = ent.text.lower()
        if re.search(r'\d{4}', ent.text):
            return "year_included"
        elif any(word in text_lower for word in ["today", "yesterday", "tomorrow"]):
            return "relative"
        else:
            return "general"
    
    def _remove_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping the longer/more confident ones."""
        # Sort by start position
        entities.sort(key=lambda x: x.start)
        
        filtered_entities = []
        for current in entities:
            # Check if current entity overlaps with any in filtered list
            overlaps = False
            for existing in filtered_entities:
                if self._entities_overlap(current, existing):
                    # Keep the more confident or longer entity
                    if (current.confidence > existing.confidence or 
                        (current.confidence == existing.confidence and 
                         len(current.text) > len(existing.text))):
                        filtered_entities.remove(existing)
                    else:
                        overlaps = True
                    break
            
            if not overlaps:
                filtered_entities.append(current)
        
        return filtered_entities
    
    def _entities_overlap(self, ent1: Entity, ent2: Entity) -> bool:
        """Check if two entities overlap."""
        return not (ent1.end <= ent2.start or ent2.end <= ent1.start)
    
    def _create_entity_mapping(self, entities: List[Entity], doc) -> Dict[int, Entity]:
        """Create mapping from token indices to entities."""
        entity_map = {}
        
        for entity in entities:
            # Find tokens that belong to this entity
            for token in doc:
                if token.idx >= entity.start and token.idx < entity.end:
                    entity_map[token.i] = entity
                    
        return entity_map
    
    def _extract_dependency_relationships(self, doc, entity_map: Dict[int, Entity]) -> List[Relationship]:
        """Extract relationships using dependency parsing."""
        relationships = []
        
        for token in doc:
            if token.i in entity_map:
                subject_entity = entity_map[token.i]
                
                # Look for objects through dependency relations
                for child in token.children:
                    if child.i in entity_map:
                        object_entity = entity_map[child.i]
                        
                        # Create relationship based on dependency label
                        predicate = self._dependency_to_predicate(token.dep_, child.dep_)
                        if predicate:
                            confidence = self._calculate_relationship_confidence(
                                token, child, subject_entity, object_entity
                            )
                            
                            relationship = Relationship(
                                subject=subject_entity,
                                predicate=predicate,
                                object=object_entity,
                                confidence=confidence,
                                context=doc.text,
                                attributes={
                                    "dependency_path": f"{token.dep_}-{child.dep_}",
                                    "sentence": token.sent.text
                                }
                            )
                            relationships.append(relationship)
        
        return relationships
    
    def _extract_pattern_relationships(self, doc, entity_map: Dict[int, Entity]) -> List[Relationship]:
        """Extract relationships using predefined patterns."""
        relationships = []
        
        # Define relationship patterns
        patterns = [
            (r"(.+) is (.+)", "is_a"),
            (r"(.+) works for (.+)", "employed_by"),
            (r"(.+) founded (.+)", "founded"),
            (r"(.+) owns (.+)", "owns"),
            (r"(.+) located in (.+)", "located_in"),
        ]
        
        text = doc.text
        entities_by_text = {ent.text: ent for ent in entity_map.values()}
        
        for pattern, predicate in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                subj_text = match.group(1).strip()
                obj_text = match.group(2).strip()
                
                # Find matching entities
                subject_entity = None
                object_entity = None
                
                for ent_text, entity in entities_by_text.items():
                    if ent_text in subj_text:
                        subject_entity = entity
                    if ent_text in obj_text:
                        object_entity = entity
                
                if subject_entity and object_entity:
                    relationship = Relationship(
                        subject=subject_entity,
                        predicate=predicate,
                        object=object_entity,
                        confidence=0.6,  # Pattern-based relationships have medium confidence
                        context=match.group(0),
                        attributes={
                            "extraction_method": "pattern_matching",
                            "pattern": pattern
                        }
                    )
                    relationships.append(relationship)
        
        return relationships
    
    def _dependency_to_predicate(self, subj_dep: str, obj_dep: str) -> Optional[str]:
        """Convert dependency labels to relationship predicates."""
        predicate_map = {
            ("nsubj", "dobj"): "acts_on",
            ("nsubj", "prep"): "related_to",
            ("compound", "compound"): "part_of",
            ("amod", "noun"): "describes",
            ("nmod", "nmod"): "associated_with"
        }
        
        return predicate_map.get((subj_dep, obj_dep))
    
    def _calculate_relationship_confidence(self, subj_token, obj_token, 
                                         subj_entity: Entity, obj_entity: Entity) -> float:
        """Calculate confidence score for a relationship."""
        base_confidence = 0.5
        
        # Boost confidence for strong dependency relations
        strong_deps = {"nsubj", "dobj", "nmod", "compound"}
        if subj_token.dep_ in strong_deps or obj_token.dep_ in strong_deps:
            base_confidence += 0.2
        
        # Boost confidence for high-confidence entities
        entity_conf_boost = (subj_entity.confidence + obj_entity.confidence) / 2 * 0.2
        base_confidence += entity_conf_boost
        
        # Reduce confidence for very distant tokens
        distance = abs(subj_token.i - obj_token.i)
        if distance > 10:
            base_confidence -= 0.1
        
        return min(max(base_confidence, 0.0), 1.0)
    
    def extract_concepts(self, text: str, min_confidence: float = 0.4) -> List[Entity]:
        """Extract conceptual entities (noun phrases) from text."""
        if not text or not text.strip():
            return []
        
        doc = self.nlp(text)
        concepts = []
        
        # Extract noun phrases as concepts
        for noun_phrase in doc.noun_chunks:
            # Filter out very short or very long phrases
            if 2 <= len(noun_phrase.text.split()) <= 5:
                confidence = self._calculate_concept_confidence(noun_phrase)
                
                if confidence >= min_confidence:
                    concept = Entity(
                        text=noun_phrase.text.strip(),
                        label="CONCEPT",
                        start=noun_phrase.start_char,
                        end=noun_phrase.end_char,
                        confidence=confidence,
                        attributes={
                            "phrase_type": "noun_phrase",
                            "root_lemma": noun_phrase.root.lemma_
                        },
                        canonical_form=noun_phrase.root.lemma_.lower()
                    )
                    concepts.append(concept)
        
        return concepts
    
    def _calculate_concept_confidence(self, noun_phrase) -> float:
        """Calculate confidence score for a concept."""
        confidence = 0.5
        
        # Boost confidence for phrases with proper nouns
        if any(token.pos_ == "PROPN" for token in noun_phrase):
            confidence += 0.2
        
        # Boost confidence for phrases with specific POS patterns
        pos_pattern = " ".join([token.pos_ for token in noun_phrase])
        good_patterns = {"ADJ NOUN", "NOUN NOUN", "DET ADJ NOUN"}
        if pos_pattern in good_patterns:
            confidence += 0.1
        
        # Reduce confidence for very common words
        common_words = {"thing", "stuff", "something", "anything"}
        if any(token.lemma_.lower() in common_words for token in noun_phrase):
            confidence -= 0.3
        
        return min(max(confidence, 0.0), 1.0)