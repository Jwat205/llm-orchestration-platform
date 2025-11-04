"""
Enhanced HTML processor with semantic extraction and graph awareness.
"""
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import re

@dataclass
class HTMLProcessingResult:
    text: str
    structured_content: Dict[str, Any]
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class HTMLProcessor:
    """Enhanced HTML processor with semantic structure extraction."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_html(self, html_content: str, base_url: Optional[str] = None) -> HTMLProcessingResult:
        """Process HTML with semantic structure and entity extraction."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract clean text
            text = self._extract_clean_text(soup)
            
            # Extract structured content
            structured_content = self._extract_structured_content(soup)
            
            # Extract entities
            entities = self._extract_html_entities(soup, text)
            
            # Extract relationships
            relationships = self._extract_html_relationships(soup, entities)
            
            # Generate metadata
            metadata = self._generate_html_metadata(soup, base_url)
            
            return HTMLProcessingResult(
                text=text,
                structured_content=structured_content,
                entities=entities,
                relationships=relationships,
                metadata=metadata
            )
        except Exception as e:
            self.logger.error(f"Error processing HTML: {e}")
            raise
    
    def _extract_clean_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from HTML while preserving structure."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text with some structure preservation
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_structured_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract structured content elements."""
        content = {
            'title': '',
            'headings': [],
            'links': [],
            'images': [],
            'tables': [],
            'lists': [],
            'forms': []
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            content['title'] = title_tag.get_text(strip=True)
        
        # Extract headings
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            content['headings'].append({
                'level': int(heading.name[1]),
                'text': heading.get_text(strip=True),
                'id': heading.get('id', ''),
                'class': heading.get('class', [])
            })
        
        # Extract links
        for link in soup.find_all('a', href=True):
            content['links'].append({
                'text': link.get_text(strip=True),
                'href': link['href'],
                'title': link.get('title', ''),
                'rel': link.get('rel', [])
            })
        
        # Extract images
        for img in soup.find_all('img'):
            content['images'].append({
                'src': img.get('src', ''),
                'alt': img.get('alt', ''),
                'title': img.get('title', ''),
                'width': img.get('width', ''),
                'height': img.get('height', '')
            })
        
        # Extract tables
        for table in soup.find_all('table'):
            rows = []
            for row in table.find_all('tr'):
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                rows.append(cells)
            content['tables'].append({'rows': rows})
        
        return content
    
    def _extract_html_entities(self, soup: BeautifulSoup, text: str) -> List[Dict[str, Any]]:
        """Extract entities from HTML structure and content."""
        entities = []
        
        # Extract structured entities from HTML elements
        # Links as entities
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            if link_text:
                entities.append({
                    'text': link_text,
                    'type': 'LINK',
                    'attributes': {
                        'href': link['href'],
                        'title': link.get('title', ''),
                        'rel': link.get('rel', [])
                    },
                    'confidence': 1.0
                })
        
        # Email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        for email in emails:
            entities.append({
                'text': email,
                'type': 'EMAIL',
                'confidence': 0.9
            })
        
        # Phone numbers
        phones = re.findall(r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b', text)
        for phone in phones:
            entities.append({
                'text': phone,
                'type': 'PHONE',
                'confidence': 0.9
            })
        
        return entities
    
    def _extract_html_relationships(self, soup: BeautifulSoup, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships from HTML structure."""
        relationships = []
        
        # Parent-child relationships from HTML structure
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            # Find content under this heading
            content_elements = []
            current = heading.next_sibling
            
            while current and not (hasattr(current, 'name') and 
                                 current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if hasattr(current, 'get_text'):
                    text = current.get_text(strip=True)
                    if text:
                        content_elements.append(text)
                current = current.next_sibling
            
            for content in content_elements:
                relationships.append({
                    'source': heading.get_text(strip=True),
                    'target': content[:100] + '...' if len(content) > 100 else content,
                    'type': 'CONTAINS',
                    'strength': 0.8
                })
        
        return relationships
    
    def _generate_html_metadata(self, soup: BeautifulSoup, base_url: Optional[str]) -> Dict[str, Any]:
        """Generate metadata from HTML document."""
        metadata = {
            'base_url': base_url,
            'title': '',
            'description': '',
            'keywords': '',
            'author': '',
            'language': '',
            'encoding': 'utf-8'
        }
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if name == 'description' or property_attr == 'og:description':
                metadata['description'] = content
            elif name == 'keywords':
                metadata['keywords'] = content
            elif name == 'author':
                metadata['author'] = content
            elif name == 'language' or meta.get('http-equiv', '').lower() == 'content-language':
                metadata['language'] = content
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)
        
        # Extract language from html tag
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag['lang']
        
        # Count elements
        metadata.update({
            'heading_count': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
            'link_count': len(soup.find_all('a', href=True)),
            'image_count': len(soup.find_all('img')),
            'table_count': len(soup.find_all('table')),
            'form_count': len(soup.find_all('form'))
        })
        
        return metadata