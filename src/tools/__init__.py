"""
DocPilot Tools
==============

Collection of tools for code analysis, documentation handling, and repository interaction.
"""

# Import tools from respective modules to make them available under tools.*
from .code_tools import (
    get_code_structure,
    get_function_details,
    get_class_details,
    # Commented out as it seems deprecated or less used
    # find_relevant_code_snippets 
)
from .doc_tools import (
    scan_docs,
    get_doc_content,
    find_docs_to_update,
    get_doc_update_suggestions,
)
from .repo_tools import (
    scan_repository,
    get_tech_stack,
    identify_api_components,
    generate_repo_tree,
)

# Import the new API tools
from .api_tools import (
    detect_api_framework,
    extract_api_endpoints,
    extract_api_schemas,
)

# Define __all__ for explicit public interface
__all__ = [
    # Code Tools
    "get_code_structure",
    "get_function_details",
    "get_class_details",
    # Doc Tools
    "scan_docs",
    "get_doc_content",
    "find_docs_to_update",
    "get_doc_update_suggestions",
    # Repo Tools
    "scan_repository",
    "get_tech_stack",
    "identify_api_components",
    "generate_repo_tree",
    # API Tools (New)
    "detect_api_framework",
    "extract_api_endpoints",
    "extract_api_schemas",
]

# Optional: Logging configuration for the tools module if needed
# from ..utils.logging import core_logger
# logger = core_logger()
# logger.debug("DocPilot tools module loaded.") 