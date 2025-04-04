from dataclasses import dataclass, field
from typing import List, Optional, ClassVar, Type
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig, AgentResult
from .code_analyzer import CodeElement
from ..utils.metrics import Usage
from ..prompts.agent_prompts import QUALITY_CHECKER_PROMPT

@dataclass
class QualityCheckInput:
    """Input for quality checking"""
    code_element_name: str
    docstring: str
    code: Optional[str] = None
    style_guide: str = "google"
    language: str = "python"

    def __post_init__(self):
        """Validate the input after initialization"""
        if not self.code_element_name or not self.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not self.docstring or not self.docstring.strip():
            raise ValueError("Docstring cannot be empty")

class QualityIssue(BaseModel):
    """Represents a documentation quality issue"""
    category: str = Field(description="Category of the issue (e.g., clarity, completeness)")
    severity: str = Field(description="Severity of the issue (e.g., low, medium, high)")
    description: str = Field(description="Description of the issue")
    suggestion: str = Field(description="Suggestion to fix the issue")

class QualityResult(BaseModel):
    """Result of documentation quality check"""
    score: float = Field(description="Overall quality score (0.0-10.0)")
    strengths: List[str] = Field(default_factory=list, description="Strengths of the documentation")
    issues: List[QualityIssue] = Field(default_factory=list, description="Issues found in the documentation")
    improvements: List[str] = Field(default_factory=list, description="Suggested improvements")

class CompletenessResult(BaseModel):
    """Result of completeness analysis"""
    missing_elements: List[str] = Field(default_factory=list, description="Missing documentation elements")
    completeness_score: float = Field(description="Completeness score (0.0-1.0)")

class ConsistencyResult(BaseModel):
    """Result of consistency check"""
    inconsistencies: List[str] = Field(default_factory=list, description="Style inconsistencies found")
    consistency_score: float = Field(description="Consistency score (0.0-1.0)")
    style_guide_violations: List[str] = Field(default_factory=list, description="Style guide violations")

class QualityChecker(BaseAgent[QualityCheckInput, QualityResult]):
    """Agent for checking documentation quality"""
    
    # Set class variables for type checking
    deps_type: ClassVar[Type[QualityCheckInput]] = QualityCheckInput
    result_type: ClassVar[Type[QualityResult]] = QualityResult
    default_system_prompt: ClassVar[str] = QUALITY_CHECKER_PROMPT
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config,
            deps_type=self.deps_type,
            result_type=self.result_type
        )
    
    async def check_quality(
        self,
        input_data: QualityCheckInput
    ) -> AgentResult[QualityResult]:
        """Check the quality of documentation for a code element"""
        # Validate input
        if not input_data.code_element_name or not input_data.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not input_data.docstring or not input_data.docstring.strip():
            raise ValueError("Docstring cannot be empty")
            
        code_context = f"\n\nCode context:\n```{input_data.language}\n{input_data.code}\n```" if input_data.code else ""
        
        return await self.run(
            user_prompt=f"Check documentation quality for {input_data.code_element_name} using {input_data.style_guide} style guide:\n\n```{input_data.language}\n{input_data.docstring}\n```{code_context}",
            deps=input_data
        )
    
    async def analyze_completeness(
        self,
        input_data: QualityCheckInput
    ) -> AgentResult[CompletenessResult]:
        """Analyze documentation completeness"""
        # Validate input
        if not input_data.code_element_name or not input_data.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not input_data.docstring or not input_data.docstring.strip():
            raise ValueError("Docstring cannot be empty")
            
        code_context = f"\n\nCode context:\n```{input_data.language}\n{input_data.code}\n```" if input_data.code else ""
        
        # Create a specialized agent for completeness checks
        completeness_agent = BaseAgent[QualityCheckInput, CompletenessResult](
            config=self.config,
            system_prompt="You are an expert in analyzing documentation completeness.",
            deps_type=QualityCheckInput,
            result_type=CompletenessResult
        )
        
        return await completeness_agent.run(
            user_prompt=f"Analyze completeness of documentation for {input_data.code_element_name}:\n\n```{input_data.language}\n{input_data.docstring}\n```{code_context}",
            deps=input_data
        )
    
    async def check_consistency(
        self,
        input_data: QualityCheckInput
    ) -> AgentResult[ConsistencyResult]:
        """Check documentation consistency with style guide"""
        # Validate input
        if not input_data.code_element_name or not input_data.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not input_data.docstring or not input_data.docstring.strip():
            raise ValueError("Docstring cannot be empty")
        
        # Create a specialized agent for consistency checks
        consistency_agent = BaseAgent[QualityCheckInput, ConsistencyResult](
            config=self.config,
            system_prompt=f"You are an expert in {input_data.style_guide} style documentation. Check for consistency issues.",
            deps_type=QualityCheckInput,
            result_type=ConsistencyResult
        )
            
        return await consistency_agent.run(
            user_prompt=f"Check consistency of documentation with {input_data.style_guide} style guide:\n\n```{input_data.language}\n{input_data.docstring}\n```",
            deps=input_data
        )