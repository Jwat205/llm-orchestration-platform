"""
Transformer-based entity and relationship extraction using BERT and other models.
"""
import torch
from transformers import (
    AutoTokenizer, AutoModelForTokenClassification,
    AutoModelForSequenceClassification, pipeline,
    BertTokenizer, BertForSequenceClassification
)
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class TransformerEntity:
    """Entity extracted using transformer models."""
    text: str
    label: str
    start: int
    end: int
    confidence: float
    model_scores: Dict[str, float]
    features: Dict[str, Any]

@dataclass
class TransformerRelationship:
    """Relationship extracted using transformer models."""
    subject: TransformerEntity
    predicate: str
    object: TransformerEntity
    confidence: float
    model_scores: Dict[str, float]
    context_window: str
    features: Dict[str, Any]

class TransformerExtractor:
    """Advanced entity and relationship extraction using transformer models."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize transformer extractor with multiple models.
        
        Args:
            config: Configuration for models and parameters
        """
        self.config = config or self._default_config()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Model storage
        self.ner_model = None
        self.ner_tokenizer = None
        self.relation_model = None
        self.relation_tokenizer = None
        self.classification_pipeline = None
        
        # Entity linking models
        self.entity_linking_model = None
        
        # Load models
        self._load_models()
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for transformer models."""
        return {
            "ner_model": "dbmdz/bert-large-cased-finetuned-conll03-english",
            "relation_model": "microsoft/DialoGPT-medium",
            "entity_linking_model": "facebook/entity-linker",
            "classification_model": "microsoft/deberta-v3-base",
            "max_length": 512,
            "batch_size": 8,
            "confidence_threshold": 0.7,
            "use_gpu": True
        }
    
    def _load_models(self):
        """Load all transformer models."""
        try:
            logger.info("Loading transformer models...")
            
            # Load NER model
            self._load_ner_model()
            
            # Load relation extraction model
            self._load_relation_model()
            
            # Load classification pipeline
            self._load_classification_pipeline()
            
            logger.info("All transformer models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load transformer models: {e}")
            raise
    
    def _load_ner_model(self):
        """Load Named Entity Recognition model."""
        model_name = self.config["ner_model"]
        
        self.ner_tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.ner_model = AutoModelForTokenClassification.from_pretrained(model_name)
        
        if self.config["use_gpu"] and torch.cuda.is_available():
            self.ner_model.to(self.device)
        
        self.ner_model.eval()
    

    def _load_relation_model(self):
        from transformers import DebertaV2Tokenizer, AutoModelForSequenceClassification

        """Load relation extraction model."""
        model_name = "microsoft/deberta-v3-base"

        # ✅ Force use of slow DeBERTa tokenizer directly
        self.relation_tokenizer = DebertaV2Tokenizer.from_pretrained(model_name)

        self.relation_model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=10  # Set this to match your task
        )

        if self.config["use_gpu"] and torch.cuda.is_available():
            self.relation_model.to(self.device)

        self.relation_model.eval()  

    def _load_classification_pipeline(self):
        """Load classification pipeline for entity typing."""
        self.classification_pipeline = pipeline(
            "text-classification",
            model=self.config["classification_model"],
            device=0 if self.config["use_gpu"] and torch.cuda.is_available() else -1
        )
    
    def extract_entities(self, text: str, min_confidence: float = None) -> List[TransformerEntity]:
        """
        Extract entities using transformer NER model.
        
        Args:
            text: Input text
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of extracted entities
        """
        if min_confidence is None:
            min_confidence = self.config["confidence_threshold"]
        
        if not text or not text.strip():
            return []
        
        # Tokenize text
        inputs = self.ner_tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=self.config["max_length"]
        )
        
        if self.config["use_gpu"] and torch.cuda.is_available():
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get predictions
        with torch.no_grad():
            outputs = self.ner_model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # Convert predictions to entities
        entities = self._predictions_to_entities(
            text, inputs, predictions, min_confidence
        )
        
        # Enhance entities with additional features
        enhanced_entities = []
        for entity in entities:
            enhanced_entity = self._enhance_entity(entity, text)
            enhanced_entities.append(enhanced_entity)
        
        return enhanced_entities
    
    def _predictions_to_entities(self, text: str, inputs: Dict, 
                                predictions: torch.Tensor, 
                                min_confidence: float) -> List[TransformerEntity]:
        """Convert model predictions to entity objects."""
        entities = []
        tokens = self.ner_tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        
        # Get label names
        id2label = self.ner_model.config.id2label
        
        current_entity = None
        current_tokens = []
        current_scores = []
        
        for i, (token, pred_scores) in enumerate(zip(tokens, predictions[0])):
            if token in ["[CLS]", "[SEP]", "[PAD]"]:
                continue
            
            # Get best prediction
            best_label_id = torch.argmax(pred_scores).item()
            confidence = pred_scores[best_label_id].item()
            best_label = id2label[best_label_id]
            
            if confidence < min_confidence:
                continue
            
            # Handle BIO tagging
            if best_label.startswith("B-"):
                # Start new entity
                if current_entity is not None:
                    # Finish previous entity
                    entity = self._create_entity_from_tokens(
                        current_tokens, current_scores, text, inputs
                    )
                    if entity:
                        entities.append(entity)
                
                # Start new entity
                current_entity = best_label[2:]  # Remove "B-" prefix
                current_tokens = [(token, i)]
                current_scores = [confidence]
                
            elif best_label.startswith("I-") and current_entity:
                # Continue current entity
                if best_label[2:] == current_entity:
                    current_tokens.append((token, i))
                    current_scores.append(confidence)
                else:
                    # Inconsistent tagging, start new entity
                    if current_entity is not None:
                        entity = self._create_entity_from_tokens(
                            current_tokens, current_scores, text, inputs
                        )
                        if entity:
                            entities.append(entity)
                    
                    current_entity = best_label[2:]
                    current_tokens = [(token, i)]
                    current_scores = [confidence]
            else:
                # End current entity
                if current_entity is not None:
                    entity = self._create_entity_from_tokens(
                        current_tokens, current_scores, text, inputs
                    )
                    if entity:
                        entities.append(entity)
                    
                    current_entity = None
                    current_tokens = []
                    current_scores = []
        
        # Handle last entity
        if current_entity is not None:
            entity = self._create_entity_from_tokens(
                current_tokens, current_scores, text, inputs
            )
            if entity:
                entities.append(entity)
        
        return entities
    
    def _create_entity_from_tokens(self, tokens: List[Tuple[str, int]], 
                                  scores: List[float], text: str, 
                                  inputs: Dict) -> Optional[TransformerEntity]:
        """Create entity from token sequence."""
        if not tokens:
            return None
        
        # Reconstruct text from tokens
        token_texts = [token for token, _ in tokens]
        entity_text = self.ner_tokenizer.convert_tokens_to_string(token_texts)
        
        # Find entity position in original text
        start_pos = text.find(entity_text)
        if start_pos == -1:
            # Try alternative matching
            start_pos = self._find_entity_position(entity_text, text)
        
        if start_pos == -1:
            return None
        
        end_pos = start_pos + len(entity_text)
        
        # Calculate average confidence
        avg_confidence = np.mean(scores)
        
        # Determine entity label
        label = self._infer_entity_label(entity_text, token_texts)
        
        return TransformerEntity(
            text=entity_text.strip(),
            label=label,
            start=start_pos,
            end=end_pos,
            confidence=avg_confidence,
            model_scores={"ner_model": avg_confidence},
            features={}
        )
    
    def _find_entity_position(self, entity_text: str, full_text: str) -> int:
        """Find entity position using fuzzy matching."""
        # Clean entity text
        cleaned_entity = re.sub(r'\s+', ' ', entity_text.strip())
        
        # Try exact match first
        pos = full_text.find(cleaned_entity)
        if pos != -1:
            return pos
        
        # Try case-insensitive match
        pos = full_text.lower().find(cleaned_entity.lower())
        if pos != -1:
            return pos
        
        # Try word-by-word matching
        words = cleaned_entity.split()
        if words:
            first_word_pos = full_text.find(words[0])
            if first_word_pos != -1:
                return first_word_pos
        
        return -1
    
    def _infer_entity_label(self, entity_text: str, tokens: List[str]) -> str:
        """Infer entity label from text and tokens."""
        # Use classification pipeline for better labeling
        if self.classification_pipeline:
            try:
                result = self.classification_pipeline(entity_text)
                if result and len(result) > 0:
                    return result[0]["label"]
            except Exception as e:
                logger.warning(f"Classification failed: {e}")
        
        # Fallback to rule-based classification
        text_lower = entity_text.lower()
        
        if any(indicator in text_lower for indicator in ["inc", "corp", "ltd", "company"]):
            return "ORG"
        elif re.match(r'^\d{4}$', entity_text):  # Year
            return "DATE"
        elif re.match(r'^\$?\d+\.?\d*[kmb]?$', entity_text.lower()):  # Money
            return "MONEY"
        elif entity_text.istitle():
            return "PERSON"
        else:
            return "MISC"
    
    def _enhance_entity(self, entity: TransformerEntity, text: str) -> TransformerEntity:
        """Enhance entity with additional features."""
        # Extract contextual features
        context_window = self._get_context_window(entity, text, window_size=50)
        
        # Calculate additional scores
        entity.model_scores.update({
            "context_relevance": self._calculate_context_relevance(entity, context_window),
            "entity_importance": self._calculate_entity_importance(entity, text)
        })
        
        # Add features
        entity.features = {
            "context_window": context_window,
            "word_count": len(entity.text.split()),
            "char_count": len(entity.text),
            "is_title_case": entity.text.istitle(),
            "is_all_caps": entity.text.isupper(),
            "contains_digits": bool(re.search(r'\d', entity.text)),
            "entity_density": self._calculate_entity_density(entity, text)
        }
        
        return entity
    
    def _get_context_window(self, entity: TransformerEntity, text: str, window_size: int = 50) -> str:
        """Get context window around entity."""
        start = max(0, entity.start - window_size)
        end = min(len(text), entity.end + window_size)
        return text[start:end]
    
    def _calculate_context_relevance(self, entity: TransformerEntity, context: str) -> float:
        """Calculate how relevant the entity is to its context."""
        # Simple relevance based on context diversity
        context_words = set(context.lower().split())
        entity_words = set(entity.text.lower().split())
        
        if len(context_words) == 0:
            return 0.5
        
        overlap = len(entity_words.intersection(context_words))
        return min(1.0, overlap / len(context_words) + 0.5)
    
    def _calculate_entity_importance(self, entity: TransformerEntity, text: str) -> float:
        """Calculate importance of entity in the text."""
        # Frequency-based importance
        entity_count = text.lower().count(entity.text.lower())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.5
        
        frequency_score = min(1.0, entity_count / text_length * 10)
        
        # Position-based importance (entities at beginning are more important)
        position_score = 1.0 - (entity.start / len(text))
        
        # Combine scores
        return (frequency_score + position_score) / 2
    
    def _calculate_entity_density(self, entity: TransformerEntity, text: str) -> float:
        """Calculate entity density in the text."""
        total_chars = len(text)
        entity_chars = len(entity.text)
        return entity_chars / total_chars if total_chars > 0 else 0.0
    
    def extract_relationships(self, text: str, entities: List[TransformerEntity] = None,
                             min_confidence: float = None) -> List[TransformerRelationship]:
        """
        Extract relationships between entities using transformer models.
        
        Args:
            text: Input text
            entities: Pre-extracted entities
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of extracted relationships
        """
        if min_confidence is None:
            min_confidence = self.config["confidence_threshold"]
        
        if entities is None:
            entities = self.extract_entities(text)
        
        if len(entities) < 2:
            return []
        
        relationships = []
        
        # Extract pairwise relationships
        for i, subj_entity in enumerate(entities):
            for j, obj_entity in enumerate(entities[i+1:], i+1):
                relationship = self._extract_pairwise_relationship(
                    text, subj_entity, obj_entity, min_confidence
                )
                if relationship:
                    relationships.append(relationship)
        
        # Post-process relationships
        relationships = self._post_process_relationships(relationships)
        
        return relationships
    
    def _extract_pairwise_relationship(self, text: str, 
                                     subj_entity: TransformerEntity,
                                     obj_entity: TransformerEntity,
                                     min_confidence: float) -> Optional[TransformerRelationship]:
        """Extract relationship between two entities."""
        # Create context window around both entities
        start_pos = min(subj_entity.start, obj_entity.start)
        end_pos = max(subj_entity.end, obj_entity.end)
        
        context_start = max(0, start_pos - 100)
        context_end = min(len(text), end_pos + 100)
        context = text[context_start:context_end]
        
        # Create input for relation classification
        relation_input = self._create_relation_input(
            subj_entity.text, obj_entity.text, context
        )
        
        # Get relation prediction
        relation_type, confidence = self._predict_relation(relation_input)
        
        if confidence < min_confidence:
            return None
        
        # Calculate additional scores
        model_scores = {
            "relation_model": confidence,
            "distance_score": self._calculate_distance_score(subj_entity, obj_entity),
            "context_score": self._calculate_context_score(context, subj_entity, obj_entity)
        }
        
        # Overall confidence
        overall_confidence = np.mean(list(model_scores.values()))
        
        if overall_confidence < min_confidence:
            return None
        
        return TransformerRelationship(
            subject=subj_entity,
            predicate=relation_type,
            object=obj_entity,
            confidence=overall_confidence,
            model_scores=model_scores,
            context_window=context,
            features=self._extract_relationship_features(subj_entity, obj_entity, context)
        )
    
    def _create_relation_input(self, subject: str, object_entity: str, context: str) -> str:
        """Create input string for relation classification."""
        # Format: [CLS] subject [SEP] object [SEP] context [SEP]
        return f"{subject} [SEP] {object_entity} [SEP] {context}"
    
    def _predict_relation(self, relation_input: str) -> Tuple[str, float]:
        """Predict relation type and confidence."""
        # Tokenize input
        inputs = self.relation_tokenizer(
            relation_input,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=self.config["max_length"]
        )
        
        if self.config["use_gpu"] and torch.cuda.is_available():
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get prediction
        with torch.no_grad():
            outputs = self.relation_model(**inputs)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # Get best prediction
        best_class = torch.argmax(probabilities, dim=-1).item()
        confidence = probabilities[0][best_class].item()
        
        # Map class to relation type
        relation_type = self._map_class_to_relation(best_class)
        
        return relation_type, confidence
    
    def _map_class_to_relation(self, class_id: int) -> str:
        """Map classification class to relation type."""
        # Define relation mapping
        relation_map = {
            0: "related_to",
            1: "part_of",
            2: "located_in",
            3: "employed_by",
            4: "founded_by",
            5: "owns",
            6: "member_of",
            7: "causes",
            8: "similar_to",
            9: "opposite_to"
        }
        
        return relation_map.get(class_id, "related_to")
    
    def _calculate_distance_score(self, subj_entity: TransformerEntity, 
                                 obj_entity: TransformerEntity) -> float:
        """Calculate score based on distance between entities."""
        distance = abs(subj_entity.start - obj_entity.start)
        
        # Closer entities are more likely to be related
        # Use exponential decay
        distance_score = np.exp(-distance / 100)
        return min(1.0, distance_score)
    
    def _calculate_context_score(self, context: str, 
                               subj_entity: TransformerEntity,
                               obj_entity: TransformerEntity) -> float:
        """Calculate score based on context richness."""
        context_words = context.split()
        
        # Score based on context length and richness
        length_score = min(1.0, len(context_words) / 50)
        
        # Check for relationship indicators
        relationship_indicators = [
            "is", "was", "has", "have", "owns", "works", "located", 
            "founded", "created", "leads", "manages", "part"
        ]
        
        indicator_count = sum(1 for word in context_words 
                            if word.lower() in relationship_indicators)
        indicator_score = min(1.0, indicator_count / 5)
        
        return (length_score + indicator_score) / 2
    
    def _extract_relationship_features(self, subj_entity: TransformerEntity,
                                     obj_entity: TransformerEntity,
                                     context: str) -> Dict[str, Any]:
        """Extract features for the relationship."""
        return {
            "distance": abs(subj_entity.start - obj_entity.start),
            "context_length": len(context.split()),
            "subject_type": subj_entity.label,
            "object_type": obj_entity.label,
            "same_sentence": self._in_same_sentence(subj_entity, obj_entity, context),
            "dependency_path": self._extract_dependency_path(subj_entity, obj_entity, context)
        }
    
    def _in_same_sentence(self, subj_entity: TransformerEntity,
                         obj_entity: TransformerEntity, context: str) -> bool:
        """Check if entities are in the same sentence."""
        # Simple check based on sentence boundaries
        sentences = context.split('.')
        
        for sentence in sentences:
            if subj_entity.text in sentence and obj_entity.text in sentence:
                return True
        
        return False
    
    def _extract_dependency_path(self, subj_entity: TransformerEntity,
                               obj_entity: TransformerEntity, context: str) -> str:
        """Extract dependency path between entities (simplified)."""
        # This is a simplified version - in practice, you'd use a dependency parser
        words_between = []
        
        # Find words between entities in context
        subj_pos = context.find(subj_entity.text)
        obj_pos = context.find(obj_entity.text)
        
        if subj_pos != -1 and obj_pos != -1:
            start = min(subj_pos + len(subj_entity.text), obj_pos + len(obj_entity.text))
            end = max(subj_pos, obj_pos)
            
            if start < end:
                between_text = context[start:end].strip()
                words_between = between_text.split()
        
        return " ".join(words_between[:5])  # Limit to first 5 words
    
    def _post_process_relationships(self, relationships: List[TransformerRelationship]) -> List[TransformerRelationship]:
        """Post-process extracted relationships."""
        # Remove duplicate relationships
        unique_relationships = []
        seen_pairs = set()
        
        for rel in relationships:
            pair_key = (rel.subject.text, rel.predicate, rel.object.text)
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                unique_relationships.append(rel)
        
        # Sort by confidence
        unique_relationships.sort(key=lambda x: x.confidence, reverse=True)
        
        return unique_relationships
    
    def extract_events(self, text: str, min_confidence: float = None) -> List[Dict[str, Any]]:
        """Extract events from text using transformer models."""
        if min_confidence is None:
            min_confidence = self.config["confidence_threshold"]
        
        # Extract entities first
        entities = self.extract_entities(text, min_confidence)
        
        # Find event triggers (verbs, action words)
        event_patterns = [
            r'\b(announced|launched|founded|acquired|merged|released)\b',
            r'\b(happened|occurred|took place|began|started|ended)\b',
            r'\b(created|built|developed|designed|implemented)\b'
        ]
        
        events = []
        
        for pattern in event_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                event_trigger = match.group(1)
                event_start = match.start()
                event_end = match.end()
                
                # Find related entities around the event
                related_entities = []
                for entity in entities:
                    if abs(entity.start - event_start) < 100:  # Within 100 characters
                        related_entities.append(entity)
                
                if related_entities:
                    event = {
                        "trigger": event_trigger,
                        "start": event_start,
                        "end": event_end,
                        "entities": related_entities,
                        "confidence": 0.7,  # Base confidence for pattern-based events
                        "context": text[max(0, event_start-50):min(len(text), event_end+50)]
                    }
                    events.append(event)
        
        return events
    
    def batch_extract_entities(self, texts: List[str], 
                              batch_size: int = None) -> List[List[TransformerEntity]]:
        """Extract entities from multiple texts in batches."""
        if batch_size is None:
            batch_size = self.config["batch_size"]
        
        all_entities = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_entities = []
            
            for text in batch_texts:
                entities = self.extract_entities(text)
                batch_entities.append(entities)
            
            all_entities.extend(batch_entities)
        
        return all_entities
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models."""
        return {
            "ner_model": self.config["ner_model"],
            "relation_model": self.config["relation_model"],
            "device": str(self.device),
            "max_length": self.config["max_length"],
            "batch_size": self.config["batch_size"]
        }