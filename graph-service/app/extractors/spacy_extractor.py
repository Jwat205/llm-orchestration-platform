"""
SpaCy-based Entity and Relationship Extractor.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import re

try:
    import spacy
    from spacy import displacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

class SpacyExtractor:
    """SpaCy-based extractor for entities and relationships."""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.nlp = None
        
        # Entity type mappings
        self.entity_type_mapping = {
            "PERSON": "Person",
            "ORG": "Organization", 
            "GPE": "Location",
            "LOC": "Location",
            "EVENT": "Event",
            "FAC": "Facility",
            "PRODUCT": "Product",
            "WORK_OF_ART": "WorkOfArt",
            "LANGUAGE": "Language",
            "DATE": "Date",
            "TIME": "Time",
            "PERCENT": "Percentage",
            "MONEY": "Money",
            "QUANTITY": "Quantity",
            "ORDINAL": "Ordinal",
            "CARDINAL": "Cardinal"
        }
        
        # Relationship patterns
        self.relationship_patterns = [
            (r"(.+?) (?:works for|employed by|at) (.+)", "WORKS_FOR"),
            (r"(.+?) (?:owns|founded|created) (.+)", "OWNS"),
            (r"(.+?) (?:is located in|is in|based in) (.+)", "LOCATED_IN"),
            (r"(.+?) (?:married to|spouse of) (.+)", "MARRIED_TO"),
            (r"(.+?) (?:born in|from) (.+)", "BORN_IN"),
            (r"(.+?) (?:studied at|graduated from) (.+)", "STUDIED_AT"),
            (r"(.+?) (?:part of|member of|belongs to) (.+)", "PART_OF"),
            (r"(.+?) (?:similar to|like) (.+)", "SIMILAR_TO"),
            (r"(.+?) (?:before|prior to) (.+)", "BEFORE"),
            (r"(.+?) (?:after|following) (.+)", "AFTER")
        ]
        
        # Statistics
        self.stats = {
            "texts_processed": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "processing_time": 0.0
        }
    
    async def initialize(self):
        """Initialize SpaCy extractor"""
        try:
            if SPACY_AVAILABLE:
                try:
                    self.nlp = spacy.load(self.model_name)
                    self.logger.info(f"Loaded SpaCy model: {self.model_name}")
                except OSError:
                    self.logger.warning(f"SpaCy model {self.model_name} not found, using blank model")
                    self.nlp = spacy.blank("en")
            else:
                self.logger.warning("SpaCy not available, using mock extraction")
            
            self.logger.info("SpaCy extractor initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing SpaCy extractor: {e}")
            raise
    
    async def extract(self, text: str, entity_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract entities from text"""
        start_time = datetime.now()
        
        try:
            if not SPACY_AVAILABLE or not self.nlp:
                return await self._mock_extract_entities(text, entity_types)
            
            # Process text with SpaCy
            doc = self.nlp(text)
            
            # Extract entities
            entities = []
            for ent in doc.ents:
                entity_type = self.entity_type_mapping.get(ent.label_, ent.label_)
                
                # Filter by entity types if specified
                if entity_types and entity_type not in entity_types:
                    continue
                
                entity = {
                    "text": ent.text,
                    "type": entity_type,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "label": ent.label_,
                    "confidence": getattr(ent, 'confidence', 0.8)
                }
                entities.append(entity)
            
            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats["texts_processed"] += 1
            self.stats["entities_extracted"] += len(entities)
            self.stats["processing_time"] += processing_time
            
            return {
                "entities": entities,
                "processing_time": processing_time,
                "method": "spacy"
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting entities: {e}")
            return {"entities": [], "error": str(e)}
    
    async def extract_relationships(self, text: str, 
                                  entities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Extract relationships from text"""
        start_time = datetime.now()
        
        try:
            if not SPACY_AVAILABLE or not self.nlp:
                return await self._mock_extract_relationships(text, entities)
            
            relationships = []
            
            # If entities not provided, extract them first
            if entities is None:
                entity_result = await self.extract(text)
                entities = entity_result.get("entities", [])
            
            # Pattern-based relationship extraction
            relationships.extend(await self._extract_pattern_relationships(text, entities))
            
            # Dependency-based relationship extraction
            relationships.extend(await self._extract_dependency_relationships(text, entities))
            
            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats["relationships_extracted"] += len(relationships)
            
            return {
                "relationships": relationships,
                "processing_time": processing_time,
                "method": "spacy"
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting relationships: {e}")
            return {"relationships": [], "error": str(e)}
    
    async def _extract_pattern_relationships(self, text: str, 
                                           entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships using predefined patterns"""
        relationships = []
        
        try:
            # Create entity lookup
            entity_texts = {ent["text"].lower(): ent for ent in entities}
            
            # Apply relationship patterns
            for pattern, rel_type in self.relationship_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                
                for match in matches:
                    source_text = match.group(1).strip()
                    target_text = match.group(2).strip()
                    
                    # Find matching entities
                    source_entity = entity_texts.get(source_text.lower())
                    target_entity = entity_texts.get(target_text.lower())
                    
                    if source_entity and target_entity:
                        relationship = {
                            "source": source_entity,
                            "target": target_entity,
                            "type": rel_type,
                            "text": match.group(0),
                            "confidence": 0.7,
                            "method": "pattern_matching"
                        }
                        relationships.append(relationship)
            
            return relationships
            
        except Exception as e:
            self.logger.error(f"Error in pattern relationship extraction: {e}")
            return []
    
    async def _extract_dependency_relationships(self, text: str, 
                                              entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships using dependency parsing"""
        relationships = []
        
        try:
            doc = self.nlp(text)
            
            # Create entity span lookup
            entity_spans = {}
            for ent in entities:
                for token in doc:
                    if token.idx >= ent["start"] and token.idx < ent["end"]:
                        entity_spans[token.i] = ent
                        break
            
            # Extract relationships from dependency tree
            for token in doc:
                if token.i in entity_spans:
                    source_entity = entity_spans[token.i]
                    
                    # Look for relationships through dependencies
                    for child in token.children:
                        if child.i in entity_spans:
                            target_entity = entity_spans[child.i]
                            
                            # Map dependency to relationship type
                            rel_type = self._map_dependency_to_relationship(token.dep_, child.dep_)
                            
                            if rel_type:
                                relationship = {
                                    "source": source_entity,
                                    "target": target_entity,
                                    "type": rel_type,
                                    "dependency": child.dep_,
                                    "confidence": 0.6,
                                    "method": "dependency_parsing"
                                }
                                relationships.append(relationship)
            
            return relationships
            
        except Exception as e:
            self.logger.error(f"Error in dependency relationship extraction: {e}")
            return []
    
    def _map_dependency_to_relationship(self, head_dep: str, child_dep: str) -> Optional[str]:
        """Map dependency relations to relationship types"""
        dependency_mapping = {
            "nsubj": "SUBJECT_OF",
            "dobj": "OBJECT_OF",
            "pobj": "RELATED_TO",
            "compound": "PART_OF",
            "amod": "DESCRIBES",
            "nmod": "MODIFIES",
            "appos": "SAME_AS",
            "conj": "RELATED_TO"
        }
        
        return dependency_mapping.get(child_dep, None)
    
    async def extract_concepts(self, text: str) -> Dict[str, Any]:
        """Extract key concepts and topics from text"""
        try:
            if not SPACY_AVAILABLE or not self.nlp:
                return await self._mock_extract_concepts(text)
            
            doc = self.nlp(text)
            
            # Extract noun phrases as concepts
            concepts = []
            for chunk in doc.noun_chunks:
                if len(chunk.text.strip()) > 2:  # Filter short chunks
                    concept = {
                        "text": chunk.text,
                        "root": chunk.root.text,
                        "start": chunk.start_char,
                        "end": chunk.end_char,
                        "pos": chunk.root.pos_
                    }
                    concepts.append(concept)
            
            # Extract key verbs
            verbs = []
            for token in doc:
                if token.pos_ == "VERB" and not token.is_stop:
                    verb = {
                        "text": token.text,
                        "lemma": token.lemma_,
                        "pos": token.pos_
                    }
                    verbs.append(verb)
            
            return {
                "concepts": concepts,
                "verbs": verbs,
                "method": "spacy"
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting concepts: {e}")
            return {"concepts": [], "verbs": [], "error": str(e)}
    
    async def _mock_extract_entities(self, text: str, entity_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Mock entity extraction when SpaCy is not available"""
        # Simple regex-based extraction for common patterns
        entities = []
        
        # Email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        for email in emails:
            entities.append({
                "text": email,
                "type": "Email",
                "confidence": 0.9,
                "method": "regex"
            })
        
        # Phone numbers
        phones = re.findall(r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\) \d{3}-\d{4}\b', text)
        for phone in phones:
            entities.append({
                "text": phone,
                "type": "Phone",
                "confidence": 0.8,
                "method": "regex"
            })
        
        # URLs
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        for url in urls:
            entities.append({
                "text": url,
                "type": "URL",
                "confidence": 0.9,
                "method": "regex"
            })
        
        # Dates (simple pattern)
        dates = re.findall(r'\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b', text)
        for date in dates:
            entities.append({
                "text": date,
                "type": "Date",
                "confidence": 0.7,
                "method": "regex"
            })
        
        return {
            "entities": entities,
            "method": "mock"
        }
    
    async def _mock_extract_relationships(self, text: str, entities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Mock relationship extraction"""
        relationships = []
        
        if entities and len(entities) >= 2:
            # Create simple relationships between entities
            for i in range(len(entities) - 1):
                relationship = {
                    "source": entities[i],
                    "target": entities[i + 1],
                    "type": "RELATED_TO",
                    "confidence": 0.5,
                    "method": "mock"
                }
                relationships.append(relationship)
        
        return {
            "relationships": relationships,
            "method": "mock"
        }
    
    async def _mock_extract_concepts(self, text: str) -> Dict[str, Any]:
        """Mock concept extraction"""
        # Simple word frequency analysis
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        word_freq = {}
        
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top concepts
        concepts = []
        for word, freq in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]:
            concepts.append({
                "text": word,
                "frequency": freq,
                "method": "frequency"
            })
        
        return {
            "concepts": concepts,
            "method": "mock"
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get extractor statistics"""
        return self.stats.copy()
    
    async def shutdown(self):
        """Shutdown SpaCy extractor"""
        self.logger.info("SpaCy extractor shutdown")