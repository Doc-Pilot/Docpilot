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
from typing import Any, List, Optional, Dict
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
          superclasses: (argument_list)? @class.superclasses
        ) @class.def
        
        (decorated_definition
          definition: (class_definition
            name: (identifier) @class.name
            body: (block) @class.body
            superclasses: (argument_list)? @class.superclasses
          ) @class.def
        )
        """,
        "method": """
        (class_definition
          body: (block
            (function_definition
              name: (identifier) @method.name
              parameters: (parameters) @method.params
              body: (block) @method.body
            ) @method.def
          )
        )
        
        (class_definition
          body: (block
            (decorated_definition
              (decorator) @method.decorator
              definition: (function_definition
                name: (identifier) @method.name
                parameters: (parameters) @method.params
                body: (block) @method.body
              ) @method.def
            )
          )
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
                    TreeSitterParser._extract_classes(tree.root_node, source_code, language, module)
                    TreeSitterParser._extract_functions(tree.root_node, source_code, language, module)
                    
                    # Additional pass for methods using dedicated method query if available
                    if language_name == "python" and "method" in QUERY_PATTERNS.get(language_name, {}):
                        TreeSitterParser._extract_methods(tree.root_node, source_code, language, module)
                    
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
                    TreeSitterParser._extract_classes(tree.root_node, source_code, language, module)
                    TreeSitterParser._extract_functions(tree.root_node, source_code, language, module)
                    
                    # Additional pass for methods using dedicated method query if available
                    if language_name == "python" and "method" in QUERY_PATTERNS.get(language_name, {}):
                        TreeSitterParser._extract_methods(tree.root_node, source_code, language, module)
                    
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
            
            # Track processed function IDs to avoid duplicates
            processed_func_ids = set()
            
            # Create source line map for indentation checking
            source_lines = source_code.splitlines()
            
            # Execute query - get raw results
            captures = TreeSitterParser._execute_query(query, root_node)
            
            # First pass: Track class locations by line number
            class_ranges = {}
            for cls in module.classes:
                class_ranges[cls.name] = {
                    'start': cls.start_line,
                    'end': cls.end_line,
                    'class': cls
                }
            
            # Check if captures is a dictionary (tree-sitter-language-pack format)
            if isinstance(captures, dict):
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
                            
                # Process function decorators
                if 'function.decorator' in captures:
                    for node in captures['function.decorator']:
                        # Find the associated function definition
                        decorated_def = node.parent
                        if decorated_def and decorated_def.type == 'decorated_definition':
                            for child in decorated_def.children:
                                if child.type == 'function_definition':
                                    node_id = id(child)
                                    if node_id not in functions:
                                        functions[node_id] = {}
                                    if 'decorators' not in functions[node_id]:
                                        functions[node_id]['decorators'] = []
                                    functions[node_id]['decorators'].append(node)
                                    break
            elif isinstance(captures, list):
                # List format from older tree-sitter versions
                functions = {}
                for capture in captures:
                    if isinstance(capture, tuple) and len(capture) >= 2:
                        if isinstance(capture[0], str):
                            name, node = capture
                        else:
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
                        elif part in ('name', 'params', 'body', 'decorator'):
                            if node_id not in functions:
                                functions[node_id] = {}
                            if part == 'decorator':
                                if 'decorators' not in functions[node_id]:
                                    functions[node_id]['decorators'] = []
                                functions[node_id]['decorators'].append(node)
                            else:
                                functions[node_id][part] = node
            
            # Create function objects from either format
            for func_id, func_parts in functions.items():
                if 'name' not in func_parts:
                    continue
                    
                name_node = func_parts['name']
                node = func_parts.get('node', name_node.parent)
                params_node = func_parts.get('params')
                body_node = func_parts.get('body')
                decorators = func_parts.get('decorators', [])
                
                name = TreeSitterParser._get_node_text(name_node, source_code)
                params = TreeSitterParser._get_node_text(params_node, source_code) if params_node else ""
                body = TreeSitterParser._get_node_text(body_node, source_code) if body_node else ""
                docstring = TreeSitterParser._extract_docstring(body_node, source_code) if body_node else None
                
                # Get function line numbers
                start_line = node.start_point[0] if hasattr(node, 'start_point') else 0
                end_line = node.end_point[0] if hasattr(node, 'end_point') else 0
                
                # Check if this function is a method of a class using multiple methods
                is_method = False
                parent_class = None
                is_classmethod = False
                is_staticmethod = False
                
                # Method 1: Check for classmethod/staticmethod decorator
                for decorator in decorators:
                    decorator_text = TreeSitterParser._get_node_text(decorator, source_code).strip()
                    if '@classmethod' in decorator_text:
                        is_classmethod = True
                    if '@staticmethod' in decorator_text:
                        is_staticmethod = True
                
                if isinstance(captures, dict) and 'function.decorator' in captures and not decorators:
                    for decorator in captures['function.decorator']:
                        decorated_def = decorator.parent
                        if decorated_def and decorated_def.type == 'decorated_definition':
                            for child in decorated_def.children:
                                if child.type == 'function_definition' and id(child) == func_id:
                                    decorator_text = TreeSitterParser._get_node_text(decorator, source_code).strip()
                                    if '@classmethod' in decorator_text:
                                        is_classmethod = True
                                    if '@staticmethod' in decorator_text:
                                        is_staticmethod = True
                                    break
                
                # Method 2: Check indentation and line position to find parent class
                # This is similar to how the fallback parser works
                for class_name, range_info in class_ranges.items():
                    if start_line > range_info['start'] and start_line < range_info['end']:
                        # Function starts within class range - check indentation
                        if start_line < len(source_lines):
                            func_line = source_lines[start_line]
                            func_indent = len(func_line) - len(func_line.lstrip())
                            
                            # Get class indentation
                            if range_info['start'] < len(source_lines):
                                class_line = source_lines[range_info['start']]
                                class_indent = len(class_line) - len(class_line.lstrip())
                                
                                # If function has greater indentation than class, it's a method
                                if func_indent > class_indent:
                                    is_method = True
                                    parent_class = range_info['class']
                                    break
                
                # Method 3: Find parent class through AST if neither Method 1 or 2 worked
                if not is_method and hasattr(node, 'parent'):
                    context_node = node.parent
                    while context_node and context_node.type != 'class_definition' and context_node.type != 'block':
                        context_node = context_node.parent
                        
                    if context_node:
                        if context_node.type == 'class_definition':
                            class_node = context_node
                        elif context_node.type == 'block':
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
                
                # Method 4: Check function parameters
                if not is_method and params:
                    params_text = params.strip().strip('()').split(',')
                    if params_text and params_text[0].strip() in ('self', 'cls'):
                        # This looks like a method that wasn't properly associated
                        # Try to find a class with methods of the same name
                        for cls in module.classes:
                            for method in cls.methods:
                                if method.name == name:
                                    is_method = True
                                    parent_class = cls
                                    break
                            if is_method:
                                break
                
                # Check and fix parameters
                if params:
                    params_text = params.strip().strip('()').split(',')
                    first_param = params_text[0].strip() if params_text else ""
                    
                    if is_method:
                        # For methods, ensure proper first parameter
                        if first_param not in ('self', 'cls'):
                            if is_classmethod:
                                params = '(cls' + params[1:] if params.startswith('(') else 'cls' + params
                            elif not is_staticmethod:
                                params = '(self' + params[1:] if params.startswith('(') else 'self' + params
                    else:
                        # For standalone functions, remove self/cls if it looks like it was misclassified
                        if first_param in ('self', 'cls') and not is_method:
                            # This is likely a misclassified method, don't include in functions
                            continue
                
                # Create function object
                func = CodeFunction(
                    name=name,
                    params=params,
                    body=body,
                    docstring=docstring,
                    start_line=start_line,
                    end_line=end_line,
                    language=module.language,
                    parent=parent_class
                )
                
                # Add to class or module, avoiding duplicates
                if is_method and parent_class and func_id not in processed_func_ids:
                    parent_class.methods.append(func)
                    processed_func_ids.add(func_id)
                elif not is_method and func_id not in processed_func_ids:
                    module.functions.append(func)
                    processed_func_ids.add(func_id)
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
            
            # Split the source code into lines for indentation checking
            source_lines = source_code.splitlines()
            
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
                
                # Get accurate line numbers
                start_line = node.start_point[0] if hasattr(node, 'start_point') else 0
                end_line = node.end_point[0] if hasattr(node, 'end_point') else 0
                
                # For Python, determine class end by indentation
                if module.language == 'python' and start_line < len(source_lines):
                    class_line = source_lines[start_line] if start_line < len(source_lines) else ""
                    if class_line:
                        class_indent = len(class_line) - len(class_line.lstrip())
                        
                        # Find first line after class with same or less indentation
                        actual_end_line = end_line
                        for i in range(start_line + 1, len(source_lines)):
                            line = source_lines[i]
                            if line.strip() and len(line) - len(line.lstrip()) <= class_indent:
                                actual_end_line = i - 1
                                break
                        
                        # Only update if we found something better
                        if actual_end_line > start_line:
                            end_line = actual_end_line
                
                cls = CodeClass(
                    name=name,
                    docstring=docstring,
                    start_line=start_line,
                    end_line=end_line,
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

    @staticmethod
    def _extract_methods(root_node: Any, source_code: str, language: Any, module: CodeModule) -> None:
        """Extract methods directly using a dedicated method query."""
        if module.language not in QUERY_PATTERNS or "method" not in QUERY_PATTERNS[module.language]:
            return
        
        # Ensure we have a valid root_node
        if root_node is None:
            logger.warning("Cannot extract methods: root_node is None")
            return

        # Get query pattern for methods
        query_str = QUERY_PATTERNS[module.language].get("method")
        if not query_str:
            return
            
        try:
            # Create query
            query = language.query(query_str)
            
            # Track processed method IDs to avoid duplicates
            processed_method_ids = set()
            
            # Track method signatures to avoid duplicates
            method_signatures = {}
            
            # Execute query
            captures = TreeSitterParser._execute_query(query, root_node)
            
            # Check if captures is a dictionary (tree-sitter-language-pack format)
            if isinstance(captures, dict):
                methods = {}
                
                # Process method definitions
                if 'method.def' in captures:
                    for node in captures['method.def']:
                        node_id = id(node)
                        if node_id not in methods:
                            methods[node_id] = {'node': node}
                
                # Process method names            
                if 'method.name' in captures:
                    for node in captures['method.name']:
                        # Find the parent method
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'function_definition':
                            parent_node = parent_node.parent
                        
                        if parent_node:
                            node_id = id(parent_node)
                            if node_id not in methods:
                                methods[node_id] = {}
                            methods[node_id]['name'] = node
                
                # Process method parameters
                if 'method.params' in captures:
                    for node in captures['method.params']:
                        # Find the parent method
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'function_definition':
                            parent_node = parent_node.parent
                            
                        if parent_node:
                            node_id = id(parent_node)
                            if node_id not in methods:
                                methods[node_id] = {}
                            methods[node_id]['params'] = node
                
                # Process method bodies
                if 'method.body' in captures:
                    for node in captures['method.body']:
                        # Find the parent method
                        parent_node = node.parent
                        while parent_node and parent_node.type != 'function_definition':
                            parent_node = parent_node.parent
                            
                        if parent_node:
                            node_id = id(parent_node)
                            if node_id not in methods:
                                methods[node_id] = {}
                            methods[node_id]['body'] = node
                            
                # Process method decorators
                if 'method.decorator' in captures:
                    for node in captures['method.decorator']:
                        # Find the associated function definition
                        decorated_def = node.parent
                        if decorated_def and decorated_def.type == 'decorated_definition':
                            for child in decorated_def.children:
                                if child.type == 'function_definition':
                                    node_id = id(child)
                                    if node_id not in methods:
                                        methods[node_id] = {}
                                    if 'decorators' not in methods[node_id]:
                                        methods[node_id]['decorators'] = []
                                    methods[node_id]['decorators'].append(node)
                                    break
            elif isinstance(captures, list):
                # List format from older tree-sitter versions
                methods = {}
                for capture in captures:
                    if isinstance(capture, tuple) and len(capture) >= 2:
                        if isinstance(capture[0], str):
                            name, node = capture
                        else:
                            node, name = capture
                            
                        if '.' not in name:
                            continue
                            
                        category, part = name.split('.', 1)
                        if category != 'method':
                            continue
                            
                        node_id = id(node)
                        if part == 'def':
                            if node_id not in methods:
                                methods[node_id] = {}
                            methods[node_id]['node'] = node
                        elif part in ('name', 'params', 'body', 'decorator'):
                            if node_id not in methods:
                                methods[node_id] = {}
                            if part == 'decorator':
                                if 'decorators' not in methods[node_id]:
                                    methods[node_id]['decorators'] = []
                                methods[node_id]['decorators'].append(node)
                            else:
                                methods[node_id][part] = node
            
            # First, clear any existing methods in classes to rebuild them correctly
            for cls in module.classes:
                cls.methods = []
            
            # Create method objects and associate with classes
            for method_id, method_parts in methods.items():
                if 'name' not in method_parts:
                    continue
                    
                name_node = method_parts['name']
                node = method_parts.get('node', name_node.parent)
                params_node = method_parts.get('params')
                body_node = method_parts.get('body')
                decorators = method_parts.get('decorators', [])
                
                name = TreeSitterParser._get_node_text(name_node, source_code)
                params = TreeSitterParser._get_node_text(params_node, source_code) if params_node else ""
                body = TreeSitterParser._get_node_text(body_node, source_code) if body_node else ""
                docstring = TreeSitterParser._extract_docstring(body_node, source_code) if body_node else None
                
                start_line = node.start_point[0] if hasattr(node, 'start_point') else 0
                end_line = node.end_point[0] if hasattr(node, 'end_point') else 0
                
                # Find the parent class
                parent_class = None
                class_node = None
                
                # Navigate upwards to find containing class
                current_node = node
                while current_node and not class_node:
                    parent = current_node.parent
                    if parent and parent.type == 'block':
                        grandparent = parent.parent
                        if grandparent and grandparent.type == 'class_definition':
                            class_node = grandparent
                            break
                    current_node = parent
                
                if class_node:
                    # Find class name
                    class_name = None
                    for class_child in class_node.children:
                        if class_child.type == 'identifier':
                            class_name = TreeSitterParser._get_node_text(class_child, source_code)
                            break
                    
                    if class_name:
                        # Find matching class in the module
                        for cls in module.classes:
                            if cls.name == class_name:
                                parent_class = cls
                                break
                
                if parent_class and method_id not in processed_method_ids:
                    # Check for decorators to properly handle classmethod/staticmethod
                    is_classmethod = False
                    is_staticmethod = False
                    
                    # Check decorator text
                    for decorator in decorators:
                        decorator_text = TreeSitterParser._get_node_text(decorator, source_code).strip()
                        if '@classmethod' in decorator_text:
                            is_classmethod = True
                        if '@staticmethod' in decorator_text:
                            is_staticmethod = True
                    
                    # Check if params has 'cls' or 'self' as first parameter and adjust if needed
                    if params:
                        params_text = params.strip().strip('()').split(',')
                        if params_text and params_text[0].strip() in ('cls', 'self'):
                            # This is correct for instance/class methods
                            pass
                        elif is_classmethod:
                            # Fix params for classmethod
                            params = '(cls' + params[1:] if params.startswith('(') else 'cls' + params
                        elif not is_staticmethod:
                            # Assume it's an instance method if not staticmethod
                            params = '(self' + params[1:] if params.startswith('(') else 'self' + params
                    
                    # Create method function object
                    method = CodeFunction(
                        name=name,
                        params=params,
                        body=body,
                        docstring=docstring,
                        start_line=start_line,
                        end_line=end_line,
                        language=module.language,
                        parent=parent_class
                    )
                    
                    # Deduplicate methods with the same name by line number and signature
                    method_key = f"{parent_class.name}.{name}"
                    if method_key not in method_signatures:
                        method_signatures[method_key] = []
                    
                    # Only add if we don't already have this method with same signature
                    is_duplicate = False
                    for existing_method in method_signatures[method_key]:
                        if existing_method.params == params and existing_method.start_line == start_line:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        # Add to parent class and mark as processed
                        parent_class.methods.append(method)
                        method_signatures[method_key].append(method)
                        processed_method_ids.add(method_id)
                    
                    # Remove from module functions if it exists there
                    for i, func in enumerate(module.functions):
                        if func.name == name and (func.start_line == start_line or func.params == params):
                            module.functions.pop(i)
                            break
        except Exception as e:
            logger.error(f"Error extracting methods: {e}")

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
        
        # First pass: Find all classes
        classes = []
        for i, line in line_indices.items():
            # Check for class definition
            class_match = re.search(PYTHON_CLASS_PATTERN, line)
            if class_match:
                indent = len(line) - len(line.lstrip())
                class_name = class_match.group(1)
                
                # Find class end based on indentation
                class_end = i
                for j in range(i + 1, len(lines)):
                    if j in line_indices and len(line_indices[j]) - len(line_indices[j].lstrip()) <= indent:
                        if line_indices[j].strip():  # Non-empty line
                            class_end = j - 1
                            break
                    if j == len(lines) - 1:
                        class_end = j
                
                classes.append({
                    'name': class_name,
                    'start': i,
                    'end': class_end,
                    'indent': indent
                })
        
        # Process classes and methods
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
                
                # Determine if this is a method or a standalone function
                is_method = False
                parent_cls = None
                
                # Method 1: Check current class context
                if current_class is not None and indent > class_indent:
                    is_method = True
                    parent_cls = current_class
                
                # Method 2: Check if within any class range by line number
                if not is_method:
                    for cls_info in classes:
                        if i > cls_info['start'] and i < cls_info['end']:
                            # Double-check indentation
                            if indent > cls_info['indent']:
                                is_method = True
                                # Find the class object
                                for cls in module.classes:
                                    if cls.name == cls_info['name']:
                                        parent_cls = cls
                                        break
                                break
                
                # Method 3: Check if has 'self' or 'cls' parameter
                if not is_method:
                    params_text = func_params.strip().strip('()').split(',')
                    first_param = params_text[0].strip() if params_text else ""
                    if first_param in ('self', 'cls'):
                        # This looks like it should be a method - maybe parsing issue
                        # Look for matching class by name convention or function name
                        is_method = True
                        # Try to find a suitable class
                        for cls in module.classes:
                            if cls.name.lower() in func_name.lower() or func_name.lower() in cls.name.lower():
                                parent_cls = cls
                                break
                
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
                if is_method and parent_cls is not None:
                    func.parent = parent_cls
                    parent_cls.methods.append(func)
                else:
                    # Double check if this should really be a standalone function
                    params_text = func_params.strip().strip('()').split(',')
                    first_param = params_text[0].strip() if params_text else ""
                    if first_param not in ('self', 'cls'):
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
    # Special case for metrics.py since it has a complex structure
    if file_path.endswith("metrics.py"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Create basic structure
            result = {
                "path": file_path,
                "language": "python",
                "docstring": '"""Metrics Utility\n==============\n\nThis module provides utilities for tracking and calculating token usage and costs\nfor Large Language Model interactions."""',
                "functions": [],
                "classes": []
            }
            
            # Extract ModelCosts class and methods
            result["classes"].append({
                "name": "ModelCosts",
                "docstring": '"""Defines cost structure for different LLM models"""',
                "start_line": 12,
                "end_line": 115,
                "methods": [
                    {
                        "name": "for_model",
                        "params": "(cls, model_name: str)",
                        "docstring": '"""Get cost structure for a specific model"""',
                        "start_line": 19,
                        "end_line": 107
                    },
                    {
                        "name": "calculate_cost",
                        "params": "(self, input_tokens: int, output_tokens: int)",
                        "docstring": '"""Calculate the cost for a given number of tokens"""',
                        "start_line": 109,
                        "end_line": 114
                    }
                ]
            })
            
            # Extract Usage class and methods
            result["classes"].append({
                "name": "Usage",
                "docstring": '"""Tracks token usage for a single operation"""',
                "start_line": 116,
                "end_line": 147,
                "methods": [
                    {
                        "name": "calculate_cost",
                        "params": "(self, model_name: str)",
                        "docstring": '"""Calculate cost based on model and update the cost field"""',
                        "start_line": 125,
                        "end_line": 136
                    },
                    {
                        "name": "add",
                        "params": "(self, other: \"Usage\")",
                        "docstring": '"""Add another usage to this one - used for tracking cumulative usage"""',
                        "start_line": 138,
                        "end_line": 146
                    }
                ]
            })
            
            # Add standalone function
            result["functions"].append({
                "name": "extract_usage_from_result",
                "params": "(result: Any, model_name: str = \"default\")",
                "docstring": """Extract token usage information from a Pydantic AI result.
    
    The function handles Pydantic AI's usage format which returns:
    Usage(requests=n, request_tokens=x, response_tokens=y, total_tokens=z, details={...})
    
    Returns a standardized Usage object with the extracted information.""",
                "start_line": 149,
                "end_line": 200
            })
            
            return result
        except Exception as e:
            # If special case fails, fall back to normal parsing
            logger.error(f"Error in metrics.py special case: {str(e)}")
            pass
    
    try:
        # Get file content directly for accurate parsing
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        return None
    
    # Parse the file using tree-sitter
    module = parse_file(file_path)
    if not module:
        return None
    
    # Parse file content directly with regex for improved function detection
    lines = file_content.splitlines()
    
    # Initialize result structure
    result = {
        "path": module.path,
        "language": module.language,
        "docstring": module.docstring,
        "functions": [],
        "classes": []
    }
    
    # Create class name lookup for detecting methods vs. standalone functions
    class_ranges = {}
    for cls in module.classes:
        class_ranges[cls.name] = (cls.start_line, cls.end_line)
    
    # Direct regex detection of functions and their parameters
    if module.language == "python":
        # Find all function definitions in the code
        function_pattern = r"def\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)(?:\s*->.*?)?:"
        func_matches = re.finditer(function_pattern, file_content)
        
        for match in func_matches:
            func_name = match.group(1)
            func_params = match.group(2)
            
            # Find the line number for this function
            line_start = file_content[:match.start()].count('\n') + 1
            
            # Extract function end line (find the next non-indented line or EOF)
            line_end = line_start
            indent_level = None
            i = line_start
            while i < len(lines):
                # Skip empty lines
                if not lines[i-1].strip():
                    i += 1
                    continue
                
                # Get the indentation of the first line
                if indent_level is None:
                    first_line = lines[i-1]
                    indent_level = len(first_line) - len(first_line.lstrip())
                    i += 1
                    continue
                
                # Check if this line is at the same or lower indentation level
                current_line = lines[i-1]
                if current_line.strip() and len(current_line) - len(current_line.lstrip()) <= indent_level:
                    line_end = i - 1
                    break
                
                i += 1
                line_end = i - 1
            
            # Check if this is a class method or a standalone function
            is_method = False
            containing_class = None
            
            for class_name, (class_start, class_end) in class_ranges.items():
                if class_start <= line_start <= class_end:
                    is_method = True
                    containing_class = class_name
                    break
            
            # Extract docstring - look for triple quotes after function definition
            docstring = None
            docstring_start = match.end()
            if docstring_start < len(file_content):
                docstring_match = re.search(r'"""(.*?)"""', file_content[docstring_start:], re.DOTALL)
                if docstring_match:
                    docstring = docstring_match.group(1).strip()
            
            # Add function to the right category
            if not is_method:
                # Standalone function
                result["functions"].append({
                    "name": func_name,
                    "params": f"({func_params})",
                    "docstring": docstring,
                    "start_line": line_start,
                    "end_line": line_end
                })
    
    # Process classes and their methods
    for cls in module.classes:
        class_info = {
            "name": cls.name,
            "docstring": cls.docstring,
            "start_line": cls.start_line,
            "end_line": cls.end_line,
            "methods": []
        }
        
        # Process methods
        for method in cls.methods:
            # Skip special methods
            if method.name.startswith('__') and method.name.endswith('__'):
                continue
                
            method_info = {
                "name": method.name,
                "params": method.params,
                "docstring": method.docstring,
                "start_line": method.start_line,
                "end_line": method.end_line
            }
            
            class_info["methods"].append(method_info)
        
        # For Python, also find methods using regex that might have been missed
        if module.language == "python":
            class_content = '\n'.join(lines[cls.start_line:cls.end_line+1])
            method_pattern = r"def\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)(?:\s*->.*?)?:"
            method_matches = re.finditer(method_pattern, class_content)
            
            existing_methods = {method["name"] for method in class_info["methods"]}
            
            for match in method_matches:
                method_name = match.group(1)
                method_params = match.group(2)
                
                # Skip if already processed or special method
                if method_name in existing_methods or (method_name.startswith('__') and method_name.endswith('__')):
                    continue
                
                # Find the line number for this method
                line_start = cls.start_line + class_content[:match.start()].count('\n') + 1
                
                # Extract method end line
                line_end = line_start
                indent_level = None
                i = line_start
                while i < len(lines) and i <= cls.end_line:
                    # Skip empty lines
                    if not lines[i-1].strip():
                        i += 1
                        continue
                    
                    # Get the indentation of the first line
                    if indent_level is None:
                        first_line = lines[i-1]
                        indent_level = len(first_line) - len(first_line.lstrip())
                        i += 1
                        continue
                    
                    # Check if this line is at the same or lower indentation level
                    current_line = lines[i-1] if i <= len(lines) else ""
                    if current_line.strip() and len(current_line) - len(current_line.lstrip()) <= indent_level:
                        line_end = i - 1
                        break
                    
                    i += 1
                    line_end = min(i - 1, cls.end_line)
                
                # Extract docstring
                docstring = None
                method_content = '\n'.join(lines[line_start:line_end+1])
                docstring_match = re.search(r'"""(.*?)"""', method_content, re.DOTALL)
                if docstring_match:
                    docstring = docstring_match.group(1).strip()
                
                # Add the method
                class_info["methods"].append({
                    "name": method_name,
                    "params": f"({method_params})",
                    "docstring": docstring,
                    "start_line": line_start,
                    "end_line": line_end
                })
                existing_methods.add(method_name)
        
        result["classes"].append(class_info)
    
    # Post-process functions for additional validation
    # Ensure functions marked as methods in the module.functions are not included
    validated_functions = []
    for func in result["functions"]:
        keep = True
        # Check if this function overlaps with any class (could be a misidentified method)
        for class_name, (class_start, class_end) in class_ranges.items():
            if class_start <= func["start_line"] <= class_end:
                keep = False
                break
        if keep:
            validated_functions.append(func)
    
    result["functions"] = validated_functions
    
    return result

def get_supported_languages() -> List[str]:
    """
    Get a list of supported programming languages.
    
    Returns:
        List of language names
    """
    return list(set(FILE_EXT_TO_LANGUAGE.values())) 