"""
Knowledge Graph Inference Engine
Handles logical reasoning, rule application, and knowledge inference
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import networkx as nx
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class InferenceType(Enum):
    """Types of inference operations"""
    TRANSITIVE = "transitive"
    SYMMETRIC = "symmetric"
    INVERSE = "inverse"
    SUBCLASS = "subclass"
    EQUIVALENCE = "equivalence"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    CONTRADICTION = "contradiction"


class ConfidenceLevel(Enum):
    """Confidence levels for inferences"""
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5
    UNCERTAIN = 0.3


@dataclass
class InferenceRule:
    """Represents a logical inference rule"""
    id: str
    name: str
    rule_type: InferenceType
    pattern: str  # Pattern to match
    conclusion: str  # What to infer
    confidence: float = 0.8
    conditions: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    enabled: bool = True
    priority: int = 1
    description: str = ""


@dataclass
class InferenceResult:
    """Result of an inference operation"""
    rule_id: str
    source_entities: List[str]
    inferred_relationship: Tuple[str, str, str]  # (subject, predicate, object)
    confidence: float
    reasoning_path: List[str]
    timestamp: datetime
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)


class InferenceEngine:
    """
    Advanced inference engine for knowledge graphs
    Handles rule-based reasoning, pattern matching, and logical deduction
    """
    
    def __init__(self, 
                 graph_engine,
                 ontology_manager,
                 max_inference_depth: int = 5,
                 confidence_threshold: float = 0.5):
        self.graph_engine = graph_engine
        self.ontology_manager = ontology_manager
        self.max_depth = max_inference_depth
        self.confidence_threshold = confidence_threshold
        
        # Rule storage
        self.rules: Dict[str, InferenceRule] = {}
        self.rule_index: Dict[InferenceType, List[str]] = {}
        
        # Inference cache
        self.inference_cache: Dict[str, List[InferenceResult]] = {}
        self.cache_ttl = timedelta(hours=1)
        
        # Performance tracking
        self.inference_stats = {
            'total_inferences': 0,
            'successful_inferences': 0,
            'cache_hits': 0,
            'rule_applications': {},
            'avg_confidence': 0.0
        }
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """Initialize common inference rules with fixed regex patterns"""
        
        # Transitive rules - Fixed regex patterns with unique group names
        self.add_rule(InferenceRule(
            id="transitive_subclass",
            name="Transitive Subclass",
            rule_type=InferenceType.TRANSITIVE,
            pattern=r"(?P<entity_a>\w+) subClassOf (?P<entity_b>\w+), (?P<entity_b_repeat>\w+) subClassOf (?P<entity_c>\w+)",
            conclusion=r"(?P<entity_a>\w+) subClassOf (?P<entity_c>\w+)",
            confidence=0.9,
            description="If A is subclass of B and B is subclass of C, then A is subclass of C"
        ))
        
        self.add_rule(InferenceRule(
            id="transitive_partof",
            name="Transitive Part-Of",
            rule_type=InferenceType.TRANSITIVE,
            pattern=r"(?P<part_a>\w+) partOf (?P<part_b>\w+), (?P<part_b_repeat>\w+) partOf (?P<part_c>\w+)",
            conclusion=r"(?P<part_a>\w+) partOf (?P<part_c>\w+)",
            confidence=0.85,
            description="If A is part of B and B is part of C, then A is part of C"
        ))
        
        # Symmetric rules
        self.add_rule(InferenceRule(
            id="symmetric_similar",
            name="Symmetric Similarity",
            rule_type=InferenceType.SYMMETRIC,
            pattern=r"(?P<entity_x>\w+) similarTo (?P<entity_y>\w+)",
            conclusion=r"(?P<entity_y>\w+) similarTo (?P<entity_x>\w+)",
            confidence=1.0,
            description="If A is similar to B, then B is similar to A"
        ))
        
        # Inverse rules
        self.add_rule(InferenceRule(
            id="inverse_parent_child",
            name="Inverse Parent-Child",
            rule_type=InferenceType.INVERSE,
            pattern=r"(?P<parent>\w+) parentOf (?P<child>\w+)",
            conclusion=r"(?P<child>\w+) childOf (?P<parent>\w+)",
            confidence=1.0,
            description="If A is parent of B, then B is child of A"
        ))
        
        # Temporal inference - Fixed regex pattern
        self.add_rule(InferenceRule(
            id="temporal_sequence",
            name="Temporal Sequence",
            rule_type=InferenceType.TEMPORAL,
            pattern=r"(?P<event_a>\w+) before (?P<event_b>\w+), (?P<event_b_repeat>\w+) before (?P<event_c>\w+)",
            conclusion=r"(?P<event_a>\w+) before (?P<event_c>\w+)",
            confidence=0.8,
            description="If A happens before B and B happens before C, then A happens before C"
        ))
        
        # Causal inference - Fixed regex pattern
        self.add_rule(InferenceRule(
            id="causal_chain",
            name="Causal Chain",
            rule_type=InferenceType.CAUSAL,
            pattern=r"(?P<cause_a>\w+) causes (?P<cause_b>\w+), (?P<cause_b_repeat>\w+) causes (?P<cause_c>\w+)",
            conclusion=r"(?P<cause_a>\w+) influences (?P<cause_c>\w+)",
            confidence=0.7,
            description="If A causes B and B causes C, then A influences C"
        ))
    
    def add_rule(self, rule: InferenceRule) -> bool:
        """Add a new inference rule with improved validation"""
        try:
            # Validate rule pattern - compile to check for errors
            compiled_pattern = re.compile(rule.pattern)
            
            # Check for duplicate group names in pattern
            group_names = compiled_pattern.groupindex.keys()
            if len(group_names) != len(set(group_names)):
                logger.error(f"Duplicate group names in pattern: {rule.pattern}")
                return False
            
            self.rules[rule.id] = rule
            
            # Index by type
            if rule.rule_type not in self.rule_index:
                self.rule_index[rule.rule_type] = []
            self.rule_index[rule.rule_type].append(rule.id)
            
            logger.info(f"Added inference rule: {rule.name}")
            return True
            
        except re.error as e:
            logger.error(f"Invalid rule pattern: {rule.pattern}, error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding rule {rule.id}: {e}")
            return False
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove an inference rule"""
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            del self.rules[rule_id]
            
            # Remove from index
            if rule.rule_type in self.rule_index:
                if rule_id in self.rule_index[rule.rule_type]:
                    self.rule_index[rule.rule_type].remove(rule_id)
            
            # Clear related cache entries
            self._clear_cache_for_rule(rule_id)
            
            logger.info(f"Removed inference rule: {rule_id}")
            return True
        
        return False
    
    async def infer_relationships(self, 
                                entity_id: str = None,
                                relationship_type: str = None,
                                max_results: int = 100) -> List[InferenceResult]:
        """
        Perform inference to discover new relationships
        """
        cache_key = f"{entity_id}:{relationship_type}:{max_results}"
        
        # Check cache
        if cache_key in self.inference_cache:
            cached_results = self.inference_cache[cache_key]
            if cached_results and self._is_cache_valid(cached_results[0].timestamp):
                self.inference_stats['cache_hits'] += 1
                return cached_results
        
        results = []
        
        try:
            # Get relevant entities and relationships
            if entity_id:
                entities = [entity_id]
                if hasattr(self.graph_engine, 'get_entity_relationships'):
                    relationships = await self.graph_engine.get_entity_relationships(entity_id)
                else:
                    relationships = []
            else:
                if hasattr(self.graph_engine, 'get_all_entities'):
                    entities = await self.graph_engine.get_all_entities()
                else:
                    entities = []
                if hasattr(self.graph_engine, 'get_all_relationships'):
                    relationships = await self.graph_engine.get_all_relationships()
                else:
                    relationships = []
            
            # Apply inference rules
            for rule_type in InferenceType:
                if rule_type in self.rule_index:
                    rule_results = await self._apply_rules_by_type(
                        rule_type, entities, relationships, max_results
                    )
                    results.extend(rule_results)
            
            # Filter by confidence threshold
            results = [r for r in results if r.confidence >= self.confidence_threshold]
            
            # Sort by confidence
            results.sort(key=lambda x: x.confidence, reverse=True)
            
            # Limit results
            results = results[:max_results]
            
            # Cache results
            self.inference_cache[cache_key] = results
            
            # Update stats
            self.inference_stats['total_inferences'] += len(results)
            self.inference_stats['successful_inferences'] += len([r for r in results if r.confidence > 0.7])
            
            if results:
                avg_conf = sum(r.confidence for r in results) / len(results)
                self.inference_stats['avg_confidence'] = avg_conf
            
            logger.info(f"Generated {len(results)} inferences for {cache_key}")
            
        except Exception as e:
            logger.error(f"Error during inference: {e}")
        
        return results
    
    async def _apply_rules_by_type(self, 
                                 rule_type: InferenceType, 
                                 entities: List[str], 
                                 relationships: List[Dict], 
                                 max_results: int) -> List[InferenceResult]:
        """Apply all rules of a specific type"""
        results = []
        
        if rule_type not in self.rule_index:
            return results
        
        for rule_id in self.rule_index[rule_type]:
            rule = self.rules[rule_id]
            if not rule.enabled:
                continue
            
            try:
                rule_results = await self._apply_single_rule(rule, relationships)
                results.extend(rule_results)
                
                # Track rule usage
                if rule_id not in self.inference_stats['rule_applications']:
                    self.inference_stats['rule_applications'][rule_id] = 0
                self.inference_stats['rule_applications'][rule_id] += len(rule_results)
                
            except Exception as e:
                logger.error(f"Error applying rule {rule_id}: {e}")
        
        return results
    
    async def _apply_single_rule(self, 
                               rule: InferenceRule, 
                               relationships: List[Dict]) -> List[InferenceResult]:
        """Apply a single inference rule to the relationships"""
        results = []
        
        try:
            if rule.rule_type == InferenceType.TRANSITIVE:
                results = await self._apply_transitive_rule(rule, relationships)
            elif rule.rule_type == InferenceType.SYMMETRIC:
                results = await self._apply_symmetric_rule(rule, relationships)
            elif rule.rule_type == InferenceType.INVERSE:
                results = await self._apply_inverse_rule(rule, relationships)
            elif rule.rule_type == InferenceType.TEMPORAL:
                results = await self._apply_temporal_rule(rule, relationships)
            elif rule.rule_type == InferenceType.CAUSAL:
                results = await self._apply_causal_rule(rule, relationships)
            
        except Exception as e:
            logger.error(f"Error in rule application {rule.id}: {e}")
        
        return results
    
    async def _apply_transitive_rule(self, 
                                   rule: InferenceRule, 
                                   relationships: List[Dict]) -> List[InferenceResult]:
        """Apply transitive closure rules"""
        results = []
        
        try:
            # Group relationships by predicate
            rel_groups = {}
            for rel in relationships:
                pred = rel.get('predicate', rel.get('relationship_type', rel.get('type')))
                if pred not in rel_groups:
                    rel_groups[pred] = []
                rel_groups[pred].append(rel)
            
            # Find transitive patterns
            for predicate, rels in rel_groups.items():
                if len(rels) < 2:
                    continue
                
                # Build relationship map
                rel_map = {}
                for rel in rels:
                    subj = rel.get('subject', rel.get('source_id'))
                    obj = rel.get('object', rel.get('target_id'))
                    if subj and obj:
                        if subj not in rel_map:
                            rel_map[subj] = []
                        rel_map[subj].append(obj)
                
                # Find transitive closures
                for entity, targets in rel_map.items():
                    for target in targets:
                        if target in rel_map:
                            for final_target in rel_map[target]:
                                if final_target != entity:  # Avoid self-loops
                                    # Check if this inference already exists
                                    if not await self._relationship_exists(entity, predicate, final_target):
                                        result = InferenceResult(
                                            rule_id=rule.id,
                                            source_entities=[entity, target, final_target],
                                            inferred_relationship=(entity, predicate, final_target),
                                            confidence=rule.confidence,
                                            reasoning_path=[f"{entity} -> {target} -> {final_target}"],
                                            timestamp=datetime.now(),
                                            evidence=[
                                                {"relation": f"{entity} {predicate} {target}"},
                                                {"relation": f"{target} {predicate} {final_target}"}
                                            ]
                                        )
                                        results.append(result)
        except Exception as e:
            logger.error(f"Error in transitive rule application: {e}")
        
        return results
    
    async def _apply_symmetric_rule(self, 
                                  rule: InferenceRule, 
                                  relationships: List[Dict]) -> List[InferenceResult]:
        """Apply symmetric relationship rules"""
        results = []
        
        try:
            for rel in relationships:
                pred = rel.get('predicate', rel.get('relationship_type', rel.get('type')))
                subj = rel.get('subject', rel.get('source_id'))
                obj = rel.get('object', rel.get('target_id'))
                
                if pred and subj and obj:
                    # Check if reverse relationship exists
                    if not await self._relationship_exists(obj, pred, subj):
                        result = InferenceResult(
                            rule_id=rule.id,
                            source_entities=[subj, obj],
                            inferred_relationship=(obj, pred, subj),
                            confidence=rule.confidence,
                            reasoning_path=[f"Symmetric: {subj} {pred} {obj} → {obj} {pred} {subj}"],
                            timestamp=datetime.now(),
                            evidence=[{"relation": f"{subj} {pred} {obj}"}]
                        )
                        results.append(result)
        except Exception as e:
            logger.error(f"Error in symmetric rule application: {e}")
        
        return results
    
    async def _apply_inverse_rule(self, 
                                rule: InferenceRule, 
                                relationships: List[Dict]) -> List[InferenceResult]:
        """Apply inverse relationship rules"""
        results = []
        
        try:
            # Define inverse relationship mappings
            inverse_map = {
                'parentOf': 'childOf',
                'childOf': 'parentOf',
                'contains': 'containedIn',
                'containedIn': 'contains',
                'above': 'below',
                'below': 'above',
                'before': 'after',
                'after': 'before'
            }
            
            for rel in relationships:
                pred = rel.get('predicate', rel.get('relationship_type', rel.get('type')))
                subj = rel.get('subject', rel.get('source_id'))
                obj = rel.get('object', rel.get('target_id'))
                
                if pred and subj and obj and pred in inverse_map:
                    inverse_pred = inverse_map[pred]
                    
                    # Check if inverse relationship exists
                    if not await self._relationship_exists(obj, inverse_pred, subj):
                        result = InferenceResult(
                            rule_id=rule.id,
                            source_entities=[subj, obj],
                            inferred_relationship=(obj, inverse_pred, subj),
                            confidence=rule.confidence,
                            reasoning_path=[f"Inverse: {subj} {pred} {obj} → {obj} {inverse_pred} {subj}"],
                            timestamp=datetime.now(),
                            evidence=[{"relation": f"{subj} {pred} {obj}"}]
                        )
                        results.append(result)
        except Exception as e:
            logger.error(f"Error in inverse rule application: {e}")
        
        return results
    
    async def _apply_temporal_rule(self, 
                                 rule: InferenceRule, 
                                 relationships: List[Dict]) -> List[InferenceResult]:
        """Apply temporal reasoning rules"""
        results = []
        
        try:
            # Find temporal relationships
            temporal_rels = [r for r in relationships 
                            if r.get('predicate', r.get('relationship_type', '')).lower() in ['before', 'after', 'during', 'overlaps']]
            
            # Apply temporal transitivity
            for rel1 in temporal_rels:
                for rel2 in temporal_rels:
                    if rel1 != rel2:
                        pred1 = rel1.get('predicate', rel1.get('relationship_type'))
                        pred2 = rel2.get('predicate', rel2.get('relationship_type'))
                        
                        if (rel1.get('object', rel1.get('target_id')) == rel2.get('subject', rel2.get('source_id')) and 
                            pred1 == 'before' and pred2 == 'before'):
                            
                            # A before B, B before C → A before C
                            entity_a = rel1.get('subject', rel1.get('source_id'))
                            entity_c = rel2.get('object', rel2.get('target_id'))
                            
                            if entity_a and entity_c and not await self._relationship_exists(entity_a, 'before', entity_c):
                                result = InferenceResult(
                                    rule_id=rule.id,
                                    source_entities=[entity_a, rel1.get('object', rel1.get('target_id')), entity_c],
                                    inferred_relationship=(entity_a, 'before', entity_c),
                                    confidence=rule.confidence,
                                    reasoning_path=[
                                        f"{entity_a} before {rel1.get('object', rel1.get('target_id'))}",
                                        f"{rel1.get('object', rel1.get('target_id'))} before {entity_c}",
                                        f"Therefore: {entity_a} before {entity_c}"
                                    ],
                                    timestamp=datetime.now(),
                                    evidence=[
                                        {"relation": f"{entity_a} before {rel1.get('object', rel1.get('target_id'))}"},
                                        {"relation": f"{rel1.get('object', rel1.get('target_id'))} before {entity_c}"}
                                    ]
                                )
                                results.append(result)
        except Exception as e:
            logger.error(f"Error in temporal rule application: {e}")
        
        return results
    
    async def _apply_causal_rule(self, 
                               rule: InferenceRule, 
                               relationships: List[Dict]) -> List[InferenceResult]:
        """Apply causal reasoning rules"""
        results = []
        
        try:
            # Find causal relationships
            causal_rels = [r for r in relationships 
                          if r.get('predicate', r.get('relationship_type', '')).lower() in ['causes', 'leads_to', 'results_in']]
            
            # Apply causal transitivity with reduced confidence
            for rel1 in causal_rels:
                for rel2 in causal_rels:
                    if rel1 != rel2 and rel1.get('object', rel1.get('target_id')) == rel2.get('subject', rel2.get('source_id')):
                        entity_a = rel1.get('subject', rel1.get('source_id'))
                        entity_c = rel2.get('object', rel2.get('target_id'))
                        
                        if entity_a and entity_c and not await self._relationship_exists(entity_a, 'influences', entity_c):
                            result = InferenceResult(
                                rule_id=rule.id,
                                source_entities=[entity_a, rel1.get('object', rel1.get('target_id')), entity_c],
                                inferred_relationship=(entity_a, 'influences', entity_c),
                                confidence=rule.confidence * 0.8,  # Reduced confidence for causal chains
                                reasoning_path=[
                                    f"{entity_a} causes {rel1.get('object', rel1.get('target_id'))}",
                                    f"{rel1.get('object', rel1.get('target_id'))} causes {entity_c}",
                                    f"Therefore: {entity_a} influences {entity_c}"
                                ],
                                timestamp=datetime.now(),
                                evidence=[
                                    {"relation": f"{entity_a} causes {rel1.get('object', rel1.get('target_id'))}"},
                                    {"relation": f"{rel1.get('object', rel1.get('target_id'))} causes {entity_c}"}
                                ]
                            )
                            results.append(result)
        except Exception as e:
            logger.error(f"Error in causal rule application: {e}")
        
        return results
    
    async def _relationship_exists(self, subject: str, predicate: str, obj: str) -> bool:
        """Check if a relationship already exists in the graph"""
        try:
            if hasattr(self.graph_engine, 'query_relationships'):
                existing = await self.graph_engine.query_relationships(
                    source_id=subject,
                    relationship_type=predicate,
                    target_id=obj
                )
                return len(existing) > 0
            return False
        except Exception:
            return False
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cache entry is still valid"""
        return datetime.now() - timestamp < self.cache_ttl
    
    def _clear_cache_for_rule(self, rule_id: str):
        """Clear cache entries affected by rule removal"""
        # Simple approach: clear all cache
        # In production, you'd want more sophisticated cache invalidation
        self.inference_cache.clear()
    
    async def detect_contradictions(self, 
                                  entity_id: str = None) -> List[Dict[str, Any]]:
        """Detect contradictory relationships in the graph"""
        contradictions = []
        
        try:
            # Get relationships to check
            if entity_id and hasattr(self.graph_engine, 'get_entity_relationships'):
                relationships = await self.graph_engine.get_entity_relationships(entity_id)
            elif hasattr(self.graph_engine, 'get_all_relationships'):
                relationships = await self.graph_engine.get_all_relationships()
            else:
                relationships = []
            
            # Define contradiction patterns
            contradiction_patterns = [
                # Spatial contradictions
                ("above", "below"),
                ("left", "right"),
                ("inside", "outside"),
                # Temporal contradictions
                ("before", "after"),
                ("during", "outside_time"),
                # Logical contradictions
                ("is", "is_not"),
                ("has", "lacks"),
                # Hierarchical contradictions
                ("parent", "child"),
                ("ancestor", "descendant")
            ]
            
            # Check for contradictions
            rel_map = {}
            for rel in relationships:
                subj = rel.get('subject', rel.get('source_id'))
                obj = rel.get('object', rel.get('target_id'))
                pred = rel.get('predicate', rel.get('relationship_type', rel.get('type')))
                
                if subj and obj:
                    key = (subj, obj)
                    if key not in rel_map:
                        rel_map[key] = []
                    rel_map[key].append(pred)
            
            for (subj, obj), predicates in rel_map.items():
                for pred1, pred2 in contradiction_patterns:
                    if pred1 in predicates and pred2 in predicates:
                        contradictions.append({
                            'type': 'contradiction',
                            'subject': subj,
                            'object': obj,
                            'conflicting_predicates': [pred1, pred2],
                            'confidence': 0.9,
                            'detected_at': datetime.now().isoformat()
                        })
        
        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
        
        return contradictions
    
    def get_inference_statistics(self) -> Dict[str, Any]:
        """Get inference engine statistics"""
        return {
            **self.inference_stats,
            'total_rules': len(self.rules),
            'rules_by_type': {t.value: len(rules) for t, rules in self.rule_index.items()},
            'cache_size': len(self.inference_cache),
            'active_rules': len([r for r in self.rules.values() if r.enabled])
        }
    
    def export_rules(self, file_path: str) -> bool:
        """Export rules to JSON file"""
        try:
            rules_data = {}
            for rule_id, rule in self.rules.items():
                rules_data[rule_id] = {
                    'name': rule.name,
                    'rule_type': rule.rule_type.value,
                    'pattern': rule.pattern,
                    'conclusion': rule.conclusion,
                    'confidence': rule.confidence,
                    'conditions': rule.conditions,
                    'exceptions': rule.exceptions,
                    'enabled': rule.enabled,
                    'priority': rule.priority,
                    'description': rule.description
                }
            
            with open(file_path, 'w') as f:
                json.dump(rules_data, f, indent=2)
            
            logger.info(f"Exported {len(rules_data)} rules to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting rules: {e}")
            return False
    
    def import_rules(self, file_path: str) -> bool:
        """Import rules from JSON file"""
        try:
            with open(file_path, 'r') as f:
                rules_data = json.load(f)
            
            imported_count = 0
            for rule_id, rule_data in rules_data.items():
                rule = InferenceRule(
                    id=rule_id,
                    name=rule_data['name'],
                    rule_type=InferenceType(rule_data['rule_type']),
                    pattern=rule_data['pattern'],
                    conclusion=rule_data['conclusion'],
                    confidence=rule_data['confidence'],
                    conditions=rule_data.get('conditions', []),
                    exceptions=rule_data.get('exceptions', []),
                    enabled=rule_data.get('enabled', True),
                    priority=rule_data.get('priority', 1),
                    description=rule_data.get('description', '')
                )
                
                if self.add_rule(rule):
                    imported_count += 1
            
            logger.info(f"Imported {imported_count} rules from {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing rules: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
        
        # Clear caches
        self.inference_cache.clear()
        
        logger.info("Inference engine cleaned up")
            