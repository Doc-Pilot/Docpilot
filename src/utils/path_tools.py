"""
Path Utility Tools
=================

Utilities for finding files and resolving paths within a repository.
"""

import os
import re
from typing import Optional

from ..utils.logging import core_logger
logger = core_logger()

# TODO: Replace simulation with actual grep_search tool call
# from ..tools.search_tools import grep_search

def find_python_file_defining_variable(
    repo_path: str,
    variable_name: str,
    type_name: str = "APIRouter" # Default to finding FastAPI routers
) -> Optional[str]:
    """
    Searches Python files within a repository to find the relative path
    of the file defining a variable with a specific type assignment.

    Args:
        repo_path: The absolute path to the repository root.
        variable_name: The name of the variable to find (e.g., 'github_router').
        type_name: The type being assigned (e.g., 'APIRouter').

    Returns:
        The relative path to the file if found, otherwise None.
    """
    logger.info(f"Searching for file defining '{variable_name} = {type_name}()' in {repo_path}")

    # Construct a regex pattern to find the assignment
    # Pattern: variable_name whitespace? = whitespace? TypeName whitespace? (
    # Allow optional leading whitespace
    pattern = rf"^\\s*{re.escape(variable_name)}\\s*=\\s*{re.escape(type_name)}\\s*\\(\""

    try:
        # --- SIMULATED GREP SEARCH ---
        # Replace this block with the actual tool call when available
        search_results = {"success": False, "matches": []}
        found_match = False
        for root, _, files in os.walk(repo_path):
            if found_match: break # Optimization: Stop walking once found
            for file in files:
                if file.endswith(".py"):
                    file_abs_path = os.path.join(root, file)
                    try:
                        with open(file_abs_path, 'r', encoding='utf-8') as f:
                            for line_num, line in enumerate(f):
                                if re.search(pattern, line):
                                    file_rel_path = os.path.relpath(file_abs_path, repo_path)
                                    search_results["matches"] = [{'file': file_rel_path, 'line': line_num + 1, 'content': line.strip()}]
                                    search_results["success"] = True
                                    found_match = True
                                    break # Found in this file
                    except Exception as e:
                        logger.warning(f"Could not read file {file_abs_path} during search: {e}")
                if found_match: break # Stop inner loop once found
        # --- END SIMULATED GREP SEARCH ---

        # Uncomment and adapt when grep_search tool is available:
        # search_results = grep_search(
        #     query=pattern,
        #     include_pattern='*.py',
        #     # Assuming grep_search operates relative to the workspace/repo_path context
        # )

        if search_results.get("success") and search_results.get("matches"):
            first_match = search_results["matches"][0]
            relative_path = first_match.get("file")
            if relative_path:
                relative_path = relative_path.replace(os.sep, '/')
                logger.info(f"Found definition of '{variable_name}' in: {relative_path}")
                return relative_path
            else:
                logger.warning(f"Grep search succeeded but no file path found in match for '{variable_name}'.")
        else:
            logger.warning(f"Could not find file defining '{variable_name} = {type_name}()'. Grep search failed or returned no matches.")

    except Exception as e:
        logger.error(f"Error during file search for variable '{variable_name}': {e}", exc_info=True)

    return None