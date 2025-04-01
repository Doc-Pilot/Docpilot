from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig
from .code_analyzer import CodeElement

@dataclass
class DocGeneratorInput:
    """Input for documentation generation"""
    code: str
    element_name: str
    language: str = "python"
    style_guide: str = "google"
    element_type: Optional[str] = None
    existing_docstring: Optional[str] = None

    def __post_init__(self):
        """Validate the input after initialization"""
        if not self.code or not self.code.strip():
            raise ValueError("Code cannot be empty")
        if not self.element_name or not self.element_name.strip():
            raise ValueError("Element name cannot be empty")

class DocumentationResult(BaseModel):
    """Result of documentation generation"""
    docstring: str = Field(description="Generated docstring")
    language: str = Field(description="Language of the docstring")
    style: str = Field(description="Style guide followed")
    includes_params: bool = Field(description="Whether parameters are documented")
    includes_returns: bool = Field(description="Whether return values are documented")
    includes_examples: bool = Field(description="Whether examples are included")

class ExamplesResult(BaseModel):
    """Generated code examples"""
    examples: List[Dict[str, str]] = Field(default_factory=list, description="List of code examples")
    explanation: str = Field(description="Explanation of the examples")

class ImprovementsResult(BaseModel):
    """Documentation improvement suggestions"""
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    rationale: List[str] = Field(default_factory=list, description="Rationale for each suggestion")

class DocGenerator(BaseAgent[DocumentationResult]):
    """Agent for generating code documentation"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt="""You are a documentation expert. Generate high-quality documentation that:
            1. Follows the specified style guide (default: Google style)
            2. Clearly explains purpose, parameters, and return values
            3. Includes helpful examples where appropriate
            4. Is concise yet comprehensive
            5. Maintains consistency with existing documentation conventions
            
            Provide clear, accurate documentation that helps developers understand and use the code.""",
            model_type=DocumentationResult
        )
    
    def generate_docstring(
        self,
        input_data: DocGeneratorInput
    ) -> DocumentationResult:
        """Generate a docstring for the provided code element"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("Code cannot be empty")
        if not input_data.element_name or not input_data.element_name.strip():
            raise ValueError("Element name cannot be empty")
            
        return self.run_sync(
            user_prompt=f"Generate a {input_data.style_guide} style docstring for this {input_data.element_type or 'code'} in {input_data.language}:\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
    
    def generate_examples(
        self,
        input_data: DocGeneratorInput
    ) -> ExamplesResult:
        """Generate usage examples for the provided code element"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("Code cannot be empty")
        if not input_data.element_name or not input_data.element_name.strip():
            raise ValueError("Element name cannot be empty")
            
        result = self.run_sync(
            user_prompt=f"Generate usage examples for this {input_data.element_type or 'code'} in {input_data.language}:\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
        if not isinstance(result, ExamplesResult):
            # Handle the case where we got a different result type
            return ExamplesResult(
                examples=[{"title": "Basic Usage", "code": "# No example available"}],
                explanation="Examples could not be generated automatically."
            )
        return result
    
    def suggest_improvements(
        self,
        input_data: DocGeneratorInput
    ) -> ImprovementsResult:
        """Suggest improvements for the existing docstring"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("Code cannot be empty")
        if not input_data.element_name or not input_data.element_name.strip():
            raise ValueError("Element name cannot be empty")
            
        if not input_data.existing_docstring:
            return ImprovementsResult(
                suggestions=["No existing docstring to improve."],
                rationale=["Provide an existing docstring to get improvement suggestions."]
            )
            
        result = self.run_sync(
            user_prompt=f"Suggest improvements for this existing docstring for {input_data.element_name} ({input_data.style_guide} style):\n\n```{input_data.language}\n{input_data.existing_docstring}\n```\n\nThe code is:\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
        if not isinstance(result, ImprovementsResult):
            # Handle the case where we got a different result type
            return ImprovementsResult(
                suggestions=["Automatic improvement suggestions not available."],
                rationale=["Please review the docstring manually."]
            )
        return result 