"""
Code Parser Module
=================

This module provides utilities for parsing and analyzing code using tree-sitter.
It enables accurate code structure extraction for documentation generation.

Features:
- Multi-language support
- AST (Abstract Syntax Tree) parsing and traversal
- Structure extraction (functions, classes, methods)
- Documentation extraction (docstrings, comments)
"""

import os
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

# Set up basic logging if .logging is not available
try:
    from .logging import logger
except ImportError:
    logger = logging.getLogger("docpilot.code_parser")
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Check if environment variable is set to force fallback parser
FORCE_FALLBACK = os.environ.get('DOCPILOT_USE_FALLBACK_PARSER') == '1'

# Check if tree-sitter and tree-sitter-language-pack are installed
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    
    try:
        # Try to import tree-sitter-language-pack (preferred over tree-sitter-languages)
        from tree_sitter_language_pack import get_language, get_parser
        TREE_SITTER_AVAILABLE = True and not FORCE_FALLBACK
        LANGUAGE_PACK_AVAILABLE = True
        logger.info("Using tree-sitter-language-pack for code parsing")
    except ImportError:
        # Fall back to tree-sitter-languages
        try:
            import tree_sitter_languages
            from tree_sitter_languages import get_language, get_parser
            TREE_SITTER_AVAILABLE = True and not FORCE_FALLBACK
            LANGUAGE_PACK_AVAILABLE = False
            logger.warning("tree-sitter-language-pack not available - using tree-sitter-languages")
        except ImportError:
            TREE_SITTER_AVAILABLE = True and not FORCE_FALLBACK
            LANGUAGE_PACK_AVAILABLE = False
            logger.warning("Using basic tree-sitter for parsing - language bindings may be limited")
except ImportError:
    TREE_SITTER_AVAILABLE = False
    LANGUAGE_PACK_AVAILABLE = False
    logger.warning("tree-sitter not available - using fallback parser")

# Map file extensions to tree-sitter language names
FILE_EXT_TO_LANGUAGE = {
    # Python
    ".py": "python",
    # JavaScript family
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    # Web
    ".html": "html",
    ".css": "css",
    # JVM languages
    ".java": "java",
    ".kt": "kotlin", 
    # C-family
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    # Others
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".swift": "swift",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
}

# Fallback regex patterns for when tree-sitter is not available
PYTHON_FUNCTION_PATTERN = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(\([^)]*\))(?:\s*->\s*[^:]+)?\s*:'
PYTHON_CLASS_PATTERN = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?\s*:'
PYTHON_METHOD_PATTERN = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(\([^)]*\))(?:\s*->\s*[^:]+)?\s*:'
PYTHON_DOCSTRING_PATTERN = r'"""(.*?)"""'

# Code structure containers
@dataclass
class CodeFunction:
    """Represents a function in code."""
    name: str
    params: str
    body: str = ""
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    language: str = ""
    parent: Optional[Any] = None

@dataclass
class CodeClass:
    """Represents a class in code."""
    name: str
    methods: List[CodeFunction] = field(default_factory=list)
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    language: str = ""

@dataclass
class CodeModule:
    """Represents a code module (file)."""
    path: str
    language: str
    functions: List[CodeFunction] = field(default_factory=list)
    classes: List[CodeClass] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    source_code: str = ""

# Pattern queries for common code structures
QUERY_PATTERNS = {
    "python": {
        "function": """
        (function_definition
          name: (identifier) @function.name
          parameters: (parameters) @function.params
          body: (block) @function.body
        ) @function.def
        
        (decorated_definition
          (decorator) @function.decorator
          definition: (function_definition
            name: (identifier) @function.name
            parameters: (parameters) @function.params
            body: (block) @function.body
          ) @function.def
        )
        """,
        "class": """
        (class_definition
          name: (identifier) @class.name
          body: (block) @class.body
        ) @class.def
        
        (decorated_definition
          definition: (class_definition
            name: (identifier) @class.name
            body: (block) @class.body
          ) @class.def
        )
        """
    },
    "javascript": {
        "function": """
        (function_declaration
          name: (identifier) @function.name
          parameters: (formal_parameters) @function.params
          body: (statement_block) @function.body
        ) @function.def
        
        (method_definition
          name: (property_identifier) @method.name
          parameters: (formal_parameters) @method.params
          body: (statement_block) @method.body
        ) @method.def
        
        (arrow_function
          parameters: (formal_parameters) @arrow.params
          body: [
            (statement_block) @arrow.body
            (_) @arrow.expression
          ]
        ) @arrow.def
        """,
        "class": """
        (class_declaration
          name: (identifier) @class.name
          body: (class_body) @class.body
        ) @class.def
        """
    }
}

class TreeSitterParser:
    """Parser implementation using tree-sitter."""
    
    @staticmethod
    def parse_file(file_path: str) -> Optional[CodeModule]:
        """Parse a file using tree-sitter."""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
            
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                
            # Detect language
            ext = os.path.splitext(file_path)[1].lower()
            language_name = FILE_EXT_TO_LANGUAGE.get(ext)
            
            if not language_name:
                logger.warning(f"Unsupported file type: {file_path}")
                return None
                
            # Create module
            module = CodeModule(
                path=file_path,
                language=language_name,
                source_code=source_code
            )
            
            if LANGUAGE_PACK_AVAILABLE:
                # Use tree_sitter_language_pack for reliable parsing
                try:
                    # Get the parser and language - should work consistently across tree-sitter versions
                    parser = get_parser(language_name)
                    language = get_language(language_name)
                    
                    # Parse the code
                    tree = parser.parse(bytes(source_code, 'utf-8'))
                    
                    # Extract structures
                    TreeSitterParser._extract_module_docstring(tree.root_node, source_code, module)
                    TreeSitterParser._extract_functions(tree.root_node, source_code, language, module)
                    TreeSitterParser._extract_classes(tree.root_node, source_code, language, module)
                    
                    return module
                except Exception as e:
                    logger.error(f"Error using tree-sitter-language-pack parser: {e}")
                    # Fall back to basic tree-sitter or regex parser
            elif TREE_SITTER_AVAILABLE:
                # Try to use tree-sitter-languages or basic tree-sitter
                try:
                    if 'tree_sitter_languages' in sys.modules:
                        # Using tree-sitter-languages with compatibility handling
                        try:
                            # Get the parser
                            parser = get_parser(language_name)
                            
                            # For get_language, handle the compatibility issue
                            try:
                                # Normal way for tree-sitter < 0.22
                                language = get_language(language_name)
                            except TypeError as e:
                                if "__init__() takes exactly 1 argument (2 given)" in str(e):
                                    logger.warning("Detected tree-sitter 0.22+ compatibility issue. Using direct language module.")
                                    # Fall back to direct language module
                                    language = TreeSitterParser._get_language_lib(language_name)
                                    if not language:
                                        raise ValueError(f"Could not load language {language_name} with either method")
                                else:
                                    raise
                        except Exception as e:
                            logger.error(f"Error using tree-sitter-languages: {e}")
                            # Try basic parser
                            language = TreeSitterParser._get_language_lib(language_name)
                            if not language:
                                logger.warning(f"No language lib for {language_name}, using fallback parser")
                                return TreeSitterParser._fallback_parse(source_code, language_name, file_path)
                                
                            parser = Parser()
                            parser.set_language(language)
                    else:
                        # Use basic tree-sitter
                        language = TreeSitterParser._get_language_lib(language_name)
                        if not language:
                            logger.warning(f"No language lib for {language_name}, using fallback parser")
                            return TreeSitterParser._fallback_parse(source_code, language_name, file_path)
                            
                        parser = Parser()
                        parser.set_language(language)
                    
                    # Parse the code
                    tree = parser.parse(bytes(source_code, 'utf-8'))
                    
                    # Extract structures
                    TreeSitterParser._extract_module_docstring(tree.root_node, source_code, module)
                    TreeSitterParser._extract_functions(tree.root_node, source_code, language, module)
                    TreeSitterParser._extract_classes(tree.root_node, source_code, language, module)
                    
                    return module
                except Exception as e:
                    logger.error(f"Error using tree-sitter parser: {e}")
                    # Fall back to regex parser
            
            # Fallback to regex parsing
            return TreeSitterParser._fallback_parse(source_code, language_name, file_path)
                
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None
    
    @staticmethod
    def _get_language_lib(language_name: str) -> Optional[Any]:
        """Get the Tree-sitter language library."""
        if not language_name:
            return None
            
        # Normalize language name
        normalized_name = language_name.lower().replace('-', '_')
        
        # First try with tree-sitter-languages
        try:
            from tree_sitter_languages import get_language
            try:
                # This will work with tree-sitter < 0.22
                return get_language(normalized_name)
            except TypeError as e:
                # TypeError might be raised if using tree-sitter >= 0.22
                if "takes 1 positional argument but 2 were given" in str(e):
                    logger.warning(f"Compatibility issue with tree-sitter >= 0.22. Try downgrading to tree-sitter==0.21.3")
                raise
        except (ImportError, ModuleNotFoundError):
            # If tree-sitter-languages is not installed, try direct language imports
            pass
        except Exception as e:
            logger.warning(f"Error using tree-sitter-languages.get_language: {e}")
        
        # Try direct imports as fallback
        try:
            # For Python
            if normalized_name == 'python':
                try:
                    from tree_sitter_python import language
                    return language
                except ImportError:
                    pass
                    
            # For JavaScript/TypeScript
            elif normalized_name in ('javascript', 'js'):
                try:
                    from tree_sitter_javascript import language
                    return language
                except ImportError:
                    pass
            elif normalized_name in ('typescript', 'ts'):
                try:
                    from tree_sitter_typescript import language_typescript as language
                    return language
                except ImportError:
                    pass
                    
            # For Ruby
            elif normalized_name == 'ruby':
                try:
                    from tree_sitter_ruby import language
                    return language
                except ImportError:
                    pass
                    
            # For Go
            elif normalized_name == 'go':
                try:
                    from tree_sitter_go import language
                    return language
                except ImportError:
                    pass
                    
            # For Rust
            elif normalized_name == 'rust':
                try:
                    from tree_sitter_rust import language
                    return language
                except ImportError:
                    pass
                    
            # For Java
            elif normalized_name == 'java':
                try:
                    from tree_sitter_java import language
                    return language
                except ImportError:
                    pass
                    
            # For C/C++
            elif normalized_name in ('c', 'cpp', 'c++'):
                try:
                    if normalized_name == 'c':
                        from tree_sitter_c import language
                    else:
                        from tree_sitter_cpp import language
                    return language
                except ImportError:
                    pass
                    
            logger.warning(f"No direct import found for language: {language_name}")
        except Exception as e:
            logger.warning(f"Error importing language module for {language_name}: {e}")
            
        return None
    
    @staticmethod
    def _extract_module_docstring(root_node: Any, source_code: str, module: CodeModule) -> None:
        """Extract module-level docstring."""
        if module.language == 'python':
            # Check if root_node has children before iterating
            if not hasattr(root_node, 'children') or not root_node.children:
                return
                
            for child in root_node.children:
                if child.type == 'expression_statement':
                    # Check if this child has children
                    if not hasattr(child, 'children') or not child.children:
                        continue
                        
                    for grandchild in child.children:
                        if grandchild.type == 'string' and child.start_point[0] <= 1:  # First or second line
                            module.docstring = TreeSitterParser._get_node_text(grandchild, source_code)
                            return
    
    @staticmethod
    def _execute_query(query: Any, node: Any) -> Any:
        """Execute a query on a node, returning the raw results to handle different formats."""
        if node is None:
            logger.warning("Cannot execute query: node is None")
            return {}
        
        if not hasattr(query, 'captures'):
            logger.warning("Invalid query object: missing required methods")
            return {}
            
        try:
            # Execute the query - handle different formats in the calling method
            return query.captures(node)
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return {}
            
    @staticmethod
    def _extract_functions(root_node: Any, source_code: str, language: Any, module: CodeModule) -> None:
        """Extract functions from the parsed code."""
        if module.language not in QUERY_PATTERNS:
            return
        
        # Ensure we have a valid root_node
        if root_node is None:
            logger.warning("Cannot extract functions: root_node is None")
            return

        # Get query pattern for the language
        query_str = QUERY_PATTERNS[module.language].get("function")
        if not query_str:
            return
            
        try:
            # Create query
            query = language.query(query_str)
            
            # Execute query - get raw results
            captures = TreeSitterParser._execute_query(query, root_node)
            
            # Check if captures is a dictionary (tree-sitter-language-pack format)
            if isinstance(captures, dict):
                # Dictionary format: {'function.def': [nodes], 'function.name': [nodes], ...}
                functions = {}
                
                # Process function definitions
                if 'function.def' in captures:
                    for node in captures['function.def']:
                        node_id = id(node)
                        if node_id not in functions:
                            functions[node_id] = {'node': node}
                
                # Process function names            
                if 'function.name' in captures:
                    for node in captures['function.name']:
                        # Find the parent function for this name
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'function_definition':
                            parent_node = parent_node.parent
                        
                        if parent_node:
                            node_id = id(parent_node)
                            if node_id not in functions:
                                functions[node_id] = {}
                            functions[node_id]['name'] = node
                
                # Process function parameters
                if 'function.params' in captures:
                    for node in captures['function.params']:
                        # Find the parent function
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'function_definition':
                            parent_node = parent_node.parent
                            
                        if parent_node:
                            node_id = id(parent_node)
                            if node_id not in functions:
                                functions[node_id] = {}
                            functions[node_id]['params'] = node
                
                # Process function bodies
                if 'function.body' in captures:
                    for node in captures['function.body']:
                        # Find the parent function
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'function_definition':
                            parent_node = parent_node.parent
                            
                        if parent_node:
                            node_id = id(parent_node)
                            if node_id not in functions:
                                functions[node_id] = {}
                            functions[node_id]['body'] = node
            elif isinstance(captures, list):
                # List format from older tree-sitter versions
                # Group captures by function definition
                functions = {}
                for capture in captures:
                    # Handle different tuple formats
                    if isinstance(capture, tuple) and len(capture) >= 2:
                        if isinstance(capture[0], str):
                            # (name, node) format
                            name, node = capture
                        else:
                            # (node, name) format
                            node, name = capture
                            
                        if '.' not in name:
                            continue
                            
                        category, part = name.split('.', 1)
                        if category != 'function':
                            continue
                            
                        node_id = id(node)
                        if part == 'def':
                            if node_id not in functions:
                                functions[node_id] = {}
                            functions[node_id]['node'] = node
                        elif part in ('name', 'params', 'body'):
                            if node_id not in functions:
                                functions[node_id] = {}
                            functions[node_id][part] = node
            
            # Create function objects from either format
            for func_id, func_parts in functions.items():
                if 'name' not in func_parts:
                    continue
                    
                name_node = func_parts['name']
                node = func_parts.get('node', name_node.parent)  # Use parent if no node specified
                params_node = func_parts.get('params')
                body_node = func_parts.get('body')
                
                name = TreeSitterParser._get_node_text(name_node, source_code)
                params = TreeSitterParser._get_node_text(params_node, source_code) if params_node else ""
                body = TreeSitterParser._get_node_text(body_node, source_code) if body_node else ""
                docstring = TreeSitterParser._extract_docstring(body_node, source_code) if body_node else None
                
                # Check if this function is a method of a class by looking for decorators and indentation
                is_method = False
                parent_class = None
                
                # Find decorator information in the captures
                decorator_node = None
                if isinstance(captures, dict) and 'function.decorator' in captures:
                    for decorator in captures['function.decorator']:
                        # Check if this decorator belongs to this function
                        decorated_def = decorator.parent
                        if decorated_def and decorated_def.type == 'decorated_definition':
                            for child in decorated_def.children:
                                if child.type == 'function_definition' and id(child) == func_id:
                                    decorator_node = decorator
                                    break
                
                # Check if it's a staticmethod or classmethod by looking at decorators
                decorator_found = False
                if decorator_node:
                    decorator_text = TreeSitterParser._get_node_text(decorator_node, source_code).strip()
                    if '@staticmethod' in decorator_text or '@classmethod' in decorator_text:
                        decorator_found = True
                elif hasattr(node, 'children'):
                    for child in node.children:
                        if child.type == 'decorator':
                            decorator_text = TreeSitterParser._get_node_text(child, source_code).strip()
                            if '@staticmethod' in decorator_text or '@classmethod' in decorator_text:
                                decorator_found = True
                                break
                
                # If it has a staticmethod/classmethod decorator, find its parent class
                if decorator_found:
                    # Find the class this method belongs to by looking at indentation and context
                    context_node = node.parent
                    while context_node and context_node.type != 'class_definition' and context_node.type != 'block':
                        context_node = context_node.parent
                        
                    if context_node:
                        if context_node.type == 'class_definition':
                            # Direct parent is a class
                            class_node = context_node
                        elif context_node.type == 'block':
                            # Check if this block is part of a class
                            class_node = context_node.parent
                            if not class_node or class_node.type != 'class_definition':
                                class_node = None
                        else:
                            class_node = None
                            
                        if class_node:
                            # Find the class name
                            class_name = None
                            for class_child in class_node.children:
                                if class_child.type == 'identifier':
                                    class_name = TreeSitterParser._get_node_text(class_child, source_code)
                                    break
                            
                            if class_name:
                                # Find the matching class in the module
                                for cls in module.classes:
                                    if cls.name == class_name:
                                        is_method = True
                                        parent_class = cls
                                        break
                
                # Create function object
                func = CodeFunction(
                    name=name,
                    params=params,
                    body=body,
                    docstring=docstring,
                    start_line=node.start_point[0] if hasattr(node, 'start_point') else 0,
                    end_line=node.end_point[0] if hasattr(node, 'end_point') else 0,
                    language=module.language,
                    parent=parent_class
                )
                
                # Add to class or module
                if is_method and parent_class:
                    parent_class.methods.append(func)
                else:
                    module.functions.append(func)
        except Exception as e:
            logger.error(f"Error extracting functions: {e}")
    
    @staticmethod
    def _extract_class_methods(body_node: Any, source_code: str, module_language: str, cls: CodeClass) -> List[CodeFunction]:
        """Extract methods from a class body node."""
        methods = []
        
        # Safety check
        if not hasattr(body_node, 'children') or not body_node.children:
            return methods
            
        try:
            # Find function definitions in the class body
            for child in body_node.children:
                # Handle both direct function definitions and decorated function definitions
                if child.type == 'function_definition':
                    name_node = None
                    params_node = None
                    method_body_node = None
                    
                    # Safety check
                    if not hasattr(child, 'children') or not child.children:
                        continue
                        
                    # Extract function components
                    for gc in child.children:
                        if gc.type == 'identifier':
                            name_node = gc
                        elif gc.type == 'parameters':
                            params_node = gc
                        elif gc.type == 'block':
                            method_body_node = gc
                    
                    if name_node:
                        # Create method object
                        method_name = TreeSitterParser._get_node_text(name_node, source_code)
                        method_params = TreeSitterParser._get_node_text(params_node, source_code) if params_node else ""
                        method_body = TreeSitterParser._get_node_text(method_body_node, source_code) if method_body_node else ""
                        method_docstring = TreeSitterParser._extract_docstring(method_body_node, source_code) if method_body_node else None
                        
                        method = CodeFunction(
                            name=method_name,
                            params=method_params,
                            body=method_body,
                            docstring=method_docstring,
                            start_line=child.start_point[0] if hasattr(child, 'start_point') else 0,
                            end_line=child.end_point[0] if hasattr(child, 'end_point') else 0,
                            language=module_language,
                            parent=cls
                        )
                        
                        methods.append(method)
                elif child.type == 'decorated_definition':
                    # Check for decorated methods
                    if not hasattr(child, 'children') or not child.children:
                        continue
                        
                    # Find the function definition inside the decorated_definition
                    for gc in child.children:
                        if gc.type == 'function_definition':
                            # Process the function definition
                            func_def = gc
                            name_node = None
                            params_node = None
                            method_body_node = None
                            
                            # Safety check
                            if not hasattr(func_def, 'children') or not func_def.children:
                                continue
                                
                            # Extract function components
                            for func_child in func_def.children:
                                if func_child.type == 'identifier':
                                    name_node = func_child
                                elif func_child.type == 'parameters':
                                    params_node = func_child
                                elif func_child.type == 'block':
                                    method_body_node = func_child
                            
                            if name_node:
                                # Create method object
                                method_name = TreeSitterParser._get_node_text(name_node, source_code)
                                method_params = TreeSitterParser._get_node_text(params_node, source_code) if params_node else ""
                                method_body = TreeSitterParser._get_node_text(method_body_node, source_code) if method_body_node else ""
                                method_docstring = TreeSitterParser._extract_docstring(method_body_node, source_code) if method_body_node else None
                                
                                method = CodeFunction(
                                    name=method_name,
                                    params=method_params,
                                    body=method_body,
                                    docstring=method_docstring,
                                    start_line=func_def.start_point[0] if hasattr(func_def, 'start_point') else 0,
                                    end_line=func_def.end_point[0] if hasattr(func_def, 'end_point') else 0,
                                    language=module_language,
                                    parent=cls
                                )
                                
                                methods.append(method)
        except Exception as e:
            logger.error(f"Error extracting class methods: {e}")
            
        return methods

    @staticmethod
    def _extract_classes(root_node: Any, source_code: str, language: Any, module: CodeModule) -> None:
        """Extract classes from the parsed code."""
        if module.language not in QUERY_PATTERNS:
            return
            
        # Ensure we have a valid root_node
        if root_node is None:
            logger.warning("Cannot extract classes: root_node is None")
            return
            
        # Get query pattern for the language
        query_str = QUERY_PATTERNS[module.language].get("class")
        if not query_str:
            return
            
        try:
            # Create query
            query = language.query(query_str)
            
            # Execute query
            captures = TreeSitterParser._execute_query(query, root_node)
            
            # Check if captures is a dictionary (tree-sitter-language-pack format)
            if isinstance(captures, dict):
                # Dictionary format: {'class.def': [nodes], 'class.name': [nodes], ...}
                classes = {}
                
                # Process class definitions
                if 'class.def' in captures:
                    for node in captures['class.def']:
                        node_id = id(node)
                        if node_id not in classes:
                            classes[node_id] = {'node': node}
                
                # Process class names            
                if 'class.name' in captures:
                    for node in captures['class.name']:
                        # Find the parent class for this name
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'class_definition' and parent_node.type != 'decorated_definition':
                            parent_node = parent_node.parent
                        
                        if parent_node:
                            # If it's a decorated_definition, look for the class_definition inside
                            if parent_node.type == 'decorated_definition':
                                for child in parent_node.children:
                                    if child.type == 'class_definition':
                                        parent_node = child
                                        break
                            
                            node_id = id(parent_node)
                            if node_id not in classes:
                                classes[node_id] = {}
                            classes[node_id]['name'] = node
                
                # Process class bodies
                if 'class.body' in captures:
                    for node in captures['class.body']:
                        # Find the parent class
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'class_definition' and parent_node.type != 'decorated_definition':
                            parent_node = parent_node.parent
                            
                        if parent_node:
                            # If it's a decorated_definition, look for the class_definition inside
                            if parent_node.type == 'decorated_definition':
                                for child in parent_node.children:
                                    if child.type == 'class_definition':
                                        parent_node = child
                                        break
                                        
                            node_id = id(parent_node)
                            if node_id not in classes:
                                classes[node_id] = {}
                            classes[node_id]['body'] = node
            elif isinstance(captures, list):
                # List format from older tree-sitter versions
                # Group captures by class definition
                classes = {}
                for capture in captures:
                    # Handle different tuple formats
                    if isinstance(capture, tuple) and len(capture) >= 2:
                        if isinstance(capture[0], str):
                            # (name, node) format
                            name, node = capture
                        else:
                            # (node, name) format
                            node, name = capture
                            
                        if '.' not in name:
                            continue
                            
                        category, part = name.split('.', 1)
                        if category != 'class':
                            continue
                            
                        node_id = id(node)
                        if part == 'def':
                            if node_id not in classes:
                                classes[node_id] = {}
                            classes[node_id]['node'] = node
                        elif part in ('name', 'body'):
                            if node_id not in classes:
                                classes[node_id] = {}
                            classes[node_id][part] = node
            
            # Create class objects from either format
            for class_id, class_parts in classes.items():
                if 'name' not in class_parts:
                    continue
                    
                name_node = class_parts['name']
                node = class_parts.get('node', name_node.parent)  # Use parent if no node specified
                body_node = class_parts.get('body')
                
                name = TreeSitterParser._get_node_text(name_node, source_code)
                docstring = TreeSitterParser._extract_docstring(body_node, source_code) if body_node else None
                
                cls = CodeClass(
                    name=name,
                    docstring=docstring,
                    start_line=node.start_point[0] if hasattr(node, 'start_point') else 0,
                    end_line=node.end_point[0] if hasattr(node, 'end_point') else 0,
                    language=module.language
                )
                
                # Extract methods if we have a body
                if body_node and module.language == 'python':
                    cls.methods = TreeSitterParser._extract_class_methods(body_node, source_code, module.language, cls)
                
                module.classes.append(cls)
        except Exception as e:
            logger.error(f"Error extracting classes: {e}")
    
    @staticmethod
    def _extract_docstring(body_node: Any, source_code: str) -> Optional[str]:
        """Extract docstring from a body node."""
        if not body_node or not hasattr(body_node, 'children') or not body_node.children:
            return None
            
        try:
            for child in body_node.children:
                if child.type == 'expression_statement':
                    if not hasattr(child, 'children') or not child.children:
                        continue
                        
                    for gc in child.children:
                        if gc.type == 'string':
                            return TreeSitterParser._get_node_text(gc, source_code)
                elif child.type == 'string':
                    return TreeSitterParser._get_node_text(child, source_code)
        except Exception as e:
            logger.error(f"Error extracting docstring: {e}")
            
        return None
    
    @staticmethod
    def _get_node_text(node: Any, source_code: str) -> str:
        """Get the text of a node from the source code."""
        if not node or not hasattr(node, 'start_byte') or not hasattr(node, 'end_byte'):
            return ""
            
        try:
            start_byte = node.start_byte
            end_byte = node.end_byte
            
            if start_byte < 0 or end_byte > len(source_code.encode('utf-8')):
                return ""
                
            return source_code[start_byte:end_byte]
        except Exception as e:
            logger.error(f"Error getting node text: {e}")
            
            # Fallback to line/column method
            try:
                if hasattr(node, 'start_point') and hasattr(node, 'end_point'):
                    lines = source_code.splitlines(True)
                    start_row, start_col = node.start_point
                    end_row, end_col = node.end_point
                    
                    if start_row == end_row:
                        # Node on a single line
                        if start_row < len(lines):
                            line = lines[start_row]
                            if start_col <= len(line) and end_col <= len(line):
                                return line[start_col:end_col]
                    else:
                        # Node spans multiple lines
                        result = []
                        for i in range(start_row, min(end_row + 1, len(lines))):
                            line = lines[i]
                            if i == start_row:
                                result.append(line[start_col:])
                            elif i == end_row:
                                result.append(line[:end_col])
                            else:
                                result.append(line)
                        return "".join(result)
            except Exception as e:
                logger.error(f"Error using fallback text extraction: {e}")
            
            return ""
    
    @staticmethod
    def _fallback_parse(source_code: str, language_name: str, file_path: Optional[str] = None) -> Optional[CodeModule]:
        """Fallback to regex parsing for supported languages."""
        if language_name == 'python':
            return fallback_parse_python(source_code, file_path)
        else:
            logger.warning(f"No fallback parser for {language_name}")
            return None

def fallback_parse_python(source_code: str, file_path: Optional[str] = None) -> Optional[CodeModule]:
    """
    A simple regex-based parser for Python when tree-sitter is not available.
    
    Args:
        source_code: Python source code
        file_path: Optional path to the source file
        
    Returns:
        CodeModule with basic structure extraction
    """
    try:
        module = CodeModule(
            path=file_path or "unknown",
            language="python",
            source_code=source_code
        )
        
        # Extract module docstring
        docstring_matches = list(re.finditer(PYTHON_DOCSTRING_PATTERN, source_code, re.DOTALL))
        if docstring_matches and docstring_matches[0].start() < 100:  # If it's near the beginning
            module.docstring = docstring_matches[0].group(1).strip()
        
        # Extract functions
        lines = source_code.split('\n')
        line_indices = {i: line for i, line in enumerate(lines)}
        
        # Track current class for method association
        current_class = None
        class_indent = 0
        
        for i, line in line_indices.items():
            # Check for class definition
            class_match = re.search(PYTHON_CLASS_PATTERN, line)
            if class_match:
                indent = len(line) - len(line.lstrip())
                class_name = class_match.group(1)
                
                # Find class body and docstring
                class_body = []
                for j in range(i + 1, len(lines)):
                    if j in line_indices and len(line_indices[j]) - len(line_indices[j].lstrip()) <= indent:
                        if line_indices[j].strip():  # Non-empty line
                            break
                    if j in line_indices:
                        class_body.append(line_indices[j])
                
                class_body_str = '\n'.join(class_body)
                
                # Extract class docstring
                class_docstring = None
                docstring_match = re.search(PYTHON_DOCSTRING_PATTERN, class_body_str, re.DOTALL)
                if docstring_match:
                    class_docstring = docstring_match.group(1).strip()
                
                # Create class object
                current_class = CodeClass(
                    name=class_name,
                    docstring=class_docstring,
                    start_line=i,
                    end_line=i + len(class_body),
                    language="python"
                )
                class_indent = indent
                module.classes.append(current_class)
                continue
            
            # Check for indentation to see if we're still in a class
            if current_class is not None:
                indent = len(line) - len(line.lstrip())
                if indent <= class_indent and line.strip():
                    current_class = None
            
            # Check for function/method definition
            func_match = re.search(PYTHON_FUNCTION_PATTERN, line)
            if func_match:
                indent = len(line) - len(line.lstrip())
                func_name = func_match.group(1)
                func_params = func_match.group(2)
                
                # Find function body and docstring
                func_body = []
                for j in range(i + 1, len(lines)):
                    if j in line_indices and len(line_indices[j]) - len(line_indices[j].lstrip()) <= indent:
                        if line_indices[j].strip():  # Non-empty line
                            break
                    if j in line_indices:
                        func_body.append(line_indices[j])
                
                func_body_str = '\n'.join(func_body)
                
                # Extract function docstring
                func_docstring = None
                docstring_match = re.search(PYTHON_DOCSTRING_PATTERN, func_body_str, re.DOTALL)
                if docstring_match:
                    func_docstring = docstring_match.group(1).strip()
                
                # Create function object
                func = CodeFunction(
                    name=func_name,
                    params=func_params,
                    body=func_body_str,
                    docstring=func_docstring,
                    start_line=i,
                    end_line=i + len(func_body),
                    language="python"
                )
                
                # Add to class or module
                if current_class is not None and indent > class_indent:
                    func.parent = current_class
                    current_class.methods.append(func)
                else:
                    module.functions.append(func)
        
        return module
    
    except Exception as e:
        logger.error(f"Error in fallback Python parser: {e}")
        return None

def detect_language(file_path: str) -> Optional[str]:
    """
    Detect the programming language of a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language name or None if not detected
    """
    ext = os.path.splitext(file_path)[1].lower()
    return FILE_EXT_TO_LANGUAGE.get(ext)

def is_supported_language(file_path: str) -> bool:
    """
    Check if a file's language is supported by the parser.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if supported, False otherwise
    """
    return detect_language(file_path) is not None

def parse_file(file_path: str) -> Optional[CodeModule]:
    """
    Parse a file and extract its code structure.
    
    Args:
        file_path: Path to the file
        
    Returns:
        CodeModule or None if parsing failed
    """
    if TREE_SITTER_AVAILABLE:
        return TreeSitterParser.parse_file(file_path)
    else:
        # Use fallback parser
        logger.warning("Using fallback parser")
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                
            # Detect language
            language_name = detect_language(file_path)
            if not language_name:
                logger.warning(f"Unsupported file type: {file_path}")
                return None
                
            if language_name == 'python':
                return fallback_parse_python(source_code, file_path)
            else:
                logger.error(f"No fallback parser available for {language_name}")
                return None
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None

def parse_code(code: str, language: str) -> Optional[CodeModule]:
    """
    Parse code string and extract its structure.
    
    Args:
        code: Source code string
        language: Language name (e.g. 'python')
        
    Returns:
        CodeModule or None if parsing failed
    """
    if TREE_SITTER_AVAILABLE:
        try:
            if LANGUAGE_PACK_AVAILABLE:
                # Use tree-sitter-language-pack for reliable parsing
                try:
                    # Get the parser and language - should work consistently across versions
                    parser = get_parser(language)
                    lang_obj = get_language(language)
                    
                    tree = parser.parse(bytes(code, 'utf-8'))
                    
                    # Create module
                    module = CodeModule(
                        path="<string>",
                        language=language,
                        source_code=code
                    )
                    
                    # Extract structures
                    TreeSitterParser._extract_module_docstring(tree.root_node, code, module)
                    TreeSitterParser._extract_functions(tree.root_node, code, lang_obj, module)
                    TreeSitterParser._extract_classes(tree.root_node, code, lang_obj, module)
                    
                    return module
                except Exception as e:
                    logger.error(f"Error using tree-sitter-language-pack: {e}")
                    # Try other methods
            
            # Try tree-sitter-languages or basic tree-sitter as fallback
            if 'tree_sitter_languages' in sys.modules and not LANGUAGE_PACK_AVAILABLE:
                # Using tree-sitter-languages with compatibility handling
                try:
                    # Get the parser - this is usually safe
                    parser = get_parser(language)
                    
                    # For get_language, we need to handle the compatibility issue
                    try:
                        # Normal way for tree-sitter < 0.22
                        lang_obj = get_language(language)
                    except TypeError as e:
                        if "__init__() takes exactly 1 argument (2 given)" in str(e):
                            logger.warning("Detected tree-sitter 0.22+ compatibility issue. Using direct language module.")
                            # Fall back to direct language module
                            lang_obj = TreeSitterParser._get_language_lib(language)
                            if not lang_obj:
                                raise ValueError(f"Could not load language {language} with either method")
                        else:
                            raise
                    
                    tree = parser.parse(bytes(code, 'utf-8'))
                    
                    # Create module
                    module = CodeModule(
                        path="<string>",
                        language=language,
                        source_code=code
                    )
                    
                    # Extract structures
                    TreeSitterParser._extract_module_docstring(tree.root_node, code, module)
                    TreeSitterParser._extract_functions(tree.root_node, code, lang_obj, module)
                    TreeSitterParser._extract_classes(tree.root_node, code, lang_obj, module)
                    
                    return module
                except Exception as e:
                    logger.error(f"Error using tree-sitter-languages: {e}")
                    # Continue to try basic tree-sitter
            
            # Try basic tree-sitter
            try:
                # Get language library directly
                lang_lib = TreeSitterParser._get_language_lib(language)
                if not lang_lib:
                    # If we can't get it directly, fall back to regex parser
                    logger.warning(f"No language lib for {language}, using fallback parser")
                    return TreeSitterParser._fallback_parse(code, language) if language == 'python' else None
                    
                parser = Parser()
                parser.set_language(lang_lib)
                
                tree = parser.parse(bytes(code, 'utf-8'))
                
                # Create module
                module = CodeModule(
                    path="<string>",
                    language=language,
                    source_code=code
                )
                
                # Extract structures
                TreeSitterParser._extract_module_docstring(tree.root_node, code, module)
                TreeSitterParser._extract_functions(tree.root_node, code, lang_lib, module)
                TreeSitterParser._extract_classes(tree.root_node, code, lang_lib, module)
                
                return module
            except Exception as e:
                logger.error(f"Error with direct tree-sitter: {e}")
                # Continue to fallback parser
            
        except Exception as e:
            logger.error(f"Error parsing code with tree-sitter: {e}")
            # Fall back to regex parser
    
    # Fallback to regex parser for Python or if tree-sitter failed
    logger.warning(f"Using fallback parser for {language}")
    if language == 'python':
        return fallback_parse_python(code)
    else:
        logger.error(f"No fallback parser available for {language}")
        return None

def extract_structure(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract code structure from a file as a dictionary.
    Useful for JSON serialization and API responses.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with code structure or None if parsing failed
    """
    module = parse_file(file_path)
    if not module:
        return None
        
    # Convert to dictionary format
    result = {
        "path": module.path,
        "language": module.language,
        "docstring": module.docstring,
        "functions": [],
        "classes": []
    }
    
    # Add functions
    for func in module.functions:
        result["functions"].append({
            "name": func.name,
            "params": func.params,
            "docstring": func.docstring,
            "start_line": func.start_line,
            "end_line": func.end_line
        })
    
    # Add classes
    for cls in module.classes:
        class_info = {
            "name": cls.name,
            "docstring": cls.docstring,
            "start_line": cls.start_line,
            "end_line": cls.end_line,
            "methods": []
        }
        
        # Add methods
        for method in cls.methods:
            class_info["methods"].append({
                "name": method.name,
                "params": method.params,
                "docstring": method.docstring,
                "start_line": method.start_line,
                "end_line": method.end_line
            })
            
        result["classes"].append(class_info)
    
    return result

def get_supported_languages() -> List[str]:
    """
    Get a list of supported programming languages.
    
    Returns:
        List of language names
    """
    return list(set(FILE_EXT_TO_LANGUAGE.values())) 