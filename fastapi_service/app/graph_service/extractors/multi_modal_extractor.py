import asyncio
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import base64
from pathlib import Path

# Core libraries
import numpy as np
import pandas as pd
from PIL import Image
import torch
import torch.nn.functional as F

# NLP and ML libraries
import spacy
import transformers
from transformers import (
    AutoTokenizer, AutoModel, AutoProcessor,
    BlipProcessor, BlipForConditionalGeneration,
    Wav2Vec2Processor, Wav2Vec2ForCTC,
    CLIPProcessor, CLIPModel
)
import sentence_transformers
from sentence_transformers import SentenceTransformer

# Computer Vision
import cv2
import pytesseract

# Audio processing
import librosa
import whisper

# Graph and knowledge base
import networkx as nx
from rdflib import Graph, URIRef, Literal, Namespace

# Utility libraries
import requests
from urllib.parse import urlparse
import mimetypes
import hashlib
from datetime import datetime, timezone 


class ModalityType(Enum):
    """Supported modality types for extraction"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    STRUCTURED = "structured"
    WEB = "web"
    CODE = "code"


class EntityType(Enum):
    """Entity types for knowledge graph"""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    PRODUCT = "PRODUCT"
    CONCEPT = "CONCEPT"
    TEMPORAL = "TEMPORAL"
    NUMERIC = "NUMERIC"
    VISUAL_OBJECT = "VISUAL_OBJECT"
    AUDIO_ELEMENT = "AUDIO_ELEMENT"
    TECHNICAL_TERM = "TECHNICAL_TERM"


class RelationshipType(Enum):
    """Relationship types for knowledge graph"""
    IS_A = "IS_A"
    PART_OF = "PART_OF"
    RELATED_TO = "RELATED_TO"
    LOCATED_AT = "LOCATED_AT"
    OCCURS_AT = "OCCURS_AT"
    CAUSED_BY = "CAUSED_BY"
    CONTAINS = "CONTAINS"
    SIMILAR_TO = "SIMILAR_TO"
    DEPENDS_ON = "DEPENDS_ON"
    CO_OCCURS = "CO_OCCURS"


@dataclass
class Entity:
    """Entity data structure"""
    id: str
    text: str
    entity_type: EntityType
    confidence: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[np.ndarray] = None
    source_modality: ModalityType = ModalityType.TEXT
    bounding_box: Optional[Tuple[int, int, int, int]] = None
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """Relationship data structure"""
    id: str
    subject_id: str
    predicate: RelationshipType
    object_id: str
    confidence: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    evidence: Optional[str] = None
    source_modality: ModalityType = ModalityType.TEXT
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Complete extraction result"""
    entities: List[Entity]
    relationships: List[Relationship]
    modality: ModalityType
    source_info: Dict[str, Any]
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiModalExtractor:
    """
    Multi-modal entity and relationship extractor that combines various AI models
    and techniques to extract structured knowledge from diverse content types.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the multi-modal extractor"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Model configurations
        self.models = {}
        self.processors = {}
        self.extractors = {}
        
        # Performance settings
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = self.config.get("batch_size", 16)
        self.max_sequence_length = self.config.get("max_sequence_length", 512)
        
        # Initialize models
        asyncio.create_task(self._initialize_models())
    
    async def _initialize_models(self):
        """Initialize all required models for multi-modal extraction"""
        try:
            # Text models
            await self._init_text_models()
            
            # Vision models
            await self._init_vision_models()
            
            # Audio models
            await self._init_audio_models()
            
            # Multi-modal models
            await self._init_multimodal_models()
            
            self.logger.info("All models initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing models: {e}")
            raise
    
    async def _init_text_models(self):
        """Initialize text processing models"""
        # SpaCy NLP model
        try:
            self.extractors['spacy'] = spacy.load("en_core_web_sm")
        except OSError:
            self.logger.warning("SpaCy model not found, downloading...")
            spacy.cli.download("en_core_web_sm")
            self.extractors['spacy'] = spacy.load("en_core_web_sm")
        
        # Sentence transformer for embeddings
        self.models['sentence_transformer'] = SentenceTransformer(
            'all-MiniLM-L6-v2'
        )
        
        # BERT for advanced NER
        self.extractors['bert_ner'] = transformers.pipeline(
            "ner",
            model="dbmdz/bert-large-cased-finetuned-conll03-english",
            aggregation_strategy="simple",
            device=0 if torch.cuda.is_available() else -1
        )
        
        # Relationship extraction model
        self.extractors['relation'] = transformers.pipeline(
            "text2text-generation",
            model="Babelscape/rebel-large",
            device=0 if torch.cuda.is_available() else -1
        )
    
    async def _init_vision_models(self):
        """Initialize computer vision models"""
        # CLIP for image-text understanding
        self.models['clip'] = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processors['clip'] = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # BLIP for image captioning
        self.models['blip'] = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )
        self.processors['blip'] = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )
        
        # Object detection model
        self.extractors['object_detection'] = transformers.pipeline(
            "object-detection",
            model="facebook/detr-resnet-50",
            device=0 if torch.cuda.is_available() else -1
        )
    
    async def _init_audio_models(self):
        """Initialize audio processing models"""
        # Whisper for speech-to-text
        self.models['whisper'] = whisper.load_model("base")
         
        # Wav2Vec2 for audio feature extraction
        self.models['wav2vec2'] = Wav2Vec2ForCTC.from_pretrained(
            "facebook/wav2vec2-base-960h"
        )
        self.processors['wav2vec2'] = Wav2Vec2Processor.from_pretrained(
            "facebook/wav2vec2-base-960h"
        )
    
    async def _init_multimodal_models(self):
        """Initialize multi-modal models"""
        # Additional multi-modal models can be added here
        pass
    
    async def extract(
        self,
        content: Union[str, bytes, Path, Dict[str, Any]],
        modality: ModalityType,
        options: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Main extraction method that routes to appropriate modality-specific extractors
        
        Args:
            content: Input content in various formats
            modality: Type of content modality
            options: Additional extraction options
            
        Returns:
            ExtractionResult containing entities and relationships
        """
        start_time = datetime.now()
        options = options or {}
        
        try:
            # Route to appropriate extractor based on modality
            if modality == ModalityType.TEXT:
                result = await self._extract_from_text(content, options)
            elif modality == ModalityType.IMAGE:
                result = await self._extract_from_image(content, options)
            elif modality == ModalityType.AUDIO:
                result = await self._extract_from_audio(content, options)
            elif modality == ModalityType.VIDEO:
                result = await self._extract_from_video(content, options)
            elif modality == ModalityType.DOCUMENT:
                result = await self._extract_from_document(content, options)
            elif modality == ModalityType.STRUCTURED:
                result = await self._extract_from_structured(content, options)
            elif modality == ModalityType.WEB:
                result = await self._extract_from_web(content, options)
            elif modality == ModalityType.CODE:
                result = await self._extract_from_code(content, options)
            else:
                raise ValueError(f"Unsupported modality: {modality}")
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            result.processing_time = processing_time
            
            # Post-process and enhance results
            result = await self._enhance_extraction_result(result, options)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during extraction: {e}")
            raise
    
    async def _extract_from_text(
        self, 
        text: str, 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from text"""
        entities = []
        relationships = []
        
        # Named Entity Recognition using SpaCy
        doc = self.extractors['spacy'](text)
        entity_map = {}
        
        for ent in doc.ents:
            entity_id = f"text_entity_{hashlib.md5(ent.text.encode()).hexdigest()[:8]}"
            
            # Map SpaCy labels to our EntityType
            entity_type = self._map_spacy_label(ent.label_)
            
            # Generate embeddings
            embeddings = self.models['sentence_transformer'].encode([ent.text])[0]
            
            entity = Entity(
                id=entity_id,
                text=ent.text,
                entity_type=entity_type,
                confidence=0.8,  # SpaCy doesn't provide confidence scores
                embeddings=embeddings,
                source_modality=ModalityType.TEXT,
                attributes={
                    "spacy_label": ent.label_,
                    "start_char": ent.start_char,
                    "end_char": ent.end_char,
                    "lemma": ent.lemma_
                }
            )
            
            entities.append(entity)
            entity_map[ent.text] = entity_id
        
        # Enhanced NER using BERT
        try:
            bert_entities = self.extractors['bert_ner'](text)
            for bert_ent in bert_entities:
                entity_id = f"bert_entity_{hashlib.md5(bert_ent['word'].encode()).hexdigest()[:8]}"
                
                entity_type = self._map_bert_label(bert_ent['entity_group'])
                embeddings = self.models['sentence_transformer'].encode([bert_ent['word']])[0]
                
                entity = Entity(
                    id=entity_id,
                    text=bert_ent['word'],
                    entity_type=entity_type,
                    confidence=bert_ent['score'],
                    embeddings=embeddings,
                    source_modality=ModalityType.TEXT,
                    attributes={
                        "bert_label": bert_ent['entity_group'],
                        "start": bert_ent['start'],
                        "end": bert_ent['end']
                    }
                )
                
                entities.append(entity)
        except Exception as e:
            self.logger.warning(f"BERT NER extraction failed: {e}")
        
        # Relationship extraction using REBEL
        try:
            rel_text = f"Extract relationships: {text}"
            rel_results = self.extractors['relation'](
                rel_text, 
                max_length=256, 
                num_beams=3, 
                num_return_sequences=1
            )
            
            if rel_results:
                rel_triplets = self._parse_rebel_output(rel_results[0]['generated_text'])
                
                for triplet in rel_triplets:
                    subject, predicate, obj = triplet
                    
                    # Find or create entity IDs
                    subject_id = entity_map.get(subject, f"implicit_entity_{hashlib.md5(subject.encode()).hexdigest()[:8]}")
                    object_id = entity_map.get(obj, f"implicit_entity_{hashlib.md5(obj.encode()).hexdigest()[:8]}")
                    
                    relationship_id = f"rel_{hashlib.md5(f'{subject_id}_{predicate}_{object_id}'.encode()).hexdigest()[:8]}"
                    
                    relationship = Relationship(
                        id=relationship_id,
                        subject_id=subject_id,
                        predicate=self._map_predicate(predicate),
                        object_id=object_id,
                        confidence=0.7,
                        evidence=text[:200],  # First 200 chars as evidence
                        source_modality=ModalityType.TEXT,
                        attributes={"original_predicate": predicate}
                    )
                    
                    relationships.append(relationship)
        except Exception as e:
            self.logger.warning(f"Relationship extraction failed: {e}")
        
        # Dependency parsing for additional relationships
        for sent in doc.sents:
            for token in sent:
                if token.dep_ in ['nsubj', 'dobj', 'pobj']:
                    # Extract syntactic relationships
                    head_id = entity_map.get(token.head.text)
                    token_id = entity_map.get(token.text)
                    
                    if head_id and token_id and head_id != token_id:
                        rel_id = f"dep_rel_{hashlib.md5(f'{head_id}_{token.dep_}_{token_id}'.encode()).hexdigest()[:8]}"
                        
                        relationship = Relationship(
                            id=rel_id,
                            subject_id=head_id,
                            predicate=RelationshipType.RELATED_TO,
                            object_id=token_id,
                            confidence=0.6,
                            source_modality=ModalityType.TEXT,
                            attributes={"dependency": token.dep_}
                        )
                        
                        relationships.append(relationship)
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.TEXT,
            source_info={"length": len(text), "type": "text"},
            processing_time=0.0,  # Will be set by main extract method
            metadata={"language": doc.lang_}
        )
    
    async def _extract_from_image(
        self, 
        image_content: Union[str, bytes, Image.Image], 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from images"""
        entities = []
        relationships = []
        
        # Load image
        if isinstance(image_content, str):
            if image_content.startswith(('http://', 'https://')):
                # URL
                response = requests.get(image_content)
                image = Image.open(response.content)
            else:
                # File path
                image = Image.open(image_content)
        elif isinstance(image_content, bytes):
            image = Image.open(image_content)
        else:
            image = image_content
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Object detection
        try:
            detected_objects = self.extractors['object_detection'](image)
            
            for i, obj in enumerate(detected_objects):
                entity_id = f"visual_object_{i}_{hashlib.md5(obj['label'].encode()).hexdigest()[:8]}"
                
                # Generate embeddings for object labels
                embeddings = self.models['sentence_transformer'].encode([obj['label']])[0]
                
                entity = Entity(
                    id=entity_id,
                    text=obj['label'],
                    entity_type=EntityType.VISUAL_OBJECT,
                    confidence=obj['score'],
                    embeddings=embeddings,
                    source_modality=ModalityType.IMAGE,
                    bounding_box=(
                        int(obj['box']['xmin']),
                        int(obj['box']['ymin']),
                        int(obj['box']['xmax']),
                        int(obj['box']['ymax'])
                    ),
                    attributes={
                        "detection_model": "DETR",
                        "box_area": (obj['box']['xmax'] - obj['box']['xmin']) * 
                                   (obj['box']['ymax'] - obj['box']['ymin'])
                    }
                )
                
                entities.append(entity)
        except Exception as e:
            self.logger.warning(f"Object detection failed: {e}")
        
        # Image captioning
        try:
            inputs = self.processors['blip'](image, return_tensors="pt")
            outputs = self.models['blip'].generate(**inputs, max_length=50)
            caption = self.processors['blip'].decode(outputs[0], skip_special_tokens=True)
            
            # Extract entities from caption using text extraction
            caption_result = await self._extract_from_text(caption, options)
            
            # Add caption entities with image context
            for entity in caption_result.entities:
                entity.id = f"caption_{entity.id}"
                entity.source_modality = ModalityType.IMAGE
                entity.attributes.update({"source": "image_caption", "caption": caption})
                entities.append(entity)
            
            # Add caption relationships
            for relationship in caption_result.relationships:
                relationship.id = f"caption_{relationship.id}"
                relationship.source_modality = ModalityType.IMAGE
                relationship.attributes.update({"source": "image_caption"})
                relationships.append(relationship)
                
        except Exception as e:
            self.logger.warning(f"Image captioning failed: {e}")
        
        # OCR for text in images
        try:
            # Convert PIL image to OpenCV format for OCR
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            ocr_text = pytesseract.image_to_string(cv_image)
            
            if ocr_text.strip():
                # Extract entities from OCR text
                ocr_result = await self._extract_from_text(ocr_text, options)
                
                # Add OCR entities with image context
                for entity in ocr_result.entities:
                    entity.id = f"ocr_{entity.id}"
                    entity.source_modality = ModalityType.IMAGE
                    entity.attributes.update({"source": "ocr", "ocr_text": ocr_text})
                    entities.append(entity)
                
                # Add OCR relationships
                for relationship in ocr_result.relationships:
                    relationship.id = f"ocr_{relationship.id}"
                    relationship.source_modality = ModalityType.IMAGE
                    relationship.attributes.update({"source": "ocr"})
                    relationships.append(relationship)
                    
        except Exception as e:
            self.logger.warning(f"OCR extraction failed: {e}")
        
        # Spatial relationships between detected objects
        if len(entities) > 1:
            visual_objects = [e for e in entities if e.entity_type == EntityType.VISUAL_OBJECT and e.bounding_box]
            
            for i, obj1 in enumerate(visual_objects):
                for j, obj2 in enumerate(visual_objects[i+1:], i+1):
                    # Calculate spatial relationships
                    spatial_rel = self._calculate_spatial_relationship(obj1.bounding_box, obj2.bounding_box)
                    
                    if spatial_rel:
                        rel_id = f"spatial_rel_{obj1.id}_{obj2.id}"
                        
                        relationship = Relationship(
                            id=rel_id,
                            subject_id=obj1.id,
                            predicate=RelationshipType.RELATED_TO,
                            object_id=obj2.id,
                            confidence=0.8,
                            source_modality=ModalityType.IMAGE,
                            attributes={"spatial_relationship": spatial_rel}
                        )
                        
                        relationships.append(relationship)
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.IMAGE,
            source_info={"width": image.width, "height": image.height, "mode": image.mode},
            processing_time=0.0,
            metadata={"image_size": image.size}
        )
    
    async def _extract_from_audio(
        self, 
        audio_content: Union[str, bytes, np.ndarray], 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from audio"""
        entities = []
        relationships = []
        
        # Load audio
        if isinstance(audio_content, str):
            # File path or URL
            audio, sr = librosa.load(audio_content, sr=16000)
        elif isinstance(audio_content, bytes):
            # Audio bytes - save temporarily and load
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
                tmp.write(audio_content)
                tmp.flush()
                audio, sr = librosa.load(tmp.name, sr=16000)
        else:
            # Already loaded audio array
            audio = audio_content
            sr = options.get('sample_rate', 16000)
        
        # Speech-to-text using Whisper
        try:
            # Whisper expects the audio to be normalized
            audio_normalized = audio / np.max(np.abs(audio)) if np.max(np.abs(audio)) > 0 else audio
            
            result = self.models['whisper'].transcribe(audio_normalized)
            transcript = result['text']
            
            if transcript.strip():
                # Extract entities from transcript
                text_result = await self._extract_from_text(transcript, options)
                
                # Add transcript entities with audio context
                for entity in text_result.entities:
                    entity.id = f"audio_{entity.id}"
                    entity.source_modality = ModalityType.AUDIO
                    entity.attributes.update({"source": "speech_transcript", "transcript": transcript})
                    entities.append(entity)
                
                # Add transcript relationships
                for relationship in text_result.relationships:
                    relationship.id = f"audio_{relationship.id}"
                    relationship.source_modality = ModalityType.AUDIO
                    relationship.attributes.update({"source": "speech_transcript"})
                    relationships.append(relationship)
            
            # Add segments with timestamps if available
            if 'segments' in result:
                for segment in result['segments']:
                    segment_id = f"audio_segment_{segment['id']}"
                    
                    entity = Entity(
                        id=segment_id,
                        text=segment['text'],
                        entity_type=EntityType.AUDIO_ELEMENT,
                        confidence=segment.get('confidence', 0.8),
                        source_modality=ModalityType.AUDIO,
                        timestamp=segment['start'],
                        attributes={
                            "start_time": segment['start'],
                            "end_time": segment['end'],
                            "duration": segment['end'] - segment['start']
                        }
                    )
                    
                    entities.append(entity)
                    
        except Exception as e:
            self.logger.warning(f"Speech-to-text failed: {e}")
        
        # Audio feature extraction
        try:
            # Extract basic audio features
            tempo, beats = librosa.beat.beat_track(y=audio, sr=sr)
            spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
            zero_crossings = librosa.feature.zero_crossing_rate(audio)[0]
            mfccs = librosa.feature.mfcc(y=audio, sr=sr)
            
            # Create audio characteristics entity
            audio_char_id = f"audio_characteristics_{hashlib.md5(str(tempo).encode()).hexdigest()[:8]}"
            
            entity = Entity(
                id=audio_char_id,
                text=f"Audio characteristics (tempo: {tempo:.1f} BPM)",
                entity_type=EntityType.AUDIO_ELEMENT,
                confidence=0.9,
                source_modality=ModalityType.AUDIO,
                attributes={
                    "tempo": float(tempo),
                    "avg_spectral_centroid": float(np.mean(spectral_centroids)),
                    "avg_zero_crossings": float(np.mean(zero_crossings)),
                    "duration": len(audio) / sr,
                    "sample_rate": sr,
                    "mfcc_features": mfccs.tolist()
                }
            )
            
            entities.append(entity)
            
        except Exception as e:
            self.logger.warning(f"Audio feature extraction failed: {e}")
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.AUDIO,
            source_info={"duration": len(audio) / sr, "sample_rate": sr},
            processing_time=0.0,
            metadata={"audio_length": len(audio)}
        )
    
    async def _extract_from_video(
        self, 
        video_content: Union[str, bytes], 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from video (combines image and audio extraction)"""
        entities = []
        relationships = []
        
        # This is a simplified implementation
        # In a full implementation, you would:
        # 1. Extract frames at regular intervals
        # 2. Extract audio track
        # 3. Process each frame as an image
        # 4. Process audio track
        # 5. Create temporal relationships between entities
        
        # For now, return placeholder result
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.VIDEO,
            source_info={"type": "video", "status": "placeholder_implementation"},
            processing_time=0.0,
            metadata={"note": "Video extraction requires additional implementation"}
        )
    
    async def _extract_from_document(
        self, 
        document_content: Union[str, bytes, Path], 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from documents (PDF, DOCX, etc.)"""
        # This would integrate with document processors to extract text
        # Then apply text extraction methods
        
        # Placeholder implementation
        if isinstance(document_content, (str, Path)):
            # Try to read as text file
            try:
                with open(document_content, 'r', encoding='utf-8') as f:
                    text = f.read()
                return await self._extract_from_text(text, options)
            except:
                pass
        
        return ExtractionResult(
            entities=[],
            relationships=[],
            modality=ModalityType.DOCUMENT,
            source_info={"type": "document", "status": "placeholder_implementation"},
            processing_time=0.0,
            metadata={"note": "Document extraction requires additional processors"}
        )
    
    async def _extract_from_structured(
        self, 
        structured_data: Dict[str, Any], 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from structured data (JSON, CSV, etc.)"""
        entities = []
        relationships = []
        
        def extract_from_dict(data: Dict[str, Any], prefix: str = ""):
            """Recursively extract entities from dictionary structure"""
            for key, value in data.items():
                entity_id = f"struct_{prefix}_{key}_{hashlib.md5(str(value).encode()).hexdigest()[:8]}"
                
                if isinstance(value, (str, int, float)):
                    # Create entity for key-value pair
                    entity = Entity(
                        id=entity_id,
                        text=f"{key}: {value}",
                        entity_type=self._infer_entity_type_from_key(key),
                        confidence=0.9,
                        source_modality=ModalityType.STRUCTURED,
                        attributes={
                            "key": key,
                            "value": value,
                            "data_type": type(value).__name__,
                            "path": f"{prefix}.{key}" if prefix else key
                        }
                    )
                    entities.append(entity)
                    
                elif isinstance(value, dict):
                    # Recursive extraction for nested dictionaries
                    extract_from_dict(value, f"{prefix}.{key}" if prefix else key)
                    
                elif isinstance(value, list) and value:
                    # Handle lists
                    for i, item in enumerate(value[:10]):  # Limit to first 10 items
                        if isinstance(item, dict):
                            extract_from_dict(item, f"{prefix}.{key}[{i}]" if prefix else f"{key}[{i}]")
                        else:
                            item_id = f"struct_item_{prefix}_{key}_{i}_{hashlib.md5(str(item).encode()).hexdigest()[:8]}"
                            entity = Entity(
                                id=item_id,
                                text=f"{key}[{i}]: {item}",
                                entity_type=self._infer_entity_type_from_key(key),
                                confidence=0.8,
                                source_modality=ModalityType.STRUCTURED,
                                attributes={
                                    "key": key,
                                    "value": item,
                                    "index": i,
                                    "data_type": type(item).__name__,
                                    "path": f"{prefix}.{key}[{i}]" if prefix else f"{key}[{i}]"
                                }
                            )
                            entities.append(entity)
        
        # Extract from structured data
        if isinstance(structured_data, dict):
            extract_from_dict(structured_data)
        elif isinstance(structured_data, list):
            for i, item in enumerate(structured_data):
                if isinstance(item, dict):
                    extract_from_dict(item, f"root[{i}]")
        
        # Create relationships between related entities
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Create relationships based on structural proximity
                path1 = entity1.attributes.get("path", "")
                path2 = entity2.attributes.get("path", "")
                
                # Check if entities are siblings (same parent)
                path1_parts = path1.split(".")
                path2_parts = path2.split(".")
                
                if len(path1_parts) == len(path2_parts) and path1_parts[:-1] == path2_parts[:-1]:
                    rel_id = f"struct_sibling_{entity1.id}_{entity2.id}"
                    
                    relationship = Relationship(
                        id=rel_id,
                        subject_id=entity1.id,
                        predicate=RelationshipType.RELATED_TO,
                        object_id=entity2.id,
                        confidence=0.7,
                        source_modality=ModalityType.STRUCTURED,
                        attributes={"relationship_type": "sibling_fields"}
                    )
                    relationships.append(relationship)
                
                # Check for parent-child relationships
                elif path1 in path2 or path2 in path1:
                    parent_id = entity1.id if path1 in path2 else entity2.id
                    child_id = entity2.id if path1 in path2 else entity1.id
                    
                    rel_id = f"struct_parent_{parent_id}_{child_id}"
                    
                    relationship = Relationship(
                        id=rel_id,
                        subject_id=parent_id,
                        predicate=RelationshipType.CONTAINS,
                        object_id=child_id,
                        confidence=0.9,
                        source_modality=ModalityType.STRUCTURED,
                        attributes={"relationship_type": "parent_child"}
                    )
                    relationships.append(relationship)
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.STRUCTURED,
            source_info={"type": "structured_data", "entity_count": len(entities)},
            processing_time=0.0,
            metadata={"structure_depth": self._calculate_structure_depth(structured_data)}
        )
    
    async def _extract_from_web(
        self, 
        web_content: Union[str, Dict[str, Any]], 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from web content"""
        entities = []
        relationships = []
        
        if isinstance(web_content, str):
            # URL provided
            try:
                response = requests.get(web_content, timeout=30)
                response.raise_for_status()
                
                # Extract text content (simplified HTML parsing)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text()
                
                # Extract entities from text
                text_result = await self._extract_from_text(text, options)
                
                # Add web context to entities
                for entity in text_result.entities:
                    entity.id = f"web_{entity.id}"
                    entity.source_modality = ModalityType.WEB
                    entity.attributes.update({
                        "source": "web_page",
                        "url": web_content,
                        "domain": urlparse(web_content).netloc
                    })
                    entities.append(entity)
                
                # Add web context to relationships
                for relationship in text_result.relationships:
                    relationship.id = f"web_{relationship.id}"
                    relationship.source_modality = ModalityType.WEB
                    relationship.attributes.update({
                        "source": "web_page",
                        "url": web_content
                    })
                    relationships.append(relationship)
                
                # Extract structured data from HTML (meta tags, JSON-LD, etc.)
                # Meta tags
                meta_tags = soup.find_all('meta')
                for meta in meta_tags:
                    if meta.get('name') and meta.get('content'):
                        combined = f"{meta.get('name')}{meta.get('content')}"
                        meta_id = f"meta_{hashlib.md5(combined.encode()).hexdigest()[:8]}"

                        entity = Entity(
                            id=meta_id,
                            text=f"{meta.get('name')}: {meta.get('content')}",
                            entity_type=EntityType.CONCEPT,
                            confidence=0.8,
                            modality=ModalityType.WEB,
                            attributes={
                                "meta_name": meta.get("name"),
                                "meta_content": meta.get("content"),
                                "source": "html_meta"
                            }
                        )
                        entities.append(entity)

                
                # JSON-LD structured data
                json_ld_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_ld_scripts:
                    try:
                        json_data = json.loads(script.string)
                        structured_result = await self._extract_from_structured(json_data, options)
                        
                        # Add JSON-LD entities with web context
                        for entity in structured_result.entities:
                            entity.id = f"jsonld_{entity.id}"
                            entity.source_modality = ModalityType.WEB
                            entity.attributes.update({
                                "source": "json_ld",
                                "url": web_content
                            })
                            entities.append(entity)
                            
                    except json.JSONDecodeError:
                        continue
                        
            except requests.RequestException as e:
                self.logger.warning(f"Failed to fetch web content: {e}")
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.WEB,
            source_info={"type": "web_page", "url": web_content if isinstance(web_content, str) else "unknown"},
            processing_time=0.0,
            metadata={"extraction_method": "html_parsing"}
        )
    
    async def _extract_from_code(
        self, 
        code_content: str, 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract entities and relationships from source code"""
        entities = []
        relationships = []
        
        # Detect programming language
        language = options.get('language', self._detect_code_language(code_content))
        
        # Basic code entity extraction using AST parsing (Python example)
        if language.lower() == 'python':
            try:
                import ast
                
                tree = ast.parse(code_content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Function entity
                        func_id = f"function_{node.name}_{node.lineno}"
                        
                        entity = Entity(
                            id=func_id,
                            text=node.name,
                            entity_type=EntityType.TECHNICAL_TERM,
                            confidence=1.0,
                            source_modality=ModalityType.CODE,
                            attributes={
                                "code_type": "function",
                                "line_number": node.lineno,
                                "arguments": [arg.arg for arg in node.args.args],
                                "language": language
                            }
                        )
                        entities.append(entity)
                    
                    elif isinstance(node, ast.ClassDef):
                        # Class entity
                        class_id = f"class_{node.name}_{node.lineno}"
                        
                        entity = Entity(
                            id=class_id,
                            text=node.name,
                            entity_type=EntityType.TECHNICAL_TERM,
                            confidence=1.0,
                            source_modality=ModalityType.CODE,
                            attributes={
                                "code_type": "class",
                                "line_number": node.lineno,
                                "bases": [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases],
                                "language": language
                            }
                        )
                        entities.append(entity)
                    
                    elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                        # Import entity
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                import_id = f"import_{alias.name}_{node.lineno}"
                                
                                entity = Entity(
                                    id=import_id,
                                    text=alias.name,
                                    entity_type=EntityType.TECHNICAL_TERM,
                                    confidence=1.0,
                                    source_modality=ModalityType.CODE,
                                    attributes={
                                        "code_type": "import",
                                        "line_number": node.lineno,
                                        "import_type": "direct",
                                        "language": language
                                    }
                                )
                                entities.append(entity)
                        
                        elif isinstance(node, ast.ImportFrom):
                            module = node.module or ""
                            for alias in node.names:
                                import_id = f"import_{module}_{alias.name}_{node.lineno}"
                                
                                entity = Entity(
                                    id=import_id,
                                    text=f"{module}.{alias.name}" if module else alias.name,
                                    entity_type=EntityType.TECHNICAL_TERM,
                                    confidence=1.0,
                                    source_modality=ModalityType.CODE,
                                    attributes={
                                        "code_type": "import",
                                        "line_number": node.lineno,
                                        "import_type": "from",
                                        "module": module,
                                        "name": alias.name,
                                        "language": language
                                    }
                                )
                                entities.append(entity)
                
                # Create relationships between code entities
                # Function calls, class inheritance, etc.
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        # Function call relationship
                        caller_line = node.lineno
                        called_function = node.func.id
                        
                        # Find caller (function or class containing this call)
                        caller_entity = None
                        for entity in entities:
                            if (entity.attributes.get("code_type") in ["function", "class"] and 
                                entity.attributes.get("line_number", 0) < caller_line):
                                caller_entity = entity
                        
                        # Find called function entity
                        called_entity = None
                        for entity in entities:
                            if (entity.attributes.get("code_type") == "function" and 
                                entity.text == called_function):
                                called_entity = entity
                                break
                        
                        if caller_entity and called_entity:
                            rel_id = f"call_{caller_entity.id}_{called_entity.id}"
                            
                            relationship = Relationship(
                                id=rel_id,
                                subject_id=caller_entity.id,
                                predicate=RelationshipType.DEPENDS_ON,
                                object_id=called_entity.id,
                                confidence=0.9,
                                source_modality=ModalityType.CODE,
                                attributes={
                                    "relationship_type": "function_call",
                                    "call_line": caller_line
                                }
                            )
                            relationships.append(relationship)
                            
            except SyntaxError as e:
                self.logger.warning(f"Failed to parse Python code: {e}")
        
        # Generic text-based extraction for other languages or as fallback
        # Extract comments, string literals, identifiers using regex
        import re
        
        # Extract comments
        comment_patterns = {
            'python': r'#.*',
            'javascript': r'//.*$|/\*[\s\S]*?\*/',
            'java': r'//.*$|/\*[\s\S]*?\*/',
            'c': r'//.*$|/\*[\s\S]*?\*/',
            'cpp': r'//.*$|/\*[\s\S]*?\*/'
        }
        
        pattern = comment_patterns.get(language.lower(), r'#.*$|//.*$|/\*[\s\S]*?\*/')
        comments = re.findall(pattern, code_content, re.MULTILINE)
        
        for i, comment in enumerate(comments):
            comment_text = re.sub(r'^[#/\*\s]+|[\*/\s]+, '', comment).strip()')
            if comment_text:
                comment_id = f"comment_{i}_{hashlib.md5(comment_text.encode()).hexdigest()[:8]}"
                
                entity = Entity(
                    id=comment_id,
                    text=comment_text,
                    entity_type=EntityType.CONCEPT,
                    confidence=0.7,
                    source_modality=ModalityType.CODE,
                    attributes={
                        "code_type": "comment",
                        "language": language,
                        "original_comment": comment
                    }
                )
                entities.append(entity)
        
        # Extract from comments and string literals using text extraction
        all_text = " ".join(comments)
        if all_text.strip():
            text_result = await self._extract_from_text(all_text, options)
            
            for entity in text_result.entities:
                entity.id = f"code_text_{entity.id}"
                entity.source_modality = ModalityType.CODE
                entity.attributes.update({
                    "source": "code_comments",
                    "language": language
                })
                entities.append(entity)
        
        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            modality=ModalityType.CODE,
            source_info={"language": language, "lines": code_content.count('\n') + 1},
            processing_time=0.0,
            metadata={"programming_language": language}
        )
    
    async def _enhance_extraction_result(
        self, 
        result: ExtractionResult, 
        options: Dict[str, Any]
    ) -> ExtractionResult:
        """Post-process and enhance extraction results"""
        
        # Deduplicate entities based on similarity
        result.entities = await self._deduplicate_entities(result.entities)
        
        # Enhance entities with additional embeddings if not present
        for entity in result.entities:
            if entity.embeddings is None:
                try:
                    entity.embeddings = self.models['sentence_transformer'].encode([entity.text])[0]
                except:
                    pass
        
        # Filter low-confidence results if requested
        min_confidence = options.get('min_confidence', 0.0)
        if min_confidence > 0:
            result.entities = [e for e in result.entities if e.confidence >= min_confidence]
            result.relationships = [r for r in result.relationships if r.confidence >= min_confidence]
        
        # Add cross-modal relationships if multiple modalities involved
        if len(set(e.source_modality for e in result.entities)) > 1:
            cross_modal_rels = await self._find_cross_modal_relationships(result.entities)
            result.relationships.extend(cross_modal_rels)
        
        # Sort entities and relationships by confidence
        result.entities.sort(key=lambda x: x.confidence, reverse=True)
        result.relationships.sort(key=lambda x: x.confidence, reverse=True)
        
        return result
    
    async def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities based on text similarity"""
        if len(entities) <= 1:
            return entities
        
        # Create embeddings matrix for similarity comparison
        embeddings_list = []
        valid_entities = []
        
        for entity in entities:
            if entity.embeddings is not None:
                embeddings_list.append(entity.embeddings)
                valid_entities.append(entity)
        
        if len(embeddings_list) <= 1:
            return entities
        
        # Compute pairwise similarities
        embeddings_matrix = np.array(embeddings_list)
        similarities = np.dot(embeddings_matrix, embeddings_matrix.T)
        
        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings_matrix, axis=1)
        similarities = similarities / np.outer(norms, norms)
        
        # Find duplicates (similarity > threshold)
        threshold = 0.95
        to_remove = set()
        
        for i in range(len(valid_entities)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(valid_entities)):
                if j in to_remove:
                    continue
                if similarities[i, j] > threshold:
                    # Keep the one with higher confidence
                    if valid_entities[i].confidence >= valid_entities[j].confidence:
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
                        break
        
        # Return entities excluding duplicates
        deduplicated = [entity for i, entity in enumerate(valid_entities) if i not in to_remove]
        
        # Add back entities without embeddings
        deduplicated.extend([entity for entity in entities if entity.embeddings is None])
        
        return deduplicated
    
    async def _find_cross_modal_relationships(self, entities: List[Entity]) -> List[Relationship]:
        """Find relationships between entities from different modalities"""
        relationships = []
        
        # Group entities by modality
        modality_groups = {}
        for entity in entities:
            modality = entity.source_modality
            if modality not in modality_groups:
                modality_groups[modality] = []
            modality_groups[modality].append(entity)
        
        # Find cross-modal similarities
        for modality1, entities1 in modality_groups.items():
            for modality2, entities2 in modality_groups.items():
                if modality1 >= modality2:  # Avoid duplicates
                    continue
                
                for entity1 in entities1:
                    for entity2 in entities2:
                        if (entity1.embeddings is not None and 
                            entity2.embeddings is not None):
                            
                            # Calculate similarity
                            similarity = np.dot(entity1.embeddings, entity2.embeddings) / (
                                np.linalg.norm(entity1.embeddings) * np.linalg.norm(entity2.embeddings)
                            )
                            
                            # Create relationship if similarity is high enough
                            if similarity > 0.8:
                                rel_id = f"cross_modal_{entity1.id}_{entity2.id}"
                                
                                relationship = Relationship(
                                    id=rel_id,
                                    subject_id=entity1.id,
                                    predicate=RelationshipType.SIMILAR_TO,
                                    object_id=entity2.id,
                                    confidence=float(similarity),
                                    attributes={
                                        "relationship_type": "cross_modal_similarity",
                                        "modality1": modality1.value,
                                        "modality2": modality2.value
                                    }
                                )
                                relationships.append(relationship)
        
        return relationships
    
    # Helper methods for mapping and utility functions
    
    def _map_spacy_label(self, spacy_label: str) -> EntityType:
        """Map SpaCy entity labels to our EntityType enum"""
        mapping = {
            "PERSON": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "GPE": EntityType.LOCATION,
            "LOC": EntityType.LOCATION,
            "EVENT": EntityType.EVENT,
            "PRODUCT": EntityType.PRODUCT,
            "DATE": EntityType.TEMPORAL,
            "TIME": EntityType.TEMPORAL,
            "MONEY": EntityType.NUMERIC,
            "PERCENT": EntityType.NUMERIC,
            "QUANTITY": EntityType.NUMERIC,
            "ORDINAL": EntityType.NUMERIC,
            "CARDINAL": EntityType.NUMERIC,
        }
        return mapping.get(spacy_label, EntityType.CONCEPT)
    
    def _map_bert_label(self, bert_label: str) -> EntityType:
        """Map BERT NER labels to our EntityType enum"""
        mapping = {
            "PER": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "LOC": EntityType.LOCATION,
            "MISC": EntityType.CONCEPT,
        }
        return mapping.get(bert_label, EntityType.CONCEPT)
    
    def _map_predicate(self, predicate: str) -> RelationshipType:
        """Map extracted predicates to our RelationshipType enum"""
        predicate_lower = predicate.lower()
        
        mapping = {
            "is": RelationshipType.IS_A,
            "is a": RelationshipType.IS_A,
            "part of": RelationshipType.PART_OF,
            "located at": RelationshipType.LOCATED_AT,
            "located in": RelationshipType.LOCATED_AT,
            "occurs at": RelationshipType.OCCURS_AT,
            "caused by": RelationshipType.CAUSED_BY,
            "contains": RelationshipType.CONTAINS,
            "similar to": RelationshipType.SIMILAR_TO,
            "depends on": RelationshipType.DEPENDS_ON,
        }
        
        for key, value in mapping.items():
            if key in predicate_lower:
                return value
        
        return RelationshipType.RELATED_TO
    
    def _parse_rebel_output(self, rebel_text: str) -> List[Tuple[str, str, str]]:
        """Parse REBEL model output into triplets"""
        triplets = []
        
        # REBEL outputs in format: <triplet> subject <subj> object <obj> <triplet> ...
        import re
        
        # Extract triplets using regex
        pattern = r'<triplet>\s*([^<]+?)\s*<subj>\s*([^<]+?)\s*<obj>\s*([^<]+?)(?=\s*<triplet>|$)'
        matches = re.findall(pattern, rebel_text)
        
        for match in matches:
            subject, predicate, obj = match
            triplets.append((subject.strip(), predicate.strip(), obj.strip()))
        
        return triplets
    
    def _calculate_spatial_relationship(
        self, 
        box1: Tuple[int, int, int, int], 
        box2: Tuple[int, int, int, int]
    ) -> Optional[str]:
        """Calculate spatial relationship between two bounding boxes"""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Calculate centers
        center1_x, center1_y = (x1_min + x1_max) / 2, (y1_min + y1_max) / 2
        center2_x, center2_y = (x2_min + x2_max) / 2, (y2_min + y2_max) / 2
        
        # Determine relative positions
        if center1_x < center2_x - 50:  # threshold for "left of"
            if center1_y < center2_y - 50:
                return "top_left_of"
            elif center1_y > center2_y + 50:
                return "bottom_left_of"
            else:
                return "left_of"
        elif center1_x > center2_x + 50:
            if center1_y < center2_y - 50:
                return "top_right_of"
            elif center1_y > center2_y + 50:
                return "bottom_right_of"
            else:
                return "right_of"
        else:  # roughly same x position
            if center1_y < center2_y - 50:
                return "above"
            elif center1_y > center2_y + 50:
                return "below"
        
        return "near"  # Default for close objects
    
    def _infer_entity_type_from_key(self, key: str) -> EntityType:
        """Infer entity type from dictionary key"""
        key_lower = key.lower()
        
        if any(word in key_lower for word in ['name', 'title', 'person', 'author', 'user']):
            return EntityType.PERSON
        elif any(word in key_lower for word in ['company', 'org', 'organization', 'business']):
            return EntityType.ORGANIZATION
        elif any(word in key_lower for word in ['location', 'address', 'city', 'country', 'place']):
            return EntityType.LOCATION
        elif any(word in key_lower for word in ['date', 'time', 'when', 'created', 'updated']):
            return EntityType.TEMPORAL
        elif any(word in key_lower for word in ['price', 'cost', 'amount', 'number', 'count', 'id']):
            return EntityType.NUMERIC
        elif any(word in key_lower for word in ['product', 'item', 'service']):
            return EntityType.PRODUCT
        elif any(word in key_lower for word in ['event', 'meeting', 'conference', 'activity']):
            return EntityType.EVENT
        else:
            return EntityType.CONCEPT
    
    def _calculate_structure_depth(self, data: Any, current_depth: int = 0) -> int:
        """Calculate the maximum depth of a nested data structure"""
        if isinstance(data, dict):
            if not data:
                return current_depth
            return max(self._calculate_structure_depth(v, current_depth + 1) for v in data.values())
        elif isinstance(data, list):
            if not data:
                return current_depth
            return max(self._calculate_structure_depth(item, current_depth + 1) for item in data)
        else:
            return current_depth
    
    def _detect_code_language(self, code: str) -> str:
        """Detect programming language from code content"""
        # Simple heuristic-based language detection
        code_lower = code.lower()
        
        if 'def ' in code and 'import ' in code:
            return 'python'
        elif 'function ' in code or 'const ' in code or 'let ' in code:
            return 'javascript'
        elif 'public class ' in code or 'import java' in code:
            return 'java'
        elif '#include' in code or 'int main(' in code:
            return 'c'
        elif '#include' in code and ('std::' in code or 'using namespace' in code):
            return 'cpp'
        elif 'SELECT ' in code.upper() and 'FROM ' in code.upper():
            return 'sql'
        else:
            return 'unknown'


# Example usage and configuration
class ExtractorConfig:
    """Configuration class for the multi-modal extractor"""
    
    DEFAULT_CONFIG = {
        "batch_size": 16,
        "max_sequence_length": 512,
        "min_confidence": 0.5,
        "enable_caching": True,
        "cache_ttl": 3600,  # 1 hour
        "max_entities_per_modality": 100,
        "enable_cross_modal_relationships": True,
        "similarity_threshold": 0.8,
        "enable_deduplication": True,
        "deduplication_threshold": 0.95,
    }
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get default configuration"""
        return cls.DEFAULT_CONFIG.copy()
    
    @classmethod
    def create_config(cls, **overrides) -> Dict[str, Any]:
        """Create configuration with overrides"""
        config = cls.get_default_config()
        config.update(overrides)
        return config


# Factory function for easy instantiation
async def create_multi_modal_extractor(config: Optional[Dict[str, Any]] = None) -> MultiModalExtractor:
    """
    Factory function to create and initialize a MultiModalExtractor
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Initialized MultiModalExtractor instance
    """
    if config is None:
        config = ExtractorConfig.get_default_config()
    
    extractor = MultiModalExtractor(config)
    await extractor._initialize_models()  # Ensure models are loaded
    
    return extractor


# Example usage
if __name__ == "__main__":
    async def example_usage():
        """Example of how to use the MultiModalExtractor"""
        
        # Create extractor with custom config
        config = ExtractorConfig.create_config(
            min_confidence=0.7,
            enable_deduplication=True
        )
        
        extractor = await create_multi_modal_extractor(config)
        
        # Extract from text
        text = "Apple Inc. was founded by Steve Jobs in Cupertino, California."
        text_result = await extractor.extract(text, ModalityType.TEXT)
        
        print(f"Text entities: {len(text_result.entities)}")
        print(f"Text relationships: {len(text_result.relationships)}")
        
        # Extract from structured data
        data = {
            "name": "John Doe",
            "company": "Tech Corp",
            "location": "San Francisco",
            "projects": [
                {"name": "Project A", "status": "completed"},
                {"name": "Project B", "status": "in_progress"}
            ]
        }
        structured_result = await extractor.extract(data, ModalityType.STRUCTURED)

        print(f"Structured entities: {len(structured_result.entities)}")
        print(f"Structured relationships: {len(structured_result.relationships)}")

        # Example: Save results to JSON
        def serialize_result(result: ExtractionResult) -> Dict[str, Any]:
            """Convert ExtractionResult to JSON-serializable dict"""
            return {
                "entities": [
                    {
                        "id": e.id,
                        "text": e.text,
                        "entity_type": e.entity_type.value,
                        "confidence": e.confidence,
                        "attributes": e.attributes,
                        "source_modality": e.source_modality.value,
                        "bounding_box": e.bounding_box,
                        "timestamp": e.timestamp,
                    }
                    for e in result.entities
                ],
                "relationships": [
                    {
                        "id": r.id,
                        "subject_id": r.subject_id,
                        "predicate": r.predicate.value,
                        "object_id": r.object_id,
                        "confidence": r.confidence,
                        "evidence": r.evidence,
                        "source_modality": r.source_modality.value,
                        "timestamp": r.timestamp,
                        "attributes": r.attributes,
                    }
                    for r in result.relationships
                ],
                "modality": result.modality.value,
                "source_info": result.source_info,
                "processing_time": result.processing_time,
                "metadata": result.metadata,
            }

        with open("extraction_results.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "text_extraction": serialize_result(text_result),
                    "structured_extraction": serialize_result(structured_result),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print("Extraction results saved to extraction_results.json")

    asyncio.run(example_usage())