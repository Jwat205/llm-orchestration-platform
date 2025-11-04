"""
Multi-Modal Entity and Relationship Extractor
Handles extraction from various modalities: text, images, audio, video, and documents.
"""
import asyncio
from typing import List, Dict, Any, Optional, Union, BinaryIO
import logging
from dataclasses import dataclass
from enum import Enum
import base64
import io
from pathlib import Path
import tempfile
import os

# Optional imports for different modalities
try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    import speech_recognition as sr
    HAS_SPEECH = True
except ImportError:
    HAS_SPEECH = False

try:
    import cv2
    import numpy as np
    HAS_VIDEO = True
except ImportError:
    HAS_VIDEO = False

try:
    from pdf2image import convert_from_path
    import fitz  # PyMuPDF
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from transformers import pipeline, BlipProcessor, BlipForConditionalGeneration
    import torch
    HAS_VISION_MODELS = True
except ImportError:
    HAS_VISION_MODELS = False

logger = logging.getLogger(__name__)

class Modality(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    DOCUMENT = "document"

@dataclass
class MultiModalEntity:
    text: str
    entity_type: str
    confidence: float
    modality: Modality
    source_info: Dict[str, Any]
    bbox: Optional[Dict[str, int]] = None  # Bounding box for image/video
    timestamp: Optional[float] = None  # Timestamp for audio/video
    page_number: Optional[int] = None  # Page number for documents

@dataclass
class MultiModalRelationship:
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    modality: Modality
    context: str
    source_info: Dict[str, Any]

class MultiModalExtractor:
    """Extract entities and relationships from multiple modalities"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Vision models
        self.image_captioning_model = None
        self.image_captioning_processor = None
        self.ocr_engine = None
        
        # Audio processing
        self.speech_recognizer = None
        
        # Configuration
        self.supported_image_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        self.supported_audio_formats = {'.wav', '.mp3', '.flac', '.m4a'}
        self.supported_video_formats = {'.mp4', '.avi', '.mkv', '.mov'}
        self.supported_document_formats = {'.pdf', '.docx', '.txt'}
        
        # Processing parameters
        self.ocr_confidence_threshold = self.config.get("ocr_confidence_threshold", 60)
        self.speech_confidence_threshold = self.config.get("speech_confidence_threshold", 0.7)
        self.image_caption_max_length = self.config.get("image_caption_max_length", 50)
        
    async def initialize(self):
        """Initialize multi-modal processing capabilities"""
        try:
            logger.info("Initializing multi-modal extractor...")
            
            # Initialize vision models if available
            if HAS_VISION_MODELS:
                await self._initialize_vision_models()
            
            # Initialize OCR if available
            if HAS_OCR:
                await self._initialize_ocr()
            
            # Initialize speech recognition if available
            if HAS_SPEECH:
                await self._initialize_speech_recognition()
            
            logger.info("Multi-modal extractor initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing multi-modal extractor: {e}")
            raise
    
    async def _initialize_vision_models(self):
        """Initialize vision models for image processing"""
        try:
            # Initialize BLIP for image captioning
            model_name = self.config.get("vision_model", "Salesforce/blip-image-captioning-base")
            self.image_captioning_processor = BlipProcessor.from_pretrained(model_name)
            self.image_captioning_model = BlipForConditionalGeneration.from_pretrained(model_name)
            
            if torch.cuda.is_available():
                self.image_captioning_model = self.image_captioning_model.cuda()
            
            logger.info("Vision models initialized")
        except Exception as e:
            logger.error(f"Error initializing vision models: {e}")
    
    async def _initialize_ocr(self):
        """Initialize OCR engine"""
        try:
            # Configure Tesseract path if specified
            tesseract_path = self.config.get("tesseract_path")
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
            logger.info("OCR engine initialized")
        except Exception as e:
            logger.error(f"Error initializing OCR: {e}")
    
    async def _initialize_speech_recognition(self):
        """Initialize speech recognition"""
        try:
            self.speech_recognizer = sr.Recognizer()
            logger.info("Speech recognition initialized")
        except Exception as e:
            logger.error(f"Error initializing speech recognition: {e}")
    
    async def extract_from_file(self, file_path: str, modality: Optional[Modality] = None) -> Dict[str, Any]:
        """Extract entities and relationships from a file"""
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Auto-detect modality if not specified
            if not modality:
                modality = self._detect_modality(path)
            
            if modality == Modality.TEXT:
                return await self._extract_from_text_file(path)
            elif modality == Modality.IMAGE:
                return await self._extract_from_image(path)
            elif modality == Modality.AUDIO:
                return await self._extract_from_audio(path)
            elif modality == Modality.VIDEO:
                return await self._extract_from_video(path)
            elif modality == Modality.PDF:
                return await self._extract_from_pdf(path)
            else:
                raise ValueError(f"Unsupported modality: {modality}")
                
        except Exception as e:
            logger.error(f"Error extracting from file {file_path}: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    async def extract_from_data(self, data: Union[str, bytes, BinaryIO], modality: Modality, **kwargs) -> Dict[str, Any]:
        """Extract entities and relationships from raw data"""
        try:
            if modality == Modality.TEXT:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return await self._extract_from_text(data)
            
            elif modality == Modality.IMAGE:
                return await self._extract_from_image_data(data, **kwargs)
            
            elif modality == Modality.AUDIO:
                return await self._extract_from_audio_data(data, **kwargs)
            
            else:
                raise ValueError(f"Unsupported modality for raw data: {modality}")
                
        except Exception as e:
            logger.error(f"Error extracting from data: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    def _detect_modality(self, path: Path) -> Modality:
        """Auto-detect modality from file extension"""
        suffix = path.suffix.lower()
        
        if suffix in self.supported_image_formats:
            return Modality.IMAGE
        elif suffix in self.supported_audio_formats:
            return Modality.AUDIO
        elif suffix in self.supported_video_formats:
            return Modality.VIDEO
        elif suffix == '.pdf':
            return Modality.PDF
        else:
            return Modality.TEXT
    
    async def _extract_from_text_file(self, path: Path) -> Dict[str, Any]:
        """Extract from text file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            return await self._extract_from_text(text)
        except Exception as e:
            logger.error(f"Error reading text file: {e}")
            return {"entities": [], "relationships": []}
    
    async def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """Extract entities and relationships from text"""
        # This would integrate with existing text extractors
        # For now, return basic structure
        entities = []
        relationships = []
        
        # Basic regex-based extraction for demonstration
        import re
        
        # Extract email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        for email in emails:
            entities.append(MultiModalEntity(
                text=email,
                entity_type="EMAIL",
                confidence=0.9,
                modality=Modality.TEXT,
                source_info={"source": "regex"}
            ))
        
        # Extract URLs
        urls = re.findall(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?', text)
        for url in urls:
            entities.append(MultiModalEntity(
                text=url,
                entity_type="URL",
                confidence=0.9,
                modality=Modality.TEXT,
                source_info={"source": "regex"}
            ))
        
        return {
            "entities": entities,
            "relationships": relationships,
            "text_content": text
        }
    
    async def _extract_from_image(self, path: Path) -> Dict[str, Any]:
        """Extract entities and relationships from image"""
        entities = []
        relationships = []
        extracted_text = ""
        image_description = ""
        
        try:
            # Load image
            if HAS_OCR:
                image = Image.open(path)
                
                # OCR extraction
                if HAS_OCR:
                    ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                    extracted_text = self._process_ocr_data(ocr_data, entities)
                
                # Image captioning
                if HAS_VISION_MODELS and self.image_captioning_model:
                    image_description = await self._generate_image_caption(image)
            
            # Extract entities from text content
            if extracted_text:
                text_results = await self._extract_from_text(extracted_text)
                for entity in text_results["entities"]:
                    entity.modality = Modality.IMAGE
                    entity.source_info["ocr"] = True
                    entities.append(entity)
            
            # Extract entities from image description
            if image_description:
                desc_results = await self._extract_from_text(image_description)
                for entity in desc_results["entities"]:
                    entity.modality = Modality.IMAGE
                    entity.source_info["from_caption"] = True
                    entities.append(entity)
            
            return {
                "entities": entities,
                "relationships": relationships,
                "extracted_text": extracted_text,
                "image_description": image_description
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    async def _extract_from_image_data(self, data: bytes, **kwargs) -> Dict[str, Any]:
        """Extract from image data in memory"""
        try:
            # Save to temporary file and process
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tmp_file.write(data)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = await self._extract_from_image(tmp_path)
                return result
            finally:
                # Clean up temporary file
                if tmp_path.exists():
                    tmp_path.unlink()
                    
        except Exception as e:
            logger.error(f"Error processing image data: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    def _process_ocr_data(self, ocr_data: Dict[str, List], entities: List[MultiModalEntity]) -> str:
        """Process OCR data and extract entities with bounding boxes"""
        extracted_text = ""
        
        try:
            for i, text in enumerate(ocr_data['text']):
                confidence = int(ocr_data['conf'][i])
                
                if confidence > self.ocr_confidence_threshold and text.strip():
                    extracted_text += text + " "
                    
                    # Create entity with bounding box
                    bbox = {
                        'left': ocr_data['left'][i],
                        'top': ocr_data['top'][i],
                        'width': ocr_data['width'][i],
                        'height': ocr_data['height'][i]
                    }
                    
                    # Simple entity classification based on text patterns
                    entity_type = self._classify_ocr_text(text)
                    if entity_type:
                        entity = MultiModalEntity(
                            text=text,
                            entity_type=entity_type,
                            confidence=confidence / 100.0,
                            modality=Modality.IMAGE,
                            source_info={"ocr": True},
                            bbox=bbox
                        )
                        entities.append(entity)
        
        except Exception as e:
            logger.error(f"Error processing OCR data: {e}")
        
        return extracted_text.strip()
    
    def _classify_ocr_text(self, text: str) -> Optional[str]:
        """Classify OCR extracted text into entity types"""
        import re
        
        # Email
        if re.match(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
            return "EMAIL"
        
        # Phone number
        if re.match(r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b', text):
            return "PHONE"
        
        # URL
        if re.match(r'https?://', text):
            return "URL"
        
        # Date
        if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
            return "DATE"
        
        # Number
        if re.match(r'^\d+(\.\d+)?$', text):
            return "NUMBER"
        
        return None
    
    async def _generate_image_caption(self, image: Image.Image) -> str:
        """Generate description of image content"""
        try:
            if not self.image_captioning_model:
                return ""
            
            # Process image
            inputs = self.image_captioning_processor(image, return_tensors="pt")
            
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate caption
            with torch.no_grad():
                output = self.image_captioning_model.generate(
                    **inputs,
                    max_length=self.image_caption_max_length,
                    num_beams=5,
                    early_stopping=True
                )
            
            caption = self.image_captioning_processor.decode(output[0], skip_special_tokens=True)
            return caption
            
        except Exception as e:
            logger.error(f"Error generating image caption: {e}")
            return ""
    
    async def _extract_from_audio(self, path: Path) -> Dict[str, Any]:
        """Extract entities and relationships from audio file"""
        entities = []
        relationships = []
        transcribed_text = ""
        
        try:
            if not HAS_SPEECH:
                return {"entities": [], "relationships": [], "error": "Speech recognition not available"}
            
            # Transcribe audio to text
            transcribed_text = await self._transcribe_audio(path)
            
            if transcribed_text:
                # Extract entities from transcribed text
                text_results = await self._extract_from_text(transcribed_text)
                for entity in text_results["entities"]:
                    entity.modality = Modality.AUDIO
                    entity.source_info["transcribed"] = True
                    entities.append(entity)
                relationships = text_results["relationships"]
            
            return {
                "entities": entities,
                "relationships": relationships,
                "transcribed_text": transcribed_text
            }
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    async def _transcribe_audio(self, path: Path) -> str:
        """Transcribe audio file to text"""
        try:
            with sr.AudioFile(str(path)) as source:
                audio = self.speech_recognizer.record(source)
            
            # Use Google Speech Recognition (free tier)
            text = self.speech_recognizer.recognize_google(audio)
            return text
            
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return ""
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
            return ""
    
    async def _extract_from_audio_data(self, data: bytes, **kwargs) -> Dict[str, Any]:
        """Extract from audio data in memory"""
        try:
            # Save to temporary file and process
            audio_format = kwargs.get('format', 'wav')
            with tempfile.NamedTemporaryFile(suffix=f'.{audio_format}', delete=False) as tmp_file:
                tmp_file.write(data)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = await self._extract_from_audio(tmp_path)
                return result
            finally:
                # Clean up temporary file
                if tmp_path.exists():
                    tmp_path.unlink()
                    
        except Exception as e:
            logger.error(f"Error processing audio data: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    async def _extract_from_video(self, path: Path) -> Dict[str, Any]:
        """Extract entities and relationships from video file"""
        entities = []
        relationships = []
        
        try:
            if not HAS_VIDEO:
                return {"entities": [], "relationships": [], "error": "Video processing not available"}
            
            # Extract frames and audio from video
            frames_data = await self._extract_video_frames(path)
            audio_data = await self._extract_video_audio(path)
            
            # Process extracted content
            if frames_data:
                for frame_data in frames_data[:5]:  # Limit to first 5 frames
                    frame_results = await self._extract_from_image_data(frame_data["image_data"])
                    for entity in frame_results["entities"]:
                        entity.modality = Modality.VIDEO
                        entity.timestamp = frame_data["timestamp"]
                        entities.append(entity)
            
            if audio_data:
                audio_results = await self._extract_from_audio_data(audio_data)
                for entity in audio_results["entities"]:
                    entity.modality = Modality.VIDEO
                    entities.append(entity)
            
            return {
                "entities": entities,
                "relationships": relationships,
                "frames_processed": len(frames_data) if frames_data else 0
            }
            
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    async def _extract_video_frames(self, path: Path) -> List[Dict[str, Any]]:
        """Extract key frames from video"""
        frames = []
        
        try:
            cap = cv2.VideoCapture(str(path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Extract frames at regular intervals
            interval = max(1, frame_count // 10)  # Extract 10 frames max
            
            for i in range(0, frame_count, interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                
                if ret:
                    # Convert frame to bytes
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_data = {
                        "image_data": buffer.tobytes(),
                        "timestamp": i / fps,
                        "frame_number": i
                    }
                    frames.append(frame_data)
            
            cap.release()
            
        except Exception as e:
            logger.error(f"Error extracting video frames: {e}")
        
        return frames
    
    async def _extract_video_audio(self, path: Path) -> Optional[bytes]:
        """Extract audio track from video"""
        try:
            # This would require ffmpeg or similar tool
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error extracting video audio: {e}")
            return None
    
    async def _extract_from_pdf(self, path: Path) -> Dict[str, Any]:
        """Extract entities and relationships from PDF"""
        entities = []
        relationships = []
        
        try:
            if not HAS_PDF:
                return {"entities": [], "relationships": [], "error": "PDF processing not available"}
            
            # Extract text and images from PDF
            pdf_data = await self._process_pdf(path)
            
            # Process text content
            if pdf_data["text"]:
                text_results = await self._extract_from_text(pdf_data["text"])
                for entity in text_results["entities"]:
                    entity.modality = Modality.PDF
                    entity.source_info["from_text"] = True
                    entities.append(entity)
                relationships.extend(text_results["relationships"])
            
            # Process images in PDF
            for page_num, images in pdf_data["images"].items():
                for img_data in images:
                    img_results = await self._extract_from_image_data(img_data)
                    for entity in img_results["entities"]:
                        entity.modality = Modality.PDF
                        entity.page_number = page_num
                        entity.source_info["from_image"] = True
                        entities.append(entity)
            
            return {
                "entities": entities,
                "relationships": relationships,
                "pages_processed": pdf_data["page_count"],
                "text_content": pdf_data["text"]
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}
    
    async def _process_pdf(self, path: Path) -> Dict[str, Any]:
        """Process PDF and extract text and images"""
        result = {
            "text": "",
            "images": {},
            "page_count": 0
        }
        
        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(str(path))
            result["page_count"] = doc.page_count
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Extract text
                page_text = page.get_text()
                result["text"] += f"\n--- Page {page_num + 1} ---\n{page_text}"
                
                # Extract images
                image_list = page.get_images()
                page_images = []
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                            page_images.append(img_data)
                        
                        pix = None
                    except Exception as e:
                        logger.error(f"Error extracting image {img_index} from page {page_num}: {e}")
                
                if page_images:
                    result["images"][page_num] = page_images
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Error processing PDF with PyMuPDF: {e}")
        
        return result
    
    async def get_supported_modalities(self) -> Dict[str, List[str]]:
        """Get supported modalities and formats"""
        return {
            "text": [".txt", ".md", ".csv"],
            "image": list(self.supported_image_formats),
            "audio": list(self.supported_audio_formats) if HAS_SPEECH else [],
            "video": list(self.supported_video_formats) if HAS_VIDEO else [],
            "pdf": [".pdf"] if HAS_PDF else [],
            "document": list(self.supported_document_formats)
        }
    
    async def get_capabilities(self) -> Dict[str, bool]:
        """Get available processing capabilities"""
        return {
            "ocr": HAS_OCR,
            "speech_recognition": HAS_SPEECH,
            "video_processing": HAS_VIDEO,
            "pdf_processing": HAS_PDF,
            "vision_models": HAS_VISION_MODELS,
            "image_captioning": HAS_VISION_MODELS and self.image_captioning_model is not None
        }
    
    async def shutdown(self):
        """Cleanup resources"""
        try:
            # Clear model references
            self.image_captioning_model = None
            self.image_captioning_processor = None
            self.speech_recognizer = None
            
            # Clear CUDA cache if using GPU
            if HAS_VISION_MODELS and torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Multi-modal extractor shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")