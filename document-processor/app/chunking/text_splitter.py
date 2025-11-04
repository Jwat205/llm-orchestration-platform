"""
Text splitter with multiple splitting strategies and configurable options.
"""

import re
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class TextChunk:
    """Represents a chunk of text with metadata"""
    content: str
    start_index: int
    end_index: int
    chunk_id: str
    metadata: Dict[str, Any]

class BaseSplitter(ABC):
    """Abstract base class for text splitters"""
    
    @abstractmethod
    def split(self, text: str) -> List[TextChunk]:
        """Split text into chunks"""
        pass

class RecursiveCharacterTextSplitter(BaseSplitter):
    """Recursively split text by different separators"""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 separators: List[str] = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
    
    def split(self, text: str) -> List[TextChunk]:
        """Split text recursively using separators"""
        chunks = []
        splits = self._split_text(text, self.separators)
        
        current_chunk = ""
        current_start = 0
        chunk_id = 0
        
        for split in splits:
            if len(current_chunk) + len(split) <= self.chunk_size:
                current_chunk += split
            else:
                if current_chunk:
                    chunk = TextChunk(
                        content=current_chunk.strip(),
                        start_index=current_start,
                        end_index=current_start + len(current_chunk),
                        chunk_id=f"chunk_{chunk_id:04d}",
                        metadata={"method": "recursive_character"}
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                
                # Handle overlap
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + split
                current_start = current_start + overlap_start
        
        # Add final chunk
        if current_chunk.strip():
            chunk = TextChunk(
                content=current_chunk.strip(),
                start_index=current_start,
                end_index=current_start + len(current_chunk),
                chunk_id=f"chunk_{chunk_id:04d}",
                metadata={"method": "recursive_character"}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text by separators"""
        if not separators:
            return [text]
        
        separator = separators[0]
        splits = text.split(separator)
        
        if len(splits) == 1:
            return self._split_text(text, separators[1:])
        
        result = []
        for split in splits:
            if len(split) <= self.chunk_size:
                result.append(split)
            else:
                result.extend(self._split_text(split, separators[1:]))
        
        return result

class SentenceTextSplitter(BaseSplitter):
    """Split text by sentences"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split(self, text: str) -> List[TextChunk]:
        """Split text by sentences"""
        sentences = self._split_into_sentences(text)
        chunks = []
        
        current_chunk = ""
        current_sentences = []
        chunk_id = 0
        start_pos = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + " "
                current_sentences.append(sentence)
            else:
                if current_chunk:
                    chunk = TextChunk(
                        content=current_chunk.strip(),
                        start_index=start_pos,
                        end_index=start_pos + len(current_chunk),
                        chunk_id=f"sentence_chunk_{chunk_id:04d}",
                        metadata={
                            "method": "sentence",
                            "sentence_count": len(current_sentences)
                        }
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                
                # Handle overlap
                overlap_sentences = max(1, self.chunk_overlap // 100)
                overlap_text = " ".join(current_sentences[-overlap_sentences:])
                current_chunk = overlap_text + " " + sentence + " "
                current_sentences = current_sentences[-overlap_sentences:] + [sentence]
                start_pos += len(current_chunk) - len(overlap_text) - len(sentence) - 2
        
        # Add final chunk
        if current_chunk.strip():
            chunk = TextChunk(
                content=current_chunk.strip(),
                start_index=start_pos,
                end_index=start_pos + len(current_chunk),
                chunk_id=f"sentence_chunk_{chunk_id:04d}",
                metadata={
                    "method": "sentence",
                    "sentence_count": len(current_sentences)
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using regex"""
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        return [s.strip() for s in sentences if s.strip()]

class ParagraphTextSplitter(BaseSplitter):
    """Split text by paragraphs"""
    
    def __init__(self, max_chunk_size: int = 2000):
        self.max_chunk_size = max_chunk_size
    
    def split(self, text: str) -> List[TextChunk]:
        """Split text by paragraphs"""
        paragraphs = text.split('\n\n')
        chunks = []
        chunk_id = 0
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            start_pos = text.find(paragraph)
            
            if len(paragraph) <= self.max_chunk_size:
                chunk = TextChunk(
                    content=paragraph,
                    start_index=start_pos,
                    end_index=start_pos + len(paragraph),
                    chunk_id=f"para_chunk_{chunk_id:04d}",
                    metadata={
                        "method": "paragraph",
                        "paragraph_index": i
                    }
                )
                chunks.append(chunk)
                chunk_id += 1
            else:
                # Split large paragraphs further
                sub_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.max_chunk_size
                )
                sub_chunks = sub_splitter.split(paragraph)
                
                for sub_chunk in sub_chunks:
                    sub_chunk.chunk_id = f"para_chunk_{chunk_id:04d}"
                    sub_chunk.metadata.update({
                        "method": "paragraph_recursive",
                        "paragraph_index": i
                    })
                    chunks.append(sub_chunk)
                    chunk_id += 1
        
        return chunks

class TokenTextSplitter(BaseSplitter):
    """Split text by tokens (approximated by word count)"""
    
    def __init__(self, 
                 chunk_size: int = 500,
                 chunk_overlap: int = 50,
                 tokens_per_word: float = 1.3):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokens_per_word = tokens_per_word
    
    def split(self, text: str) -> List[TextChunk]:
        """Split text by estimated token count"""
        words = text.split()
        chunks = []
        chunk_id = 0
        
        words_per_chunk = int(self.chunk_size / self.tokens_per_word)
        overlap_words = int(self.chunk_overlap / self.tokens_per_word)
        
        for i in range(0, len(words), words_per_chunk - overlap_words):
            chunk_words = words[i:i + words_per_chunk]
            chunk_content = " ".join(chunk_words)
            
            # Find start position in original text
            if i == 0:
                start_pos = 0
            else:
                start_phrase = " ".join(words[i:i+5])  # Use first 5 words to find position
                start_pos = text.find(start_phrase)
            
            chunk = TextChunk(
                content=chunk_content,
                start_index=start_pos,
                end_index=start_pos + len(chunk_content),
                chunk_id=f"token_chunk_{chunk_id:04d}",
                metadata={
                    "method": "token",
                    "estimated_tokens": len(chunk_words) * self.tokens_per_word,
                    "word_count": len(chunk_words)
                }
            )
            chunks.append(chunk)
            chunk_id += 1
        
        return chunks

class CustomTextSplitter(BaseSplitter):
    """Custom text splitter with user-defined splitting function"""
    
    def __init__(self, 
                 split_function: Callable[[str], List[str]],
                 chunk_size: int = 1000,
                 metadata_extractor: Callable[[str, int], Dict[str, Any]] = None):
        self.split_function = split_function
        self.chunk_size = chunk_size
        self.metadata_extractor = metadata_extractor or (lambda x, i: {})
    
    def split(self, text: str) -> List[TextChunk]:
        """Split text using custom function"""
        splits = self.split_function(text)
        chunks = []
        chunk_id = 0
        
        for i, split in enumerate(splits):
            start_pos = text.find(split)
            
            chunk = TextChunk(
                content=split,
                start_index=start_pos,
                end_index=start_pos + len(split),
                chunk_id=f"custom_chunk_{chunk_id:04d}",
                metadata={
                    "method": "custom",
                    **self.metadata_extractor(split, i)
                }
            )
            chunks.append(chunk)
            chunk_id += 1
        
        return chunks

class TextSplitterFactory:
    """Factory for creating text splitters"""
    
    @staticmethod
    def create_splitter(splitter_type: str, **kwargs) -> BaseSplitter:
        """Create a text splitter of the specified type"""
        splitters = {
            "recursive": RecursiveCharacterTextSplitter,
            "sentence": SentenceTextSplitter,
            "paragraph": ParagraphTextSplitter,
            "token": TokenTextSplitter,
            "custom": CustomTextSplitter
        }
        
        if splitter_type not in splitters:
            raise ValueError(f"Unknown splitter type: {splitter_type}")
        
        return splitters[splitter_type](**kwargs)
    
    @staticmethod
    def get_available_splitters() -> List[str]:
        """Get list of available splitter types"""
        return ["recursive", "sentence", "paragraph", "token", "custom"]