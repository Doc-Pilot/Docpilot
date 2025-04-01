from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig
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

class CodeAnalyzer(BaseAgent[CodeAnalysisResult]):
    """Agent for analyzing code elements"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt=CODE_ANALYZER_PROMPT,
            model_type=CodeAnalysisResult
        )
    
    def analyze_code(self, code_element: CodeElement) -> CodeAnalysisResult:
        """Analyze a code element and return structured results"""
        # Validate input
        if not code_element.name or not code_element.name.strip():
            raise ValueError("Code element name cannot be empty")
        if not code_element.code or not code_element.code.strip():
            raise ValueError("Code cannot be empty")
            
        return self.run_sync(
            user_prompt=f"Analyze this {code_element.element_type or 'code'} element named {code_element.name}:\n\n```{code_element.language or ''}\n{code_element.code}\n```",
            deps=CodeElement(
                name=code_element.name,
                code=code_element.code,
                file_path=code_element.file_path,
                element_type=code_element.element_type,
                language=code_element.language
            )
        )
    
    def parse_docstring(self, docstring: str) -> DocstringResult:
        """Parse docstring and extract structured information"""
        # Validate input
        if not docstring or not docstring.strip():
            raise ValueError("Docstring cannot be empty")
            
        result = self.run_sync(
            user_prompt=f"Parse this docstring and extract structured information:\n\n{docstring}",
            deps=CodeElement(
                name="docstring",
                code=docstring
            )
        )
        if not isinstance(result, DocstringResult):
            # Convert CodeAnalysisResult to DocstringResult if needed
            return DocstringResult(
                description=result.summary,
                params=[{"name": inp.get("name", ""), "description": inp.get("description", "")} 
                       for inp in result.inputs],
                returns=result.outputs[0].get("description") if result.outputs else None,
                examples=[]
            )
        return result
    
    def calculate_complexity(self, code: str) -> ComplexityResult:
        """Calculate complexity of code and provide improvement suggestions"""
        # Validate input
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")
            
        result = self.run_sync(
            user_prompt=f"Calculate the complexity of this code and suggest improvements:\n\n```\n{code}\n```",
            deps=CodeElement(
                name="complexity_analysis",
                code=code
            )
        )
        if not isinstance(result, ComplexityResult):
            # Convert CodeAnalysisResult to ComplexityResult if needed
            return ComplexityResult(
                score=result.complexity,
                factors=[],
                suggestions=[]
            )
        return result