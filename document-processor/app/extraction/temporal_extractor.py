"""
Temporal extractor for identifying time-related information, events, and temporal relationships
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json

# Date parsing libraries (with fallbacks)
try:
    from dateutil import parser as date_parser
    from dateutil.relativedelta import relativedelta
    import pytz
    DATE_PARSING_AVAILABLE = True
except ImportError:
    DATE_PARSING_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

logger = logging.getLogger(__name__)


class TemporalType(Enum):
    """Types of temporal information"""
    ABSOLUTE_DATE = "ABSOLUTE_DATE"
    RELATIVE_TIME = "RELATIVE_TIME"
    DURATION = "DURATION"
    FREQUENCY = "FREQUENCY"
    TIME_PERIOD = "TIME_PERIOD"
    EVENT_TIME = "EVENT_TIME"
    TEMPORAL_SEQUENCE = "TEMPORAL_SEQUENCE"
    TEMPORAL_RELATION = "TEMPORAL_RELATION"
    HISTORICAL_PERIOD = "HISTORICAL_PERIOD"
    FUTURE_PROJECTION = "FUTURE_PROJECTION"


class TemporalRelation(Enum):
    """Types of temporal relationships"""
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    DURING = "DURING"
    SIMULTANEOUS = "SIMULTANEOUS"
    OVERLAPS = "OVERLAPS"
    CONTAINS = "CONTAINS"
    STARTS = "STARTS"
    ENDS = "ENDS"
    ADJACENT = "ADJACENT"


@dataclass
class TemporalEntity:
    """Represents a temporal entity or expression"""
    text: str
    temporal_type: TemporalType
    start_position: int
    end_position: int
    normalized_value: Optional[str]
    confidence: float
    extraction_method: str
    metadata: Dict[str, Any]
    parsed_datetime: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    context: Optional[str] = None


@dataclass
class TemporalRelationship:
    """Represents a temporal relationship between entities or events"""
    source_entity: str
    target_entity: str
    relation_type: TemporalRelation
    confidence: float
    evidence_text: str
    extraction_method: str
    metadata: Dict[str, Any]


class TemporalExtractor:
    """Enhanced temporal information extractor"""
    
    def __init__(self):
        self.spacy_model = None
        self.temporal_patterns = self._load_temporal_patterns()
        self.relative_time_patterns = self._load_relative_time_patterns()
        self.temporal_signal_words = self._load_temporal_signals()
        
        # Initialize models
        self._initialize_models()
        
        # Configuration
        self.min_confidence = 0.3
        self.context_window = 50
        
        # Time units for duration calculation
        self.time_units = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2592000,  # 30 days
            "year": 31536000   # 365 days
        }
    
    def _initialize_models(self):
        """Initialize NLP models for temporal extraction"""
        
        if SPACY_AVAILABLE:
            try:
                self.spacy_model = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded for temporal extraction")
            except OSError:
                logger.warning("spaCy model not found for temporal extraction")
                self.spacy_model = None
    
    async def extract_temporal_information(
        self,
        text: str,
        temporal_types: Optional[List[TemporalType]] = None,
        reference_time: Optional[datetime] = None,
        extract_relations: bool = True
    ) -> Dict[str, Any]:
        """Extract all temporal information from text"""
        
        if reference_time is None:
            reference_time = datetime.now()
        
        result = {
            "temporal_entities": [],
            "temporal_relationships": [],
            "timeline": [],
            "temporal_patterns": {},
            "reference_time": reference_time.isoformat()
        }
        
        try:
            # Extract temporal entities
            temporal_entities = await self.extract_temporal_entities(
                text, temporal_types, reference_time
            )
            result["temporal_entities"] = [self._entity_to_dict(e) for e in temporal_entities]
            
            # Extract temporal relationships
            if extract_relations:
                temporal_relationships = await self.extract_temporal_relationships(
                    text, temporal_entities
                )
                result["temporal_relationships"] = [
                    self._relationship_to_dict(r) for r in temporal_relationships
                ]
            
            # Create timeline
            timeline = await self.create_timeline(temporal_entities)
            result["timeline"] = timeline
            
            # Analyze temporal patterns
            patterns = await self.analyze_temporal_patterns(text, temporal_entities)
            result["temporal_patterns"] = patterns
            
            return result
            
        except Exception as e:
            logger.error(f"Error in temporal extraction: {e}")
            return result
    
    async def extract_temporal_entities(
        self,
        text: str,
        temporal_types: Optional[List[TemporalType]] = None,
        reference_time: Optional[datetime] = None
    ) -> List[TemporalEntity]:
        """Extract temporal entities from text"""
        
        if reference_time is None:
            reference_time = datetime.now()
        
        all_entities = []
        
        try:
            # Method 1: Pattern-based extraction
            pattern_entities = await self._extract_with_patterns(text, temporal_types, reference_time)
            all_entities.extend(pattern_entities)
            
            # Method 2: spaCy NER extraction
            if self.spacy_model:
                spacy_entities = await self._extract_with_spacy(text, temporal_types, reference_time)
                all_entities.extend(spacy_entities)
            
            # Method 3: Date parsing extraction
            if DATE_PARSING_AVAILABLE:
                parsed_entities = await self._extract_with_date_parsing(text, temporal_types, reference_time)
                all_entities.extend(parsed_entities)
            
            # Method 4: Relative time extraction
            relative_entities = await self._extract_relative_times(text, temporal_types, reference_time)
            all_entities.extend(relative_entities)
            
            # Merge and deduplicate entities
            merged_entities = await self._merge_temporal_entities(all_entities)
            
            # Filter by confidence and type
            filtered_entities = self._filter_temporal_entities(merged_entities, temporal_types)
            
            return filtered_entities
            
        except Exception as e:
            logger.error(f"Error extracting temporal entities: {e}")
            return []
    
    async def extract_temporal_relationships(
        self,
        text: str,
        temporal_entities: List[TemporalEntity]
    ) -> List[TemporalRelationship]:
        """Extract temporal relationships between entities"""
        
        relationships = []
        
        try:
            # Method 1: Signal word based relationships
            signal_relationships = await self._extract_signal_relationships(text, temporal_entities)
            relationships.extend(signal_relationships)
            
            # Method 2: Proximity based relationships
            proximity_relationships = await self._extract_proximity_relationships(text, temporal_entities)
            relationships.extend(proximity_relationships)
            
            # Method 3: Sequence pattern relationships
            sequence_relationships = await self._extract_sequence_relationships(text, temporal_entities)
            relationships.extend(sequence_relationships)
            
            # Merge and filter relationships
            merged_relationships = await self._merge_temporal_relationships(relationships)
            
            return merged_relationships
            
        except Exception as e:
            logger.error(f"Error extracting temporal relationships: {e}")
            return []
    
    async def create_timeline(self, temporal_entities: List[TemporalEntity]) -> List[Dict[str, Any]]:
        """Create a chronological timeline from temporal entities"""
        
        timeline_events = []
        
        for entity in temporal_entities:
            if entity.parsed_datetime or entity.normalized_value:
                event = {
                    "text": entity.text,
                    "type": entity.temporal_type.value,
                    "datetime": entity.parsed_datetime.isoformat() if entity.parsed_datetime else None,
                    "normalized": entity.normalized_value,
                    "confidence": entity.confidence,
                    "context": entity.context
                }
                timeline_events.append(event)
        
        # Sort by datetime if available
        dated_events = [e for e in timeline_events if e["datetime"]]
        undated_events = [e for e in timeline_events if not e["datetime"]]
        
        dated_events.sort(key=lambda x: x["datetime"])
        
        return dated_events + undated_events
    
    async def analyze_temporal_patterns(
        self,
        text: str,
        temporal_entities: List[TemporalEntity]
    ) -> Dict[str, Any]:
        """Analyze temporal patterns in the text"""
        
        analysis = {
            "temporal_density": 0.0,
            "temporal_types": {},
            "time_periods": {},
            "temporal_focus": "",
            "chronological_order": True,
            "temporal_coherence": 0.0
        }
        
        if not temporal_entities:
            return analysis
        
        # Calculate temporal density
        text_length = len(text)
        analysis["temporal_density"] = len(temporal_entities) / text_length * 1000
        
        # Analyze temporal types
        type_counts = Counter(entity.temporal_type.value for entity in temporal_entities)
        analysis["temporal_types"] = dict(type_counts)
        
        # Identify time periods
        periods = self._identify_time_periods(temporal_entities)
        analysis["time_periods"] = periods
        
        # Determine temporal focus
        analysis["temporal_focus"] = self._determine_temporal_focus(temporal_entities)
        
        # Check chronological order
        analysis["chronological_order"] = self._check_chronological_order(temporal_entities)
        
        # Calculate temporal coherence
        analysis["temporal_coherence"] = self._calculate_temporal_coherence(temporal_entities)
        
        return analysis
    
    # Extraction method implementations
    async def _extract_with_patterns(
        self,
        text: str,
        temporal_types: Optional[List[TemporalType]],
        reference_time: datetime
    ) -> List[TemporalEntity]:
        """Extract temporal entities using regex patterns"""
        
        entities = []
        
        for temporal_type, patterns in self.temporal_patterns.items():
            if temporal_types and temporal_type not in temporal_types:
                continue
            
            for pattern_info in patterns:
                pattern = pattern_info["pattern"]
                confidence = pattern_info["confidence"]
                
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group()
                    
                    # Normalize the temporal expression
                    normalized_value = self._normalize_temporal_expression(
                        matched_text, temporal_type, reference_time
                    )
                    
                    # Parse datetime if possible
                    parsed_datetime = self._parse_datetime(matched_text, reference_time)
                    
                    # Calculate duration if applicable
                    duration_seconds = self._calculate_duration(matched_text)
                    
                    # Extract context
                    context = self._extract_context(text, match.start(), match.end())
                    
                    entity = TemporalEntity(
                        text=matched_text,
                        temporal_type=temporal_type,
                        start_position=match.start(),
                        end_position=match.end(),
                        normalized_value=normalized_value,
                        confidence=confidence,
                        extraction_method="patterns",
                        metadata={
                            "pattern_name": pattern_info["name"],
                            "regex_groups": match.groups()
                        },
                        parsed_datetime=parsed_datetime,
                        duration_seconds=duration_seconds,
                        context=context
                    )
                    entities.append(entity)
        
        return entities
    
    async def _extract_with_spacy(
        self,
        text: str,
        temporal_types: Optional[List[TemporalType]],
        reference_time: datetime
    ) -> List[TemporalEntity]:
        """Extract temporal entities using spaCy NER"""
        
        if not self.spacy_model:
            return []
        
        def extract():
            doc = self.spacy_model(text)
            entities = []
            
            for ent in doc.ents:
                if ent.label_ in ["DATE", "TIME", "EVENT"]:
                    # Classify temporal type
                    temporal_type = self._classify_spacy_temporal_type(ent.text, ent.label_)
                    
                    if temporal_types and temporal_type not in temporal_types:
                        continue
                    
                    # Normalize and parse
                    normalized_value = self._normalize_temporal_expression(
                        ent.text, temporal_type, reference_time
                    )
                    parsed_datetime = self._parse_datetime(ent.text, reference_time)
                    duration_seconds = self._calculate_duration(ent.text)
                    context = self._extract_context(text, ent.start_char, ent.end_char)
                    
                    entity = TemporalEntity(
                        text=ent.text,
                        temporal_type=temporal_type,
                        start_position=ent.start_char,
                        end_position=ent.end_char,
                        normalized_value=normalized_value,
                        confidence=0.8,  # Default spaCy confidence
                        extraction_method="spacy",
                        metadata={
                            "spacy_label": ent.label_,
                            "pos_tags": [token.pos_ for token in ent]
                        },
                        parsed_datetime=parsed_datetime,
                        duration_seconds=duration_seconds,
                        context=context
                    )
                    entities.append(entity)
            
            return entities
        
        return await asyncio.to_thread(extract)
    
    async def _extract_with_date_parsing(
        self,
        text: str,
        temporal_types: Optional[List[TemporalType]],
        reference_time: datetime
    ) -> List[TemporalEntity]:
        """Extract temporal entities using dateutil parsing"""
        
        if not DATE_PARSING_AVAILABLE:
            return []
        
        entities = []
        
        # Split text into potential date phrases
        date_candidates = re.findall(
            r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b',
            text, re.IGNORECASE
        )
        
        for candidate in date_candidates:
            try:
                parsed_date = date_parser.parse(candidate, default=reference_time)
                
                # Find position in text
                start_pos = text.find(candidate)
                if start_pos >= 0:
                    temporal_type = TemporalType.ABSOLUTE_DATE
                    
                    if temporal_types and temporal_type not in temporal_types:
                        continue
                    
                    context = self._extract_context(text, start_pos, start_pos + len(candidate))
                    
                    entity = TemporalEntity(
                        text=candidate,
                        temporal_type=temporal_type,
                        start_position=start_pos,
                        end_position=start_pos + len(candidate),
                        normalized_value=parsed_date.isoformat(),
                        confidence=0.9,
                        extraction_method="date_parsing",
                        metadata={
                            "parser_used": "dateutil",
                            "default_time": reference_time.isoformat()
                        },
                        parsed_datetime=parsed_date,
                        context=context
                    )
                    entities.append(entity)
                    
            except (ValueError, TypeError):
                continue
        
        return entities
    
    async def _extract_relative_times(
        self,
        text: str,
        temporal_types: Optional[List[TemporalType]],
        reference_time: datetime
    ) -> List[TemporalEntity]:
        """Extract relative time expressions"""
        
        entities = []
        
        for pattern_info in self.relative_time_patterns:
            pattern = pattern_info["pattern"]
            confidence = pattern_info["confidence"]
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matched_text = match.group()
                
                temporal_type = TemporalType.RELATIVE_TIME
                if temporal_types and temporal_type not in temporal_types:
                    continue
                
                # Calculate absolute time from relative expression
                absolute_time = self._resolve_relative_time(matched_text, reference_time)
                normalized_value = absolute_time.isoformat() if absolute_time else None
                
                context = self._extract_context(text, match.start(), match.end())
                
                entity = TemporalEntity(
                    text=matched_text,
                    temporal_type=temporal_type,
                    start_position=match.start(),
                    end_position=match.end(),
                    normalized_value=normalized_value,
                    confidence=confidence,
                    extraction_method="relative_time",
                    metadata={
                        "pattern_name": pattern_info["name"],
                        "reference_time": reference_time.isoformat()
                    },
                    parsed_datetime=absolute_time,
                    context=context
                )
                entities.append(entity)
        
        return entities
    
    async def _extract_signal_relationships(
        self,
        text: str,
        temporal_entities: List[TemporalEntity]
    ) -> List[TemporalRelationship]:
        """Extract temporal relationships using signal words"""
        
        relationships = []
        
        for signal_word, relation_type in self.temporal_signal_words.items():
            pattern = rf'\b{re.escape(signal_word)}\b'
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Find temporal entities near the signal word
                nearby_entities = self._find_nearby_entities(
                    temporal_entities, match.start(), match.end(), window=100
                )
                
                if len(nearby_entities) >= 2:
                    # Create relationship between the two nearest entities
                    entity1, entity2 = nearby_entities[:2]
                    
                    # Determine source and target based on position and relation type
                    if relation_type in [TemporalRelation.BEFORE, TemporalRelation.AFTER]:
                        source = entity1 if entity1.start_position < match.start() else entity2
                        target = entity2 if source == entity1 else entity1
                    else:
                        source, target = entity1, entity2
                    
                    relationship = TemporalRelationship(
                        source_entity=source.text,
                        target_entity=target.text,
                        relation_type=relation_type,
                        confidence=0.7,
                        evidence_text=text[source.start_position:target.end_position],
                        extraction_method="signal_words",
                        metadata={
                            "signal_word": signal_word,
                            "signal_position": match.start()
                        }
                    )
                    relationships.append(relationship)
        
        return relationships
    
    async def _extract_proximity_relationships(
        self,
        text: str,
        temporal_entities: List[TemporalEntity]
    ) -> List[TemporalRelationship]:
        """Extract temporal relationships based on proximity"""
        
        relationships = []
        
        # Sort entities by position
        sorted_entities = sorted(temporal_entities, key=lambda x: x.start_position)
        
        for i, entity1 in enumerate(sorted_entities):
            for entity2 in sorted_entities[i+1:]:
                distance = entity2.start_position - entity1.end_position
                
                if distance > 200:  # Too far apart
                    break
                
                # Infer relationship type based on context and entity types
                relation_type = self._infer_temporal_relation(entity1, entity2, text)
                
                if relation_type:
                    confidence = max(0.3, 1.0 - (distance / 200))
                    
                    relationship = TemporalRelationship(
                        source_entity=entity1.text,
                        target_entity=entity2.text,
                        relation_type=relation_type,
                        confidence=confidence,
                        evidence_text=text[entity1.start_position:entity2.end_position],
                        extraction_method="proximity",
                        metadata={
                            "distance": distance,
                            "context_window": text[entity1.start_position:entity2.end_position]
                        }
                    )
                    relationships.append(relationship)
        
        return relationships
    
    async def _extract_sequence_relationships(
        self,
        text: str,
        temporal_entities: List[TemporalEntity]
    ) -> List[TemporalRelationship]:
        """Extract temporal relationships from sequence patterns"""
        
        relationships = []
        
        # Look for sequence indicators
        sequence_patterns = [
            r'\b(?:first|initially|at first)\b.*?\b(?:then|next|after(?:ward)?s?|subsequently)\b',
            r'\b(?:before|prior to)\b.*?\b(?:after|following|then)\b',
            r'\b(?:during|while)\b.*?\b(?:until|till)\b'
        ]
        
        for pattern in sequence_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                sequence_text = match.group()
                
                # Find temporal entities within the sequence
                sequence_entities = []
                for entity in temporal_entities:
                    if (match.start() <= entity.start_position <= match.end() or
                        match.start() <= entity.end_position <= match.end()):
                        sequence_entities.append(entity)
                
                if len(sequence_entities) >= 2:
                    # Create sequential relationships
                    for i in range(len(sequence_entities) - 1):
                        relationship = TemporalRelationship(
                            source_entity=sequence_entities[i].text,
                            target_entity=sequence_entities[i+1].text,
                            relation_type=TemporalRelation.BEFORE,
                            confidence=0.8,
                            evidence_text=sequence_text,
                            extraction_method="sequence_patterns",
                            metadata={
                                "sequence_pattern": pattern,
                                "sequence_position": i
                            }
                        )
                        relationships.append(relationship)
        
        return relationships
    
    # Helper methods
    def _normalize_temporal_expression(
        self,
        expression: str,
        temporal_type: TemporalType,
        reference_time: datetime
    ) -> Optional[str]:
        """Normalize temporal expression to standard format"""
        
        expression_lower = expression.lower()
        
        if temporal_type == TemporalType.ABSOLUTE_DATE:
            # Try to parse as standard date
            if DATE_PARSING_AVAILABLE:
                try:
                    parsed = date_parser.parse(expression, default=reference_time)
                    return parsed.strftime("%Y-%m-%d")
                except:
                    pass
        
        elif temporal_type == TemporalType.DURATION:
            # Normalize duration expressions
            duration_seconds = self._calculate_duration(expression)
            if duration_seconds:
                return f"{duration_seconds}s"
        
        elif temporal_type == TemporalType.RELATIVE_TIME:
            # Resolve relative time to absolute
            absolute_time = self._resolve_relative_time(expression, reference_time)
            if absolute_time:
                return absolute_time.isoformat()
        
        return expression
    
    def _parse_datetime(self, expression: str, reference_time: datetime) -> Optional[datetime]:
        """Parse datetime from temporal expression"""
        
        if not DATE_PARSING_AVAILABLE:
            return None
        
        try:
            return date_parser.parse(expression, default=reference_time)
        except (ValueError, TypeError):
            return None
    
    def _calculate_duration(self, expression: str) -> Optional[int]:
        """Calculate duration in seconds from expression"""
        
        expression_lower = expression.lower()
        
        # Pattern for extracting number and unit
        duration_pattern = r'(\d+(?:\.\d+)?)\s*([a-z]+)'
        match = re.search(duration_pattern, expression_lower)
        
        if match:
            number = float(match.group(1))
            unit = match.group(2)
            
            # Normalize unit
            for base_unit, multiplier in self.time_units.items():
                if unit.startswith(base_unit) or unit + 's' == base_unit + 's':
                    return int(number * multiplier)
        
        return None
    
    def _resolve_relative_time(self, expression: str, reference_time: datetime) -> Optional[datetime]:
        """Resolve relative time expression to absolute datetime"""
        
        expression_lower = expression.lower()
        
        # Simple relative time resolution
        if "yesterday" in expression_lower:
            return reference_time - timedelta(days=1)
        elif "tomorrow" in expression_lower:
            return reference_time + timedelta(days=1)
        elif "last week" in expression_lower:
            return reference_time - timedelta(weeks=1)
        elif "next week" in expression_lower:
            return reference_time + timedelta(weeks=1)
        elif "last month" in expression_lower:
            return reference_time - relativedelta(months=1) if DATE_PARSING_AVAILABLE else reference_time - timedelta(days=30)
        elif "next month" in expression_lower:
            return reference_time + relativedelta(months=1) if DATE_PARSING_AVAILABLE else reference_time + timedelta(days=30)
        
        # Pattern-based relative time
        relative_pattern = r'(\d+)\s*(day|week|month|year)s?\s*(ago|from now)'
        match = re.search(relative_pattern, expression_lower)
        
        if match:
            number = int(match.group(1))
            unit = match.group(2)
            direction = match.group(3)
            
            if unit == "day":
                delta = timedelta(days=number)
            elif unit == "week":
                delta = timedelta(weeks=number)
            elif unit == "month":
                delta = relativedelta(months=number) if DATE_PARSING_AVAILABLE else timedelta(days=number * 30)
            elif unit == "year":
                delta = relativedelta(years=number) if DATE_PARSING_AVAILABLE else timedelta(days=number * 365)
            else:
                return None
            
            if direction == "ago":
                return reference_time - delta
            else:
                return reference_time + delta
        
        return None
    
    def _extract_context(self, text: str, start: int, end: int) -> str:
        """Extract context around temporal entity"""
        
        context_start = max(0, start - self.context_window)
        context_end = min(len(text), end + self.context_window)
        
        return text[context_start:context_end].strip()
    
    def _classify_spacy_temporal_type(self, text: str, spacy_label: str) -> TemporalType:
        """Classify temporal type from spaCy entity"""
        
        text_lower = text.lower()
        
        if spacy_label == "DATE":
            if any(word in text_lower for word in ["yesterday", "tomorrow", "last", "next"]):
                return TemporalType.RELATIVE_TIME
            else:
                return TemporalType.ABSOLUTE_DATE
        elif spacy_label == "TIME":
            return TemporalType.EVENT_TIME
        else:
            return TemporalType.TIME_PERIOD
    
    def _find_nearby_entities(
        self,
        entities: List[TemporalEntity],
        start: int,
        end: int,
        window: int = 100
    ) -> List[TemporalEntity]:
        """Find temporal entities near a given position"""
        
        nearby = []
        
        for entity in entities:
            # Check if entity is within window
            if (abs(entity.start_position - start) <= window or
                abs(entity.end_position - end) <= window):
                nearby.append(entity)
        
        # Sort by distance
        nearby.sort(key=lambda x: min(abs(x.start_position - start), abs(x.end_position - end)))
        
        return nearby
    
    def _infer_temporal_relation(
        self,
        entity1: TemporalEntity,
        entity2: TemporalEntity,
        text: str
    ) -> Optional[TemporalRelation]:
        """Infer temporal relationship between two entities"""
        
        # Extract context between entities
        context_start = entity1.end_position
        context_end = entity2.start_position
        context = text[context_start:context_end].lower()
        
        # Check for explicit relation signals
        if any(word in context for word in ["before", "prior to", "earlier"]):
            return TemporalRelation.BEFORE
        elif any(word in context for word in ["after", "following", "later"]):
            return TemporalRelation.AFTER
        elif any(word in context for word in ["during", "while", "throughout"]):
            return TemporalRelation.DURING
        elif any(word in context for word in ["simultaneously", "at the same time"]):
            return TemporalRelation.SIMULTANEOUS
        
        # Infer based on temporal types and parsed times
        if entity1.parsed_datetime and entity2.parsed_datetime:
            if entity1.parsed_datetime < entity2.parsed_datetime:
                return TemporalRelation.BEFORE
            elif entity1.parsed_datetime > entity2.parsed_datetime:
                return TemporalRelation.AFTER
            else:
                return TemporalRelation.SIMULTANEOUS
        
        # Default inference based on position
        return TemporalRelation.BEFORE
    
    async def _merge_temporal_entities(self, entities: List[TemporalEntity]) -> List[TemporalEntity]:
        """Merge overlapping or duplicate temporal entities"""
        
        if not entities:
            return []
        
        # Sort by position
        sorted_entities = sorted(entities, key=lambda x: x.start_position)
        
        merged = []
        current_group = [sorted_entities[0]]
        
        for entity in sorted_entities[1:]:
            # Check if overlaps with current group
            if any(self._entities_overlap(entity, e) for e in current_group):
                current_group.append(entity)
            else:
                # Merge current group and start new one
                merged_entity = self._merge_entity_group(current_group)
                merged.append(merged_entity)
                current_group = [entity]
        
        # Merge final group
        if current_group:
            merged_entity = self._merge_entity_group(current_group)
            merged.append(merged_entity)
        
        return merged
    
    def _entities_overlap(self, entity1: TemporalEntity, entity2: TemporalEntity) -> bool:
        """Check if two temporal entities overlap"""
        
        # Position overlap
        pos_overlap = (entity1.start_position < entity2.end_position and
                      entity2.start_position < entity1.end_position)
        
        # Text similarity
        text_similar = entity1.text.lower() in entity2.text.lower() or entity2.text.lower() in entity1.text.lower()
        
        return pos_overlap or text_similar
    
    def _merge_entity_group(self, group: List[TemporalEntity]) -> TemporalEntity:
        """Merge a group of similar temporal entities"""
        
        if len(group) == 1:
            return group[0]
        
        # Use highest confidence entity as base
        base_entity = max(group, key=lambda x: x.confidence)
        
        # Combine extraction methods
        methods = list(set(e.extraction_method for e in group))
        combined_method = "+".join(methods)
        
        # Average confidence
        avg_confidence = sum(e.confidence for e in group) / len(group)
        
        # Use the most specific normalized value
        best_normalized = None
        for entity in group:
            if entity.normalized_value:
                best_normalized = entity.normalized_value
                break
        
        merged_entity = TemporalEntity(
            text=base_entity.text,
            temporal_type=base_entity.temporal_type,
            start_position=min(e.start_position for e in group),
            end_position=max(e.end_position for e in group),
            normalized_value=best_normalized or base_entity.normalized_value,
            confidence=min(avg_confidence * 1.1, 1.0),
            extraction_method=combined_method,
            metadata={
                "merged_from": len(group),
                "original_methods": methods,
                "original_confidences": [e.confidence for e in group]
            },
            parsed_datetime=base_entity.parsed_datetime,
            duration_seconds=base_entity.duration_seconds,
            context=base_entity.context
        )
        
        return merged_entity
    
    async def _merge_temporal_relationships(
        self,
        relationships: List[TemporalRelationship]
    ) -> List[TemporalRelationship]:
        """Merge duplicate temporal relationships"""
        
        # Group by entity pair and relation type
        relationship_groups = defaultdict(list)
        
        for rel in relationships:
            key = (rel.source_entity, rel.target_entity, rel.relation_type)
            relationship_groups[key].append(rel)
        
        merged = []
        for group in relationship_groups.values():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Merge group
                base_rel = max(group, key=lambda x: x.confidence)
                avg_confidence = sum(r.confidence for r in group) / len(group)
                
                merged_rel = TemporalRelationship(
                    source_entity=base_rel.source_entity,
                    target_entity=base_rel.target_entity,
                    relation_type=base_rel.relation_type,
                    confidence=min(avg_confidence * 1.1, 1.0),
                    evidence_text=base_rel.evidence_text,
                    extraction_method="+".join(set(r.extraction_method for r in group)),
                    metadata={
                        "merged_from": len(group),
                        "original_confidences": [r.confidence for r in group]
                    }
                )
                merged.append(merged_rel)
        
        return merged
    
    def _filter_temporal_entities(
        self,
        entities: List[TemporalEntity],
        temporal_types: Optional[List[TemporalType]]
    ) -> List[TemporalEntity]:
        """Filter temporal entities by confidence and type"""
        
        filtered = []
        
        for entity in entities:
            # Filter by confidence
            if entity.confidence < self.min_confidence:
                continue
            
            # Filter by type
            if temporal_types and entity.temporal_type not in temporal_types:
                continue
            
            filtered.append(entity)
        
        return filtered
    
    def _identify_time_periods(self, entities: List[TemporalEntity]) -> Dict[str, List[str]]:
        """Identify different time periods mentioned in entities"""
        
        periods = {
            "historical": [],
            "recent": [],
            "current": [],
            "future": []
        }
        
        current_year = datetime.now().year
        
        for entity in entities:
            if entity.parsed_datetime:
                year = entity.parsed_datetime.year
                
                if year < current_year - 10:
                    periods["historical"].append(entity.text)
                elif year < current_year:
                    periods["recent"].append(entity.text)
                elif year == current_year:
                    periods["current"].append(entity.text)
                else:
                    periods["future"].append(entity.text)
            else:
                # Classify based on text content
                text_lower = entity.text.lower()
                if any(word in text_lower for word in ["historical", "ancient", "past", "ago"]):
                    periods["historical"].append(entity.text)
                elif any(word in text_lower for word in ["recent", "lately", "yesterday"]):
                    periods["recent"].append(entity.text)
                elif any(word in text_lower for word in ["today", "now", "current"]):
                    periods["current"].append(entity.text)
                elif any(word in text_lower for word in ["future", "tomorrow", "will", "next"]):
                    periods["future"].append(entity.text)
        
        return periods
    
    def _determine_temporal_focus(self, entities: List[TemporalEntity]) -> str:
        """Determine the main temporal focus of the text"""
        
        type_counts = Counter(entity.temporal_type for entity in entities)
        
        if not type_counts:
            return "none"
        
        most_common_type = type_counts.most_common(1)[0][0]
        
        focus_mapping = {
            TemporalType.ABSOLUTE_DATE: "historical",
            TemporalType.RELATIVE_TIME: "narrative",
            TemporalType.DURATION: "process-oriented",
            TemporalType.FREQUENCY: "cyclical", 
            TemporalType.EVENT_TIME: "event-driven",
            TemporalType.FUTURE_PROJECTION: "predictive"
        }
        
        return focus_mapping.get(most_common_type, "mixed")
    
    def _check_chronological_order(self, entities: List[TemporalEntity]) -> bool:
        """Check if temporal entities appear in chronological order"""
        
        dated_entities = [e for e in entities if e.parsed_datetime]
        
        if len(dated_entities) < 2:
            return True
        
        # Sort by position in text
        text_order = sorted(dated_entities, key=lambda x: x.start_position)
        
        # Sort by datetime
        chrono_order = sorted(dated_entities, key=lambda x: x.parsed_datetime)
        
        return text_order == chrono_order
    
    def _calculate_temporal_coherence(self, entities: List[TemporalEntity]) -> float:
        """Calculate temporal coherence score"""
        
        if len(entities) < 2:
            return 1.0
        
        coherence_factors = []
        
        # Factor 1: Chronological order
        chrono_order = self._check_chronological_order(entities)
        coherence_factors.append(1.0 if chrono_order else 0.5)
        
        # Factor 2: Consistent temporal focus
        type_counts = Counter(entity.temporal_type for entity in entities)
        max_type_ratio = max(type_counts.values()) / len(entities)
        coherence_factors.append(max_type_ratio)
        
        # Factor 3: Temporal density consistency
        positions = [e.start_position for e in entities]
        gaps = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
        gap_variance = np.var(gaps) if len(gaps) > 1 else 0
        gap_consistency = 1.0 / (1.0 + gap_variance / 1000)  # Normalize variance
        coherence_factors.append(gap_consistency)
        
        return sum(coherence_factors) / len(coherence_factors)
    
    def _entity_to_dict(self, entity: TemporalEntity) -> Dict[str, Any]:
        """Convert temporal entity to dictionary"""
        
        return {
            "text": entity.text,
            "temporal_type": entity.temporal_type.value,
            "start_position": entity.start_position,
            "end_position": entity.end_position,
            "normalized_value": entity.normalized_value,
            "confidence": entity.confidence,
            "extraction_method": entity.extraction_method,
            "metadata": entity.metadata,
            "parsed_datetime": entity.parsed_datetime.isoformat() if entity.parsed_datetime else None,
            "duration_seconds": entity.duration_seconds,
            "context": entity.context
        }
    
    def _relationship_to_dict(self, relationship: TemporalRelationship) -> Dict[str, Any]:
        """Convert temporal relationship to dictionary"""
        
        return {
            "source_entity": relationship.source_entity,
            "target_entity": relationship.target_entity,
            "relation_type": relationship.relation_type.value,
            "confidence": relationship.confidence,
            "evidence_text": relationship.evidence_text,
            "extraction_method": relationship.extraction_method,
            "metadata": relationship.metadata
        }
    
    def _load_temporal_patterns(self) -> Dict[TemporalType, List[Dict[str, Any]]]:
        """Load regex patterns for temporal extraction"""
        
        return {
            TemporalType.ABSOLUTE_DATE: [
                {
                    "name": "iso_date",
                    "pattern": r'\b\d{4}-\d{2}-\d{2}\b',
                    "confidence": 0.95
                },
                {
                    "name": "written_date",
                    "pattern": r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
                    "confidence": 0.9
                },
                {
                    "name": "numeric_date",
                    "pattern": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
                    "confidence": 0.8
                }
            ],
            TemporalType.EVENT_TIME: [
                {
                    "name": "time_format",
                    "pattern": r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b',
                    "confidence": 0.9
                }
            ],
            TemporalType.DURATION: [
                {
                    "name": "duration_pattern",
                    "pattern": r'\b\d+(?:\.\d+)?\s*(?:second|minute|hour|day|week|month|year)s?\b',
                    "confidence": 0.8
                }
            ],
            TemporalType.FREQUENCY: [
                {
                    "name": "frequency_pattern",
                    "pattern": r'\b(?:daily|weekly|monthly|yearly|annually|every\s+\w+)\b',
                    "confidence": 0.8
                }
            ]
        }
    
    def _load_relative_time_patterns(self) -> List[Dict[str, Any]]:
        """Load patterns for relative time expressions"""
        
        return [
            {
                "name": "relative_days",
                "pattern": r'\b(?:yesterday|today|tomorrow)\b',
                "confidence": 0.95
            },
            {
                "name": "relative_periods",
                "pattern": r'\b(?:last|next)\s+(?:week|month|year)\b',
                "confidence": 0.9
            },
            {
                "name": "time_ago",
                "pattern": r'\b\d+\s*(?:day|week|month|year)s?\s+ago\b',
                "confidence": 0.9
            },
            {
                "name": "time_from_now",
                "pattern": r'\bin\s+\d+\s*(?:day|week|month|year)s?\b',
                "confidence": 0.9
            }
        ]
    
    def _load_temporal_signals(self) -> Dict[str, TemporalRelation]:
        """Load temporal signal words and their corresponding relations"""
        
        return {
            "before": TemporalRelation.BEFORE,
            "after": TemporalRelation.AFTER,
            "during": TemporalRelation.DURING,
            "while": TemporalRelation.DURING,
            "simultaneously": TemporalRelation.SIMULTANEOUS,
            "at the same time": TemporalRelation.SIMULTANEOUS,
            "then": TemporalRelation.AFTER,
            "next": TemporalRelation.AFTER,
            "previously": TemporalRelation.BEFORE,
            "earlier": TemporalRelation.BEFORE,
            "later": TemporalRelation.AFTER,
            "following": TemporalRelation.AFTER,
            "preceding": TemporalRelation.BEFORE,
            "until": TemporalRelation.ENDS,
            "since": TemporalRelation.STARTS
        }