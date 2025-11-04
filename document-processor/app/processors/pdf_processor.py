"""
Enhanced PDF processor with graph-aware processing capabilities.
Extracts text, metadata, and structural information from PDF documents
for knowledge graph construction and semantic analysis.
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import fitz  # PyMuPDF
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import spacy
from transformers import pipeline
import logging

logger = logging.getLogger(__name__)

@dataclass
class PDFMetadata:
    """Metadata extracted from PDF documents"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    page_count: int = 0
    file_size: int = 0

@dataclass
class PDFSection:
    """Represents a section of a PDF document"""
    content: str
    page_number: int
    section_type: str  # header, paragraph, table, figure, etc.
    bbox: Optional[Tuple[float, float, float, float]] = None
    font_info: Optional[Dict[str, Any]] = None

@dataclass
class PDFProcessingResult:
    """Result of PDF processing operation"""
    text_content: str
    sections: List[PDFSection]
    metadata: PDFMetadata
    entities: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    structure: Dict[str, Any]

class PDFProcessor:
    """Enhanced PDF processor with graph-aware capabilities"""
    
    def __init__(self, 
                 enable_ocr: bool = True,
                 extract_images: bool = True,
                 extract_tables: bool = True,
                 language_model: str = "en_core_web_sm"):
        """
        Initialize PDF processor
        
        Args:
            enable_ocr: Enable OCR for scanned documents
            extract_images: Extract and process images
            extract_tables: Extract table structures
            language_model: SpaCy model for NLP processing
        """
        self.enable_ocr = enable_ocr
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        
        # Load NLP models
        try:
            self.nlp = spacy.load(language_model)
        except OSError:
            logger.warning(f"Language model {language_model} not found. Using basic English model.")
            self.nlp = spacy.load("en_core_web_sm")
        
        # Initialize transformer pipeline for advanced entity extraction
        self.ner_pipeline = pipeline("ner", 
                                    model="dbmdz/bert-large-cased-finetuned-conll03-english",
                                    aggregation_strategy="simple")
        
        # Initialize text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ";", ",", " ", ""]
        )
    
    async def process_pdf(self, file_path: str) -> PDFProcessingResult:
        """
        Process PDF document with comprehensive extraction
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            PDFProcessingResult containing all extracted information
        """
        try:
            # Open PDF document
            doc = fitz.open(file_path)
            
            # Extract metadata
            metadata = self._extract_metadata(doc)
            
            # Extract text and structure
            sections = []
            full_text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Extract text with structure information
                page_sections = await self._extract_page_structure(page, page_num)
                sections.extend(page_sections)
                
                # Accumulate full text
                page_text = page.get_text()
                full_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            
            # Extract entities using multiple methods
            entities = await self._extract_entities(full_text)
            
            # Extract tables if enabled
            tables = []
            if self.extract_tables:
                tables = await self._extract_tables(doc)
            
            # Extract images if enabled
            images = []
            if self.extract_images:
                images = await self._extract_images(doc)
            
            # Build document structure
            structure = self._build_document_structure(sections)
            
            doc.close()
            
            return PDFProcessingResult(
                text_content=full_text,
                sections=sections,
                metadata=metadata,
                entities=entities,
                tables=tables,
                images=images,
                structure=structure
            )
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
    
    def _extract_metadata(self, doc: fitz.Document) -> PDFMetadata:
        """Extract metadata from PDF document"""
        metadata_dict = doc.metadata
        
        return PDFMetadata(
            title=metadata_dict.get("title"),
            author=metadata_dict.get("author"),
            subject=metadata_dict.get("subject"),
            creator=metadata_dict.get("creator"),
            producer=metadata_dict.get("producer"),
            creation_date=metadata_dict.get("creationDate"),
            modification_date=metadata_dict.get("modDate"),
            page_count=len(doc),
            file_size=Path(doc.name).stat().st_size if doc.name else 0
        )
    
    async def _extract_page_structure(self, page: fitz.Page, page_num: int) -> List[PDFSection]:
        """Extract structured content from a page"""
        sections = []
        
        # Get text blocks with formatting information
        blocks = page.get_text("dict")
        
        for block in blocks["blocks"]:
            if "lines" in block:  # Text block
                block_text = ""
                font_sizes = []
                font_names = []
                
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"]
                        font_sizes.append(span["size"])
                        font_names.append(span["font"])
                    block_text += line_text + "\n"
                
                if block_text.strip():
                    # Determine section type based on formatting
                    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12
                    section_type = self._classify_section_type(block_text, avg_font_size)
                    
                    sections.append(PDFSection(
                        content=block_text.strip(),
                        page_number=page_num + 1,
                        section_type=section_type,
                        bbox=(block["bbox"][0], block["bbox"][1], block["bbox"][2], block["bbox"][3]),
                        font_info={
                            "avg_size": avg_font_size,
                            "fonts": list(set(font_names))
                        }
                    ))
        
        return sections
    
    def _classify_section_type(self, text: str, font_size: float) -> str:
        """Classify section type based on content and formatting"""
        text_lower = text.lower().strip()
        
        # Check for headers based on font size and content
        if font_size > 14 or (len(text.split()) < 10 and text.isupper()):
            return "header"
        
        # Check for common section indicators
        if any(text_lower.startswith(indicator) for indicator in 
               ["abstract", "introduction", "conclusion", "references", "bibliography"]):
            return "section_header"
        
        # Check for list items
        if text_lower.startswith(("•", "-", "*")) or text_lower.startswith(tuple(f"{i}." for i in range(1, 100))):
            return "list_item"
        
        # Check for table-like content
        if "\t" in text or (text.count("|") > 2 and len(text.split("\n")) > 1):
            return "table"
        
        # Default to paragraph
        return "paragraph"
    
    async def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using multiple NLP approaches"""
        entities = []
        
        # SpaCy NER
        doc = self.nlp(text[:1000000])  # Limit text size for processing
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 1.0,
                "method": "spacy"
            })
        
        # Transformer-based NER for enhanced extraction
        chunks = self.text_splitter.split_text(text)
        for chunk in chunks[:10]:  # Limit processing for performance
            try:
                ner_results = self.ner_pipeline(chunk)
                for result in ner_results:
                    entities.append({
                        "text": result["word"],
                        "label": result["entity_group"],
                        "start": result["start"],
                        "end": result["end"],
                        "confidence": result["score"],
                        "method": "transformer"
                    })
            except Exception as e:
                logger.warning(f"Error in transformer NER: {str(e)}")
        
        return entities
    
    async def _extract_tables(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract table structures from PDF"""
        tables = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Find table-like structures using text analysis
            blocks = page.get_text("dict")
            
            for block in blocks["blocks"]:
                if "lines" in block:
                    text = ""
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text += span["text"]
                        text += "\n"
                    
                    # Simple table detection heuristic
                    lines = text.strip().split("\n")
                    if len(lines) > 2:
                        # Check for consistent column structure
                        tab_counts = [line.count("\t") for line in lines if line.strip()]
                        if tab_counts and max(tab_counts) > 1 and len(set(tab_counts)) <= 2:
                            tables.append({
                                "page": page_num + 1,
                                "content": text,
                                "bbox": block["bbox"],
                                "rows": len(lines),
                                "columns": max(tab_counts) + 1
                            })
        
        return tables
    
    async def _extract_images(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract image information from PDF"""
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                images.append({
                    "page": page_num + 1,
                    "index": img_index,
                    "xref": img[0],
                    "smask": img[1],
                    "width": img[2],
                    "height": img[3],
                    "bpc": img[4],
                    "colorspace": img[5],
                    "alt": img[6],
                    "name": img[7],
                    "filter": img[8]
                })
        
        return images
    
    def _build_document_structure(self, sections: List[PDFSection]) -> Dict[str, Any]:
        """Build hierarchical document structure"""
        structure = {
            "sections": [],
            "headers": [],
            "paragraphs": [],
            "tables": [],
            "lists": []
        }
        
        current_section = None
        
        for section in sections:
            if section.section_type == "header":
                current_section = {
                    "title": section.content,
                    "page": section.page_number,
                    "subsections": []
                }
                structure["sections"].append(current_section)
                structure["headers"].append(section.content)
            
            elif section.section_type == "paragraph":
                structure["paragraphs"].append({
                    "content": section.content,
                    "page": section.page_number,
                    "section": current_section["title"] if current_section else None
                })
            
            elif section.section_type == "table":
                structure["tables"].append({
                    "content": section.content,
                    "page": section.page_number
                })
            
            elif section.section_type == "list_item":
                structure["lists"].append({
                    "content": section.content,
                    "page": section.page_number
                })
        
        return structure

    async def process_batch(self, file_paths: List[str]) -> List[PDFProcessingResult]:
        """Process multiple PDF files in batch"""
        tasks = [self.process_pdf(file_path) for file_path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing {file_paths[i]}: {str(result)}")
            else:
                processed_results.append(result)
        
        return processed_results