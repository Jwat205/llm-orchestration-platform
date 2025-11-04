"""
Custom entity and relationship extractor with configurable extraction strategies.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum
import json
from collections import defaultdict, Counter
import inspect

logger = logging.getLogger(__name__)

class ExtractionStrategy(Enum):
    PATTERN_BASED = "pattern_based"
    RULE_BASED = "rule_based"
    KEYWORD_BASED = "keyword_based"
    CONTEXT_BASED = "context_based"
    HYBRID = "hybrid"

@dataclass
class ExtractionRule:
    """Custom extraction rule configuration"""
    name: str
    pattern: str
    entity_type: str
    confidence: float = 0.8
    context_patterns: List[str] = None
    validation_func: str = None
    priority: int = 1

@dataclass
class EntityMatch:
    """Entity extraction match result"""
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    attributes: Dict[str, Any] = None
    context: str = ""

@dataclass
class RelationshipMatch:
    """Relationship extraction match result"""
    subject_entity: str
    object_entity: str
    relation_type: str
    confidence: float
    context: str
    attributes: Dict[str, Any] = None

# custom_extractor.py
from dataclasses import replace
from typing import Any, Union

def _to_int(v: Any, default: int = -1) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def normalize_entity(obj: Union[EntityMatch, str, dict, Any], text: str) -> EntityMatch:
    """Return an EntityMatch with guaranteed int start/end.
    Works with EntityMatch, your GraphEntity, dicts, or plain strings."""
    # already good
    if isinstance(obj, EntityMatch):
        s = _to_int(obj.start)
        e = _to_int(obj.end)
        if s >= 0 and e >= s:
            return obj if (s == obj.start and e == obj.end) else replace(obj, start=s, end=e)

        # recompute span if invalid
        idx = text.lower().find(obj.text.lower())
        if idx != -1:
            return replace(obj, start=idx, end=idx + len(obj.text))
        return replace(obj, start=-1, end=-1)

    # GraphEntity-like
    if hasattr(obj, "name"):
        props = getattr(obj, "properties", {}) or {}
        s = _to_int(props.get("start", -1))
        e = _to_int(props.get("end", -1))
        if s < 0 or e < 0 or e < s:
            idx = text.lower().find((obj.name or "").lower())
            s, e = (idx, idx + len(obj.name)) if idx != -1 else (-1, -1)
        return EntityMatch(
            text=obj.name or props.get("text", ""),
            entity_type=getattr(obj, "type", "UNKNOWN"),
            start=s,
            end=e,
            confidence=getattr(obj, "confidence", 1.0),
            attributes=props,
            context=""
        )

    # dict
    if isinstance(obj, dict):
        s = _to_int(obj.get("start", -1))
        e = _to_int(obj.get("end", -1))
        if s < 0 or e < 0 or e < s:
            txt = obj.get("text", "")
            idx = text.lower().find(txt.lower())
            s, e = (idx, idx + len(txt)) if idx != -1 else (-1, -1)
        return EntityMatch(
            text=obj.get("text", ""),
            entity_type=obj.get("label", "UNKNOWN"),
            start=s,
            end=e,
            confidence=float(obj.get("confidence", 1.0)),
            attributes=obj.get("attributes", {}),
            context=obj.get("context", "")
        )

    # plain string fallback
    if isinstance(obj, str):
        idx = text.lower().find(obj.lower())
        s, e = (idx, idx + len(obj)) if idx != -1 else (-1, -1)
        return EntityMatch(obj, "UNKNOWN", s, e, 0.5, {}, "")

    # last resort
    sval = str(obj)
    return EntityMatch(sval, "UNKNOWN", -1, -1, 0.5, {}, "")


class BaseExtractor(ABC):
    """Abstract base class for extraction strategies"""
    
    @abstractmethod
    def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[EntityMatch]:
        pass
    
    @abstractmethod
    def extract_relationships(self, text: str, entities: List[EntityMatch] = None) -> List[RelationshipMatch]:
        pass

class PatternExtractor(BaseExtractor):
    """Pattern-based extraction using regex patterns"""
    
    def __init__(self, patterns: Dict[str, List[str]]):
        self.patterns = patterns
        self.compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, List[Tuple[re.Pattern, float]]]:
        compiled = {}
        for entity_type, pattern_list in self.patterns.items():
            compiled[entity_type] = []
            for pattern_def in pattern_list:
                if isinstance(pattern_def, dict):
                    pattern = pattern_def['pattern']
                    confidence = pattern_def.get('confidence', 0.8)
                else:
                    pattern = pattern_def
                    confidence = 0.8
                
                try:
                    compiled_pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                    compiled[entity_type].append((compiled_pattern, confidence))
                except re.error as e:
                    logger.warning(f"Invalid pattern for {entity_type}: {pattern} - {e}")
        
        return compiled
    
    def _to_entity_match(self, e) -> EntityMatch:
        # GraphEntity from your schema
        if hasattr(e, "id") and hasattr(e, "type") and hasattr(e, "name"):
            props = getattr(e, "properties", {}) or {}
            return EntityMatch(
                text=e.name or props.get("text", ""),
                entity_type=e.type,
                start=props.get("start", -1),
                end=props.get("end", -1),
                confidence=getattr(e, "confidence", 1.0),
                attributes=props,
                context=""
            )
        # spaCy/transformer extractor objects
        return EntityMatch(
            text=getattr(e, "text", getattr(e, "name", "")),
            entity_type=getattr(e, "label", getattr(e, "type", "UNKNOWN")),
            start=getattr(e, "start", -1),
            end=getattr(e, "end", -1),
            confidence=getattr(e, "confidence", 1.0),
            attributes=getattr(e, "attributes", {}),
            context=getattr(e, "context", "")
        )
    
    def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[EntityMatch]:
        entities = []
        
        for entity_type, pattern_list in self.compiled_patterns.items():
            for pattern, confidence in pattern_list:
                for match in pattern.finditer(text):
                    entity = EntityMatch(
                        text=match.group().strip(),
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        context=self._get_context(text, match.start(), match.end())
                    )
                    entities.append(entity)
        
        return self._deduplicate_entities(entities)
    
    def extract_relationships(self, text: str, entities: List[EntityMatch] = None) -> List[RelationshipMatch]:
        relationships = []
        
        if not entities or len(entities) < 2:
            return relationships
        
        # Simple distance-based relationship extraction
        relation_patterns = {
            'IS_A': [r'is a', r'is an', r'are'],
            'HAS': [r'has', r'have', r'contains', r'includes'],
            'PART_OF': [r'part of', r'component of', r'member of'],
            'LOCATED_IN': [r'located in', r'in', r'at'],
            'WORKS_FOR': [r'works for', r'employed by', r'at'],
            'CREATED_BY': [r'created by', r'made by', r'developed by'],
        }
        
        for i, subj in enumerate(entities):
            for j, obj in enumerate(entities[i+1:], i+1):
                relation = self._find_relation_between(text, subj, obj, relation_patterns)
                if relation:
                    relationships.append(relation)
        
        return relationships
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _find_relation_between(
        self,
        text: str,
        subj: EntityMatch,
        obj: EntityMatch,
        relation_patterns: Dict[str, List[str]],
    ) -> Optional[RelationshipMatch]:

        # subj/obj should already be EntityMatch; if not, normalize here or before call
        # quick guard
        if not hasattr(subj, "start") or not hasattr(obj, "start"):
            return None
        if subj.start < 0 or obj.start < 0:
            return None

        start_pos = min(subj.start, obj.start)
        end_pos   = max(subj.end,   obj.end)
        between_text = text[start_pos:end_pos].lower()

        for rel_type, patterns in relation_patterns.items():
            for pat in patterns:
                if re.search(pat, between_text, re.IGNORECASE):
                    return RelationshipMatch(
                        subject_entity=subj.text,
                        object_entity=obj.text,
                        relation_type=rel_type,
                        confidence=0.7,
                        context=between_text,
                    )
        return None
    
    def _deduplicate_entities(self, entities: List[EntityMatch]) -> List[EntityMatch]:
        # Remove overlapping entities, keeping higher confidence ones
        entities.sort(key=lambda x: (x.start, -x.confidence))
        deduplicated = []
        
        for entity in entities:
            overlap = False
            for existing in deduplicated:
                if self._overlaps(entity, existing):
                    overlap = True
                    break
            
            if not overlap:
                deduplicated.append(entity)
        
        return deduplicated
    
    def _overlaps(self, e1: EntityMatch, e2: EntityMatch) -> bool:
        return not (e1.end <= e2.start or e2.end <= e1.start)

class KeywordExtractor(BaseExtractor):
    """Keyword-based extraction using predefined dictionaries"""
    
    def __init__(self, keywords: Dict[str, List[str]]):
        self.keywords = keywords
        self.keyword_patterns = self._build_keyword_patterns()
    
    def _build_keyword_patterns(self) -> Dict[str, re.Pattern]:
        patterns = {}
        for entity_type, keyword_list in self.keywords.items():
            # Create word boundary patterns for exact matches
            pattern_str = r'\b(' + '|'.join(re.escape(kw) for kw in keyword_list) + r')\b'
            patterns[entity_type] = re.compile(pattern_str, re.IGNORECASE)
        
        return patterns
    
    def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[EntityMatch]:
        entities = []
        
        for entity_type, pattern in self.keyword_patterns.items():
            for match in pattern.finditer(text):
                entity = EntityMatch(
                    text=match.group().strip(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,  # High confidence for exact keyword matches
                    context=self._get_context(text, match.start(), match.end())
                )
                entities.append(entity)
        
        return entities
    
    def extract_relationships(
        self,
        text: str,
        entities: List[EntityMatch] = None
    ) -> List[RelationshipMatch]:
        if not entities or len(entities) < 2:
            return []

        relationships: List[RelationshipMatch] = []
        bounds = self._get_sentence_boundaries(text)
        for i, s in enumerate(entities):
            for o in entities[i+1:]:
                if self._in_same_sentence(s, o, bounds):
                    relationships.append(
                        RelationshipMatch(
                            subject_entity=s.text,
                            object_entity=o.text,
                            relation_type="CO_OCCURS",
                            confidence=0.6,
                            context=self._get_sentence_containing(text, s.start, bounds),
                        )
                    )
        return relationships
    
    def _get_context(self, text: str, start: int, end: int, window: int = 30) -> str:
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _get_sentence_boundaries(self, text: str) -> List[Tuple[int, int]]:
        sentences = re.split(r'[.!?]+', text)
        boundaries = []
        start = 0
        
        for sentence in sentences:
            end = start + len(sentence)
            if sentence.strip():
                boundaries.append((start, end))
            start = end + 1  # Account for delimiter
        
        return boundaries
    
    def _in_same_sentence(self, e1: EntityMatch, e2: EntityMatch, 
                         sentence_boundaries: List[Tuple[int, int]]) -> bool:
        for start, end in sentence_boundaries:
            if start <= e1.start <= end and start <= e2.start <= end:
                return True
        return False
    
    def _get_sentence_containing(self, text: str, pos: int, 
                                sentence_boundaries: List[Tuple[int, int]]) -> str:
        for start, end in sentence_boundaries:
            if start <= pos <= end:
                return text[start:end].strip()
        return ""

class RuleBasedExtractor(BaseExtractor):
    """Rule-based extraction with custom validation functions"""
    
    def __init__(self, rules: List[ExtractionRule]):
        self.rules = rules
        self.compiled_rules = self._compile_rules()
    
    def _compile_rules(self) -> List[Tuple[ExtractionRule, re.Pattern]]:
        compiled = []
        for rule in self.rules:
            try:
                pattern = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
                compiled.append((rule, pattern))
            except re.error as e:
                logger.warning(f"Invalid rule pattern {rule.name}: {rule.pattern} - {e}")
        
        return compiled
    
    def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[EntityMatch]:
        entities = []
        
        for rule, pattern in self.compiled_rules:
            for match in pattern.finditer(text):
                if self._validate_match(match, rule, text):
                    entity = EntityMatch(
                        text=match.group().strip(),
                        entity_type=rule.entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=rule.confidence,
                        context=self._get_context(text, match.start(), match.end())
                    )
                    entities.append(entity)
        
        return sorted(entities, key=lambda x: x.confidence, reverse=True)
    
    def extract_relationships(self, text: str, entities: List[EntityMatch] = None) -> List[RelationshipMatch]:
        # Implement rule-based relationship extraction
        return []
    
    def _validate_match(self, match: re.Match, rule: ExtractionRule, text: str) -> bool:
        if not rule.validation_func:
            return True
        
        # Simple validation functions
        validation_funcs = {
            'is_uppercase': lambda m: m.group().isupper(),
            'is_capitalized': lambda m: m.group().istitle(),
            'has_digits': lambda m: any(c.isdigit() for c in m.group()),
            'min_length': lambda m: len(m.group().strip()) >= 3,
            'not_common_word': lambda m: m.group().lower() not in {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        }
        
        func = validation_funcs.get(rule.validation_func)
        if func:
            return func(match)
        
        return True
    
    def _get_context(self, text: str, start: int, end: int, window: int = 40) -> str:
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()

class CustomExtractor:
    """Main custom extractor that combines multiple extraction strategies"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.extractors = self._initialize_extractors()
        self.entity_filters = config.get('entity_filters', {})
        self.relationship_filters = config.get('relationship_filters', {})
    
    def _initialize_extractors(self) -> Dict[str, BaseExtractor]:
        extractors = {}
        
        # Initialize pattern-based extractor
        if 'patterns' in self.config:
            extractors['pattern'] = PatternExtractor(self.config['patterns'])
        
        # Initialize keyword-based extractor
        if 'keywords' in self.config:
            extractors['keyword'] = KeywordExtractor(self.config['keywords'])
        
        # Initialize rule-based extractor
        if 'rules' in self.config:
            rules = [ExtractionRule(**rule) for rule in self.config['rules']]
            extractors['rule'] = RuleBasedExtractor(rules)
        
        return extractors
    
    def _normalize_strategy(self, strategy) -> ExtractionStrategy:
        """Normalize strategy input to ExtractionStrategy enum"""
        if isinstance(strategy, ExtractionStrategy):
            return strategy
        elif isinstance(strategy, str):
            try:
                return ExtractionStrategy(strategy.lower())
            except ValueError:
                logger.warning(f"Unknown strategy string: {strategy}, defaulting to HYBRID")
                return ExtractionStrategy.HYBRID
        elif isinstance(strategy, (int, float)):
            # Handle numeric values that might be passed incorrectly
            logger.warning(f"Received numeric strategy: {strategy}, defaulting to HYBRID")
            return ExtractionStrategy.HYBRID
        else:
            logger.warning(f"Unknown strategy type: {type(strategy)}, defaulting to HYBRID")
            return ExtractionStrategy.HYBRID
    
    def extract_entities(self, text: str, strategy: Union[ExtractionStrategy, str, Any] = ExtractionStrategy.HYBRID,
                        context: Dict[str, Any] = None) -> List[EntityMatch]:
        """Extract entities using specified strategy"""
        # Normalize the strategy input
        strategy = self._normalize_strategy(strategy)
        
        all_entities = []
        
        if strategy == ExtractionStrategy.HYBRID:
            # Use all available extractors
            for extractor in self.extractors.values():
                try:
                    entities = extractor.extract_entities(text, context)
                    all_entities.extend(entities)
                except Exception as e:
                    logger.error(f"Extractor failed: {e}")
                    continue
        else:
            # Use specific extractor
            extractor_name = strategy.value.split('_')[0]
            if extractor_name in self.extractors:
                try:
                    all_entities = self.extractors[extractor_name].extract_entities(text, context)
                except Exception as e:
                    logger.error(f"Extractor {extractor_name} failed: {e}")
                    all_entities = []
        
        # Apply filters and deduplication
        filtered_entities = self._filter_entities(all_entities)
        deduplicated_entities = self._deduplicate_entities(filtered_entities)
        
        return sorted(deduplicated_entities, key=lambda x: x.confidence, reverse=True)
    
    def extract_relationships(self, text: str, entities: List[EntityMatch] = None,
                            strategy: Union[ExtractionStrategy, str, Any] = ExtractionStrategy.HYBRID) -> List[RelationshipMatch]:
        """Extract relationships using specified strategy"""
        # Normalize the strategy input
        strategy = self._normalize_strategy(strategy)
        
        all_relationships = []
        
        if entities is None:
            entities = self.extract_entities(text, strategy)
        
        if strategy == ExtractionStrategy.HYBRID:
            # Use all available extractors
            for extractor in self.extractors.values():
                try:
                    relationships = extractor.extract_relationships(text, entities)
                    all_relationships.extend(relationships)
                except Exception as e:
                    logger.error(f"Relationship extractor failed: {e}")
                    continue
        else:
            # Use specific extractor
            extractor_name = strategy.value.split('_')[0]
            if extractor_name in self.extractors:
                try:
                    all_relationships = self.extractors[extractor_name].extract_relationships(text, entities)
                except Exception as e:
                    logger.error(f"Relationship extractor {extractor_name} failed: {e}")
                    all_relationships = []
        
        # Apply filters
        filtered_relationships = self._filter_relationships(all_relationships)
        
        return sorted(filtered_relationships, key=lambda x: x.confidence, reverse=True)
    
    def extract_with_confidence_threshold(self, text: str, entity_threshold: float = 0.7,
                                        relationship_threshold: float = 0.6) -> Tuple[List[EntityMatch], List[RelationshipMatch]]:
        """Extract entities and relationships with confidence thresholds"""
        entities = self.extract_entities(text)
        filtered_entities = [e for e in entities if e.confidence >= entity_threshold]
        
        relationships = self.extract_relationships(text, filtered_entities)
        filtered_relationships = [r for r in relationships if r.confidence >= relationship_threshold]
        
        return filtered_entities, filtered_relationships
    
    def _filter_entities(self, entities: List[EntityMatch]) -> List[EntityMatch]:
        """Apply entity filters"""
        filtered = []
        
        for entity in entities:
            if self._should_keep_entity(entity):
                filtered.append(entity)
        
        return filtered
    
    def _should_keep_entity(self, entity: EntityMatch) -> bool:
        """Check if entity should be kept based on filters"""
        filters = self.entity_filters
        
        # Minimum length filter
        if 'min_length' in filters:
            if len(entity.text.strip()) < filters['min_length']:
                return False
        
        # Maximum length filter
        if 'max_length' in filters:
            if len(entity.text.strip()) > filters['max_length']:
                return False
        
        # Blacklist filter
        if 'blacklist' in filters:
            if entity.text.lower() in filters['blacklist']:
                return False
        
        # Whitelist filter (if specified, entity must be in whitelist)
        if 'whitelist' in filters:
            if entity.text.lower() not in filters['whitelist']:
                return False
        
        return True
    
    def _filter_relationships(self, relationships: List[RelationshipMatch]) -> List[RelationshipMatch]:
        """Apply relationship filters"""
        filtered = []
        
        for relationship in relationships:
            if self._should_keep_relationship(relationship):
                filtered.append(relationship)
        
        return filtered
    
    def _should_keep_relationship(self, relationship: RelationshipMatch) -> bool:
        """Check if relationship should be kept based on filters"""
        filters = self.relationship_filters
        
        # Minimum confidence filter
        if 'min_confidence' in filters:
            if relationship.confidence < filters['min_confidence']:
                return False
        
        # Relationship type filter
        if 'allowed_types' in filters:
            if relationship.relation_type not in filters['allowed_types']:
                return False
        
        return True
    
    def _deduplicate_entities(self, entities: List[EntityMatch]) -> List[EntityMatch]:
        """Remove duplicate and overlapping entities"""
        if not entities:
            return []
        
        # Sort by position and confidence
        entities.sort(key=lambda x: (x.start, -x.confidence))
        
        deduplicated = []
        for entity in entities:
            # Check for overlap with existing entities
            overlap = False
            for existing in deduplicated:
                if self._entities_overlap(entity, existing):
                    # Keep the one with higher confidence
                    if entity.confidence > existing.confidence:
                        deduplicated.remove(existing)
                        deduplicated.append(entity)
                    overlap = True
                    break
            
            if not overlap:
                deduplicated.append(entity)
        
        return deduplicated
    
    def _entities_overlap(self, e1: EntityMatch, e2: EntityMatch) -> bool:
        """Check if two entities overlap in text position"""
        return not (e1.end <= e2.start or e2.end <= e1.start)
    
    def add_custom_patterns(self, entity_type: str, patterns: List[str]):
        """Add custom patterns for an entity type"""
        if 'pattern' not in self.extractors:
            self.extractors['pattern'] = PatternExtractor({})
        
        if entity_type not in self.extractors['pattern'].patterns:
            self.extractors['pattern'].patterns[entity_type] = []
        
        self.extractors['pattern'].patterns[entity_type].extend(patterns)
        self.extractors['pattern'].compiled_patterns = self.extractors['pattern']._compile_patterns()
    
    def add_custom_keywords(self, entity_type: str, keywords: List[str]):
        """Add custom keywords for an entity type"""
        if 'keyword' not in self.extractors:
            self.extractors['keyword'] = KeywordExtractor({})
        
        if entity_type not in self.extractors['keyword'].keywords:
            self.extractors['keyword'].keywords[entity_type] = []
        
        self.extractors['keyword'].keywords[entity_type].extend(keywords)
        self.extractors['keyword'].keyword_patterns = self.extractors['keyword']._build_keyword_patterns()
    
    def get_extraction_statistics(self, text: str) -> Dict[str, Any]:
        """Get statistics about extraction results"""
        entities = self.extract_entities(text)
        relationships = self.extract_relationships(text, entities)
        
        entity_types = Counter(e.entity_type for e in entities)
        relationship_types = Counter(r.relation_type for r in relationships)
        
        stats = {
            'total_entities': len(entities),
            'total_relationships': len(relationships),
            'entity_types': dict(entity_types),
            'relationship_types': dict(relationship_types),
            'avg_entity_confidence': sum(e.confidence for e in entities) / len(entities) if entities else 0,
            'avg_relationship_confidence': sum(r.confidence for r in relationships) / len(relationships) if relationships else 0,
            'text_length': len(text),
            'extraction_density': (len(entities) + len(relationships)) / len(text.split()) if text.split() else 0
        }
        
        return stats