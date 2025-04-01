from dataclasses import dataclass, field
from typing import List, Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig
from .code_analyzer import CodeElement
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

class QualityChecker(BaseAgent[QualityResult]):
    """Agent for checking documentation quality"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt=QUALITY_CHECKER_PROMPT,
            model_type=QualityResult
        )
    
    def check_quality(
        self,
        input_data: QualityCheckInput
    ) -> QualityResult:
        """Check the quality of documentation for a code element"""
        # Validate input
        if not input_data.code_element_name or not input_data.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not input_data.docstring or not input_data.docstring.strip():
            raise ValueError("Docstring cannot be empty")
            
        code_context = f"\n\nCode context:\n```{input_data.language}\n{input_data.code}\n```" if input_data.code else ""
        
        return self.run_sync(
            user_prompt=f"Check documentation quality for {input_data.code_element_name} using {input_data.style_guide} style guide:\n\n```{input_data.language}\n{input_data.docstring}\n```{code_context}",
            deps=input_data
        )
    
    def analyze_completeness(
        self,
        input_data: QualityCheckInput
    ) -> CompletenessResult:
        """Analyze documentation completeness"""
        # Validate input
        if not input_data.code_element_name or not input_data.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not input_data.docstring or not input_data.docstring.strip():
            raise ValueError("Docstring cannot be empty")
            
        code_context = f"\n\nCode context:\n```{input_data.language}\n{input_data.code}\n```" if input_data.code else ""
        
        result = self.run_sync(
            user_prompt=f"Analyze completeness of documentation for {input_data.code_element_name}:\n\n```{input_data.language}\n{input_data.docstring}\n```{code_context}",
            deps=input_data
        )
        if not isinstance(result, CompletenessResult):
            # Convert QualityResult to CompletenessResult if needed
            missing = []
            if isinstance(result, QualityResult):
                missing = [issue.description for issue in result.issues 
                          if "missing" in issue.description.lower() or "lacks" in issue.description.lower()]
            
            return CompletenessResult(
                missing_elements=missing,
                completeness_score=len(missing) > 0 and 0.5 or 1.0
            )
        return result
    
    def check_consistency(
        self,
        input_data: QualityCheckInput
    ) -> ConsistencyResult:
        """Check documentation consistency with style guide"""
        # Validate input
        if not input_data.code_element_name or not input_data.code_element_name.strip():
            raise ValueError("Code element name cannot be empty")
        if not input_data.docstring or not input_data.docstring.strip():
            raise ValueError("Docstring cannot be empty")
            
        result = self.run_sync(
            user_prompt=f"Check consistency of documentation with {input_data.style_guide} style guide:\n\n```{input_data.language}\n{input_data.docstring}\n```",
            deps=input_data
        )
        if not isinstance(result, ConsistencyResult):
            # Convert QualityResult to ConsistencyResult if needed
            inconsistencies = []
            if isinstance(result, QualityResult):
                inconsistencies = [issue.description for issue in result.issues 
                                 if "style" in issue.description.lower() or "format" in issue.description.lower()]
            
            return ConsistencyResult(
                inconsistencies=inconsistencies,
                consistency_score=len(inconsistencies) > 0 and 0.7 or 1.0,
                style_guide_violations=[]
            )
        return result