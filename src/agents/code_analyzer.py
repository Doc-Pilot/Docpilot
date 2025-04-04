from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, ClassVar, Type
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig, AgentResult
from ..prompts.agent_prompts import CODE_ANALYZER_PROMPT

@dataclass
class CodeElement:
    """Represents a code element to be analyzed"""
    name: str
    code: str
    file_path: Optional[str] = None
    element_type: Optional[str] = None
    language: Optional[str] = None

    def __post_init__(self):
        """Validate the code element after initialization"""
        if not self.name or not self.name.strip():
            raise ValueError("Code element name cannot be empty")
        if not self.code or not self.code.strip():
            raise ValueError("Code cannot be empty")

class CodeAnalysisResult(BaseModel):
    """Result of code analysis"""
    language: str = Field(description="Programming language of the code")
    complexity: int = Field(description="Complexity score from 1-10")
    summary: str = Field(description="Brief summary of the code")
    purpose: str = Field(description="Purpose of the code element")
    dependencies: List[str] = Field(default_factory=list, description="External dependencies used")
    inputs: List[Dict[str, Any]] = Field(default_factory=list, description="Input parameters")
    outputs: List[Dict[str, Any]] = Field(default_factory=list, description="Output values")
    
class DocstringResult(BaseModel):
    """Result of docstring parsing"""
    description: str = Field(description="Extracted description")
    params: List[Dict[str, str]] = Field(default_factory=list, description="Extracted parameters")
    returns: Optional[str] = Field(None, description="Extracted return value description")
    examples: List[str] = Field(default_factory=list, description="Extracted examples")
    
class ComplexityResult(BaseModel):
    """Result of complexity calculation"""
    score: int = Field(description="Complexity score (1-10)")
    factors: List[str] = Field(default_factory=list, description="Factors contributing to complexity")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions to reduce complexity")

class CodeAnalyzer(BaseAgent[CodeElement, CodeAnalysisResult]):
    """Agent for analyzing code elements"""
    
    # Set class variables for type checking
    deps_type: ClassVar[Type[CodeElement]] = CodeElement
    result_type: ClassVar[Type[CodeAnalysisResult]] = CodeAnalysisResult
    default_system_prompt: ClassVar[str] = CODE_ANALYZER_PROMPT
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config,
            deps_type=self.deps_type,
            result_type=self.result_type
        )
    
    async def analyze_code(self, code_element: CodeElement) -> AgentResult[CodeAnalysisResult]:
        """Analyze a code element and return structured results"""
        # Validate input
        if not code_element.name or not code_element.name.strip():
            raise ValueError("Code element name cannot be empty")
        if not code_element.code or not code_element.code.strip():
            raise ValueError("Code cannot be empty")
            
        return await self.run(
            user_prompt=f"Analyze this {code_element.element_type or 'code'} element named {code_element.name}:\n\n```{code_element.language or ''}\n{code_element.code}\n```",
            deps=code_element
        )
    
    async def parse_docstring(self, docstring: str) -> AgentResult[DocstringResult]:
        """Parse docstring and extract structured information"""
        # Validate input
        if not docstring or not docstring.strip():
            raise ValueError("Docstring cannot be empty")
        
        # Create a specialized agent for docstring parsing
        docstring_agent = BaseAgent[CodeElement, DocstringResult](
            config=self.config,
            system_prompt="You are an expert at parsing docstrings from code. Extract structured information about parameters, return values, and examples.",
            deps_type=CodeElement,
            result_type=DocstringResult
        )
            
        return await docstring_agent.run(
            user_prompt=f"Parse this docstring and extract structured information:\n\n{docstring}",
            deps=CodeElement(
                name="docstring",
                code=docstring
            )
        )
    
    async def calculate_complexity(self, code: str) -> AgentResult[ComplexityResult]:
        """Calculate complexity of code and provide improvement suggestions"""
        # Validate input
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")
        
        # Create a specialized agent for complexity analysis
        complexity_agent = BaseAgent[CodeElement, ComplexityResult](
            config=self.config,
            system_prompt="You are an expert at analyzing code complexity. Rate code on a scale of 1-10, identify factors contributing to complexity, and suggest improvements.",
            deps_type=CodeElement,
            result_type=ComplexityResult
        )
            
        return await complexity_agent.run(
            user_prompt=f"Calculate the complexity of this code and suggest improvements:\n\n```\n{code}\n```",
            deps=CodeElement(
                name="complexity_analysis",
                code=code
            )
        )