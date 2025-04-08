"""
Tools Module
===========

This module provides a collection of tools that can be used by LLM agents 
to interact with code and documentation. Each tool is a standalone function
that can be called directly or via an agent system.

Categories:
- Code Analysis: Tools for parsing and analyzing code structure
- Documentation: Tools for generating and evaluating documentation
- Repository: Tools for analyzing repository structure and APIs
"""

# Import all tools for direct access from tools module
from .code_tools import (
    get_code_structure,
    parse_code_snippet,
    get_function_details,
    get_class_details,
    get_supported_languages
)

from .doc_tools import (
    scan_docs,
    find_docs_to_update,
    get_doc_update_suggestions,
    get_doc_content,
    get_doc_type,
)

from .repo_tools import (
    scan_repository,
    generate_repo_tree,
    get_tech_stack,
    identify_api_components
)

# Make all functions available at module level
__all__ = [
    # Code analysis tools
    "get_code_structure",
    "parse_code_snippet",
    "get_function_details",
    "get_class_details",
    "get_supported_languages",
    
    # Documentation tools
    "scan_docs",
    "find_docs_to_update",
    "get_doc_update_suggestions",
    "get_doc_content",
    "get_doc_type",
    
    # Repository tools
    "scan_repository",
    "generate_repo_tree",
    "get_tech_stack",
    "identify_api_components"
] 