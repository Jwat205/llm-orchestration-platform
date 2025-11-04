"""
Advanced Inference Engine for Knowledge Graph.
Supports semantic reasoning, rule-based inference, and ML-based predictions.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import math
from dataclasses import dataclass

@dataclass
class InferenceRule:
    id: str
    name: str
    premise: Dict[str, Any]
    conclusion: Dict[str, Any]
    confidence: float
    rule_type: str  # 'logical', 'statistical', 'semantic'

@dataclass
class InferredRelationship:
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    evidence: List[Dict[str, Any]]
    reasoning_path: List[str]

class InferenceEngine:
    """Advanced inference engine with multiple reasoning strategies."""
    
    def __init__(self, graph_engine):
        self.logger = logging.getLogger(__name__)
        self.graph_engine = graph_engine
        self.inference_rules = {}
        self.inference_cache = {}
        self.inference_stats = {
            "total_inferences": 0,
            "successful_inferences": 0,
            "rule_based_inferences": 0,
            "semantic_inferences": 0,
            "statistical_inferences": 0
        }
        
        # Initialize default rules
        self._initialize_default_rules()
    
    async def initialize(self):
        """Initialize inference engine"""
        await self._load_inference_rules()
        self.logger.info("Inference engine initialized")
    
    async def shutdown(self):
        """Shutdown inference engine"""
        await self._save_inference_rules()
        self.logger.info("Inference engine shutdown")
    
    def _initialize_default_rules(self):
        """Initialize default inference rules"""
        # Transitivity rules
        self.inference_rules["transitivity_location"] = InferenceRule(
            id="transitivity_location",
            name="Location Transitivity",
            premise={
                "pattern": "(A)-[:LOCATED_IN]->(B), (B)-[:LOCATED_IN]->(C)",
                "constraints": {}
            },
            conclusion={
                "relationship": "(A)-[:LOCATED_IN]->(C)",
                "confidence_modifier": 0.8
            },
            confidence=0.9,
            rule_type="logical"
        )
        
        self.inference_rules["symmetric_similarity"] = InferenceRule(
            id="symmetric_similarity",
            name="Similarity Symmetry",
            premise={
                "pattern": "(A)-[:SIMILAR_TO]->(B)",
                "constraints": {}
            },
            conclusion={
                "relationship": "(B)-[:SIMILAR_TO]->(A)",
                "confidence_modifier": 1.0
            },
            confidence=1.0,
            rule_type="logical"
        )
        
        # Statistical inference rules
        self.inference_rules["co_occurrence"] = InferenceRule(
            id="co_occurrence",
            name="Co-occurrence Based Inference",
            premise={
                "pattern": "(A)-[:*]-(C), (B)-[:*]-(C)",
                "constraints": {"min_shared_connections": 3}
            },
            conclusion={
                "relationship": "(A)-[:RELATED_TO]->(B)",
                "confidence_modifier": 0.6
            },
            confidence=0.7,
            rule_type="statistical"
        )
    
    async def infer(self, entities: List[str], inference_type: str = "all", 
                   confidence_threshold: float = 0.5) -> List[InferredRelationship]:
        """Main inference method"""
        try:
            inferred_relationships = []
            
            if inference_type in ["all", "rule_based"]:
                rule_inferences = await self._rule_based_inference(entities, confidence_threshold)
                inferred_relationships.extend(rule_inferences)
            
            if inference_type in ["all", "semantic"]:
                semantic_inferences = await self._semantic_inference(entities, confidence_threshold)
                inferred_relationships.extend(semantic_inferences)
            
            if inference_type in ["all", "statistical"]:
                statistical_inferences = await self._statistical_inference(entities, confidence_threshold)
                inferred_relationships.extend(statistical_inferences)
            
            # Remove duplicates and sort by confidence
            unique_inferences = self._deduplicate_inferences(inferred_relationships)
            unique_inferences.sort(key=lambda x: x.confidence, reverse=True)
            
            # Update statistics
            self.inference_stats["total_inferences"] += len(unique_inferences)
            self.inference_stats["successful_inferences"] += len([
                inf for inf in unique_inferences if inf.confidence >= confidence_threshold
            ])
            
            return unique_inferences
            
        except Exception as e:
            self.logger.error(f"Error in inference: {e}")
            return []
    
    async def _rule_based_inference(self, entities: List[str], 
                                  confidence_threshold: float) -> List[InferredRelationship]:
        """Apply rule-based inference"""
        inferred = []
        
        try:
            for rule_id, rule in self.inference_rules.items():
                if rule.rule_type != "logical":
                    continue
                
                # Apply rule to entity combinations
                rule_inferences = await self._apply_rule(rule, entities, confidence_threshold)
                inferred.extend(rule_inferences)
            
            self.inference_stats["rule_based_inferences"] += len(inferred)
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in rule-based inference: {e}")
            return []
    
    async def _semantic_inference(self, entities: List[str], 
                                confidence_threshold: float) -> List[InferredRelationship]:
        """Apply semantic inference using embeddings and similarity"""
        inferred = []
        
        try:
            # Get entity embeddings if available
            entity_embeddings = await self._get_entity_embeddings(entities)
            
            if not entity_embeddings:
                return []
            
            # Find semantically similar entities
            for i, entity_a in enumerate(entities):
                if entity_a not in entity_embeddings:
                    continue
                
                for j, entity_b in enumerate(entities[i+1:], i+1):
                    if entity_b not in entity_embeddings:
                        continue
                    
                    # Calculate semantic similarity
                    similarity = self._cosine_similarity(
                        entity_embeddings[entity_a],
                        entity_embeddings[entity_b]
                    )
                    
                    if similarity >= confidence_threshold:
                        inferred_rel = InferredRelationship(
                            source_id=entity_a,
                            target_id=entity_b,
                            relationship_type="SEMANTICALLY_SIMILAR",
                            confidence=similarity,
                            evidence=[{
                                "type": "embedding_similarity",
                                "similarity_score": similarity
                            }],
                            reasoning_path=["semantic_similarity_calculation"]
                        )
                        inferred.append(inferred_rel)
            
            self.inference_stats["semantic_inferences"] += len(inferred)
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in semantic inference: {e}")
            return []
    
    async def _statistical_inference(self, entities: List[str], 
                                   confidence_threshold: float) -> List[InferredRelationship]:
        """Apply statistical inference based on graph patterns"""
        inferred = []
        
        try:
            # Apply statistical rules
            for rule_id, rule in self.inference_rules.items():
                if rule.rule_type != "statistical":
                    continue
                
                rule_inferences = await self._apply_statistical_rule(rule, entities, confidence_threshold)
                inferred.extend(rule_inferences)
            
            self.inference_stats["statistical_inferences"] += len(inferred)
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in statistical inference: {e}")
            return []
    
    async def _apply_rule(self, rule: InferenceRule, entities: List[str], 
                         confidence_threshold: float) -> List[InferredRelationship]:
        """Apply a specific inference rule"""
        inferred = []
        
        try:
            # Parse rule premise pattern
            premise_pattern = rule.premise.get("pattern", "")
            
            if "transitivity" in rule.id.lower():
                # Handle transitivity rules
                inferred.extend(await self._apply_transitivity_rule(rule, entities, confidence_threshold))
            
            elif "symmetric" in rule.id.lower():
                # Handle symmetry rules
                inferred.extend(await self._apply_symmetry_rule(rule, entities, confidence_threshold))
            
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error applying rule {rule.id}: {e}")
            return []
    
    async def _apply_transitivity_rule(self, rule: InferenceRule, entities: List[str], 
                                     confidence_threshold: float) -> List[InferredRelationship]:
        """Apply transitivity rule (A->B, B->C implies A->C)"""
        inferred = []
        
        try:
            for entity_a in entities:
                # Get relationships from A
                relationships_from_a = await self.graph_engine.get_entity_relationships(
                    entity_a, direction="outgoing"
                )
                
                for rel_ab in relationships_from_a:
                    entity_b = rel_ab["target_id"]
                    
                    # Get relationships from B
                    relationships_from_b = await self.graph_engine.get_entity_relationships(
                        entity_b, direction="outgoing"
                    )
                    
                    for rel_bc in relationships_from_b:
                        entity_c = rel_bc["target_id"]
                        
                        # Check if relationship types match rule
                        if (rel_ab["type"] == rel_bc["type"] and 
                            rel_ab["type"] in ["LOCATED_IN", "PART_OF", "SUBCLASS_OF"]):
                            
                            # Calculate confidence
                            confidence = (rel_ab["strength"] * rel_bc["strength"] * 
                                        rule.confidence * rule.conclusion["confidence_modifier"])
                            
                            if confidence >= confidence_threshold:
                                inferred_rel = InferredRelationship(
                                    source_id=entity_a,
                                    target_id=entity_c,
                                    relationship_type=rel_ab["type"],
                                    confidence=confidence,
                                    evidence=[
                                        {"relationship": rel_ab},
                                        {"relationship": rel_bc}
                                    ],
                                    reasoning_path=[
                                        f"transitivity_rule_{rule.id}",
                                        f"{entity_a}->{entity_b}->{entity_c}"
                                    ]
                                )
                                inferred.append(inferred_rel)
            
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in transitivity rule: {e}")
            return []
    
    async def _apply_symmetry_rule(self, rule: InferenceRule, entities: List[str], 
                                 confidence_threshold: float) -> List[InferredRelationship]:
        """Apply symmetry rule (A->B implies B->A for symmetric relations)"""
        inferred = []
        
        try:
            for entity in entities:
                relationships = await self.graph_engine.get_entity_relationships(
                    entity, direction="outgoing"
                )
                
                for rel in relationships:
                    # Check if relationship type is symmetric
                    if rel["type"] in ["SIMILAR_TO", "CONNECTED_TO", "MARRIED_TO"]:
                        
                        # Check if reverse relationship already exists
                        reverse_exists = await self._check_reverse_relationship_exists(
                            rel["target_id"], entity, rel["type"]
                        )
                        
                        if not reverse_exists:
                            confidence = rel["strength"] * rule.confidence
                            
                            if confidence >= confidence_threshold:
                                inferred_rel = InferredRelationship(
                                    source_id=rel["target_id"],
                                    target_id=entity,
                                    relationship_type=rel["type"],
                                    confidence=confidence,
                                    evidence=[{"relationship": rel}],
                                    reasoning_path=[
                                        f"symmetry_rule_{rule.id}",
                                        f"symmetric_property_{rel['type']}"
                                    ]
                                )
                                inferred.append(inferred_rel)
            
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in symmetry rule: {e}")
            return []
    
    async def _apply_statistical_rule(self, rule: InferenceRule, entities: List[str], 
                                    confidence_threshold: float) -> List[InferredRelationship]:
        """Apply statistical inference rule"""
        inferred = []
        
        try:
            if "co_occurrence" in rule.id:
                inferred.extend(await self._apply_co_occurrence_rule(rule, entities, confidence_threshold))
            
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in statistical rule {rule.id}: {e}")
            return []
    
    async def _apply_co_occurrence_rule(self, rule: InferenceRule, entities: List[str], 
                                      confidence_threshold: float) -> List[InferredRelationship]:
        """Apply co-occurrence based inference"""
        inferred = []
        
        try:
            min_shared = rule.premise["constraints"].get("min_shared_connections", 2)
            
            for i, entity_a in enumerate(entities):
                for entity_b in entities[i+1:]:
                    # Find shared connections
                    shared_connections = await self._find_shared_connections(entity_a, entity_b)
                    
                    if len(shared_connections) >= min_shared:
                        # Calculate confidence based on shared connections
                        confidence = min(1.0, len(shared_connections) / 10.0) * rule.confidence
                        
                        if confidence >= confidence_threshold:
                            inferred_rel = InferredRelationship(
                                source_id=entity_a,
                                target_id=entity_b,
                                relationship_type="RELATED_TO",
                                confidence=confidence,
                                evidence=[{
                                    "shared_connections": shared_connections,
                                    "connection_count": len(shared_connections)
                                }],
                                reasoning_path=[
                                    f"co_occurrence_rule_{rule.id}",
                                    f"shared_connections_{len(shared_connections)}"
                                ]
                            )
                            inferred.append(inferred_rel)
            
            return inferred
            
        except Exception as e:
            self.logger.error(f"Error in co-occurrence rule: {e}")
            return []
    
    async def _get_entity_embeddings(self, entities: List[str]) -> Dict[str, List[float]]:
        """Get embeddings for entities"""
        embeddings = {}
        
        try:
            # This would integrate with an embedding service
            # For now, return mock embeddings
            for entity in entities:
                # Generate mock embedding (in practice, this would be real embeddings)
                embeddings[entity] = [0.1 * i for i in range(384)]  # Mock 384-dim embedding
            
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Error getting entity embeddings: {e}")
            return {}
    
    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
            magnitude_a = math.sqrt(sum(a * a for a in vec_a))
            magnitude_b = math.sqrt(sum(b * b for b in vec_b))
            
            if magnitude_a == 0 or magnitude_b == 0:
                return 0.0
            
            return dot_product / (magnitude_a * magnitude_b)
            
        except Exception as e:
            self.logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def _check_reverse_relationship_exists(self, source_id: str, target_id: str, 
                                               relationship_type: str) -> bool:
        """Check if reverse relationship already exists"""
        try:
            relationships = await self.graph_engine.get_entity_relationships(source_id, direction="outgoing")
            
            for rel in relationships:
                if rel["target_id"] == target_id and rel["type"] == relationship_type:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking reverse relationship: {e}")
            return False
    
    async def _find_shared_connections(self, entity_a: str, entity_b: str) -> List[str]:
        """Find shared connections between two entities"""
        try:
            connections_a = set()
            connections_b = set()
            
            # Get connections for entity A
            rels_a = await self.graph_engine.get_entity_relationships(entity_a)
            for rel in rels_a:
                connections_a.add(rel["target_id"] if rel["source_id"] == entity_a else rel["source_id"])
            
            # Get connections for entity B
            rels_b = await self.graph_engine.get_entity_relationships(entity_b)
            for rel in rels_b:
                connections_b.add(rel["target_id"] if rel["source_id"] == entity_b else rel["source_id"])
            
            # Find intersection
            shared = connections_a.intersection(connections_b)
            return list(shared)
            
        except Exception as e:
            self.logger.error(f"Error finding shared connections: {e}")
            return []
    
    def _deduplicate_inferences(self, inferences: List[InferredRelationship]) -> List[InferredRelationship]:
        """Remove duplicate inferences"""
        unique_inferences = {}
        
        for inference in inferences:
            key = f"{inference.source_id}_{inference.target_id}_{inference.relationship_type}"
            
            if key not in unique_inferences or inference.confidence > unique_inferences[key].confidence:
                unique_inferences[key] = inference
        
        return list(unique_inferences.values())
    
    async def add_inference_rule(self, rule: InferenceRule):
        """Add a new inference rule"""
        self.inference_rules[rule.id] = rule
        self.logger.info(f"Added inference rule: {rule.id}")
    
    async def remove_inference_rule(self, rule_id: str):
        """Remove an inference rule"""
        if rule_id in self.inference_rules:
            del self.inference_rules[rule_id]
            self.logger.info(f"Removed inference rule: {rule_id}")
    
    async def get_inference_rules(self) -> Dict[str, InferenceRule]:
        """Get all inference rules"""
        return self.inference_rules.copy()
    
    async def get_inference_statistics(self) -> Dict[str, Any]:
        """Get inference statistics"""
        return self.inference_stats.copy()
    
    async def _load_inference_rules(self):
        """Load inference rules from storage"""
        # This would load rules from persistent storage
        self.logger.debug("Loading inference rules from storage")
    
    async def _save_inference_rules(self):
        """Save inference rules to storage"""
        # This would save rules to persistent storage
        self.logger.debug("Saving inference rules to storage")