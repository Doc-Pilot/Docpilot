"""
API Documentation Agent
======================

This agent specializes in discovering and documenting API endpoints from a repository.
It analyzes code to identify API routes, parameters, and schemas, then generates
accurate documentation based on the discovered components.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import RunContext
import ast
import inspect
import re
import os
import textwrap
from datetime import datetime # Import datetime for timestamp

# Import agent base and config
from .base import BaseAgent, AgentConfig

# Import external tools the agent uses
from ..tools.code_tools import (
    get_code_structure,
    get_class_details,
)
from ..tools.repo_tools import (
    get_tech_stack,
    identify_api_components
)

# Import utility functions for parsing (ASSUME THESE FILES/FUNCTIONS EXIST)
from src.parsers.fastapi_parser import parse_fastapi_endpoint, parse_pydantic_model
from src.utils.api_parsers import (
    parse_flask_endpoint, parse_express_endpoint,
    parse_django_endpoint, parse_generic_endpoint,
    parse_django_model, parse_typescript_model,
    parse_generic_model, is_data_model # Keep non-FastAPI parsers here for now
)

# Import markdown formatters
from src.utils.api_formatters import (
    _format_markdown_endpoint,
    _format_markdown_schema
)

# Import git utils
from src.github.git_utils import checkout_repository, write_doc_file, cleanup_repo_dir, commit_and_push

# Import logger
from ..utils.logging import core_logger
logger = core_logger()


# --- Data Models (Defines Agent I/O) ---

@dataclass
class ApiDocDependency:
    repo_path: str # Local path if already checked out, OR identifier if needs cloning
    repo_url: Optional[str] = None # URL for cloning
    branch: Optional[str] = None # Branch to checkout/commit to
    target_doc_path: str = "DOCPILOT_API.md" # Default target file path
    commit_message: str = "[Docpilot] Updated API documentation" # Default commit message
    auth_token: Optional[str] = None # Optional auth token for Git operations
    changed_files: List[str] = field(default_factory=list)
    framework: Optional[str] = None
    # output_path: Optional[str] = None # Keep previous fields if needed
    # api_patterns: List[str] = field(default_factory=list)
    # doc_format: str = "markdown"

class ApiEndpoint(BaseModel):
    # Simplified for clarity, assuming validation elsewhere if needed
    path: str
    method: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    tags: List[str] = field(default_factory=list)

class ApiSchema(BaseModel):
    name: str
    description: Optional[str] = None
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    references: List[str] = field(default_factory=list)

class ApiDocumentation(BaseModel):
    # Add fields related to git operation status
    title: str
    description: Optional[str] = None
    version: Optional[str] = None
    base_url: Optional[str] = None
    endpoints: List[ApiEndpoint] = field(default_factory=list)
    schemas: List[ApiSchema] = field(default_factory=list)
    auth_methods: List[Dict[str, Any]] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    generated_at: str
    confidence_score: float
    markdown_content: Optional[str] = None # Store the generated markdown separately
    git_checkout_success: bool = False
    git_write_success: bool = False
    git_commit_success: bool = False
    git_push_success: bool = False
    error_message: Optional[str] = None # Store any error messages

# --- Agent Class ---

class ApiDocAgent(BaseAgent[ApiDocDependency, ApiDocumentation]):
    """
    Agent for discovering and documenting API endpoints from a repository.
    Orchestrates tools and utility parsers to extract API information and
    returns a structured ApiDocumentation object.
    """

    deps_type = ApiDocDependency
    result_type = ApiDocumentation
    default_system_prompt = """
    You are ApiDoc, an expert API documentation writer. Your task is to generate accurate
    and comprehensive documentation for APIs by analyzing source code using available tools.
    Focus on extracting structured data about endpoints (paths, methods, params, bodies, responses)
    and schemas (names, properties, types, required fields).
    Return the result as a structured ApiDocumentation object.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        system_prompt: Optional[str] = None
    ):
        """Initialize the ApiDocAgent."""
        super().__init__(
            config=config,
            system_prompt=system_prompt,
            deps_type=self.deps_type,
            result_type=self.result_type
        )
        self._register_tools()

        # Map framework strings to imported parser utility functions
        self.framework_parsers = {
            "fastapi": parse_fastapi_endpoint,
            "flask": parse_flask_endpoint,
            "express": parse_express_endpoint,
            "django": parse_django_endpoint,
            "generic": parse_generic_endpoint
        }
        self.schema_parsers = {
            "fastapi": parse_pydantic_model,
            "django": parse_django_model,
            "express": parse_typescript_model,
            "nestjs": parse_typescript_model,
            "generic": parse_generic_model
        }

    def _register_tools(self):
        """Register tools the agent calls externally."""
        # Core tools needed for the agent's workflow
        self.tool_plain(get_tech_stack)
        self.tool_plain(identify_api_components)
        self.tool_plain(get_code_structure)
        self.tool_plain(get_class_details)
        # Agent's own methods (_detect*, _extract*) are internal helpers, not tools

    # --- Internal Helper Methods (Not Tools) --- 

    def _detect_api_framework(self, deps: ApiDocDependency) -> Dict[str, Any]:
        """Internal helper: Detect API framework using get_tech_stack tool."""
        repo_path = deps.repo_path
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

        # Check detected frameworks
        for lang, frameworks in tech_stack.items():
             if lang.endswith("_frameworks") and isinstance(frameworks, list):
                 lang_key = lang.split("_")[0]
                 if lang_key in known_frameworks:
                     for fw in frameworks:
                         fw_lower = fw.lower()
                         if any(known_fw == fw_lower for known_fw in known_frameworks[lang_key]):
                             api_frameworks[fw_lower] = max(api_frameworks.get(fw_lower, 0), 0.9)

        # Check dependencies if no direct detection
        if not api_frameworks:
            logger.info("No direct framework detected, checking dependencies...")
            dep_to_framework = {
                "fastapi": ("fastapi", 0.7), "flask": ("flask", 0.7),
                "express": ("express", 0.7), "django": ("django", 0.6),
                "djangorestframework": ("django", 0.8),
                "@nestjs/core": ("nestjs", 0.7), "koa": ("koa", 0.7),
                "spring-boot-starter-web": ("spring boot", 0.7),
                "jersey-server": ("jersey", 0.7),
                "rails": ("rails", 0.7), "sinatra": ("sinatra", 0.7),
                "gin-gonic/gin": ("gin", 0.7), "labstack/echo": ("echo", 0.7),
                "laravel/framework": ("laravel", 0.7), "symfony/http-kernel": ("symfony", 0.7)
            }
            all_deps = (
                tech_stack.get("python_packages", []) + tech_stack.get("node_packages", []) +
                tech_stack.get("java_packages", []) # Add other languages
            )
            for dep in all_deps:
                dep_lower = str(dep).lower()
                for dep_key, (framework_name, confidence) in dep_to_framework.items():
                    if dep_key in dep_lower:
                        api_frameworks[framework_name] = max(api_frameworks.get(framework_name, 0), confidence)

        primary_framework, primary_confidence = None, 0.0
        if api_frameworks:
            sorted_frameworks = sorted(api_frameworks.items(), key=lambda item: (-item[1], item[0]))
            primary_framework, primary_confidence = sorted_frameworks[0]
            logger.info(f"Determined primary framework: {primary_framework} (Confidence: {primary_confidence:.2f})")
        else:
            logger.warning("Could not determine primary API framework.")

        # Return success status and the primary framework found
        return {"success": True, "primary_framework": primary_framework}

    def _extract_api_endpoints(self, ctx: RunContext[ApiDocDependency]) -> Dict[str, Any]:
        """Internal helper: Extract API endpoints using tools and utility parsers."""
        repo_path = ctx.deps.repo_path
        framework = ctx.deps.framework
        changed_files = ctx.deps.changed_files
        logger.info(f"Extracting API endpoints for framework '{framework}'")

        if not framework: return {"success": False, "error": "Framework not available for endpoint extraction"}

        # Identify potential endpoint files
        api_components = identify_api_components(repo_path=repo_path)
        if not api_components.get("success", False):
            err_msg = "Failed to identify API components: " + api_components.get("error", "Unknown error")
            logger.error(err_msg)
            return {"success": False, "error": err_msg}

        potential_files = set(
            api_components.get("routers", []) + api_components.get("handlers", []) +
            api_components.get("controllers", []) + api_components.get("views", []) +
            api_components.get("entry_points", [])
        )

        # Filter files based on changes if provided
        files_to_analyze = potential_files
        if changed_files:
            relevant_changed = {f for f in changed_files if f in potential_files}
            if not relevant_changed:
                 logger.info("No changed files match identified API component paths.")
                 return {"success": True, "endpoints": [], "message": "No relevant changed files for endpoint analysis"}
            logger.info(f"Focusing endpoint analysis on {len(relevant_changed)} relevant changed files.")
            files_to_analyze = relevant_changed

        if not files_to_analyze:
            logger.info("No files identified for endpoint analysis.")
            return {"success": True, "endpoints": []}

        # Select the appropriate imported parser function
        parser_func = self.framework_parsers.get(framework.lower(), self.framework_parsers["generic"])
        logger.info(f"Using endpoint parser: {parser_func.__name__}")

        # Parse each identified file
        all_endpoints = []
        for file_path in files_to_analyze:
            absolute_path = os.path.join(repo_path, file_path)
            if not os.path.exists(absolute_path):
                logger.warning(f"File not found during endpoint extraction: {absolute_path}, skipping.")
                continue
            try:
                structure = get_code_structure(file_path=absolute_path)
                if not structure.get("success", False):
                    logger.warning(f"Could not get structure for {file_path}, skipping endpoint parsing.")
                    continue
                
                # Call the imported utility parser
                file_endpoints = parser_func(file_path=file_path, file_structure=structure, repo_path=repo_path)
                
                if file_endpoints: # Expecting a list
                    # Ensure relative path is stored in source_file
                    for ep in file_endpoints:
                         # Parser should ideally return relative path, but enforce here
                         ep["source_file"] = file_path 
                    all_endpoints.extend(file_endpoints)
                    logger.debug(f"Parsed {len(file_endpoints)} endpoint candidates from {file_path}")
            except Exception as e:
                logger.exception(f"Error parsing endpoints in file '{file_path}': {e}", exc_info=True)

        logger.info(f"Extracted {len(all_endpoints)} total endpoint candidates.")
        # Return raw list of endpoint dicts
        return {"success": True, "endpoints": all_endpoints}

    def _extract_api_schemas(self, ctx: RunContext[ApiDocDependency]) -> Dict[str, Any]:
        """Internal helper: Extract API schemas using tools and utility parsers."""
        repo_path = ctx.deps.repo_path
        framework = ctx.deps.framework or "generic"
        # changed_files = ctx.deps.changed_files # Consider changed_files if needed
        logger.info(f"Extracting API schemas for framework '{framework}'")

        # Identify potential schema files
        api_components = identify_api_components(repo_path=repo_path)
        if not api_components.get("success", False):
             err_msg = "Failed to identify API components for schemas: " + api_components.get("error", "Unknown error")
             logger.error(err_msg)
             return {"success": False, "error": err_msg}

        potential_files = set(
            api_components.get("schemas", []) + api_components.get("models", []) +
            api_components.get("dtos", []) + api_components.get("entities", [])
        )

        # TODO: Filter by changed_files if needed

        if not potential_files:
            logger.info("No potential schema files identified.")
            return {"success": True, "schemas": []}

        # Select the appropriate imported schema parser function
        schema_parser_func = self.schema_parsers.get(framework.lower(), self.schema_parsers["generic"])
        logger.info(f"Using schema parser: {schema_parser_func.__name__}")

        # Parse schemas from identified files
        all_schemas = []
        parsed_schema_names = set()
        for file_path in potential_files:
            absolute_path = os.path.join(repo_path, file_path)
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
                    class_name = cls_struct.get("name")
                    # Use imported is_data_model utility to check if it looks like a schema
                    if not class_name or not is_data_model(cls_struct, framework):
                        continue
                    
                    # Get details including body_source needed for AST parsing
                    class_info = get_class_details(file_path=absolute_path, class_name=class_name)
                    if not class_info.get("success", False) or class_info.get("body_source") is None:
                         logger.warning(f"Could not get details or body_source for potential schema {class_name} in {file_path}")
                         continue

                    # Call the imported utility parser
                    parsed_parts = schema_parser_func(class_info) # Returns {properties: ..., required: ...}
                    
                    # Combine results into a dictionary
                    schema_details = {
                        "name": class_name,
                        "description": class_info.get("docstring", cls_struct.get("docstring", "")),
                        "properties": parsed_parts.get("properties", {}),
                        "required": parsed_parts.get("required", []),
                        "source_file": file_path, # Relative path
                        "source_line": cls_struct.get("start_line")
                    }
                    
                    # Add schema if name not already parsed (basic deduplication)
                    if class_name not in parsed_schema_names:
                         all_schemas.append(schema_details)
                         parsed_schema_names.add(class_name)
                         logger.debug(f"Parsed schema '{class_name}' from {file_path}")
            except Exception as e:
                logger.exception(f"Error processing schemas in file '{file_path}': {e}", exc_info=True)

        logger.info(f"Extracted {len(all_schemas)} unique schema candidates.")
        # Return raw list of schema dicts
        return {"success": True, "schemas": all_schemas}

    # --- Main Execution Logic --- 

    async def run(self, deps: ApiDocDependency) -> ApiDocumentation:
        """
        Executes the API documentation generation workflow, including Git operations.
        Handles both local paths and remote URLs.
        1. Checks out repository if URL is provided.
        2. Detects framework using the checked-out path.
        3. Extracts endpoints and schemas.
        4. Formats the extracted data into Markdown.
        5. Writes the Markdown file to the repository (if applicable).
        6. Commits and pushes the changes (if applicable).
        7. Cleans up and returns status.
        """
        # Extract initial deps
        repo_url = deps.repo_url
        local_path = deps.repo_path # Initial path, might be local dir or placeholder
        branch = deps.branch
        auth_token = deps.auth_token
        target_doc_path = deps.target_doc_path
        logger.info(f"Starting ApiDocAgent run. Input path: {local_path}, URL: {repo_url}")

        # Initialize status fields and working variables
        git_checkout_ok = False
        git_write_ok = False
        git_commit_ok = False
        git_push_ok = False
        final_markdown = None
        error_msg = None
        primary_framework = "unknown"
        confidence = 0.0
        temp_repo_dir = None
        effective_repo_path = local_path # Path used by tools

        try:
            # --- Step 1: Checkout Repository (if URL provided) ---
            if repo_url:
                logger.info(f"Attempting to checkout repo: {repo_url} (Branch: {branch or 'default'})")
                temp_repo_dir = checkout_repository(repo_url=repo_url, branch=branch, auth_token=auth_token)
                
                if not temp_repo_dir:
                    error_msg = "Failed to checkout repository."
                    logger.error(error_msg)
                    # Cannot proceed, return status (cleanup happens in finally)
                    return self._create_final_result(deps, primary_framework, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)
                
                git_checkout_ok = True # Checkout succeeded
                effective_repo_path = temp_repo_dir # Use the temp dir for subsequent analysis
                logger.info(f"Repository checked out successfully to: {effective_repo_path}")
            elif not os.path.isdir(effective_repo_path):
                 # No URL, check if the provided local path is valid
                 error_msg = f"Local repository path not found or invalid: {effective_repo_path}"
                 logger.error(error_msg)
                 return self._create_final_result(deps, primary_framework, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)
            else:
                # Using provided local repo_path, no checkout needed
                 logger.info(f"Using provided local path: {effective_repo_path}")
                 # Consider checkout "ok" since we have a valid local path to work with
                 git_checkout_ok = True 

            # --- Step 2: Detect Framework (using effective_repo_path) ---
            # Update deps temporarily for tool calls needing repo_path
            original_repo_path = deps.repo_path
            deps.repo_path = effective_repo_path 
            framework_result = self._detect_api_framework(deps) 
            deps.repo_path = original_repo_path # Restore original path in deps

            if not framework_result.get("success", False) or not framework_result.get("primary_framework"):
                error_msg = framework_result.get("error", "Failed to determine primary framework.")
                logger.error(error_msg)
                return self._create_final_result(deps, primary_framework, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)
            
            primary_framework = framework_result["primary_framework"]
            deps.framework = primary_framework # Store framework in deps for extractors
            logger.info(f"Primary framework detected: {primary_framework}")
            
            # --- Step 3: Extract API Components (using effective_repo_path) ---
            deps.repo_path = effective_repo_path # Update again for extractors
            endpoint_results = self._extract_api_endpoints(deps) 
            schema_results = self._extract_api_schemas(deps)
            deps.repo_path = original_repo_path # Restore original path

            extracted_endpoints = endpoint_results.get("endpoints", [])
            extracted_schemas = schema_results.get("schemas", [])
            confidence = 0.7 if extracted_endpoints or extracted_schemas else 0.1

            # --- Step 4: Format into Markdown ---
            final_markdown = self._format_documentation_markdown(extracted_endpoints, extracted_schemas, primary_framework)
            if not final_markdown:
                 logger.warning("Markdown generation resulted in empty content.")

            # --- Step 5 & 6: Write/Commit/Push (Only if we cloned via URL) ---
            if temp_repo_dir: # Check if we are in a temp dir from cloning
                 logger.info(f"Writing documentation to {target_doc_path} in {temp_repo_dir}")
                 write_success = write_doc_file(
                     repo_dir=temp_repo_dir, 
                     doc_content=final_markdown or "", 
                     target_path=target_doc_path
                 )
                 git_write_ok = write_success

                 if not write_success:
                     error_msg = error_msg or "Failed to write documentation file to repository."
                     logger.error(error_msg)
                 else:
                     logger.info("Documentation file written successfully.")
                     # Attempt commit and push only if write succeeded
                     logger.info(f"Attempting to commit and push changes for branch '{branch}'")
                     if not repo_url: # Should not happen if temp_repo_dir exists, but safety check
                          logger.error("Cannot commit/push without original repo_url.")
                          error_msg = error_msg or "Commit/Push skipped: Missing repo_url."
                     else:
                          commit_ok, push_ok = commit_and_push(
                              repo_dir=temp_repo_dir,
                              commit_message=deps.commit_message,
                              branch=branch,
                              repo_url=repo_url,
                              auth_token=auth_token
                          )
                          git_commit_ok = commit_ok
                          git_push_ok = push_ok
                          if not commit_ok:
                              error_msg = error_msg or "Commit failed."
                              logger.error("Commit failed.") # Log specific error
                          elif not push_ok:
                              error_msg = error_msg or "Push failed after successful commit."
                              logger.warning("Push failed after successful commit.")
                          else:
                              logger.info("Commit and push successful.")
            else:
                # Running on a local path, skip Git write/commit/push
                logger.info("Skipping Git write/commit/push operations for local path run.")
                git_write_ok = False 
                git_commit_ok = False
                git_push_ok = False

        except Exception as e:
            logger.exception(f"An unexpected error occurred during ApiDocAgent run: {e}")
            error_msg = f"Unexpected agent error: {str(e)}"

        finally:
            # --- Step 7: Cleanup Temporary Directory ---
            if temp_repo_dir:
                 cleanup_repo_dir(temp_repo_dir)

        # Assemble and return final result object with status
        logger.info("ApiDocAgent run finished.")
        return self._create_final_result(deps, primary_framework, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)

    def _format_documentation_markdown(self, endpoints: List[Dict], schemas: List[Dict], framework: str) -> Optional[str]:
        """Helper function to format extracted endpoints and schemas into a single Markdown string."""
        markdown_sections = []
        endpoint_markdown = ""
        schema_markdown = ""

        if endpoints:
            markdown_sections.append("# API Endpoints")
            for endpoint_data in endpoints:
                markdown_sections.append(_format_markdown_endpoint(endpoint_data))
            endpoint_markdown = "\n\n".join(markdown_sections)
            markdown_sections = []

        if schemas:
            markdown_sections.append("# Schemas")
            for schema_data in schemas:
                schema_name = schema_data.get("name", "UnknownSchema")
                formatter_input = {"name": schema_name, "fields": schema_data.get("fields", [])}
                markdown_sections.append(_format_markdown_schema(formatter_input))
            schema_markdown = "\n\n".join(markdown_sections)

        if not endpoint_markdown and not schema_markdown:
             return None # Return None if nothing was formatted

        final_markdown = f"# API Documentation ({framework.capitalize()})\n\n" \
                         f"{endpoint_markdown}\n\n{schema_markdown}"
        return final_markdown
        
    def _create_final_result(self, deps: ApiDocDependency, framework: str, confidence: float, markdown: Optional[str], checkout_ok: bool, write_ok: bool, commit_ok: bool, push_ok: bool, error: Optional[str]) -> ApiDocumentation:
        """Helper to assemble the final ApiDocumentation result object."""
        repo_id = deps.repo_url or deps.repo_path # Use URL or path for title
        return ApiDocumentation(
            title=f"API Documentation for {os.path.basename(repo_id)}",
            description=f"Generated docs for '{framework}' framework. Status: {error if error else 'Success'}." if not markdown else f"Generated docs for '{framework}' framework.",
            frameworks=[framework] if framework != "unknown" else [],
            generated_at=datetime.utcnow().isoformat(),
            confidence_score=confidence,
            markdown_content=markdown,
            git_checkout_success=checkout_ok,
            git_write_success=write_ok,
            git_commit_success=commit_ok,
            git_push_success=push_ok,
            error_message=error
        )

    # System prompt method remains (can be simplified if needed)
    def system_prompt(self, deps: ApiDocDependency):
        """ Generate a dynamic system prompt based on the dependencies. """
        prompt = self.default_system_prompt
        # Use framework from context, which should be set by run()
        framework = deps.framework 
        if framework:
             framework_prompts = {
                 "fastapi": "Focus on FastAPI specifics: decorators (@app.get), Pydantic models, Path/Query/Body params.",
                 "flask": "Focus on Flask specifics: @app.route, request object, Blueprints.",
                 "express": "Focus on Express specifics: router.get/post, req/res objects, middleware.",
                 "django": "Focus on Django REST Framework specifics: ViewSets, Serializers, urls.py.",
             }
             guidance = framework_prompts.get(framework.lower(), f"Detected framework: {framework}. Adapt analysis accordingly.")
             prompt += f"\n\nFramework-specific guidance ({framework}): {guidance}"
        return prompt.strip()