"""
Code chunker that splits source code intelligently based on structure and syntax.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class CodeElementType(Enum):
    """Types of code elements"""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    BLOCK = "block"

@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata"""
    content: str
    start_line: int
    end_line: int
    chunk_id: str
    element_type: CodeElementType
    name: Optional[str] = None
    dependencies: List[str] = None
    complexity: int = 0
    metadata: Dict[str, Any] = None

class CodeChunker:
    """Intelligent code chunker that respects code structure"""
    
    def __init__(self, 
                 max_chunk_size: int = 2000,
                 preserve_functions: bool = True,
                 preserve_classes: bool = True,
                 include_imports: bool = True):
        """
        Initialize code chunker
        
        Args:
            max_chunk_size: Maximum characters per chunk
            preserve_functions: Keep functions intact
            preserve_classes: Keep classes intact
            include_imports: Include imports in relevant chunks
        """
        self.max_chunk_size = max_chunk_size
        self.preserve_functions = preserve_functions
        self.preserve_classes = preserve_classes
        self.include_imports = include_imports
        
        # Language-specific patterns
        self.language_patterns = {
            'python': {
                'class': r'^class\s+(\w+)',
                'function': r'^def\s+(\w+)',
                'import': r'^(?:import|from)\s+',
                'comment': r'^\s*#',
                'docstring': r'^\s*"""'
            },
            'javascript': {
                'class': r'^class\s+(\w+)',
                'function': r'^(?:function\s+(\w+)|const\s+(\w+)\s*=.*=>)',
                'import': r'^(?:import|const.*require)',
                'comment': r'^\s*//',
                'block_comment': r'/\*.*?\*/'
            },
            'java': {
                'class': r'(?:public|private|protected)?\s*class\s+(\w+)',
                'method': r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(',
                'import': r'^import\s+',
                'comment': r'^\s*//',
                'block_comment': r'/\*.*?\*/'
            }
        }
    
    def chunk_code(self, 
                   code: str, 
                   language: str = 'python',
                   file_path: Optional[str] = None) -> List[CodeChunk]:
        """
        Chunk code based on structure and syntax
        
        Args:
            code: Source code to chunk
            language: Programming language
            file_path: Optional file path for context
            
        Returns:
            List of code chunks
        """
        try:
            if language.lower() == 'python':
                return self._chunk_python_code(code, file_path)
            elif language.lower() in ['javascript', 'typescript']:
                return self._chunk_javascript_code(code, language, file_path)
            elif language.lower() == 'java':
                return self._chunk_java_code(code, file_path)
            else:
                return self._chunk_generic_code(code, language, file_path)
                
        except Exception as e:
            logger.error(f"Error chunking {language} code: {str(e)}")
            return self._fallback_chunking(code, language, file_path)
    
    def _chunk_python_code(self, code: str, file_path: Optional[str] = None) -> List[CodeChunk]:
        """Chunk Python code using AST analysis"""
        chunks = []
        
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            
            # Extract imports
            imports = self._extract_python_imports(tree, lines)
            
            # Process top-level elements
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    chunk = self._create_python_class_chunk(node, lines, imports)
                    if chunk:
                        chunks.append(chunk)
                
                elif isinstance(node, ast.FunctionDef) and not self._is_method(node, tree):
                    chunk = self._create_python_function_chunk(node, lines, imports)
                    if chunk:
                        chunks.append(chunk)
            
            # Handle remaining code (variables, loose statements)
            covered_lines = set()
            for chunk in chunks:
                covered_lines.update(range(chunk.start_line, chunk.end_line + 1))
            
            remaining_chunks = self._create_remaining_chunks(
                lines, covered_lines, imports, 'python'
            )
            chunks.extend(remaining_chunks)
            
        except SyntaxError as e:
            logger.warning(f"Python syntax error: {str(e)}")
            return self._chunk_by_patterns(code, 'python', file_path)
        
        return self._sort_and_deduplicate_chunks(chunks)
    
    def _extract_python_imports(self, tree: ast.AST, lines: List[str]) -> List[str]:
        """Extract import statements from Python AST"""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                imports.append(import_line.strip())
        
        return imports
    
    def _create_python_class_chunk(self, 
                                 node: ast.ClassDef, 
                                 lines: List[str],
                                 imports: List[str]) -> Optional[CodeChunk]:
        """Create chunk for Python class"""
        if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
            return None
        
        start_line = node.lineno - 1  # Convert to 0-based
        end_line = node.end_lineno - 1 if node.end_lineno else start_line
        
        # Get class content
        class_lines = lines[start_line:end_line + 1]
        content = '\n'.join(class_lines)
        
        # Add relevant imports
        if self.include_imports:
            relevant_imports = self._get_relevant_imports(content, imports)
            if relevant_imports:
                content = '\n'.join(relevant_imports) + '\n\n' + content
        
        # Calculate complexity
        complexity = self._calculate_python_complexity(node)
        
        # Extract dependencies
        dependencies = self._extract_python_dependencies(node)
        
        return CodeChunk(
            content=content,
            start_line=start_line + 1,  # Convert back to 1-based
            end_line=end_line + 1,
            chunk_id=f"class_{node.name}",
            element_type=CodeElementType.CLASS,
            name=node.name,
            dependencies=dependencies,
            complexity=complexity,
            metadata={
                'docstring': ast.get_docstring(node),
                'base_classes': [ast.unparse(base) if hasattr(ast, 'unparse') else str(base) 
                               for base in node.bases],
                'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            }
        )
    
    def _create_python_function_chunk(self, 
                                    node: ast.FunctionDef, 
                                    lines: List[str],
                                    imports: List[str]) -> Optional[CodeChunk]:
        """Create chunk for Python function"""
        if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
            return None
        
        start_line = node.lineno - 1
        end_line = node.end_lineno - 1 if node.end_lineno else start_line
        
        # Get function content
        function_lines = lines[start_line:end_line + 1]
        content = '\n'.join(function_lines)
        
        # Add relevant imports
        if self.include_imports:
            relevant_imports = self._get_relevant_imports(content, imports)
            if relevant_imports:
                content = '\n'.join(relevant_imports) + '\n\n' + content
        
        # Calculate complexity
        complexity = self._calculate_python_complexity(node)
        
        # Extract dependencies
        dependencies = self._extract_python_dependencies(node)
        
        return CodeChunk(
            content=content,
            start_line=start_line + 1,
            end_line=end_line + 1,
            chunk_id=f"function_{node.name}",
            element_type=CodeElementType.FUNCTION,
            name=node.name,
            dependencies=dependencies,
            complexity=complexity,
            metadata={
                'docstring': ast.get_docstring(node),
                'parameters': [arg.arg for arg in node.args.args],
                'returns': ast.unparse(node.returns) if hasattr(ast, 'unparse') and node.returns else None,
                'is_async': isinstance(node, ast.AsyncFunctionDef)
            }
        )
    
    def _calculate_python_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for Python AST node"""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _extract_python_dependencies(self, node: ast.AST) -> List[str]:
        """Extract dependencies from Python AST node"""
        dependencies = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                dependencies.append(child.id)
            elif isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name):
                    dependencies.append(child.value.id)
        
        return list(set(dependencies))  # Remove duplicates
    
    def _is_method(self, node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Check if a function is a method (inside a class)"""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                if node in parent.body:
                    return True
        return False
    
    def _chunk_javascript_code(self, 
                             code: str, 
                             language: str,
                             file_path: Optional[str] = None) -> List[CodeChunk]:
        """Chunk JavaScript/TypeScript code using pattern matching"""
        return self._chunk_by_patterns(code, language, file_path)
    
    def _chunk_java_code(self, code: str, file_path: Optional[str] = None) -> List[CodeChunk]:
        """Chunk Java code using pattern matching"""
        return self._chunk_by_patterns(code, 'java', file_path)
    
    def _chunk_by_patterns(self, 
                          code: str, 
                          language: str,
                          file_path: Optional[str] = None) -> List[CodeChunk]:
        """Chunk code using regex patterns"""
        chunks = []
        lines = code.split('\n')
        patterns = self.language_patterns.get(language, {})
        
        current_chunk_lines = []
        current_element_type = CodeElementType.BLOCK
        current_name = None
        chunk_id = 0
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for class definition
            if 'class' in patterns:
                class_match = re.match(patterns['class'], line)
                if class_match:
                    # Save previous chunk
                    if current_chunk_lines:
                        chunks.append(self._create_pattern_chunk(
                            current_chunk_lines, current_element_type, 
                            current_name, chunk_id, i - len(current_chunk_lines)
                        ))
                        chunk_id += 1
                    
                    # Start new class chunk
                    current_chunk_lines = [lines[i]]
                    current_element_type = CodeElementType.CLASS
                    current_name = class_match.group(1)
                    
                    # Find class end (simplified)
                    brace_count = line.count('{') - line.count('}')
                    i += 1
                    
                    while i < len(lines) and brace_count > 0:
                        current_chunk_lines.append(lines[i])
                        brace_count += lines[i].count('{') - lines[i].count('}')
                        i += 1
                    
                    # Save class chunk
                    chunks.append(self._create_pattern_chunk(
                        current_chunk_lines, current_element_type,
                        current_name, chunk_id, i - len(current_chunk_lines)
                    ))
                    chunk_id += 1
                    current_chunk_lines = []
                    continue
            
            # Check for function definition
            if 'function' in patterns:
                func_match = re.match(patterns['function'], line)
                if func_match:
                    # Save previous chunk
                    if current_chunk_lines:
                        chunks.append(self._create_pattern_chunk(
                            current_chunk_lines, current_element_type,
                            current_name, chunk_id, i - len(current_chunk_lines)
                        ))
                        chunk_id += 1
                    
                    # Start new function chunk
                    current_chunk_lines = [lines[i]]
                    current_element_type = CodeElementType.FUNCTION
                    current_name = func_match.group(1) or func_match.group(2)
                    
                    # Find function end (simplified)
                    brace_count = line.count('{') - line.count('}')
                    i += 1
                    
                    while i < len(lines) and brace_count > 0:
                        current_chunk_lines.append(lines[i])
                        brace_count += lines[i].count('{') - lines[i].count('}')
                        i += 1
                    
                    # Save function chunk
                    chunks.append(self._create_pattern_chunk(
                        current_chunk_lines, current_element_type,
                        current_name, chunk_id, i - len(current_chunk_lines)
                    ))
                    chunk_id += 1
                    current_chunk_lines = []
                    continue
            
            # Add line to current chunk
            current_chunk_lines.append(lines[i])
            
            # Check if chunk is getting too large
            if len('\n'.join(current_chunk_lines)) > self.max_chunk_size:
                chunks.append(self._create_pattern_chunk(
                    current_chunk_lines, current_element_type,
                    current_name, chunk_id, i - len(current_chunk_lines) + 1
                ))
                chunk_id += 1
                current_chunk_lines = []
                current_element_type = CodeElementType.BLOCK
                current_name = None
            
            i += 1
        
        # Add final chunk
        if current_chunk_lines:
            chunks.append(self._create_pattern_chunk(
                current_chunk_lines, current_element_type,
                current_name, chunk_id, len(lines) - len(current_chunk_lines)
            ))
        
        return chunks
    
    def _create_pattern_chunk(self, 
                            lines: List[str],
                            element_type: CodeElementType,
                            name: Optional[str],
                            chunk_id: int,
                            start_line: int) -> CodeChunk:
        """Create a code chunk from pattern matching"""
        content = '\n'.join(lines)
        
        return CodeChunk(
            content=content,
            start_line=start_line + 1,  # Convert to 1-based
            end_line=start_line + len(lines),
            chunk_id=f"{element_type.value}_{chunk_id:04d}",
            element_type=element_type,
            name=name,
            dependencies=[],
            complexity=self._estimate_complexity(content),
            metadata={'pattern_based': True}
        )
    
    def _estimate_complexity(self, content: str) -> int:
        """Estimate complexity based on control flow keywords"""
        complexity_keywords = ['if', 'else', 'elif', 'for', 'while', 'try', 'catch', 'switch', 'case']
        complexity = 1
        
        content_lower = content.lower()
        for keyword in complexity_keywords:
            complexity += content_lower.count(keyword)
        
        return complexity
    
    def _chunk_generic_code(self, 
                          code: str, 
                          language: str,
                          file_path: Optional[str] = None) -> List[CodeChunk]:
        """Generic code chunking for unsupported languages"""
        lines = code.split('\n')
        chunks = []
        chunk_id = 0
        
        current_chunk_lines = []
        
        for i, line in enumerate(lines):
            current_chunk_lines.append(line)
            
            # Check if chunk is getting too large
            if len('\n'.join(current_chunk_lines)) > self.max_chunk_size:
                content = '\n'.join(current_chunk_lines)
                
                chunk = CodeChunk(
                    content=content,
                    start_line=i - len(current_chunk_lines) + 2,  # Convert to 1-based
                    end_line=i + 1,
                    chunk_id=f"generic_chunk_{chunk_id:04d}",
                    element_type=CodeElementType.BLOCK,
                    name=None,
                    dependencies=[],
                    complexity=self._estimate_complexity(content),
                    metadata={'language': language, 'generic_chunking': True}
                )
                
                chunks.append(chunk)
                chunk_id += 1
                current_chunk_lines = []
        
        # Add final chunk
        if current_chunk_lines:
            content = '\n'.join(current_chunk_lines)
            
            chunk = CodeChunk(
                content=content,
                start_line=len(lines) - len(current_chunk_lines) + 1,
                end_line=len(lines),
                chunk_id=f"generic_chunk_{chunk_id:04d}",
                element_type=CodeElementType.BLOCK,
                name=None,
                dependencies=[],
                complexity=self._estimate_complexity(content),
                metadata={'language': language, 'generic_chunking': True}
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _get_relevant_imports(self, content: str, imports: List[str]) -> List[str]:
        """Get imports that are relevant to the given content"""
        relevant_imports = []
        content_lower = content.lower()
        
        for import_stmt in imports:
            # Extract imported names
            if 'import' in import_stmt:
                # Simple heuristic: check if any word in import appears in content
                import_words = re.findall(r'\b\w+\b', import_stmt)
                for word in import_words:
                    if word.lower() in content_lower and word not in ['import', 'from', 'as']:
                        relevant_imports.append(import_stmt)
                        break
        
        return relevant_imports
    
    def _create_remaining_chunks(self, 
                               lines: List[str],
                               covered_lines: set,
                               imports: List[str],
                               language: str) -> List[CodeChunk]:
        """Create chunks for uncovered lines (variables, loose statements)"""
        chunks = []
        chunk_id = 0
        current_chunk_lines = []
        
        for i, line in enumerate(lines):
            if (i + 1) not in covered_lines and line.strip():  # Convert to 1-based for comparison
                current_chunk_lines.append((i, line))
                
                # Check if chunk is getting too large
                if len('\n'.join([l[1] for l in current_chunk_lines])) > self.max_chunk_size:
                    if current_chunk_lines:
                        chunks.append(self._create_remaining_chunk(
                            current_chunk_lines, imports, language, chunk_id
                        ))
                        chunk_id += 1
                        current_chunk_lines = []
        
        # Add final chunk
        if current_chunk_lines:
            chunks.append(self._create_remaining_chunk(
                current_chunk_lines, imports, language, chunk_id
            ))
        
        return chunks
    
    def _create_remaining_chunk(self, 
                              indexed_lines: List[Tuple[int, str]],
                              imports: List[str],
                              language: str,
                              chunk_id: int) -> CodeChunk:
        """Create chunk from remaining uncovered lines"""
        lines = [line for _, line in indexed_lines]
        content = '\n'.join(lines)
        
        # Add relevant imports
        if self.include_imports:
            relevant_imports = self._get_relevant_imports(content, imports)
            if relevant_imports:
                content = '\n'.join(relevant_imports) + '\n\n' + content
        
        start_line = indexed_lines[0][0] + 1  # Convert to 1-based
        end_line = indexed_lines[-1][0] + 1
        
        return CodeChunk(
            content=content,
            start_line=start_line,
            end_line=end_line,
            chunk_id=f"remaining_{chunk_id:04d}",
            element_type=CodeElementType.BLOCK,
            name=None,
            dependencies=[],
            complexity=self._estimate_complexity(content),
            metadata={'language': language, 'remaining_code': True}
        )
    
    def _sort_and_deduplicate_chunks(self, chunks: List[CodeChunk]) -> List[CodeChunk]:
        """Sort chunks by line number and remove duplicates"""
        # Sort by start line
        chunks.sort(key=lambda chunk: chunk.start_line)
        
        # Remove duplicates (chunks with overlapping line ranges)
        deduplicated = []
        for chunk in chunks:
            overlaps = False
            for existing in deduplicated:
                if (chunk.start_line <= existing.end_line and 
                    chunk.end_line >= existing.start_line):
                    overlaps = True
                    break
            
            if not overlaps:
                deduplicated.append(chunk)
        
        return deduplicated
    
    def _fallback_chunking(self, 
                         code: str, 
                         language: str,
                         file_path: Optional[str] = None) -> List[CodeChunk]:
        """Fallback chunking when all else fails"""
        lines = code.split('\n')
        chunks = []
        chunk_size = self.max_chunk_size // 50  # Estimate lines per chunk
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            content = '\n'.join(chunk_lines)
            
            chunk = CodeChunk(
                content=content,
                start_line=i + 1,
                end_line=min(i + chunk_size, len(lines)),
                chunk_id=f"fallback_chunk_{i // chunk_size:04d}",
                element_type=CodeElementType.BLOCK,
                name=None,
                dependencies=[],
                complexity=self._estimate_complexity(content),
                metadata={
                    'language': language,
                    'fallback_chunking': True,
                    'file_path': file_path
                }
            )
            
            chunks.append(chunk)
        
        return chunks