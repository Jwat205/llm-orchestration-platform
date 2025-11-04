"""
Enhanced text processor with entity and relationship extraction.
"""
import re
from typing import List, Dict, Any
from dataclasses import dataclass
import logging

@dataclass
class TextProcessingResult:
    cleaned_text: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class TextProcessor:
    """Enhanced text processor with graph-aware capabilities."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> TextProcessingResult:
        """Process text with entity and relationship extraction."""
        try:
            cleaned_text = self._clean_text(text)
            entities = self._extract_entities(cleaned_text)
            relationships = self._extract_relationships(cleaned_text, entities)
            processing_metadata = self._generate_metadata(cleaned_text, metadata or {})
            
            return TextProcessingResult(
                cleaned_text=cleaned_text,
                entities=entities,
                relationships=relationships,
                metadata=processing_metadata
            )
        except Exception as e:
            self.logger.error(f"Error processing text: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text while preserving entity boundaries."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but preserve sentence structure
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        # Normalize punctuation spacing
        text = re.sub(r'\s*([\.!\?])\s*', r'\1 ', text)
        return text.strip()
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities from text."""
        entities = []
        
        # Simple regex patterns for common entities
        patterns = {
            'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'PHONE': r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b',
            'URL': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            'DATE': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
            'MONEY': r'\$\d+(?:,\d{3})*(?:\.\d{2})?',
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append({
                    'text': match.group(),
                    'type': entity_type,
                    'start': match.start(),
                    'end': match.end(),
                    'confidence': 0.8
                })
        
        return entities
    
    def _extract_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between entities."""
        relationships = []
        
        # Simple co-occurrence based relationships
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                distance = abs(entity1['start'] - entity2['start'])
                if distance < 100:  # Entities within 100 characters
                    relationships.append({
                        'source': entity1['text'],
                        'target': entity2['text'],
                        'type': 'CO_OCCURS',
                        'strength': max(0.1, 1.0 - (distance / 100.0)),
                        'context': text[max(0, min(entity1['start'], entity2['start']) - 50):
                                      max(entity1['end'], entity2['end']) + 50]
                    })
        
        return relationships
    
    def _generate_metadata(self, text: str, base_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate processing metadata."""
        metadata = base_metadata.copy()
        metadata.update({
            'text_length': len(text),
            'word_count': len(text.split()),
            'sentence_count': len(re.split(r'[.!?]+', text)),
            'paragraph_count': len(text.split('\n\n')),
            'processing_timestamp': None  # Would add actual timestamp
        })
        return metadata