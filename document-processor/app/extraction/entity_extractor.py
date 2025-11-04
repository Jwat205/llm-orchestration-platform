"""
Enhanced entity extractor with multiple extraction methods
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
from datetime import datetime
import json

# NLP libraries (with fallbacks)
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Enhanced entity extractor supporting multiple extraction methods"""
    
    def __init__(self):
        self.spacy_model = None
        self.transformer_pipeline = None
        self.pattern_rules = self._load_pattern_rules()
        
        # Initialize models
        self._initialize_models()
        
        # Entity type mappings
        self.entity_type_mappings = {
            # spaCy mappings
            "PERSON": "PERSON",
            "ORG": "ORGANIZATION", 
            "GPE": "LOCATION",
            "LOC": "LOCATION",
            "DATE": "DATE",
            "TIME": "TIME",
            "MONEY": "MONEY",
            "PERCENT": "PERCENT",
            "PRODUCT": "PRODUCT",
            "EVENT": "EVENT",
            "WORK_OF_ART": "WORK_OF_ART",
            "LAW": "LAW",
            "LANGUAGE": "LANGUAGE",
            
            # Transformer mappings (BERT NER)
            "PER": "PERSON",
            "MISC": "MISCELLANEOUS"
        }
        
        # Confidence thresholds
        self.min_confidence = 0.5
        self.high_confidence_threshold = 0.8
    
    def _initialize_models(self):
        """Initialize NLP models"""
        
        if SPACY_AVAILABLE:
            try:
                import spacy
                self.spacy_model = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded successfully")
            except OSError:
                logger.warning("spaCy model 'en_core_web_sm' not found")
                self.spacy_model = None
        
        if TRANSFORMERS_AVAILABLE:
            try:
                self.transformer_pipeline = pipeline(
                    "ner",
                    model="dbmdz/bert-large-cased-finetuned-conll03-english",
                    tokenizer="dbmdz/bert-large-cased-finetuned-conll03-english",
                    aggregation_strategy="simple"
                )
                logger.info("Transformer NER model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load transformer model: {e}")
                self.transformer_pipeline = None
    
    async def extract(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
        use_spacy: bool = True,
        use_transformers: bool = True,
        use_patterns: bool = True,
        merge_strategies: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities using multiple methods and merge results"""
        
        if merge_strategies is None:
            merge_strategies = ["confidence_weighted", "consensus"]
        
        all_entities = []
        extraction_methods = []
        
        try:
            # Method 1: spaCy extraction
            if use_spacy and self.spacy_model:
                spacy_entities = await self._extract_with_spacy(text, entity_types)
                all_entities.extend(spacy_entities)
                extraction_methods.append("spacy")
            
            # Method 2: Transformer extraction
            if use_transformers and self.transformer_pipeline:
                transformer_entities = await self._extract_with_transformers(text, entity_types)
                all_entities.extend(transformer_entities)
                extraction_methods.append("transformers")
            
            # Method 3: Pattern-based extraction
            if use_patterns:
                pattern_entities = await self._extract_with_patterns(text, entity_types)
                all_entities.extend(pattern_entities)
                extraction_methods.append("patterns")
            
            # Merge and deduplicate entities
            merged_entities = await self._merge_entities(
                all_entities, merge_strategies, extraction_methods
            )
            
            # Filter by confidence and types
            filtered_entities = self._filter_entities(merged_entities, entity_types)
            
            # Enrich with additional metadata
            enriched_entities = await self._enrich_entities(filtered_entities, text)
            
            return enriched_entities
            
        except Exception as e:
            logger.error(f"Error in entity extraction: {e}")
            return []
    
    async def extract_batch(
        self,
        texts: List[str],
        entity_types: Optional[List[str]] = None,
        batch_size: int = 50
    ) -> List[List[Dict[str, Any]]]:
        """Extract entities from multiple texts in batch"""
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            batch_tasks = [
                self.extract(text, entity_types) for text in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in batch extraction: {result}")
                    results.append([])
                else:
                    results.append(result)
        
        return results
    
    async def analyze_entity_patterns(
        self,
        text: str,
        entities: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze entity patterns in text"""
        
        if entities is None:
            entities = await self.extract(text)
        
        analysis = {
            "total_entities": len(entities),
            "entity_types": {},
            "confidence_distribution": {},
            "position_analysis": {},
            "co_occurrence_patterns": {},
            "entity_density": 0.0
        }
        
        if not entities:
            return analysis
        
        # Entity type distribution
        type_counts = Counter(entity["type"] for entity in entities)
        analysis["entity_types"] = dict(type_counts)
        
        # Confidence distribution
        confidences = [entity["confidence"] for entity in entities]
        analysis["confidence_distribution"] = {
            "high": len([c for c in confidences if c >= self.high_confidence_threshold]),
            "medium": len([c for c in confidences if 0.5 <= c < self.high_confidence_threshold]),
            "low": len([c for c in confidences if c < 0.5]),
            "average": sum(confidences) / len(confidences),
            "min": min(confidences),
            "max": max(confidences)
        }
        
        # Position analysis
        text_length = len(text)
        positions = [entity.get("start", 0) / text_length for entity in entities]
        analysis["position_analysis"] = {
            "early_text": len([p for p in positions if p < 0.33]),
            "middle_text": len([p for p in positions if 0.33 <= p < 0.66]),
            "late_text": len([p for p in positions if p >= 0.66])
        }
        
        # Co-occurrence patterns
        sentences = text.split('.')
        co_occurrences = defaultdict(int)
        
        for sentence in sentences:
            sentence_entities = [e for e in entities if e["name"] in sentence]
            
            for i, entity1 in enumerate(sentence_entities):
                for entity2 in sentence_entities[i+1:]:
                    pair = tuple(sorted([entity1["name"], entity2["name"]]))
                    co_occurrences[pair] += 1
        
        analysis["co_occurrence_patterns"] = dict(
            sorted(co_occurrences.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        # Entity density
        analysis["entity_density"] = len(entities) / len(text) * 1000 if text else 0
        
        return analysis
    
    async def validate_entities(
        self,
        entities: List[Dict[str, Any]],
        text: str
    ) -> Dict[str, Any]:
        """Validate extracted entities"""
        
        validation_result = {
            "total_entities": len(entities),
            "valid_entities": 0,
            "invalid_entities": 0,
            "validation_issues": [],
            "confidence_adjusted": 0
        }
        
        for entity in entities:
            issues = []
            
            # Check if entity name exists in text
            if entity["name"] not in text:
                issues.append("Entity name not found in text")
            
            # Check confidence threshold
            if entity["confidence"] < self.min_confidence:
                issues.append(f"Low confidence: {entity['confidence']}")
            
            # Check entity name length
            if len(entity["name"]) < 2:
                issues.append("Entity name too short")
            
            # Check for reasonable character composition
            if not re.search(r'[a-zA-Z]', entity["name"]):
                issues.append("Entity name contains no letters")
            
            # Check position bounds
            if "start" in entity and "end" in entity:
                if entity["start"] < 0 or entity["end"] > len(text):
                    issues.append("Invalid position bounds")
                elif entity["start"] >= entity["end"]:
                    issues.append("Invalid position ordering")
            
            if issues:
                validation_result["invalid_entities"] += 1
                validation_result["validation_issues"].append({
                    "entity": entity["name"],
                    "issues": issues
                })
                
                # Adjust confidence for problematic entities
                entity["confidence"] *= 0.5
                validation_result["confidence_adjusted"] += 1
            else:
                validation_result["valid_entities"] += 1
        
        return validation_result
    
    # Extraction method implementations
    async def _extract_with_spacy(
        self,
        text: str,
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities using spaCy"""
        
        def extract():
            doc = self.spacy_model(text)
            entities = []
            
            for ent in doc.ents:
                entity_type = self.entity_type_mappings.get(ent.label_, ent.label_)
                
                if entity_types is None or entity_type in entity_types:
                    entity = {
                        "name": ent.text,
                        "type": entity_type,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "confidence": 0.8,  # Default spaCy confidence
                        "source": "spacy",
                        "original_label": ent.label_,
                        "metadata": {
                            "pos_tags": [token.pos_ for token in ent],
                            "lemma": ent.lemma_,
                            "is_alpha": ent.text.isalpha(),
                            "is_title": ent.text.istitle()
                        }
                    }
                    entities.append(entity)
            
            return entities
        
        return await asyncio.to_thread(extract)
    
    async def _extract_with_transformers(
        self,
        text: str,
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities using transformer model"""
        
        def extract():
            results = self.transformer_pipeline(text)
            entities = []
            
            for result in results:
                entity_type = self.entity_type_mappings.get(
                    result["entity_group"].replace("B-", "").replace("I-", ""),
                    result["entity_group"]
                )
                
                if entity_types is None or entity_type in entity_types:
                    entity = {
                        "name": result["word"],
                        "type": entity_type,
                        "start": result["start"],
                        "end": result["end"],
                        "confidence": result["score"],
                        "source": "transformers",
                        "original_label": result["entity_group"],
                        "metadata": {
                            "model_confidence": result["score"],
                            "is_beginning": result["entity_group"].startswith("B-")
                        }
                    }
                    entities.append(entity)
            
            return entities
        
        return await asyncio.to_thread(extract)
    
    async def _extract_with_patterns(
        self,
        text: str,
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities using pattern matching"""
        
        entities = []
        
        for entity_type, patterns in self.pattern_rules.items():
            if entity_types is None or entity_type in entity_types:
                
                for pattern_info in patterns:
                    pattern = pattern_info["pattern"]
                    confidence = pattern_info["confidence"]
                    
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        entity = {
                            "name": match.group(),
                            "type": entity_type,
                            "start": match.start(),
                            "end": match.end(),
                            "confidence": confidence,
                            "source": "patterns",
                            "pattern_name": pattern_info["name"],
                            "metadata": {
                                "pattern_matched": pattern_info["name"],
                                "regex_groups": match.groups()
                            }
                        }
                        entities.append(entity)
        
        return entities
    
    def _load_pattern_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load pattern-based extraction rules"""
        
        return {
            "PERSON": [
                {
                    "name": "full_name",
                    "pattern": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
                    "confidence": 0.7
                },
                {
                    "name": "title_name",
                    "pattern": r'\b(?:Mr|Mrs|Ms|Dr|Prof)\. [A-Z][a-z]+ [A-Z][a-z]+\b',
                    "confidence": 0.9
                }
            ],
            "ORGANIZATION": [
                {
                    "name": "company_suffix",
                    "pattern": r'\b[A-Z][a-zA-Z\s]+(Inc|Corp|Ltd|LLC|Company|Corporation|Organization)\b',
                    "confidence": 0.8
                },
                {
                    "name": "university",
                    "pattern": r'\b[A-Z][a-zA-Z\s]+(University|College|Institute)\b',
                    "confidence": 0.85
                }
            ],
            "DATE": [
                {
                    "name": "numeric_date",
                    "pattern": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
                    "confidence": 0.95
                },
                {
                    "name": "iso_date",
                    "pattern": r'\b\d{4}-\d{2}-\d{2}\b',
                    "confidence": 0.98
                },
                {
                    "name": "written_date",
                    "pattern": r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
                    "confidence": 0.9
                }
            ],
            "TIME": [
                {
                    "name": "time_format",
                    "pattern": r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b',
                    "confidence": 0.9
                }
            ],
            "EMAIL": [
                {
                    "name": "email_address",
                    "pattern": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                    "confidence": 0.95
                }
            ],
            "PHONE": [
                {
                    "name": "phone_number",
                    "pattern": r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
                    "confidence": 0.9
                }
            ],
            "URL": [
                {
                    "name": "web_url",
                    "pattern": r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?',
                    "confidence": 0.95
                }
            ],
            "MONEY": [
                {
                    "name": "currency_amount",
                    "pattern": r'\$[\d,]+(?:\.\d{2})?|\b\d+(?:\.\d{2})?\s*(?:dollars?|USD|euros?|EUR|pounds?|GBP)\b',
                    "confidence": 0.9
                }
            ],
            "PERCENT": [
                {
                    "name": "percentage",
                    "pattern": r'\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*percent\b',
                    "confidence": 0.95
                }
            ]
        }
    
    async def _merge_entities(
        self,
        entities: List[Dict[str, Any]],
        merge_strategies: List[str],
        extraction_methods: List[str]
    ) -> List[Dict[str, Any]]:
        """Merge entities from different extraction methods"""
        
        if not entities:
            return []
        
        # Group overlapping entities
        entity_groups = self._group_overlapping_entities(entities)
        
        merged_entities = []
        
        for group in entity_groups:
            if len(group) == 1:
                merged_entities.append(group[0])
            else:
                # Apply merge strategies
                merged_entity = await self._merge_entity_group(group, merge_strategies)
                merged_entities.append(merged_entity)
        
        return merged_entities
    
    def _group_overlapping_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group entities that overlap in text positions"""
        
        # Sort entities by start position
        sorted_entities = sorted(entities, key=lambda x: x.get("start", 0))
        
        groups = []
        current_group = []
        
        for entity in sorted_entities:
            if not current_group:
                current_group = [entity]
            else:
                # Check if entity overlaps with any in current group
                overlaps = False
                for existing in current_group:
                    if self._entities_overlap(entity, existing):
                        overlaps = True
                        break
                
                if overlaps:
                    current_group.append(entity)
                else:
                    groups.append(current_group)
                    current_group = [entity]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _entities_overlap(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Check if two entities overlap in text positions"""
        
        start1, end1 = entity1.get("start", 0), entity1.get("end", 0)
        start2, end2 = entity2.get("start", 0), entity2.get("end", 0)
        
        # Check for overlap or similar names
        position_overlap = start1 < end2 and start2 < end1
        name_similarity = self._calculate_name_similarity(entity1["name"], entity2["name"]) > 0.8
        
        return position_overlap or name_similarity
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two entity names"""
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
    
    async def _merge_entity_group(
        self,
        group: List[Dict[str, Any]],
        merge_strategies: List[str]
    ) -> Dict[str, Any]:
        """Merge a group of overlapping entities"""
        
        if len(group) == 1:
            return group[0]
        
        # Start with highest confidence entity as base
        base_entity = max(group, key=lambda x: x["confidence"])
        merged_entity = base_entity.copy()
        
        # Apply merge strategies
        if "confidence_weighted" in merge_strategies:
            merged_entity = self._apply_confidence_weighted_merge(group, merged_entity)
        
        if "consensus" in merge_strategies:
            merged_entity = self._apply_consensus_merge(group, merged_entity)
        
        # Combine sources
        sources = list(set(entity["source"] for entity in group))
        merged_entity["source"] = "+".join(sources)
        
        # Add merge metadata
        merged_entity["metadata"] = merged_entity.get("metadata", {})
        merged_entity["metadata"].update({
            "merged_from": len(group),
            "merge_sources": sources,
            "original_confidences": [e["confidence"] for e in group]
        })
        
        return merged_entity
    
    def _apply_confidence_weighted_merge(
        self,
        group: List[Dict[str, Any]],
        base_entity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply confidence-weighted merging"""
        
        total_confidence = sum(entity["confidence"] for entity in group)
        
        # Weighted average confidence
        base_entity["confidence"] = total_confidence / len(group)
        
        # Choose name from highest confidence entity
        highest_conf_entity = max(group, key=lambda x: x["confidence"])
        base_entity["name"] = highest_conf_entity["name"]
        
        return base_entity
    
    def _apply_consensus_merge(
        self,
        group: List[Dict[str, Any]],
        base_entity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply consensus-based merging"""
        
        # Most common type
        types = [entity["type"] for entity in group]
        type_counts = Counter(types)
        base_entity["type"] = type_counts.most_common(1)[0][0]
        
        # Boost confidence if multiple methods agree
        if len(set(types)) == 1:  # All agree on type
            base_entity["confidence"] = min(base_entity["confidence"] * 1.2, 1.0)
        
        return base_entity
    
    def _filter_entities(
        self,
        entities: List[Dict[str, Any]],
        entity_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Filter entities by confidence and type"""
        
        filtered = []
        
        for entity in entities:
            # Filter by confidence
            if entity["confidence"] < self.min_confidence:
                continue
            
            # Filter by type
            if entity_types and entity["type"] not in entity_types:
                continue
            
            filtered.append(entity)
        
        return filtered
    
    async def _enrich_entities(
        self,
        entities: List[Dict[str, Any]],
        text: str
    ) -> List[Dict[str, Any]]:
        """Enrich entities with additional metadata"""
        
        enriched = []
        
        for entity in entities:
            enriched_entity = entity.copy()
            
            # Add context information
            context = self._extract_entity_context(entity, text)
            enriched_entity["context"] = context
            
            # Add frequency information
            frequency = text.lower().count(entity["name"].lower())
            enriched_entity["frequency"] = frequency
            
            # Add position relative to document
            if "start" in entity:
                relative_position = entity["start"] / len(text)
                enriched_entity["relative_position"] = relative_position
            
            # Add canonical form
            canonical_form = self._get_canonical_form(entity["name"], entity["type"])
            if canonical_form != entity["name"]:
                enriched_entity["canonical_form"] = canonical_form
            
            # Add validation score
            validation_score = self._calculate_validation_score(entity, text)
            enriched_entity["validation_score"] = validation_score
            
            enriched.append(enriched_entity)
        
        return enriched
    
    def _extract_entity_context(
        self,
        entity: Dict[str, Any],
        text: str,
        context_window: int = 50
    ) -> Dict[str, Any]:
        """Extract context around entity"""
        
        context = {
            "before": "",
            "after": "",
            "sentence": ""
        }
        
        if "start" in entity and "end" in entity:
            start, end = entity["start"], entity["end"]
            
            # Before context
            before_start = max(0, start - context_window)
            context["before"] = text[before_start:start].strip()
            
            # After context
            after_end = min(len(text), end + context_window)
            context["after"] = text[end:after_end].strip()
            
            # Sentence context
            sentences = text.split('.')
            for sentence in sentences:
                if entity["name"] in sentence:
                    context["sentence"] = sentence.strip()
                    break
        
        return context
    
    def _get_canonical_form(self, name: str, entity_type: str) -> str:
        """Get canonical form of entity name"""
        
        canonical = name
        
        if entity_type == "PERSON":
            # Title case for person names
            canonical = name.title()
        elif entity_type == "ORGANIZATION":
            # Proper case for organizations
            canonical = name.title()
        elif entity_type == "DATE":
            # Standardize date format if possible
            # This would include actual date parsing in practice
            canonical = name
        
        return canonical
    
    def _calculate_validation_score(
        self,
        entity: Dict[str, Any],
        text: str
    ) -> float:
        """Calculate validation score for entity"""
        
        score = entity["confidence"]
        
        # Boost for high-confidence sources
        if entity["source"] == "transformers" and entity["confidence"] > 0.9:
            score *= 1.1
        elif entity["source"] == "patterns" and entity["confidence"] > 0.9:
            score *= 1.05
        
        # Boost for frequent entities
        frequency = text.lower().count(entity["name"].lower())
        if frequency > 1:
            score *= min(1.0 + (frequency - 1) * 0.1, 1.3)
        
        # Penalty for very short names
        if len(entity["name"]) < 3:
            score *= 0.8
        
        # Penalty for all caps or all lowercase (unless appropriate)
        if entity["type"] in ["PERSON", "ORGANIZATION"] and (
            entity["name"].isupper() or entity["name"].islower()
        ):
            score *= 0.9
        
        return min(score, 1.0)