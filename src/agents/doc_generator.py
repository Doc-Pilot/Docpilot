from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, ClassVar, Type
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig, AgentResult
from .code_analyzer import CodeElement
from ..utils.metrics import Usage
from ..prompts.agent_prompts import DOC_GENERATOR_PROMPT

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

class DocGenerator(BaseAgent[DocGeneratorInput, DocumentationResult]):
    """Agent for generating code documentation"""
    
    # Set class variables for type checking
    deps_type: ClassVar[Type[DocGeneratorInput]] = DocGeneratorInput
    result_type: ClassVar[Type[DocumentationResult]] = DocumentationResult
    default_system_prompt: ClassVar[str] = DOC_GENERATOR_PROMPT
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config,
            deps_type=self.deps_type,
            result_type=self.result_type
        )
    
    async def generate_docstring(
        self,
        input_data: DocGeneratorInput
    ) -> AgentResult[DocumentationResult]:
        """Generate a docstring for the provided code element"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("Code cannot be empty")
        if not input_data.element_name or not input_data.element_name.strip():
            raise ValueError("Element name cannot be empty")
            
        return await self.run(
            user_prompt=f"Generate a {input_data.style_guide} style docstring for this {input_data.element_type or 'code'} in {input_data.language}:\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
    
    async def generate_examples(
        self,
        input_data: DocGeneratorInput
    ) -> AgentResult[ExamplesResult]:
        """Generate usage examples for the provided code element"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("Code cannot be empty")
        if not input_data.element_name or not input_data.element_name.strip():
            raise ValueError("Element name cannot be empty")
            
        # Create a specialized agent for examples
        examples_agent = BaseAgent[DocGeneratorInput, ExamplesResult](
            config=self.config,
            system_prompt=f"You are an expert in {input_data.language} programming. Create helpful usage examples for code.",
            deps_type=DocGeneratorInput,
            result_type=ExamplesResult
        )
            
        return await examples_agent.run(
            user_prompt=f"Generate usage examples for this {input_data.element_type or 'code'} in {input_data.language}:\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        )
    
    async def suggest_improvements(
        self,
        input_data: DocGeneratorInput
    ) -> AgentResult[ImprovementsResult]:
        """Suggest improvements for the existing docstring"""
        # Validate input
        if not input_data.code or not input_data.code.strip():
            raise ValueError("Code cannot be empty")
        if not input_data.element_name or not input_data.element_name.strip():
            raise ValueError("Element name cannot be empty")
            
        if not input_data.existing_docstring:
            # Create an empty result without calling the LLM
            result = ImprovementsResult(
                suggestions=["No existing docstring to improve."],
                rationale=["Provide an existing docstring to get improvement suggestions."]
            )
            # Create usage info with zero tokens
            usage = Usage(model=self.config.model_name)
            # Return as AgentResult
            return AgentResult(data=result, usage=usage)
            
        # Create a specialized agent for improvement suggestions
        improvements_agent = BaseAgent[DocGeneratorInput, ImprovementsResult](
            config=self.config,
            system_prompt=f"You are an expert in {input_data.language} documentation. Analyze existing docstrings and suggest improvements.",
            deps_type=DocGeneratorInput,
            result_type=ImprovementsResult
        )
            
        return await improvements_agent.run(
            user_prompt=f"Suggest improvements for this existing docstring for {input_data.element_name} ({input_data.style_guide} style):\n\n```{input_data.language}\n{input_data.existing_docstring}\n```\n\nThe code is:\n\n```{input_data.language}\n{input_data.code}\n```",
            deps=input_data
        ) 