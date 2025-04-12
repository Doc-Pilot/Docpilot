"""
API Documentation Agent
======================

This agent specializes in discovering and documenting API endpoints from a repository.
It analyzes code to identify API routes, parameters, and schemas, then generates
accurate documentation based on the discovered components.
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError
import os
from datetime import datetime

# Import agent base and config
from .base import BaseAgent

# Import the NEW API analysis tools
from ..tools.api_tools import (
    detect_api_framework,
    extract_api_endpoints,
    extract_api_schemas,
    analyze_fastapi_app
)

# Import markdown formatters (still needed)
from ..utils.api_formatters import (
    _format_markdown_endpoint,
    _format_markdown_schema
)

# Import git utils (still needed)
from ..github.git_utils import checkout_repository, write_doc_file, cleanup_repo_dir, commit_and_push

# Import logger
from ..utils.logging import core_logger
logger = core_logger()

# --- Data Models (Defines Agent I/O - Unchanged) ---

@dataclass
class ApiDocDependency:
    repo_path: str # Local path if already checked out, OR identifier if needs cloning
    repo_url: Optional[str] = None # URL for cloning
    branch: Optional[str] = None # Branch to checkout/commit to
    target_doc_path: str = "DOCPILOT_API.md" # Default target file path
    commit_message: str = "[Docpilot] Updated API documentation" # Default commit message
    auth_token: Optional[str] = None # Optional auth token for Git operations
    changed_files: List[str] = field(default_factory=list)

class ApiEndpoint(BaseModel):
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
    # Change properties to fields to match parser output
    fields: List[Dict[str, Any]] = field(default_factory=list) 
    required: List[str] = field(default_factory=list)
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    references: List[str] = field(default_factory=list)

class ApiDocumentation(BaseModel):
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
    markdown_content: Optional[str] = None 
    git_checkout_success: bool = False
    git_write_success: bool = False
    git_commit_success: bool = False
    git_push_success: bool = False
    error_message: Optional[str] = None

# --- Agent Class (Simplified) ---

class ApiDocAgent(BaseAgent[ApiDocDependency, ApiDocumentation]):
    """
    Agent for discovering and documenting API endpoints from a repository.
    Orchestrates API analysis tools and returns structured documentation.
    """

    deps_type = ApiDocDependency
    result_type = ApiDocumentation
    default_system_prompt = """ 
    You are ApiDoc, an expert API documentation writer. You will receive structured data
    about API endpoints and schemas discovered in a repository. Your task is to format this
    information clearly and accurately into a Markdown document.
    """

    # --- Main Execution Logic --- 

    async def run(self, deps: ApiDocDependency) -> ApiDocumentation:
        """
        Executes the API documentation generation workflow using external tools.
        1. Checks out repository if URL is provided.
        2. Calls tools to detect framework, extract endpoints, and schemas.
        3. Formats the extracted data into Markdown.
        4. Handles Git operations (write/commit/push).
        5. Cleans up and returns the final ApiDocumentation object.
        """
        # Extract initial deps
        repo_url = deps.repo_url
        local_path = deps.repo_path
        branch = deps.branch
        auth_token = deps.auth_token
        target_doc_path = deps.target_doc_path
        changed_files = deps.changed_files
        logger.info(f"Starting ApiDocAgent run. Input path: {local_path}, URL: {repo_url}")

        # Initialize status fields and working variables
        git_checkout_ok = False
        git_write_ok = False
        git_commit_ok = False
        git_push_ok = False
        final_markdown = None
        error_msg = None
        primary_framework = "unknown"
        extracted_endpoints = []
        extracted_schemas = []
        confidence = 0.0
        temp_repo_dir = None
        effective_repo_path = local_path

        try:
            # --- Step 1: Checkout Repository (if URL provided) ---
            if repo_url:
                logger.info(f"Attempting to checkout repo: {repo_url} (Branch: {branch or 'default'})")
                temp_repo_dir = checkout_repository(repo_url=repo_url, branch=branch, auth_token=auth_token)
                
                if not temp_repo_dir:
                    error_msg = "Failed to checkout repository."
                    logger.error(error_msg)
                    return self._create_final_result(deps, primary_framework, extracted_endpoints, extracted_schemas, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)
                
                git_checkout_ok = True
                effective_repo_path = temp_repo_dir
                logger.info(f"Repository checked out successfully to: {effective_repo_path}")
            elif not os.path.isdir(effective_repo_path):
                 error_msg = f"Local repository path not found or invalid: {effective_repo_path}"
                 logger.error(error_msg)
                 return self._create_final_result(deps, primary_framework, extracted_endpoints, extracted_schemas, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)
            else:
                 logger.info(f"Using provided local path: {effective_repo_path}")
                 git_checkout_ok = True 

            # --- Step 2: Detect Framework (using api_tools) ---
            framework_result = detect_api_framework(effective_repo_path)
            
            if not framework_result.get("success", False):
                error_msg = framework_result.get("error", "Failed to analyze tech stack.")
                logger.error(f"Framework detection failed: {error_msg}")
                # Allow proceeding with 'generic' if detection failed but might recover
                primary_framework = "generic"
            else:
                primary_framework = framework_result.get("primary_framework")
                if not primary_framework:
                    logger.warning("No primary framework detected by tool, defaulting to 'generic' framework")
                    primary_framework = "generic"
            
            logger.info(f"Using framework for analysis: {primary_framework}")
            
            # --- Step 3: Extract API Components (using NEW logic for FastAPI) ---
            if primary_framework == 'fastapi':
                logger.info("Using new tracing-based analysis for FastAPI...")
                # TODO: Robustly find entry point. Using common default for now.
                entry_point = "src/api/app.py" 
                # Verify entry point exists
                entry_point_full_path = os.path.join(effective_repo_path, entry_point)
                if not os.path.exists(entry_point_full_path):
                     logger.error(f"Assumed FastAPI entry point not found: {entry_point_full_path}")
                     # Optionally try identify_api_components as fallback?
                     # For now, fail if assumed entry point missing
                     error_msg = f"FastAPI entry point '{entry_point}' not found."
                else:
                    analysis_result = analyze_fastapi_app(
                        repo_path=effective_repo_path, 
                        entry_point_file=entry_point
                    )
                    if analysis_result.get("success", False):
                        extracted_endpoints = analysis_result.get("endpoints", [])
                        # Schemas are now returned as a list of dicts
                        extracted_schemas = analysis_result.get("schemas", []) 
                        logger.info(f"FastAPI analysis complete. Found {len(extracted_endpoints)} endpoints, {len(extracted_schemas)} schemas.")
                    else:
                        error_msg = analysis_result.get("error", "FastAPI analysis failed.")
                        logger.error(f"FastAPI analysis failed: {error_msg}")
                        # Continue with potentially empty lists? Or fail hard?
                        # Let's continue for now, confidence will be low.
            else:
                # Use old logic for other frameworks
                logger.info(f"Using standard extraction logic for {primary_framework}...")
                logger.info("Extracting API endpoints...")
                endpoint_results = extract_api_endpoints(
                    repo_path=effective_repo_path, 
                    framework=primary_framework, 
                    changed_files=changed_files
                )
                if endpoint_results.get("success", False):
                    extracted_endpoints = endpoint_results.get("endpoints", [])
                    logger.info(f"Found {len(extracted_endpoints)} endpoint candidates.")
                else:
                    logger.warning(f"Endpoint extraction failed: {endpoint_results.get('error', 'Unknown error')}")
                    # Continue to schema extraction even if endpoints fail

                logger.info("Extracting API schemas...")
                schema_results = extract_api_schemas(
                    repo_path=effective_repo_path, 
                    framework=primary_framework, 
                    changed_files=changed_files
                )
                if schema_results.get("success", False):
                    extracted_schemas = schema_results.get("schemas", [])
                    logger.info(f"Found {len(extracted_schemas)} schema candidates.")
                else:
                     logger.warning(f"Schema extraction failed: {schema_results.get('error', 'Unknown error')}")

            confidence = 0.7 if extracted_endpoints or extracted_schemas else 0.1

            # --- Step 4: Format into Markdown ---
            logger.info("Formatting documentation...")
            final_markdown = self._format_documentation_markdown(extracted_endpoints, extracted_schemas, primary_framework)
            if not final_markdown:
                 logger.warning("Markdown generation resulted in empty content.")
                 # Don't necessarily error out, could be no APIs found

            # --- Step 5 & 6: Write/Commit/Push (Only if we cloned via URL) ---
            if temp_repo_dir: 
                 if final_markdown is not None: # Only write/commit if there's content
                    logger.info(f"Writing documentation to {target_doc_path} in {temp_repo_dir}")
                    write_success = write_doc_file(
                        repo_dir=temp_repo_dir, 
                        doc_content=final_markdown, 
                        target_path=target_doc_path
                    )
                    git_write_ok = write_success

                    if not write_success:
                        error_msg = error_msg or "Failed to write documentation file to repository."
                        logger.error(error_msg)
                    else:
                        logger.info("Documentation file written successfully.")
                        logger.info(f"Attempting to commit and push changes for branch '{branch}'")
                        if not repo_url: 
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
                                logger.error("Commit failed.")
                            elif not push_ok:
                                error_msg = error_msg or "Push failed after successful commit."
                                logger.warning("Push failed after successful commit.")
                            else:
                                logger.info("Commit and push successful.")
                 else:
                     logger.info("Skipping write/commit/push as no documentation content was generated.")
                     # Set write/commit/push status to False explicitly as no action was taken
                     git_write_ok = False
                     git_commit_ok = False
                     git_push_ok = False
            else:
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
        return self._create_final_result(deps, primary_framework, extracted_endpoints, extracted_schemas, confidence, final_markdown, git_checkout_ok, git_write_ok, git_commit_ok, git_push_ok, error_msg)

    def _format_documentation_markdown(self, endpoints: List[Dict], schemas: List[Dict], framework: str) -> Optional[str]:
        """Helper function to format extracted endpoints and schemas into a single Markdown string."""
        markdown_sections = []
        endpoint_markdown = ""
        schema_markdown = ""

        # Safety checks for inputs
        if not endpoints:
            logger.info("No endpoints found to document")
            endpoints = []
        
        if not schemas:
            logger.info("No schemas found to document")
            schemas = []
            
        if not framework:
            framework = "generic"

        # Generate endpoint documentation
        if endpoints:
            markdown_sections.append("# API Endpoints")
            # Sort endpoints for consistent output (e.g., by path, then method)
            sorted_endpoints = sorted(endpoints, key=lambda x: (x.get('path', ''), x.get('method', '')))
            for endpoint_data in sorted_endpoints:
                try:
                    endpoint_md = _format_markdown_endpoint(endpoint_data)
                    if endpoint_md:
                        markdown_sections.append(endpoint_md)
                except Exception as e:
                    logger.warning(f"Error formatting endpoint {endpoint_data.get('path')}: {e}")
                    continue # Skip this endpoint
            endpoint_markdown = "\n\n".join(markdown_sections)
            markdown_sections = []

        # Generate schema documentation
        if schemas:
            markdown_sections.append("# Schemas")
            # Sort schemas by name
            sorted_schemas = sorted(schemas, key=lambda x: x.get('name', ''))
            for schema_data in sorted_schemas:
                try:
                    schema_name = schema_data.get("name", "UnknownSchema")
                    # Ensure the formatter receives the correct structure ('fields')
                    formatter_input = {"name": schema_name, "fields": schema_data.get("fields", [])}
                    schema_md = _format_markdown_schema(formatter_input)
                    if schema_md:
                        markdown_sections.append(schema_md)
                except Exception as e:
                    logger.warning(f"Error formatting schema {schema_data.get('name', 'unknown')}: {e}")
                    continue # Skip this schema
            schema_markdown = "\n\n".join(markdown_sections)

        if not endpoint_markdown and not schema_markdown:
             logger.warning("No content generated for documentation")
             return None # Return None if nothing was formatted

        # Construct the final markdown document
        final_markdown = f"# API Documentation ({framework.capitalize()})\n\n"
        
        if endpoint_markdown:
            final_markdown += f"{endpoint_markdown}\n\n"
            
        if schema_markdown:
            final_markdown += f"{schema_markdown}"
            
        final_markdown += f"\n\n---\n*Documentation generated by DocPilot on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        
        return final_markdown
        
    def _create_final_result(self, deps: ApiDocDependency, framework: str, endpoints: List[Dict], schemas: List[Dict], confidence: float, markdown: Optional[str], checkout_ok: bool, write_ok: bool, commit_ok: bool, push_ok: bool, error: Optional[str]) -> ApiDocumentation:
        """Helper to assemble the final ApiDocumentation result object."""
        repo_id = deps.repo_url or deps.repo_path # Use URL or path for title
        
        # Map internal dict structure to Pydantic models if needed, or keep as dicts
        # For simplicity, we assume the parser output matches the Pydantic model structure
        # Or we can perform validation/mapping here
        validated_endpoints = []
        for ep_data in endpoints:
            try:
                # Basic mapping/validation example
                # This assumes parser output keys roughly match ApiEndpoint fields
                mapped_ep = {
                    "path": ep_data.get("path", "N/A"),
                    "method": ep_data.get("method", "N/A"),
                    "summary": ep_data.get("summary"),
                    "description": ep_data.get("description"),
                    "parameters": ep_data.get("parameters", []), # Assume list of dicts
                    "request_body": ep_data.get("request_body_details"), # Use the key from parser
                    "responses": ep_data.get("responses", {}), # Assume dict structure
                    "source_file": ep_data.get("source_file"),
                    "source_line": ep_data.get("source_line"),
                    "tags": ep_data.get("tags", [])
                }
                validated_endpoints.append(ApiEndpoint(**mapped_ep))
            except ValidationError as e:
                 logger.warning(f"Validation failed for endpoint data: {ep_data.get('path')} - {e}")
            except Exception as e:
                 logger.warning(f"Error processing endpoint data: {ep_data.get('path')} - {e}")
                 
        validated_schemas = []
        for schema_data in schemas:
            try:
                # Map parser output ("fields") to ApiSchema model
                mapped_schema = {
                    "name": schema_data.get("name", "UnknownSchema"),
                    "description": schema_data.get("description"),
                    "fields": schema_data.get("fields", []), # Keep as list of dicts
                    "required": schema_data.get("required", []),
                    "source_file": schema_data.get("source_file"),
                    "source_line": schema_data.get("source_line"),
                    "references": [] # References are not currently extracted
                }
                validated_schemas.append(ApiSchema(**mapped_schema))
            except ValidationError as e:
                 logger.warning(f"Validation failed for schema data: {schema_data.get('name')} - {e}")
            except Exception as e:
                 logger.warning(f"Error processing schema data: {schema_data.get('name')} - {e}")

        return ApiDocumentation(
            title=f"API Documentation for {os.path.basename(repo_id)}",
            description=f"Generated docs for '{framework}' framework. Status: {error if error else 'Success'}. Found {len(validated_endpoints)} endpoints, {len(validated_schemas)} schemas." if markdown else f"Generated docs for '{framework}' framework. Status: {error if error else 'Success'}. Found {len(validated_endpoints)} endpoints, {len(validated_schemas)} schemas. No markdown generated.",
            frameworks=[framework] if framework != "unknown" else [],
            endpoints=validated_endpoints,
            schemas=validated_schemas,
            generated_at=datetime.utcnow().isoformat(),
            confidence_score=confidence,
            markdown_content=markdown,
            git_checkout_success=checkout_ok,
            git_write_success=write_ok,
            git_commit_success=commit_ok,
            git_push_success=push_ok,
            error_message=error
        )
if __name__ == "__main__":
    docpilot_repo_path = r"D:\AIML\Agents\Docpilot"
    deps = ApiDocDependency(
        repo_path=docpilot_repo_path,
        repo_url=None,
        branch=None, 
        target_doc_path="TEST_DOCS.md",
        commit_message=None,
        auth_token=None
    )
    agent = ApiDocAgent()
    result = asyncio.run(agent.run(deps))
    print(result)
