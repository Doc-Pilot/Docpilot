from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple, ClassVar, Type
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig, AgentResult
from ..utils.metrics import Usage
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
    # Enhanced context fields
    project_description: Optional[str] = None
    related_endpoints: Optional[List[str]] = None
    authentication_details: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[str]] = None
    directory_structure: Optional[str] = None
    usage_patterns: Optional[List[str]] = None
    target_audience: Optional[str] = None
    implementation_details: Optional[Dict[str, Any]] = None
    api_files: Optional[List[Tuple[str, str]]] = None
    technologies: Optional[List[str]] = None
    
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
    
class APIDocGenerator(BaseAgent[APIDocInput, APIDocResult]):
    """Agent for generating API documentation"""
    
    # Set class variables for type checking
    deps_type: ClassVar[Type[APIDocInput]] = APIDocInput
    result_type: ClassVar[Type[APIDocResult]] = APIDocResult
    default_system_prompt: ClassVar[str] = API_DOC_GENERATOR_PROMPT
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config,
            deps_type=self.deps_type,
            result_type=self.result_type
        )
    
    async def generate_api_docs(
        self,
        input_data: APIDocInput
    ) -> AgentResult[APIDocResult]:
        """Generate API documentation for the provided code with enhanced context"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("API code cannot be empty")
        if not input_data.api_name or not input_data.api_name.strip():
            raise ValueError("API name cannot be empty")
            
        # Build the prompt with details on framework if available
        framework_text = f" using {input_data.framework}" if input_data.framework else ""
        
        # Include project description if available
        project_description = ""
        if input_data.project_description:
            project_description = f"\nProject Description: {input_data.project_description}"
        
        # Include authentication details if available
        auth_details = ""
        if input_data.authentication_details:
            auth_details = "\nAuthentication Details:"
            for auth_type, auth_info in input_data.authentication_details.items():
                auth_details += f"\n- {auth_type}: {auth_info}"
        
        # Include dependencies if available
        dependencies_text = ""
        if input_data.dependencies and len(input_data.dependencies) > 0:
            dependencies_text = f"\nDependencies: {', '.join(input_data.dependencies)}"
        
        # Include directory structure if available
        dir_structure_text = ""
        if input_data.directory_structure:
            dir_structure_text = f"\n\nProject Structure:\n```\n{input_data.directory_structure}\n```"
        
        # Include usage patterns if available
        usage_patterns_text = ""
        if input_data.usage_patterns and len(input_data.usage_patterns) > 0:
            patterns = "\n".join([f"- {pattern}" for pattern in input_data.usage_patterns])
            usage_patterns_text = f"\n\nCommon Usage Patterns:\n{patterns}"
        
        # Include target audience if available
        audience_text = ""
        if input_data.target_audience:
            audience_text = f"\n\nTarget Audience: {input_data.target_audience}"
        
        # Include implementation details if available
        implementation_text = ""
        if input_data.implementation_details:
            implementation_text = "\n\nImplementation Details:"
            for key, value in input_data.implementation_details.items():
                implementation_text += f"\n- {key}: {value}"
        
        # Include existing documentation if available
        existing_docs_text = ""
        if input_data.existing_docs:
            existing_docs_text = f"\n\nExisting Documentation:\n```markdown\n{input_data.existing_docs}\n```"
            
        # Include technologies if available
        technologies_text = ""
        if input_data.technologies and len(input_data.technologies) > 0:
            technologies_text = f"\n\nTechnologies: {', '.join(input_data.technologies)}"
            
        # Include API files content if available
        api_files_text = ""
        if input_data.api_files and len(input_data.api_files) > 0:
            api_files_text = "\n\nAPI Files:"
            for file_path, content in input_data.api_files:
                api_files_text += f"\n\nFile: {file_path}\n```\n{content}\n```"
        
        # Combine all context
        enhanced_context = f"{project_description}{auth_details}{dependencies_text}{dir_structure_text}{usage_patterns_text}{audience_text}{implementation_text}{existing_docs_text}{technologies_text}{api_files_text}"
        
        return await self.run(
            user_prompt=f"Generate API documentation for {input_data.api_name} in {input_data.language}{framework_text}. Include both Markdown documentation and OpenAPI specification.{enhanced_context}\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
    
    async def generate_api_examples(
        self,
        api_doc: APIDocResult,
        languages: List[str] = ["python", "javascript", "curl"],
        usage_patterns: Optional[List[str]] = None,
        target_audience: Optional[str] = None,
        implementation_details: Optional[Dict[str, Any]] = None
    ) -> AgentResult[APIExamplesResult]:
        """Generate usage examples for the API with enhanced context"""
        if not api_doc:
            raise ValueError("API documentation cannot be empty")
            
        # Format endpoints for readability in the prompt
        endpoints_text = "\n\n".join([
            f"### {endpoint.method} {endpoint.path}\n{endpoint.description}"
            for endpoint in api_doc.endpoints
        ])
        
        languages_text = ", ".join(languages)
        
        # Include usage patterns if available
        usage_patterns_text = ""
        if usage_patterns and len(usage_patterns) > 0:
            patterns = "\n".join([f"- {pattern}" for pattern in usage_patterns])
            usage_patterns_text = f"\n\nCommon Usage Patterns:\n{patterns}"
        
        # Include target audience if available
        audience_text = ""
        if target_audience:
            audience_text = f"\n\nTarget Audience: {target_audience}"
        
        # Include implementation details if available
        implementation_text = ""
        if implementation_details:
            implementation_text = "\n\nImplementation Details:"
            for key, value in implementation_details.items():
                implementation_text += f"\n- {key}: {value}"
        
        # Combine all context
        enhanced_context = f"{usage_patterns_text}{audience_text}{implementation_text}"
        
        # Create a specialized agent for API examples
        examples_agent = BaseAgent[APIDocResult, APIExamplesResult](
            config=self.config,
            system_prompt="You are an API documentation expert. Generate quality code examples.",
            deps_type=APIDocResult,
            result_type=APIExamplesResult
        )
        
        return await examples_agent.run(
            user_prompt=f"""Generate usage examples for these API endpoints in {languages_text}:

API: {api_doc.title} v{api_doc.version}
Description: {api_doc.description}
Base Path: {api_doc.base_path or "/"}{enhanced_context}

Endpoints:
{endpoints_text}

For each endpoint, provide example requests and expected responses.
""",
            deps=api_doc
        )
    
    async def convert_to_openapi(
        self,
        api_doc: APIDocResult
    ) -> Dict[str, Any]:
        """Convert API documentation to OpenAPI specification"""
        if not api_doc:
            raise ValueError("API documentation cannot be empty")
            
        # If we already have an OpenAPI spec, return it
        if api_doc.openapi_spec:
            return api_doc.openapi_spec
        
        # Create a dictionary result type for OpenAPI spec
        class OpenAPISpec(BaseModel):
            spec: Dict[str, Any] = Field(description="OpenAPI specification")
            
        # Create a specialized agent for OpenAPI conversion
        openapi_agent = BaseAgent[APIDocResult, OpenAPISpec](
            config=self.config,
            system_prompt="You are an OpenAPI specification expert. Convert API documentation to valid OpenAPI 3.0 specifications.",
            deps_type=APIDocResult,
            result_type=OpenAPISpec
        )
            
        result = await openapi_agent.run(
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
        
        return result.data.spec 