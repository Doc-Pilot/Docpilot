"""
API Analysis Tools
===================

Functions for detecting API frameworks, extracting endpoints, and extracting schemas
from a given repository path. These functions utilize lower-level tools and parsers.
"""

import os
import re
import textwrap
import ast
from collections import defaultdict
from typing import Dict, Any, List, Optional

# Import logger
from ..utils.logging import core_logger
logger = core_logger()

# Import lower-level tools
from .code_tools import (
    get_code_structure,
    get_class_details,
)
from .repo_tools import (
    get_tech_stack,
    identify_api_components
)

# Import parsers
from ..parsers.fastapi_parser import parse_fastapi_endpoint, parse_pydantic_model, parse_fastapi_function
from ..utils.api_parsers import (
    parse_flask_endpoint, parse_express_endpoint,
    parse_django_endpoint, parse_generic_endpoint,
    parse_django_model, parse_typescript_model,
    parse_generic_model, is_data_model
)
# Ensure the utility is imported correctly
try:
    from ..utils.path_tools import find_python_file_defining_variable
except ImportError:
    logger.error("Could not import find_python_file_defining_variable from utils.path_tools. Router resolution will fail.")
    # Define a dummy function to avoid NameError later
    def find_python_file_defining_variable(*args, **kwargs) -> Optional[str]:
        logger.error("find_python_file_defining_variable is not available due to import error.")
        return None

# --- FastAPI Analysis using Tree-Sitter Tools ---

def _extract_endpoints_from_structure(
    file_path: str,
    structure: Dict[str, Any],
    source_code: str, # Need the source code for regex matching on decorators
    app_or_router_name: str,
    prefix: str = "/",
    repo_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extracts FastAPI endpoints from a file's structure provided by get_code_structure.
    Relies on regex matching on the source code snippet for decorators.
    """
    endpoints = []
    logger.info(f"Extracting endpoints for '{app_or_router_name}' with prefix '{prefix}' from {file_path}")

    # Regex to find @<name>.<method> decorators and capture path etc.
    # Needs refinement to handle complex args like response_model, status_code, tags
    decorator_pattern = re.compile(
        rf"""
        ^\\s*@\\s*{re.escape(app_or_router_name)}\\.(get|post|put|delete|patch|options|head|trace) # Decorator name and method
        \\s*\\(\\s*                                      # Opening parenthesis
        (?:\"(.*?)\"|\'(.*?)\')                         # Path argument (double or single quotes)
        (?:\\s*,.*?)?                                   # Optional other arguments
        \\s*\\)                                         # Closing parenthesis
        """,
        re.MULTILINE | re.VERBOSE
    )

    source_lines = source_code.splitlines()

    for func_info in structure.get("functions", []) + [m for cls in structure.get("classes", []) for m in cls.get("methods", [])]:
        func_name = func_info.get("name")
        start_line = func_info.get("start_line") # 1-based index
        end_line = func_info.get("end_line")     # 1-based index
        params_str = func_info.get("params", "()") # Includes parenthesis

        if not func_name or not start_line:
            continue

        # Search for the decorator just before the function definition
        # Check the few lines preceding the function start for the decorator
        search_start_line = max(0, start_line - 5) # Search a few lines above
        search_end_line = start_line               # Up to the function def line (1-based)
        
        # Adjust to 0-based index for list slicing
        preceding_code = "\\n".join(source_lines[search_start_line:search_end_line])

        match = decorator_pattern.search(preceding_code)
        if match:
            http_method = match.group(1).upper()
            # Path is captured in group 2 (double quotes) or 3 (single quotes)
            path = match.group(2) or match.group(3)
            
            # Basic path joining
            full_path = f"{prefix.rstrip('/')}/{path.lstrip('/')}" if prefix != "/" else path

            logger.info(f"  Found endpoint: {http_method} {full_path} -> {func_name}")
            
            # --- Placeholder: Extract more details ---
            # TODO: Parse params_str for request body model (type hints)
            # TODO: Parse decorator args string (if possible from regex or further parsing) for response_model, tags, status_code
            # TODO: Extract docstring (already available in func_info)
            request_model_name = None # Placeholder
            response_model_name = None # Placeholder
            tags = [] # Placeholder
            status_code = 200 # Placeholder
            parameters = [] # Placeholder (extract from params_str)
            
            # Crude parameter extraction (needs proper parsing)
            param_names = [p.split(':')[0].strip() for p in params_str.strip('()').split(',') if p.strip()]
            parameters = [{"name": p, "in": "query", "type": "string"} for p in param_names if p not in ['request', 'background_tasks']] # Very basic guess

            endpoint_data = {
                "path": full_path,
                "method": http_method,
                "name": func_name,
                "description": func_info.get("docstring", ""),
                "parameters": parameters,
                "request_model": request_model_name,
                "response_model": response_model_name,
                "status_code": status_code,
                "tags": tags,
                "source_file": file_path,
                "source_line": start_line,
            }
            endpoints.append(endpoint_data)
            # TODO: Collect schema names found (request_model_name, response_model_name, complex param types)

    return endpoints


def analyze_fastapi_app(repo_path: str, entry_point_file: str) -> Dict[str, Any]:
    """
    Analyzes a FastAPI application starting from an entry point file,
    using tree-sitter tools to identify endpoints and schemas.
    """
    logger.info(f"Starting FastAPI analysis using tree-sitter tools from entry point: {entry_point_file}")

    all_endpoints = []
    all_schemas = {} # Use dict {schema_name: schema_details} for deduplication
    # Placeholder for schema collection, as the old method is removed
    required_schemas_to_parse = set() # Tuples (source_file, class_name, schema_name_in_endpoint)

    entry_point_full_path = os.path.join(repo_path, entry_point_file) if not os.path.isabs(entry_point_file) else entry_point_file
    if not os.path.exists(entry_point_full_path):
         return {"success": False, "error": f"Entry point file not found: {entry_point_full_path}"}

    # --- Step 1: Parse Entry Point Structure & Source ---
    try:
        with open(entry_point_full_path, 'r', encoding='utf-8') as f:
            entry_source = f.read()
        entry_structure_result = get_code_structure(entry_point_full_path)
        if not entry_structure_result or not entry_structure_result.get("success"):
             logger.error(f"Could not get code structure for entry point: {entry_point_full_path}")
             return {"success": False, "error": f"Could not parse entry point structure: {entry_point_file}"}
        entry_structure = entry_structure_result
    except Exception as e:
        logger.error(f"Failed to read or get structure for entry point {entry_point_full_path}: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to read/parse entry point: {entry_point_file}"}

    # --- Step 2: Find FastAPI App Instance and Included Routers (Regex/String Search) ---
    app_variable_name = None
    included_routers = {} # {router_var_name: prefix}

    # Find app = FastAPI()
    app_match = re.search(r"(\w+)\s*=\s*FastAPI\(", entry_source)
    if app_match:
        app_variable_name = app_match.group(1)
        logger.info(f"Found FastAPI app instance variable: '{app_variable_name}' in {entry_point_file}")
    else:
        logger.warning(f"Could not find FastAPI app instantiation in {entry_point_file}. Assuming 'app'.")
        # Fallback or fail? Let's assume 'app' for now if it exists as a variable.
        # A better check would see if 'app' is defined at the top level in entry_structure.
        app_variable_name = "app" # Fallback assumption

    # Find app.include_router(router_variable, prefix="...")
    router_pattern = re.compile(rf"{re.escape(app_variable_name)}\.include_router\s*\(\s*(\w+)(?:\s*,\s*prefix\s*=\s*['\"](.*?)['\"])?")
    for match in router_pattern.finditer(entry_source):
        router_var_name = match.group(1)
        prefix = match.group(2) or "/"
        included_routers[router_var_name] = prefix
        logger.info(f"Found included router variable: '{router_var_name}' with prefix: '{prefix}' in {entry_point_file}")

    # --- Step 3: Extract Endpoints from Entry Point ---
    entry_endpoints = _extract_endpoints_from_structure(
        entry_point_file, entry_structure, entry_source, app_variable_name, "/", repo_path
    )
    all_endpoints.extend(entry_endpoints)
    # TODO: Collect schema names referenced in entry_endpoints

    # --- Step 4: Resolve and Parse Routers ---
    logger.info(f"Attempting to resolve and parse routers: {list(included_routers.keys())}")
    for router_var, prefix in included_routers.items():
        # --- Router Resolution Heuristic ---
        # TODO: Implement a robust way to find the file defining `router_var = APIRouter()`
        # Placeholder: Use a hypothetical utility or basic search
        router_file_relative = find_python_file_defining_variable(repo_path, router_var, "APIRouter")

        if not router_file_relative:
            logger.warning(f"Could not resolve source file for router variable '{router_var}'. Skipping.")
            continue

        router_full_path = os.path.join(repo_path, router_file_relative)
        logger.info(f"Resolved router '{router_var}' to file: {router_file_relative}")

        # --- Parse Router File ---
        try:
            with open(router_full_path, 'r', encoding='utf-8') as f:
                router_source = f.read()
            router_structure_result = get_code_structure(router_full_path)
            if not router_structure_result or not router_structure_result.get("success"):
                 logger.warning(f"Could not parse structure for router file: {router_file_relative}. Skipping.")
                 continue
            router_structure = router_structure_result
        except Exception as e:
            logger.warning(f"Failed to read/parse router file {router_file_relative}: {e}. Skipping.", exc_info=True)
            continue

        # --- Extract Endpoints from Router ---
        router_endpoints = _extract_endpoints_from_structure(
            router_file_relative, router_structure, router_source, router_var, prefix, repo_path
        )
        all_endpoints.extend(router_endpoints)
        # TODO: Collect schema names referenced in router_endpoints

    # --- Step 5: Identify and Parse Schemas (Placeholder) ---
    logger.info("Schema identification and parsing needs reimplementation based on collected schema names")
    identified_schema_files = [] # Placeholder
    # TODO: Use identify_api_components or other methods to find potential schema files
    # TODO: Based on schema names collected from endpoints, parse relevant files

    parsed_schema_details = {} # Placeholder: { (file, orig_name): details }

    # TODO: Reimplement schema parsing loop:
    # 1. Collect all unique schema names needed from endpoints
    # 2. Resolve schema names to files (requires import handling/heuristics)
    # 3. For each unique (file, schema_name):
    #    - Get class details: class_info = get_class_details(file_path=schema_file, class_name=schema_name)
    #    - Validate: if is_data_model(class_info, framework='fastapi'):
    #    - Parse: parsed_parts = parse_pydantic_model(class_info)
    #    - Store details in all_schemas[schema_name] = {...}

    logger.info(f"Finished FastAPI analysis for {entry_point_file}. Found {len(all_endpoints)} endpoints (Schema parsing incomplete).")
    return {
        "success": True,
        "endpoints": all_endpoints,
        "schemas": list(all_schemas.values()) # Return currently empty list
    }


# --- Framework Detection (Keep for now, might be used to find entry point) ---

def detect_api_framework(repo_path: str) -> Dict[str, Any]:
    """Detect API framework using get_tech_stack tool."""
    logger.info(f"Detecting API framework for repo: {repo_path}")
    tech_stack_result = get_tech_stack(repo_path)

    if not tech_stack_result.get("success", False):
        error_msg = "Failed to analyze tech stack: " + tech_stack_result.get("message", "Unknown error")
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    tech_stack = tech_stack_result.get("tech_stack", {})
    api_frameworks = {}
    known_frameworks = {
        "python": ["fastapi", "flask", "django", "falcon", "sanic"],
        "javascript": ["express", "nestjs", "koa", "hapi", "next.js", "remix"],
        "java": ["spring", "spring boot", "jersey", "dropwizard", "quarkus", "micronaut"],
        "ruby": ["rails", "sinatra"], "go": ["gin", "echo", "chi"], "php": ["laravel", "symfony"]
    }

    # Check for primary_api_framework from get_tech_stack first
    primary_framework = tech_stack_result.get("primary_api_framework")
    if primary_framework:
        logger.info(f"Using primary framework from tech stack: {primary_framework}")
        return {"success": True, "primary_framework": primary_framework}

    # Check detected frameworks list
    api_frameworks_list = tech_stack.get("api_frameworks", [])
    if api_frameworks_list:
        logger.info(f"Detected API Frameworks list: {api_frameworks_list}")
        # Apply framework priority
        preferred_order = ["fastapi", "flask", "django", "express", "nestjs", "spring_boot"]
        for fw in preferred_order:
            normalized_list = [f.lower().replace(" ", "_").replace("rest_framework", "") for f in api_frameworks_list]
            if fw in normalized_list:
                primary_framework = fw
                logger.info(f"Selected primary framework from detected frameworks list: {primary_framework}")
                return {"success": True, "primary_framework": primary_framework}
        
        # If no preferred framework found, use the first one
        if api_frameworks_list:
            primary_framework = api_frameworks_list[0].lower().replace(" ", "_").replace("rest_framework", "")
            logger.info(f"Using first detected framework as primary: {primary_framework}")
            return {"success": True, "primary_framework": primary_framework}
            
    # Fallback: Check general tech stack categories for framework names
    for lang, frameworks_in_lang in tech_stack.items():
         # Example: tech_stack could have {'backend': ['FastAPI', 'Node.js']}
         if isinstance(frameworks_in_lang, list):
             for fw in frameworks_in_lang:
                 fw_lower = fw.lower()
                 for known_lang, known_fws in known_frameworks.items():
                      if fw_lower in known_fws:
                           api_frameworks[fw_lower] = max(api_frameworks.get(fw_lower, 0), 0.8) # Assign confidence

    # Check dependencies if still no direct detection
    if not api_frameworks:
        logger.info("No direct framework detected, checking dependencies...")
        dep_to_framework = {
            "fastapi": ("fastapi", 0.7), "flask": ("flask", 0.7),
            "express": ("express", 0.7), "django": ("django", 0.6),
            "djangorestframework": ("django", 0.8), # Keep DRF distinction? Agent used 'django'
            "@nestjs/core": ("nestjs", 0.7), "koa": ("koa", 0.7),
            "spring-boot-starter-web": ("spring boot", 0.7),
            "jersey-server": ("jersey", 0.7),
            "rails": ("rails", 0.7), "sinatra": ("sinatra", 0.7),
            "gin-gonic/gin": ("gin", 0.7), "labstack/echo": ("echo", 0.7),
            "laravel/framework": ("laravel", 0.7), "symfony/http-kernel": ("symfony", 0.7)
        }
        all_deps = []
        for key in tech_stack:
             # Combine all list-based dependency categories
             if key.endswith("_packages") and isinstance(tech_stack[key], list):
                  all_deps.extend(tech_stack[key])

        for dep in all_deps:
            dep_lower = str(dep).lower()
            for dep_key, (framework_name, confidence) in dep_to_framework.items():
                if dep_key in dep_lower:
                    api_frameworks[framework_name] = max(api_frameworks.get(framework_name, 0), confidence)

    primary_framework, primary_confidence = None, 0.0
    if api_frameworks:
        sorted_frameworks = sorted(api_frameworks.items(), key=lambda item: (-item[1], item[0]))
        primary_framework, primary_confidence = sorted_frameworks[0]
        logger.info(f"Determined primary framework from dependencies/fallback: {primary_framework} (Confidence: {primary_confidence:.2f})")
    else:
        logger.warning("Could not determine primary API framework even after checking dependencies.")

    # Return success status and the primary framework found (can be None)
    return {"success": True, "primary_framework": primary_framework}

# --- Endpoint Extraction (Mark as potentially deprecated for FastAPI) ---

def extract_api_endpoints(repo_path: str, framework: str, changed_files: List[str] = None) -> Dict[str, Any]:
    """Extract API endpoints using tools and utility parsers. (DEPRECATED for FastAPI - use analyze_fastapi_app)"""
    if framework == 'fastapi':
         logger.warning("extract_api_endpoints called for FastAPI. Use analyze_fastapi_app instead for better tracing.")
         # Try to find entry point (needs robust implementation)
         entry_point = "src/api/app.py" # Default, should be discovered
         entry_point_full = os.path.join(repo_path, entry_point)
         if os.path.exists(entry_point_full):
             logger.info(f"Using default entry point for analyze_fastapi_app: {entry_point}")
             return analyze_fastapi_app(repo_path, entry_point)
         else:
             logger.error(f"Default FastAPI entry point {entry_point} not found. Cannot run analyze_fastapi_app.")
             # Fallback to old logic (or error out?)
             # return {"success": False, "error": "FastAPI entry point not found"}
             pass # Let the old (non-AST) logic below run as a last resort

    if changed_files is None:
        changed_files = []

    logger.info(f"Extracting API endpoints for framework '{framework}' from {repo_path}")

    # --- REMOVE AST-based parsers from framework_parsers for FastAPI ---
    framework_parsers = {
        # "fastapi": parse_fastapi_endpoint, # REMOVED - use analyze_fastapi_app
        "flask": parse_flask_endpoint,
        "express": parse_express_endpoint,
        "django": parse_django_endpoint,
        "generic": parse_generic_endpoint
    }

    # Identify potential endpoint files using the tool
    api_components_result = identify_api_components(repo_path=repo_path)
    if not api_components_result.get("success", False):
        err_msg = "Failed to identify API components: " + api_components_result.get("message", "Unknown error")
        logger.error(err_msg)
        return {"success": False, "error": err_msg}

    components = api_components_result.get("components", {})
    
    # Collect relevant files from the components
    potential_files = []
    for component_type in ["entry_points", "routers", "handlers", "controllers", "views"]:
        potential_files.extend(components.get(component_type, []))
    potential_files = set(potential_files)  # Remove duplicates

    # Filter files based on changes if provided
    files_to_analyze = potential_files
    if changed_files:
        relevant_changed = {f for f in changed_files if f in potential_files}
        if relevant_changed:
             logger.info(f"Focusing endpoint analysis on {len(relevant_changed)} relevant changed files.")
             files_to_analyze = relevant_changed
        else:
             logger.info("No changed files match identified API component paths. Analyzing all potential files.")
             # Keep files_to_analyze as potential_files if no relevant changed files

    if not files_to_analyze:
        logger.info("No files identified for endpoint analysis.")
        return {"success": True, "endpoints": []}

    # Select the appropriate imported parser function
    parser_func = framework_parsers.get(framework.lower()) # REMOVED generic fallback here
    if not parser_func:
         logger.warning(f"No specific non-FastAPI parser for framework '{framework}'. Using generic.")
         parser_func = framework_parsers.get("generic")

    if not parser_func: # Should not happen if generic exists
         logger.error(f"Could not find any suitable endpoint parser function for framework '{framework}'")
         return {"success": False, "error": f"No parser for framework '{framework}'"}

    logger.info(f"Using endpoint parser: {parser_func.__name__}")

    # Parse each identified file
    all_endpoints = []
    parsed_files_count = 0
    for file_rel_path in files_to_analyze:
        file_abs_path = os.path.join(repo_path, file_rel_path)
        if not os.path.exists(file_abs_path):
            logger.warning(f"File identified for analysis does not exist: {file_rel_path}")
            continue

        # Get structure using the tool
        structure_result = get_code_structure(file_path=file_abs_path)
        if not structure_result or not structure_result.get("success"):
            logger.warning(f"Could not get structure for {file_rel_path}")
            continue

        file_structure = structure_result # Contains functions, classes etc.

        # Call the selected parser function (Flask, Django, Express, Generic)
        # These parsers might need updates to work with the structure dict instead of file path only
        # For now, assume they still work primarily off file_path or adapt them later.
        try:
            # Pass structure if parser accepts it, otherwise just path
            # This requires modifying the individual parser functions later
            if "file_structure" in parser_func.__code__.co_varnames:
                 endpoints_in_file = parser_func(file_path=file_rel_path, file_structure=file_structure, repo_path=repo_path)
            else:
                 endpoints_in_file = parser_func(file_path=file_rel_path, repo_path=repo_path) # Old signature

            if endpoints_in_file:
                logger.info(f"Found {len(endpoints_in_file)} endpoints in {file_rel_path} using {parser_func.__name__}")
                all_endpoints.extend(endpoints_in_file)
            parsed_files_count += 1
        except Exception as e:
            logger.error(f"Error parsing {file_rel_path} with {parser_func.__name__}: {e}", exc_info=True)

    logger.info(f"Finished endpoint extraction. Analyzed {parsed_files_count} files. Found {len(all_endpoints)} total endpoints.")
    return {"success": True, "endpoints": all_endpoints}

# --- Schema Extraction (Mark as potentially deprecated for FastAPI) ---

def extract_api_schemas(repo_path: str, framework: str, changed_files: List[str] = None) -> Dict[str, Any]:
    """Extract API schemas using tools and utility parsers. (DEPRECATED for FastAPI - use analyze_fastapi_app)"""
    if framework == 'fastapi':
         logger.warning("extract_api_schemas called for FastAPI. Schema extraction is now part of analyze_fastapi_app.")
         # Return empty for now if called directly for fastapi, as analyze_fastapi_app handles it
         # return {"success": True, "schemas": []}
         # For now, let the old logic run if called directly, but warn.

    if changed_files is None:
        changed_files = []
        
    framework = framework or "generic" # Ensure framework is not None
    logger.info(f"Extracting API schemas for framework '{framework}' from {repo_path}")

    # Map framework strings to imported schema parser utility functions
    schema_parsers = {
        "fastapi": parse_pydantic_model,
        "django": parse_django_model,
        "express": parse_typescript_model,
        "nestjs": parse_typescript_model,
        "generic": parse_generic_model
    }

    # Identify potential schema files
    api_components_result = identify_api_components(repo_path=repo_path)
    if not api_components_result.get("success", False):
         err_msg = "Failed to identify API components for schemas: " + api_components_result.get("message", "Unknown error")
         logger.error(err_msg)
         return {"success": False, "error": err_msg}

    components = api_components_result.get("components", {})
    
    # Collect relevant schema files from the components
    potential_files = []
    for component_type in ["schemas", "models", "dtos", "entities"]:
        potential_files.extend(components.get(component_type, []))
    potential_files = set(potential_files)  # Remove duplicates

    files_to_analyze = potential_files
    if changed_files:
        relevant_changed = {f for f in changed_files if f in potential_files}
        if relevant_changed: # Only filter if there are relevant changes
             logger.info(f"Focusing schema analysis on {len(relevant_changed)} relevant changed files.")
             files_to_analyze = relevant_changed
        else:
             logger.info("No changed files match identified schema component paths. Analyzing all potential files.")
             # Keep files_to_analyze as potential_files if no relevant changed files

    if not files_to_analyze:
        logger.info("No potential schema files identified for analysis.")
        return {"success": True, "schemas": []}

    # Select the appropriate imported schema parser function
    schema_parser_func = schema_parsers.get(framework.lower(), schema_parsers["generic"])
    logger.info(f"Using schema parser: {schema_parser_func.__name__}")

    # Parse schemas from identified files
    all_schemas = []
    parsed_schema_names = set()
    for file_path in files_to_analyze:
        absolute_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
        if not os.path.exists(absolute_path):
            logger.warning(f"Schema file not found: {absolute_path}, skipping.")
            continue
        try:
            structure = get_code_structure(file_path=absolute_path)
            if not structure.get("success", False):
                logger.warning(f"Could not get structure for schema file {file_path}, skipping.")
                continue
            
            classes = structure.get("classes", [])
            for cls_struct in classes:
                # Pass the file_path to is_data_model
                cls_struct['file_path'] = file_path # Ensure file path is available for is_data_model check
                class_name = cls_struct.get("name")
                
                # Use imported is_data_model utility to check if it looks like a schema
                if not class_name or not is_data_model(cls_struct, framework):
                    # Log if filtered out is moved inside is_data_model
                    continue
                
                # Get details including body_source needed for AST parsing
                class_info = get_class_details(file_path=absolute_path, class_name=class_name)
                if not class_info.get("success", False) or class_info.get("body_source") is None:
                     logger.warning(f"Could not get details or body_source for potential schema {class_name} in {file_path}")
                     continue
                
                # Add source_file to class_info for parser reference
                class_info["source_file"] = file_path

                # Call the imported utility parser
                parsed_parts = schema_parser_func(class_info) # Returns {fields: ..., required: ...}
                
                # Combine results into a dictionary
                schema_details = {
                    "name": class_name,
                    "description": class_info.get("docstring", cls_struct.get("docstring", "")),
                    # Adjust based on parser output: use "fields" instead of "properties"
                    "fields": parsed_parts.get("fields", []), 
                    "required": parsed_parts.get("required", []),
                    "source_file": file_path, # Relative path
                    "source_line": cls_struct.get("start_line")
                }
                
                # Add schema if name not already parsed (basic deduplication)
                if class_name not in parsed_schema_names:
                     all_schemas.append(schema_details)
                     parsed_schema_names.add(class_name)
                     logger.info(f"Parsed schema '{class_name}' from {file_path}")
        except Exception as e:
            logger.exception(f"Error processing schemas in file '{file_path}': {e}", exc_info=True)

    logger.info(f"Extracted {len(all_schemas)} unique schema candidates.")
    # Return list of schema dicts
    return {"success": True, "schemas": all_schemas} 