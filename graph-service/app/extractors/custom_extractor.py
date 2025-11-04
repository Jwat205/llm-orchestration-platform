"""
Custom Entity and Relationship Extractor
Provides flexible, configurable extraction capabilities for domain-specific needs.
"""
import asyncio
import re
from typing import List, Dict, Any, Optional, Callable, Pattern
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

class ExtractionMethod(Enum):
    REGEX = "regex"
    DICTIONARY = "dictionary"
    RULE_BASED = "rule_based"
    PATTERN_MATCHING = "pattern_matching"
    CUSTOM_FUNCTION = "custom_function"

@dataclass
class ExtractionRule:
    name: str
    method: ExtractionMethod
    pattern: str
    entity_type: str
    confidence: float = 0.8
    flags: int = re.IGNORECASE
    group_mapping: Dict[str, str] = field(default_factory=dict)
    validation_function: Optional[Callable] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RelationshipRule:
    name: str
    source_pattern: str
    target_pattern: str
    relation_type: str
    context_pattern: Optional[str] = None
    confidence: float = 0.7
    max_distance: int = 100
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass 
class CustomEntity:
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    rule_name: str
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CustomRelationship:
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    context: str
    rule_name: str
    attributes: Dict[str, Any] = field(default_factory=dict)

class CustomExtractor:
    """Flexible, rule-based extractor for custom entity and relationship extraction"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.entity_rules: List[ExtractionRule] = []
        self.relationship_rules: List[RelationshipRule] = []
        self.dictionaries: Dict[str, set] = {}
        self.custom_functions: Dict[str, Callable] = {}
        
        # Configuration
        self.case_sensitive = self.config.get("case_sensitive", False)
        self.overlap_resolution = self.config.get("overlap_resolution", "longest")  # longest, highest_confidence, first
        self.min_confidence = self.config.get("min_confidence", 0.5)
        
        # Load configuration files if specified
        if "rules_file" in self.config:
            asyncio.create_task(self.load_rules_from_file(self.config["rules_file"]))
        
        if "dictionaries_file" in self.config:
            asyncio.create_task(self.load_dictionaries_from_file(self.config["dictionaries_file"]))
    
    async def initialize(self):
        """Initialize the custom extractor"""
        try:
            logger.info("Initializing custom extractor...")
            
            # Load default rules if none specified
            if not self.entity_rules:
                await self._load_default_rules()
            
            # Compile regex patterns for efficiency
            await self._compile_patterns()
            
            logger.info(f"Custom extractor initialized with {len(self.entity_rules)} entity rules and {len(self.relationship_rules)} relationship rules")
            
        except Exception as e:
            logger.error(f"Error initializing custom extractor: {e}")
            raise
    
    async def extract(self, text: str, entity_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract entities and relationships from text"""
        try:
            results = {
                "entities": await self.extract_entities(text, entity_types),
                "relationships": []
            }
            
            # Extract relationships using found entities
            results["relationships"] = await self.extract_relationships(text, results["entities"])
            
            return results
            
        except Exception as e:
            logger.error(f"Error in custom extraction: {e}")
            return {"entities": [], "relationships": []}
    
    async def extract_entities(self, text: str, entity_types: Optional[List[str]] = None) -> List[CustomEntity]:
        """Extract entities using custom rules"""
        entities = []
        
        try:
            # Apply each entity rule
            for rule in self.entity_rules:
                if entity_types and rule.entity_type not in entity_types:
                    continue
                
                rule_entities = await self._apply_entity_rule(text, rule)
                entities.extend(rule_entities)
            
            # Resolve overlapping entities
            entities = await self._resolve_overlaps(entities)
            
            # Filter by confidence
            entities = [e for e in entities if e.confidence >= self.min_confidence]
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    async def extract_relationships(self, text: str, entities: Optional[List[CustomEntity]] = None) -> List[CustomRelationship]:
        """Extract relationships using custom rules"""
        if not entities:
            entities = await self.extract_entities(text)
        
        relationships = []
        
        try:
            # Apply each relationship rule
            for rule in self.relationship_rules:
                rule_relationships = await self._apply_relationship_rule(text, entities, rule)
                relationships.extend(rule_relationships)
            
            return relationships
            
        except Exception as e:
            logger.error(f"Error extracting relationships: {e}")
            return []
    
    async def _apply_entity_rule(self, text: str, rule: ExtractionRule) -> List[CustomEntity]:
        """Apply a single entity extraction rule"""
        entities = []
        
        try:
            if rule.method == ExtractionMethod.REGEX:
                entities = await self._extract_with_regex(text, rule)
            elif rule.method == ExtractionMethod.DICTIONARY:
                entities = await self._extract_with_dictionary(text, rule)
            elif rule.method == ExtractionMethod.RULE_BASED:
                entities = await self._extract_with_rules(text, rule)
            elif rule.method == ExtractionMethod.PATTERN_MATCHING:
                entities = await self._extract_with_patterns(text, rule)
            elif rule.method == ExtractionMethod.CUSTOM_FUNCTION:
                entities = await self._extract_with_custom_function(text, rule)
            
            return entities
            
        except Exception as e:
            logger.error(f"Error applying rule {rule.name}: {e}")
            return []
    
    async def _extract_with_regex(self, text: str, rule: ExtractionRule) -> List[CustomEntity]:
        """Extract entities using regex patterns"""
        entities = []
        
        try:
            pattern = re.compile(rule.pattern, rule.flags)
            
            for match in pattern.finditer(text):
                entity_text = match.group(0)
                
                # Apply group mapping if specified
                if rule.group_mapping:
                    entity_attributes = {}
                    for group_name, attr_name in rule.group_mapping.items():
                        try:
                            entity_attributes[attr_name] = match.group(group_name)
                        except IndexError:
                            pass
                else:
                    entity_attributes = rule.attributes.copy()
                
                # Validate if validation function exists
                if rule.validation_function and not rule.validation_function(entity_text):
                    continue
                
                entity = CustomEntity(
                    text=entity_text,
                    entity_type=rule.entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=rule.confidence,
                    rule_name=rule.name,
                    attributes=entity_attributes
                )
                entities.append(entity)
        
        except Exception as e:
            logger.error(f"Error in regex extraction: {e}")
        
        return entities
    
    async def _extract_with_dictionary(self, text: str, rule: ExtractionRule) -> List[CustomEntity]:
        """Extract entities using dictionary lookup"""
        entities = []
        
        try:
            # Get dictionary for this rule
            dictionary = self.dictionaries.get(rule.pattern, set())
            
            if not dictionary:
                return entities
            
            # Case handling
            text_to_search = text if self.case_sensitive else text.lower()
            dictionary_items = dictionary if self.case_sensitive else {item.lower() for item in dictionary}
            
            # Find dictionary matches
            for item in dictionary_items:
                start = 0
                while True:
                    pos = text_to_search.find(item, start)
                    if pos == -1:
                        break
                    
                    # Check word boundaries
                    if self._is_word_boundary(text_to_search, pos, pos + len(item)):
                        original_text = text[pos:pos + len(item)]
                        
                        entity = CustomEntity(
                            text=original_text,
                            entity_type=rule.entity_type,
                            start=pos,
                            end=pos + len(item),
                            confidence=rule.confidence,
                            rule_name=rule.name,
                            attributes=rule.attributes.copy()
                        )
                        entities.append(entity)
                    
                    start = pos + 1
        
        except Exception as e:
            logger.error(f"Error in dictionary extraction: {e}")
        
        return entities
    
    async def _extract_with_rules(self, text: str, rule: ExtractionRule) -> List[CustomEntity]:
        """Extract entities using rule-based logic"""
        entities = []
        
        # This is a placeholder for complex rule-based logic
        # In practice, this would involve parsing the rule.pattern as a set of logical conditions
        
        try:
            # Example: Simple rule parsing
            if "AND" in rule.pattern:
                conditions = rule.pattern.split(" AND ")
                # Apply AND logic
            elif "OR" in rule.pattern:
                conditions = rule.pattern.split(" OR ")
                # Apply OR logic
            
            # For now, fall back to regex
            return await self._extract_with_regex(text, rule)
        
        except Exception as e:
            logger.error(f"Error in rule-based extraction: {e}")
        
        return entities
    
    async def _extract_with_patterns(self, text: str, rule: ExtractionRule) -> List[CustomEntity]:
        """Extract entities using pattern matching"""
        entities = []
        
        try:
            # Pattern matching with wildcards and placeholders
            pattern = rule.pattern
            
            # Convert pattern to regex
            regex_pattern = pattern.replace("*", ".*").replace("?", ".?")
            
            # Apply as regex
            temp_rule = ExtractionRule(
                name=rule.name,
                method=ExtractionMethod.REGEX,
                pattern=regex_pattern,
                entity_type=rule.entity_type,
                confidence=rule.confidence,
                attributes=rule.attributes
            )
            
            return await self._extract_with_regex(text, temp_rule)
        
        except Exception as e:
            logger.error(f"Error in pattern matching: {e}")
        
        return entities
    
    async def _extract_with_custom_function(self, text: str, rule: ExtractionRule) -> List[CustomEntity]:
        """Extract entities using a custom function"""
        entities = []
        
        try:
            # Get custom function
            func = self.custom_functions.get(rule.pattern)
            if not func:
                logger.warning(f"Custom function {rule.pattern} not found")
                return entities
            
            # Execute custom function
            if asyncio.iscoroutinefunction(func):
                results = await func(text, rule)
            else:
                results = func(text, rule)
            
            # Convert results to CustomEntity objects
            for result in results:
                if isinstance(result, dict):
                    entity = CustomEntity(
                        text=result.get("text", ""),
                        entity_type=result.get("entity_type", rule.entity_type),
                        start=result.get("start", 0),
                        end=result.get("end", 0),
                        confidence=result.get("confidence", rule.confidence),
                        rule_name=rule.name,
                        attributes=result.get("attributes", rule.attributes.copy())
                    )
                    entities.append(entity)
        
        except Exception as e:
            logger.error(f"Error in custom function extraction: {e}")
        
        return entities
    
    async def _apply_relationship_rule(self, text: str, entities: List[CustomEntity], rule: RelationshipRule) -> List[CustomRelationship]:
        """Apply a relationship extraction rule"""
        relationships = []
        
        try:
            # Find entities matching source pattern
            source_entities = [e for e in entities if re.search(rule.source_pattern, e.text, re.IGNORECASE)]
            # Find entities matching target pattern  
            target_entities = [e for e in entities if re.search(rule.target_pattern, e.text, re.IGNORECASE)]
            
            # Find relationships between matching entities
            for source in source_entities:
                for target in target_entities:
                    if source == target:
                        continue
                    
                    # Check distance constraint
                    distance = abs(source.start - target.start)
                    if distance > rule.max_distance:
                        continue
                    
                    # Check context pattern if specified
                    if rule.context_pattern:
                        context_start = min(source.start, target.start)
                        context_end = max(source.end, target.end)
                        context = text[context_start:context_end]
                        
                        if not re.search(rule.context_pattern, context, re.IGNORECASE):
                            continue
                    
                    # Create relationship
                    relationship = CustomRelationship(
                        source_entity=source.text,
                        target_entity=target.text,
                        relation_type=rule.relation_type,
                        confidence=rule.confidence,
                        context=text[min(source.start, target.start):max(source.end, target.end)],
                        rule_name=rule.name,
                        attributes=rule.attributes.copy()
                    )
                    relationships.append(relationship)
        
        except Exception as e:
            logger.error(f"Error applying relationship rule {rule.name}: {e}")
        
        return relationships
    
    async def _resolve_overlaps(self, entities: List[CustomEntity]) -> List[CustomEntity]:
        """Resolve overlapping entity extractions"""
        if not entities:
            return entities
        
        # Sort by start position
        entities.sort(key=lambda x: (x.start, -x.end))
        
        resolved = []
        
        for entity in entities:
            # Check for overlaps with already resolved entities
            overlaps = [e for e in resolved if self._entities_overlap(entity, e)]
            
            if not overlaps:
                resolved.append(entity)
            else:
                # Apply overlap resolution strategy
                if self.overlap_resolution == "longest":
                    # Keep longest entity
                    longest = max([entity] + overlaps, key=lambda x: x.end - x.start)
                    if longest == entity:
                        # Remove overlapping entities and add current
                        resolved = [e for e in resolved if e not in overlaps]
                        resolved.append(entity)
                
                elif self.overlap_resolution == "highest_confidence":
                    # Keep highest confidence entity
                    highest_conf = max([entity] + overlaps, key=lambda x: x.confidence)
                    if highest_conf == entity:
                        resolved = [e for e in resolved if e not in overlaps]
                        resolved.append(entity)
                
                elif self.overlap_resolution == "first":
                    # Keep first entity (already in resolved)
                    pass
        
        return resolved
    
    def _entities_overlap(self, e1: CustomEntity, e2: CustomEntity) -> bool:
        """Check if two entities overlap"""
        return not (e1.end <= e2.start or e2.end <= e1.start)
    
    def _is_word_boundary(self, text: str, start: int, end: int) -> bool:
        """Check if position represents word boundaries"""
        if start > 0 and text[start - 1].isalnum():
            return False
        if end < len(text) and text[end].isalnum():
            return False
        return True
    
    async def _load_default_rules(self):
        """Load default extraction rules"""
        # Email addresses
        self.add_entity_rule(ExtractionRule(
            name="email",
            method=ExtractionMethod.REGEX,
            pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            entity_type="EMAIL",
            confidence=0.9
        ))
        
        # Phone numbers
        self.add_entity_rule(ExtractionRule(
            name="phone",
            method=ExtractionMethod.REGEX,
            pattern=r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            entity_type="PHONE",
            confidence=0.8
        ))
        
        # URLs
        self.add_entity_rule(ExtractionRule(
            name="url",
            method=ExtractionMethod.REGEX,
            pattern=r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?',
            entity_type="URL",
            confidence=0.9
        ))
        
        # Simple company relationships
        self.add_relationship_rule(RelationshipRule(
            name="works_at",
            source_pattern=r'[A-Z][a-z]+ [A-Z][a-z]+',  # Person names
            target_pattern=r'[A-Z][A-Za-z]+ (?:Inc|Corp|LLC|Ltd)',  # Company names
            relation_type="WORKS_AT",
            context_pattern=r'works? (?:at|for)',
            confidence=0.7
        ))
    
    async def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        for rule in self.entity_rules:
            if rule.method == ExtractionMethod.REGEX:
                try:
                    # Store compiled pattern in attributes for reuse
                    rule.attributes["compiled_pattern"] = re.compile(rule.pattern, rule.flags)
                except re.error as e:
                    logger.error(f"Invalid regex pattern in rule {rule.name}: {e}")
    
    def add_entity_rule(self, rule: ExtractionRule):
        """Add a custom entity extraction rule"""
        self.entity_rules.append(rule)
    
    def add_relationship_rule(self, rule: RelationshipRule):
        """Add a custom relationship extraction rule"""
        self.relationship_rules.append(rule)
    
    def add_dictionary(self, name: str, items: List[str]):
        """Add a dictionary for entity extraction"""
        self.dictionaries[name] = set(items)
    
    def add_custom_function(self, name: str, func: Callable):
        """Add a custom extraction function"""
        self.custom_functions[name] = func
    
    async def load_rules_from_file(self, file_path: str):
        """Load extraction rules from a configuration file"""
        try:
            path = Path(file_path)
            
            if path.suffix.lower() == '.json':
                with open(path, 'r') as f:
                    data = json.load(f)
            elif path.suffix.lower() in ['.yml', '.yaml']:
                with open(path, 'r') as f:
                    data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
            
            # Load entity rules
            for rule_data in data.get("entity_rules", []):
                rule = ExtractionRule(
                    name=rule_data["name"],
                    method=ExtractionMethod(rule_data["method"]),
                    pattern=rule_data["pattern"],
                    entity_type=rule_data["entity_type"],
                    confidence=rule_data.get("confidence", 0.8),
                    flags=rule_data.get("flags", re.IGNORECASE),
                    attributes=rule_data.get("attributes", {})
                )
                self.add_entity_rule(rule)
            
            # Load relationship rules
            for rule_data in data.get("relationship_rules", []):
                rule = RelationshipRule(
                    name=rule_data["name"],
                    source_pattern=rule_data["source_pattern"],
                    target_pattern=rule_data["target_pattern"],
                    relation_type=rule_data["relation_type"],
                    context_pattern=rule_data.get("context_pattern"),
                    confidence=rule_data.get("confidence", 0.7),
                    max_distance=rule_data.get("max_distance", 100),
                    attributes=rule_data.get("attributes", {})
                )
                self.add_relationship_rule(rule)
            
            logger.info(f"Loaded rules from {file_path}")
            
        except Exception as e:
            logger.error(f"Error loading rules from file: {e}")
    
    async def load_dictionaries_from_file(self, file_path: str):
        """Load dictionaries from a file"""
        try:
            path = Path(file_path)
            
            if path.suffix.lower() == '.json':
                with open(path, 'r') as f:
                    data = json.load(f)
            elif path.suffix.lower() in ['.yml', '.yaml']:
                with open(path, 'r') as f:
                    data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
            
            for name, items in data.items():
                self.add_dictionary(name, items)
            
            logger.info(f"Loaded dictionaries from {file_path}")
            
        except Exception as e:
            logger.error(f"Error loading dictionaries from file: {e}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get extractor statistics"""
        return {
            "entity_rules": len(self.entity_rules),
            "relationship_rules": len(self.relationship_rules),
            "dictionaries": len(self.dictionaries),
            "custom_functions": len(self.custom_functions),
            "config": self.config
        }
    
    async def shutdown(self):
        """Cleanup resources"""
        self.entity_rules.clear()
        self.relationship_rules.clear()
        self.dictionaries.clear()
        self.custom_functions.clear()
        logger.info("Custom extractor shutdown completed")