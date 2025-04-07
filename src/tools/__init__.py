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
    find_undocumented_elements,
    calculate_documentation_coverage,
    get_function_details,
    get_class_details,
    get_supported_languages
)

from .doc_tools import (
    scan_docs,
    get_doc_by_type,
    get_doc_content,
    find_docs_to_update,
    get_doc_update_suggestions,
    get_doc_categories,
    extract_doc_section,
    validate_doc_links,
    extract_doc_structure
)

from .repo_tools import (
    scan_repository,
    generate_repo_tree,
    get_tech_stack,
    get_code_files,
    identify_api_components
)

# Make all functions available at module level
__all__ = [
    # Code analysis tools
    "get_code_structure",
    "parse_code_snippet",
    "find_undocumented_elements",
    "calculate_documentation_coverage",
    "get_function_details",
    "get_class_details",
    "get_supported_languages",
    
    # Documentation tools
    "scan_docs",
    "get_doc_by_type",
    "get_doc_content",
    "find_docs_to_update",
    "get_doc_update_suggestions",
    "get_doc_categories",
    "extract_doc_section",
    "validate_doc_links",
    "extract_doc_structure",
    
    # Repository tools
    "scan_repository",
    "generate_repo_tree",
    "get_tech_stack",
    "get_code_files",
    "identify_api_components"
] 