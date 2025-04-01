from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig
from ..prompts.agent_prompts import REPO_ANALYZER_PROMPT

@dataclass
class RepoStructureInput:
    """Input for repository structure analysis"""
    repo_path: str
    files: List[str]
    include_patterns: List[str] = field(default_factory=lambda: ["*"])
    exclude_patterns: List[str] = field(default_factory=lambda: [])
    max_files: int = 1000
    
    def __post_init__(self):
        """Validate the input after initialization"""
        if not self.repo_path or not self.repo_path.strip():
            raise ValueError("Repository path cannot be empty")
        if not self.files:
            raise ValueError("Files list cannot be empty")

class FileNode(BaseModel):
    """Represents a file in the repository"""
    path: str = Field(description="Path to the file relative to repository root")
    file_type: str = Field(description="File type (e.g., Python, JavaScript, config)")
    size: Optional[int] = Field(None, description="File size in bytes")
    is_important: bool = Field(False, description="Whether the file is considered important")
    contains_api: bool = Field(False, description="Whether the file contains API definitions")
    purpose: Optional[str] = Field(None, description="Detected purpose of the file")
    
class DirectoryNode(BaseModel):
    """Represents a directory in the repository"""
    path: str = Field(description="Path to the directory relative to repository root")
    purpose: Optional[str] = Field(None, description="Detected purpose of the directory")
    files: List[FileNode] = Field(default_factory=list, description="Files in this directory")
    subdirectories: List[str] = Field(default_factory=list, description="Subdirectory paths")
    is_module: bool = Field(False, description="Whether this directory represents a code module")

class RepoComponent(BaseModel):
    """Represents a logical component in the repository"""
    name: str = Field(description="Component name")
    description: str = Field(description="Component description")
    paths: List[str] = Field(default_factory=list, description="Paths associated with this component")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies of this component")
    
class RepoStructureResult(BaseModel):
    """Result of repository structure analysis"""
    language_breakdown: Dict[str, float] = Field(default_factory=dict, description="Breakdown of languages used (percentage)")
    top_level_directories: List[DirectoryNode] = Field(default_factory=list, description="Top-level directories")
    components: List[RepoComponent] = Field(default_factory=list, description="Logical components identified")
    entry_points: List[str] = Field(default_factory=list, description="Main entry points to the application")
    summary: str = Field(description="Overall summary of the repository structure")
    technologies: List[str] = Field(default_factory=list, description="Technologies and frameworks used")
    architecture_pattern: Optional[str] = Field(None, description="Detected architecture pattern(s)")
    documentation_files: List[str] = Field(default_factory=list, description="Documentation files found")

class MarkdownSummaryResult(BaseModel):
    """Markdown summary of the repository structure"""
    content: str = Field(description="Markdown content describing the repository structure")
    toc: List[str] = Field(default_factory=list, description="Table of contents")
    
class RepoAnalyzer(BaseAgent[RepoStructureResult]):
    """Agent for analyzing repository structure"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt=REPO_ANALYZER_PROMPT,
            model_type=RepoStructureResult
        )
    
    def analyze_repo_structure(
        self,
        input_data: RepoStructureInput
    ) -> RepoStructureResult:
        """Analyze repository structure"""
        # Validate input
        if not input_data.repo_path or not input_data.repo_path.strip():
            raise ValueError("Repository path cannot be empty")
        if not input_data.files:
            raise ValueError("Files list cannot be empty")
            
        # Create file list to analyze
        file_list = "\n".join(input_data.files[:input_data.max_files])
        
        return self.run_sync(
            user_prompt=f"Analyze this repository structure with path {input_data.repo_path}. Here are the files (limited to {input_data.max_files}):\n\n{file_list}",
            deps=input_data
        )
    
    def generate_markdown_summary(
        self,
        repo_structure: RepoStructureResult
    ) -> MarkdownSummaryResult:
        """Generate a markdown summary of the repository structure"""
        if not repo_structure:
            raise ValueError("Repository structure cannot be empty")
            
        # Format repository structure for readability
        components_text = "\n".join([
            f"- {comp.name}: {comp.description}" 
            for comp in repo_structure.components
        ])
        
        tech_text = ", ".join(repo_structure.technologies)
        
        result = self.run_sync(
            user_prompt=f"""Generate a comprehensive markdown summary of this repository structure.

Summary: {repo_structure.summary}
Technologies: {tech_text}
Architecture: {repo_structure.architecture_pattern or 'Not detected'}
Components:
{components_text}

The markdown should include sections for Overview, Architecture, Components, and Getting Started based on the repository structure.
""",
            deps=repo_structure
        )
        
        # The result might be a RepoStructureResult or MarkdownSummaryResult due to agent flexibility
        if not isinstance(result, MarkdownSummaryResult):
            # Convert to MarkdownSummaryResult if needed
            return MarkdownSummaryResult(
                content=f"""# Repository Structure

{repo_structure.summary}

## Technology Stack

{tech_text}

## Architecture

{repo_structure.architecture_pattern or 'Not specified'}

## Components

{components_text}
""",
                toc=["Repository Structure", "Technology Stack", "Architecture", "Components"]
            )
        
        return result
    
    def identify_documentation_needs(
        self,
        repo_structure: RepoStructureResult
    ) -> Dict[str, List[str]]:
        """Identify documentation needs based on repository structure"""
        if not repo_structure:
            raise ValueError("Repository structure cannot be empty")
            
        # Convert to a simpler format for prompt clarity
        components = "\n".join([
            f"- {comp.name}: {comp.description}" 
            for comp in repo_structure.components
        ])
        
        existing_docs = "\n".join([
            f"- {doc}" for doc in repo_structure.documentation_files
        ]) or "No documentation files found."
        
        result = self.run_sync(
            user_prompt=f"""Based on this repository structure, identify documentation needs:

Summary: {repo_structure.summary}
Technologies: {', '.join(repo_structure.technologies)}
Components:
{components}

Existing documentation:
{existing_docs}

Provide a list of documentation that should be created or updated, categorized by type (README, API docs, guides, etc.).
""",
            deps=repo_structure
        )
        
        # Handle result conversion if needed
        if isinstance(result, Dict):
            return result
        elif isinstance(result, RepoStructureResult):
            # Create a basic needs dictionary
            return {
                "README": ["Main README.md needs to be created or updated"],
                "API Documentation": ["API documentation should be generated"],
                "Component Documentation": [f"Documentation for {comp.name}" for comp in repo_structure.components]
            }
        else:
            # Default return if result is in an unexpected format
            return {
                "General": ["Repository documentation needs assessment complete"],
                "README": ["README.md should be created or updated"]
            } 