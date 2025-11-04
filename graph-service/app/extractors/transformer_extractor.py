"""
Transformer-based Entity and Relationship Extractor
Uses transformer models for advanced NLP tasks including entity extraction and relationship identification.
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum
import torch
from transformers import (
    AutoTokenizer, AutoModelForTokenClassification,
    AutoModelForSequenceClassification, pipeline,
    BertTokenizer, BertForSequenceClassification
)
import spacy
from spacy import displacy
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)

class ExtractionType(Enum):
    ENTITIES = "entities"
    RELATIONSHIPS = "relationships" 
    CONCEPTS = "concepts"
    TEMPORAL = "temporal"

@dataclass
class EntityResult:
    text: str
    label: str
    start: int
    end: int
    confidence: float
    attributes: Dict[str, Any] = None

@dataclass
class RelationshipResult:
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    context: str
    attributes: Dict[str, Any] = None

class TransformerExtractor:
    """Advanced transformer-based extractor for entities and relationships"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.entity_model = None
        self.relation_model = None
        self.ner_pipeline = None
        self.relation_pipeline = None
        self.spacy_model = None
        
        # Model configurations
        self.entity_model_name = self.config.get("entity_model", "dbmdz/bert-large-cased-finetuned-conll03-english")
        self.relation_model_name = self.config.get("relation_model", "bert-base-uncased")
        self.spacy_model_name = self.config.get("spacy_model", "en_core_web_sm")
        
        # Extraction parameters
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.max_length = self.config.get("max_length", 512)
        self.batch_size = self.config.get("batch_size", 8)
        
        # Relationship extraction patterns
        self.relation_patterns = {
            "WORKS_FOR": ["works for", "employed by", "employee of"],
            "LOCATED_IN": ["located in", "based in", "situated in"],
            "FOUNDED_BY": ["founded by", "established by", "created by"],
            "PART_OF": ["part of", "division of", "subsidiary of"],
            "LEADS": ["leads", "heads", "manages", "directs"],
            "OWNS": ["owns", "possesses", "has"],
            "MEMBER_OF": ["member of", "belongs to", "part of"]
        }
        
    async def initialize(self):
        """Initialize transformer models and pipelines"""
        try:
            logger.info("Initializing transformer extractor...")
            
            # Initialize NER pipeline
            self.ner_pipeline = pipeline(
                "ner",
                model=self.entity_model_name,
                tokenizer=self.entity_model_name,
                aggregation_strategy="simple",
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Initialize relation classification pipeline
            self.relation_pipeline = pipeline(
                "text-classification",
                model=self.relation_model_name,
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Initialize spaCy model for dependency parsing
            try:
                self.spacy_model = spacy.load(self.spacy_model_name)
            except OSError:
                logger.warning(f"SpaCy model {self.spacy_model_name} not found. Installing...")
                spacy.cli.download(self.spacy_model_name)
                self.spacy_model = spacy.load(self.spacy_model_name)
            
            logger.info("Transformer extractor initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing transformer extractor: {e}")
            raise
    
    async def extract(self, text: str, extraction_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract entities and relationships from text"""
        if not extraction_types:
            extraction_types = [ExtractionType.ENTITIES.value, ExtractionType.RELATIONSHIPS.value]
        
        results = {}
        
        if ExtractionType.ENTITIES.value in extraction_types:
            results["entities"] = await self.extract_entities(text)
        
        if ExtractionType.RELATIONSHIPS.value in extraction_types:
            results["relationships"] = await self.extract_relationships(text, results.get("entities", []))
        
        if ExtractionType.CONCEPTS.value in extraction_types:
            results["concepts"] = await self.extract_concepts(text)
        
        if ExtractionType.TEMPORAL.value in extraction_types:
            results["temporal"] = await self.extract_temporal_info(text)
        
        return results
    
    async def extract_entities(self, text: str) -> List[EntityResult]:
        """Extract named entities using transformer NER"""
        try:
            # Use transformer NER pipeline
            ner_results = self.ner_pipeline(text)
            
            entities = []
            for result in ner_results:
                if result["score"] >= self.confidence_threshold:
                    entity = EntityResult(
                        text=result["word"],
                        label=result["entity_group"],
                        start=result["start"],
                        end=result["end"],
                        confidence=result["score"]
                    )
                    entities.append(entity)
            
            # Enhance with spaCy analysis
            if self.spacy_model:
                doc = self.spacy_model(text)
                for ent in doc.ents:
                    # Check if not already captured by transformer
                    overlap = any(
                        abs(e.start - ent.start_char) < 5 and abs(e.end - ent.end_char) < 5 
                        for e in entities
                    )
                    if not overlap:
                        entity = EntityResult(
                            text=ent.text,
                            label=ent.label_,
                            start=ent.start_char,
                            end=ent.end_char,
                            confidence=0.8,  # Default confidence for spaCy
                            attributes={"source": "spacy"}
                        )
                        entities.append(entity)
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    async def extract_relationships(self, text: str, entities: List[EntityResult] = None) -> List[RelationshipResult]:
        """Extract relationships between entities"""
        try:
            if not entities:
                entities = await self.extract_entities(text)
            
            relationships = []
            
            # Pattern-based relationship extraction
            relationships.extend(await self._extract_pattern_relationships(text, entities))
            
            # Dependency-based relationship extraction using spaCy
            if self.spacy_model:
                relationships.extend(await self._extract_dependency_relationships(text, entities))
            
            # Transformer-based relationship classification
            relationships.extend(await self._extract_transformer_relationships(text, entities))
            
            return relationships
            
        except Exception as e:
            logger.error(f"Error extracting relationships: {e}")
            return []
    
    async def _extract_pattern_relationships(self, text: str, entities: List[EntityResult]) -> List[RelationshipResult]:
        """Extract relationships using predefined patterns"""
        relationships = []
        text_lower = text.lower()
        
        for relation_type, patterns in self.relation_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    # Find entities around the pattern
                    pattern_pos = text_lower.find(pattern)
                    
                    # Look for entities before and after the pattern
                    source_entities = [e for e in entities if e.end <= pattern_pos]
                    target_entities = [e for e in entities if e.start >= pattern_pos + len(pattern)]
                    
                    if source_entities and target_entities:
                        source = max(source_entities, key=lambda x: x.end)
                        target = min(target_entities, key=lambda x: x.start)
                        
                        relationship = RelationshipResult(
                            source_entity=source.text,
                            target_entity=target.text,
                            relation_type=relation_type,
                            confidence=0.7,
                            context=text[max(0, source.start-50):min(len(text), target.end+50)],
                            attributes={"extraction_method": "pattern"}
                        )
                        relationships.append(relationship)
        
        return relationships
    
    async def _extract_dependency_relationships(self, text: str, entities: List[EntityResult]) -> List[RelationshipResult]:
        """Extract relationships using dependency parsing"""
        relationships = []
        
        try:
            doc = self.spacy_model(text)
            entity_map = {ent.text.lower(): ent for ent in entities}
            
            for token in doc:
                if token.dep_ in ["nsubj", "dobj", "pobj"] and token.head.pos_ == "VERB":
                    # Look for subject-verb-object relationships
                    subject = None
                    obj = None
                    
                    # Find subject
                    for child in token.head.children:
                        if child.dep_ == "nsubj" and child.text.lower() in entity_map:
                            subject = entity_map[child.text.lower()]
                        elif child.dep_ in ["dobj", "pobj"] and child.text.lower() in entity_map:
                            obj = entity_map[child.text.lower()]
                    
                    if subject and obj and subject != obj:
                        relationship = RelationshipResult(
                            source_entity=subject.text,
                            target_entity=obj.text,
                            relation_type=token.head.lemma_.upper(),
                            confidence=0.6,
                            context=token.sent.text,
                            attributes={"extraction_method": "dependency", "verb": token.head.text}
                        )
                        relationships.append(relationship)
        
        except Exception as e:
            logger.error(f"Error in dependency relationship extraction: {e}")
        
        return relationships
    
    async def _extract_transformer_relationships(self, text: str, entities: List[EntityResult]) -> List[RelationshipResult]:
        """Extract relationships using transformer classification"""
        relationships = []
        
        try:
            # Create entity pairs for classification
            entity_pairs = []
            for i, e1 in enumerate(entities):
                for j, e2 in enumerate(entities[i+1:], i+1):
                    if e1.label != e2.label:  # Different entity types more likely to be related
                        entity_pairs.append((e1, e2))
            
            # Classify relationships for each pair
            for e1, e2 in entity_pairs[:20]:  # Limit to avoid too many API calls
                # Create context sentence with entities highlighted
                context = text[max(0, min(e1.start, e2.start)-100):max(e1.end, e2.end)+100]
                query = f"[E1]{e1.text}[/E1] and [E2]{e2.text}[/E2] in context: {context}"
                
                # Use relation pipeline to classify
                if len(query) <= self.max_length:
                    try:
                        result = self.relation_pipeline(query[:self.max_length])
                        if result[0]["score"] > 0.5:
                            relationship = RelationshipResult(
                                source_entity=e1.text,
                                target_entity=e2.text,
                                relation_type=result[0]["label"],
                                confidence=result[0]["score"],
                                context=context,
                                attributes={"extraction_method": "transformer"}
                            )
                            relationships.append(relationship)
                    except Exception:
                        continue  # Skip this pair if classification fails
        
        except Exception as e:
            logger.error(f"Error in transformer relationship extraction: {e}")
        
        return relationships
    
    async def extract_concepts(self, text: str) -> List[Dict[str, Any]]:
        """Extract key concepts and topics from text"""
        concepts = []
        
        try:
            if self.spacy_model:
                doc = self.spacy_model(text)
                
                # Extract noun phrases as concepts
                for chunk in doc.noun_chunks:
                    if len(chunk.text.strip()) > 2:
                        concept = {
                            "text": chunk.text,
                            "type": "concept",
                            "start": chunk.start_char,
                            "end": chunk.end_char,
                            "pos_tags": [token.pos_ for token in chunk],
                            "confidence": 0.6
                        }
                        concepts.append(concept)
                
                # Extract keywords based on POS tags
                keywords = [token.text for token in doc if token.pos_ in ["NOUN", "ADJ"] and not token.is_stop]
                for keyword in set(keywords):
                    concept = {
                        "text": keyword,
                        "type": "keyword",
                        "confidence": 0.5
                    }
                    concepts.append(concept)
        
        except Exception as e:
            logger.error(f"Error extracting concepts: {e}")
        
        return concepts
    
    async def extract_temporal_info(self, text: str) -> List[Dict[str, Any]]:
        """Extract temporal information from text"""
        temporal_info = []
        
        try:
            if self.spacy_model:
                doc = self.spacy_model(text)
                
                for ent in doc.ents:
                    if ent.label_ in ["DATE", "TIME", "EVENT"]:
                        temporal = {
                            "text": ent.text,
                            "label": ent.label_,
                            "start": ent.start_char,
                            "end": ent.end_char,
                            "confidence": 0.8
                        }
                        temporal_info.append(temporal)
        
        except Exception as e:
            logger.error(f"Error extracting temporal info: {e}")
        
        return temporal_info
    
    async def extract_relationships_advanced(self, text: str, entities: Optional[List[Dict[str, Any]]] = None) -> List[RelationshipResult]:
        """Advanced relationship extraction with multiple methods"""
        if entities:
            # Convert dict entities to EntityResult objects
            entity_objects = []
            for ent in entities:
                entity_obj = EntityResult(
                    text=ent.get("text", ""),
                    label=ent.get("label", ""),
                    start=ent.get("start", 0),
                    end=ent.get("end", 0),
                    confidence=ent.get("confidence", 0.5)
                )
                entity_objects.append(entity_obj)
            return await self.extract_relationships(text, entity_objects)
        else:
            return await self.extract_relationships(text)
    
    async def batch_extract(self, texts: List[str], extraction_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Extract from multiple texts in batch"""
        results = []
        
        # Process in batches to avoid memory issues
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_results = await asyncio.gather(
                *[self.extract(text, extraction_types) for text in batch],
                return_exceptions=True
            )
            
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing text {i+j}: {result}")
                    results.append({"error": str(result)})
                else:
                    results.append(result)
        
        return results
    
    async def get_supported_entity_types(self) -> List[str]:
        """Get list of supported entity types"""
        return [
            "PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", 
            "WORK_OF_ART", "LAW", "LANGUAGE", "DATE", "TIME",
            "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL"
        ]
    
    async def get_supported_relation_types(self) -> List[str]:
        """Get list of supported relationship types"""
        return list(self.relation_patterns.keys()) + [
            "LOCATED_IN", "PART_OF", "WORKS_FOR", "FOUNDED_BY",
            "LEADS", "OWNS", "MEMBER_OF", "RELATED_TO", "CAUSES"
        ]
    
    async def shutdown(self):
        """Cleanup resources"""
        try:
            # Clear model references
            self.entity_model = None
            self.relation_model = None
            self.ner_pipeline = None
            self.relation_pipeline = None
            
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Transformer extractor shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")