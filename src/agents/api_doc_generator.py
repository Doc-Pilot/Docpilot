from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig
from ..prompts.agent_prompts import API_DOC_GENERATOR_PROMPT

@dataclass
class APIDocInput:
    """Input for API documentation generation"""
    code: str
    api_name: str
    language: str
    framework: Optional[str] = None
    include_examples: bool = True
    example_languages: List[str] = field(default_factory=lambda: ["python", "javascript", "curl"])
    existing_docs: Optional[str] = None
    
    def __post_init__(self):
        """Validate the input after initialization"""
        if not self.code or not self.code.strip():
            raise ValueError("API code cannot be empty")
        if not self.api_name or not self.api_name.strip():
            raise ValueError("API name cannot be empty")

class APIEndpoint(BaseModel):
    """Represents an API endpoint"""
    path: str = Field(description="Endpoint path")
    method: str = Field(description="HTTP method (GET, POST, etc.)")
    summary: str = Field(description="Short summary of the endpoint")
    description: str = Field(description="Detailed description of the endpoint")
    parameters: List[Dict[str, Any]] = Field(default_factory=list, description="Parameters for the endpoint")
    request_body: Optional[Dict[str, Any]] = Field(None, description="Request body schema")
    responses: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Possible responses")
    auth_required: bool = Field(False, description="Whether authentication is required")
    rate_limited: bool = Field(False, description="Whether the endpoint is rate limited")
    deprecated: bool = Field(False, description="Whether the endpoint is deprecated")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Example requests and responses")

class APIDocResult(BaseModel):
    """Result of API documentation generation"""
    title: str = Field(description="API title")
    version: str = Field(description="API version")
    description: str = Field(description="API description")
    base_path: Optional[str] = Field(None, description="Base path for all endpoints")
    endpoints: List[APIEndpoint] = Field(default_factory=list, description="API endpoints")
    auth_schemes: List[Dict[str, Any]] = Field(default_factory=list, description="Authentication schemes")
    markdown: str = Field(description="Markdown documentation")
    openapi_spec: Optional[Dict[str, Any]] = Field(None, description="OpenAPI specification as a dictionary")

class APIExamplesResult(BaseModel):
    """Result of API examples generation"""
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="API examples")
    
class APIDocGenerator(BaseAgent[APIDocResult]):
    """Agent for generating API documentation"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt=API_DOC_GENERATOR_PROMPT,
            model_type=APIDocResult
        )
    
    def generate_api_docs(
        self,
        input_data: APIDocInput
    ) -> APIDocResult:
        """Generate API documentation for the provided code"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("API code cannot be empty")
        if not input_data.api_name or not input_data.api_name.strip():
            raise ValueError("API name cannot be empty")
            
        # Build the prompt with details on framework if available
        framework_text = f" using {input_data.framework}" if input_data.framework else ""
        
        return self.run_sync(
            user_prompt=f"Generate API documentation for {input_data.api_name} in {input_data.language}{framework_text}. Include both Markdown documentation and OpenAPI specification.\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
    
    def generate_api_examples(
        self,
        api_doc: APIDocResult,
        languages: List[str] = ["python", "javascript", "curl"]
    ) -> APIExamplesResult:
        """Generate usage examples for the API"""
        if not api_doc:
            raise ValueError("API documentation cannot be empty")
            
        # Format endpoints for readability in the prompt
        endpoints_text = "\n\n".join([
            f"### {endpoint.method} {endpoint.path}\n{endpoint.description}"
            for endpoint in api_doc.endpoints
        ])
        
        languages_text = ", ".join(languages)
        
        result = self.run_sync(
            user_prompt=f"""Generate usage examples for these API endpoints in {languages_text}:

API: {api_doc.title} v{api_doc.version}
Description: {api_doc.description}
Base Path: {api_doc.base_path or "/"}

Endpoints:
{endpoints_text}

For each endpoint, provide example requests and expected responses.
""",
            deps=api_doc
        )
        
        if not isinstance(result, APIExamplesResult):
            # Convert to APIExamplesResult if needed
            examples = []
            for endpoint in api_doc.endpoints:
                for language in languages:
                    examples.append({
                        "endpoint": f"{endpoint.method} {endpoint.path}",
                        "language": language,
                        "code": f"# Example for {endpoint.method} {endpoint.path}\n# Not generated",
                        "response": "# Example response\n# Not generated"
                    })
            
            return APIExamplesResult(examples=examples)
        
        return result
    
    def convert_to_openapi(
        self,
        api_doc: APIDocResult
    ) -> Dict[str, Any]:
        """Convert API documentation to OpenAPI specification"""
        if not api_doc:
            raise ValueError("API documentation cannot be empty")
            
        # If we already have an OpenAPI spec, return it
        if api_doc.openapi_spec:
            return api_doc.openapi_spec
            
        result = self.run_sync(
            user_prompt=f"""Convert this API documentation to an OpenAPI 3.0 specification:

API: {api_doc.title} v{api_doc.version}
Description: {api_doc.description}
Base Path: {api_doc.base_path or "/"}

Endpoints:
{[f"{e.method} {e.path} - {e.summary}" for e in api_doc.endpoints]}

Return a valid OpenAPI 3.0 specification as a JSON object.
""",
            deps=api_doc
        )
        
        # Extract OpenAPI spec from result
        if isinstance(result, Dict):
            return result
        elif hasattr(result, "openapi_spec") and result.openapi_spec:
            return result.openapi_spec
        else:
            # Create a basic OpenAPI spec
            paths = {}
            for endpoint in api_doc.endpoints:
                if endpoint.path not in paths:
                    paths[endpoint.path] = {}
                    
                method = endpoint.method.lower()
                paths[endpoint.path][method] = {
                    "summary": endpoint.summary,
                    "description": endpoint.description,
                    "responses": {
                        "200": {
                            "description": "Successful response"
                        }
                    }
                }
            
            return {
                "openapi": "3.0.0",
                "info": {
                    "title": api_doc.title,
                    "version": api_doc.version,
                    "description": api_doc.description
                },
                "paths": paths
            } 