"""
Enhanced code processor with syntax analysis and graph-aware processing.
"""
import ast
import tokenize
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from io import StringIO
import logging
import re

@dataclass
class CodeProcessingResult:
    parsed_code: Dict[str, Any]
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    syntax_tree: Optional[Any]

class CodeProcessor:
    """Enhanced code processor with AST analysis and entity extraction."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_code(self, code: str, language: str = 'python', 
                    file_path: Optional[str] = None) -> CodeProcessingResult:
        """Process code with syntax analysis and entity extraction."""
        try:
            if language.lower() == 'python':
                return self._process_python_code(code, file_path)
            else:
                return self._process_generic_code(code, language, file_path)
        except Exception as e:
            self.logger.error(f"Error processing {language} code: {e}")
            raise
    
    def _process_python_code(self, code: str, file_path: Optional[str]) -> CodeProcessingResult:
        """Process Python code with AST analysis."""
        try:
            # Parse the AST
            tree = ast.parse(code, filename=file_path or '<string>')
            
            # Extract code elements
            parsed_code = self._extract_python_elements(tree)
            
            # Extract entities (functions, classes, variables, imports)
            entities = self._extract_python_entities(tree, code)
            
            # Extract relationships (calls, inheritance, imports)
            relationships = self._extract_python_relationships(tree, entities)
            
            # Generate metadata
            metadata = self._generate_python_metadata(tree, code, file_path)
            
            return CodeProcessingResult(
                parsed_code=parsed_code,
                entities=entities,
                relationships=relationships,
                metadata=metadata,
                syntax_tree=tree
            )
        except SyntaxError as e:
            self.logger.warning(f"Syntax error in Python code: {e}")
            return self._process_generic_code(code, 'python', file_path)
    
    def _extract_python_elements(self, tree: ast.AST) -> Dict[str, Any]:
        """Extract structured elements from Python AST."""
        elements = {
            'classes': [],
            'functions': [],
            'imports': [],
            'variables': [],
            'constants': []
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                elements['classes'].append({
                    'name': node.name,
                    'bases': [self._get_name(base) for base in node.bases],
                    'decorators': [self._get_name(dec) for dec in node.decorator_list],
                    'lineno': node.lineno,
                    'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                })
            
            elif isinstance(node, ast.FunctionDef):
                elements['functions'].append({
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [self._get_name(dec) for dec in node.decorator_list],
                    'lineno': node.lineno,
                    'returns': self._get_name(node.returns) if node.returns else None,
                    'is_async': isinstance(node, ast.AsyncFunctionDef)
                })
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        elements['imports'].append({
                            'module': alias.name,
                            'alias': alias.asname,
                            'type': 'import',
                            'lineno': node.lineno
                        })
                else:  # ImportFrom
                    for alias in node.names:
                        elements['imports'].append({
                            'module': node.module,
                            'name': alias.name,
                            'alias': alias.asname,
                            'type': 'from_import',
                            'lineno': node.lineno
                        })
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        elements['variables'].append({
                            'name': target.id,
                            'lineno': node.lineno,
                            'type': 'assignment'
                        })
        
        return elements
    
    def _extract_python_entities(self, tree: ast.AST, code: str) -> List[Dict[str, Any]]:
        """Extract entities from Python code."""
        entities = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                entities.append({
                    'text': node.name,
                    'type': 'CLASS',
                    'lineno': node.lineno,
                    'attributes': {
                        'bases': [self._get_name(base) for base in node.bases],
                        'decorators': [self._get_name(dec) for dec in node.decorator_list]
                    },
                    'confidence': 1.0
                })
            
            elif isinstance(node, ast.FunctionDef):
                entities.append({
                    'text': node.name,
                    'type': 'FUNCTION',
                    'lineno': node.lineno,
                    'attributes': {
                        'args': [arg.arg for arg in node.args.args],
                        'decorators': [self._get_name(dec) for dec in node.decorator_list],
                        'is_async': isinstance(node, ast.AsyncFunctionDef)
                    },
                    'confidence': 1.0
                })
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = node.module if isinstance(node, ast.ImportFrom) else None
                for alias in node.names:
                    entities.append({
                        'text': alias.name,
                        'type': 'IMPORT',
                        'lineno': node.lineno,
                        'attributes': {
                            'module': module_name,
                            'alias': alias.asname,
                            'import_type': 'from' if isinstance(node, ast.ImportFrom) else 'direct'
                        },
                        'confidence': 1.0
                    })
        
        return entities
    
    def _extract_python_relationships(self, tree: ast.AST, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships from Python code."""
        relationships = []
        
        # Function calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                caller = self._find_containing_function_or_class(node, tree)
                callee = self._get_name(node.func)
                
                if caller and callee:
                    relationships.append({
                        'source': caller,
                        'target': callee,
                        'type': 'CALLS',
                        'lineno': node.lineno,
                        'strength': 0.8
                    })
            
            # Class inheritance
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = self._get_name(base)
                    if base_name:
                        relationships.append({
                            'source': node.name,
                            'target': base_name,
                            'type': 'INHERITS',
                            'lineno': node.lineno,
                            'strength': 1.0
                        })
        
        return relationships
    
    def _process_generic_code(self, code: str, language: str, 
                            file_path: Optional[str]) -> CodeProcessingResult:
        """Process non-Python code with regex-based analysis."""
        entities = self._extract_generic_entities(code, language)
        relationships = []  # Generic relationship extraction would be implemented here
        
        metadata = {
            'language': language,
            'file_path': file_path,
            'line_count': len(code.split('\n')),
            'char_count': len(code),
            'word_count': len(code.split())
        }
        
        return CodeProcessingResult(
            parsed_code={'raw_code': code},
            entities=entities,
            relationships=relationships,
            metadata=metadata,
            syntax_tree=None
        )
    
    def _extract_generic_entities(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Extract entities from generic code using regex patterns."""
        entities = []
        
        # Common patterns across languages
        patterns = {
            'FUNCTION': {
                'python': r'def\s+(\w+)\s*\(',
                'javascript': r'function\s+(\w+)\s*\(',
                'java': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(',
                'c': r'\w+\s+(\w+)\s*\([^)]*\)\s*\{',
                'cpp': r'\w+\s+(\w+)\s*\([^)]*\)\s*\{'
            },
            'CLASS': {
                'python': r'class\s+(\w+)',
                'javascript': r'class\s+(\w+)',
                'java': r'(?:public|private)?\s*class\s+(\w+)',
                'cpp': r'class\s+(\w+)'
            },
            'VARIABLE': {
                'python': r'(\w+)\s*=',
                'javascript': r'(?:var|let|const)\s+(\w+)',
                'java': r'\w+\s+(\w+)\s*[=;]',
                'c': r'\w+\s+(\w+)\s*[=;]'
            }
        }
        
        for entity_type, lang_patterns in patterns.items():
            pattern = lang_patterns.get(language.lower())
            if pattern:
                matches = re.finditer(pattern, code, re.MULTILINE)
                for match in matches:
                    entities.append({
                        'text': match.group(1),
                        'type': entity_type,
                        'line': code[:match.start()].count('\n') + 1,
                        'confidence': 0.7
                    })
        
        return entities
    
    def _get_name(self, node) -> Optional[str]:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return None
    
    def _find_containing_function_or_class(self, target_node, tree) -> Optional[str]:
        """Find the containing function or class for a given node."""
        # This would implement a traversal to find the containing scope
        return None  # Simplified implementation
    
    def _generate_python_metadata(self, tree: ast.AST, code: str, 
                                 file_path: Optional[str]) -> Dict[str, Any]:
        """Generate metadata for Python code."""
        metadata = {
            'language': 'python',
            'file_path': file_path,
            'line_count': len(code.split('\n')),
            'char_count': len(code),
            'node_count': len(list(ast.walk(tree))),
            'complexity_score': self._calculate_complexity(tree)
        }
        
        # Count different node types
        node_types = {}
        for node in ast.walk(tree):
            node_type = type(node).__name__
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        metadata['node_types'] = node_types
        return metadata
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        return complexity