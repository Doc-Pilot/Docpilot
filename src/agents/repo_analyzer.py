"""
Repository Analyzer Agent
=========================

This agent analyzes repository structures to identify components,
architecture patterns, and documentation needs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, ClassVar, Type
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentResult, AgentConfig
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
    
class RepoStructureResult(AgentResult):
    """Result of repository structure analysis"""
    language_breakdown: Dict[str, float] = Field(default_factory=dict, description="Breakdown of languages used (percentage)")
    top_level_directories: List[DirectoryNode] = Field(default_factory=list, description="Top-level directories")
    components: List[RepoComponent] = Field(default_factory=list, description="Logical components identified")
    entry_points: List[str] = Field(default_factory=list, description="Main entry points to the application")
    summary: str = Field(description="Overall summary of the repository structure")
    technologies: Set[str] = Field(default_factory=set, description="Technologies and frameworks used")
    architecture_pattern: Optional[str] = Field(None, description="Detected architecture pattern(s)")
    documentation_files: List[str] = Field(default_factory=list, description="Documentation files found")
    
    def get_all_components(self) -> List[str]:
        """Get a list of all component names"""
        return [comp.name for comp in self.components]
    
    def get_technology_list(self) -> List[str]:
        """Get a list of all technologies"""
        return list(self.technologies)

class MarkdownSummaryResult(AgentResult):
    """Markdown summary of the repository structure"""
    content: str = Field(description="Markdown content describing the repository structure")
    toc: List[str] = Field(default_factory=list, description="Table of contents")
    
    def get_content(self) -> str:
        """Get the markdown content"""
        return self.content
    
class RepoAnalyzer(BaseAgent[RepoStructureInput, RepoStructureResult]):
    """Agent for analyzing repository structure"""
    
    # Set class variables for type checking and configuration
    deps_type: ClassVar[Type[RepoStructureInput]] = RepoStructureInput
    result_type: ClassVar[Type[RepoStructureResult]] = RepoStructureResult
    default_system_prompt: ClassVar[str] = REPO_ANALYZER_PROMPT
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the repository analyzer agent"""
        super().__init__(
            config=config,
            deps_type=self.deps_type,
            result_type=self.result_type
        )
        
        # Register tools
        @self.tool
        def count_files_by_extension(files: List[str]) -> Dict[str, int]:
            """Count the number of files by extension"""
            result = {}
            for file in files:
                ext = file.split(".")[-1] if "." in file else "no_extension"
                result[ext] = result.get(ext, 0) + 1
            return result
        
        @self.tool
        def extract_languages(files: List[str]) -> Set[str]:
            """Extract programming languages from file extensions"""
            extensions_to_languages = {
                "py": "Python",
                "js": "JavaScript",
                "ts": "TypeScript",
                "jsx": "React",
                "tsx": "React/TypeScript",
                "html": "HTML",
                "css": "CSS",
                "scss": "SASS",
                "java": "Java",
                "go": "Go",
                "rb": "Ruby",
                "php": "PHP",
                "c": "C",
                "cpp": "C++",
                "cs": "C#",
                "sh": "Shell",
                "rust": "Rust",
                "rs": "Rust",
                "swift": "Swift",
                "dart": "Dart",
                "kotlin": "Kotlin",
                "scala": "Scala"
            }
            
            languages = set()
            for file in files:
                ext = file.split(".")[-1] if "." in file else ""
                if ext in extensions_to_languages:
                    languages.add(extensions_to_languages[ext])
            return languages
    
    async def analyze_repo_structure(
        self,
        input_data: RepoStructureInput
    ) -> RepoStructureResult:
        """Analyze repository structure asynchronously"""
        # Create file list to analyze
        file_list = "\n".join(input_data.files[:input_data.max_files])
        
        return await self.run(
            user_prompt=f"Analyze this repository structure with path {input_data.repo_path}. Here are the files (limited to {input_data.max_files}):\n\n{file_list}",
            deps=input_data
        )
    
    async def generate_markdown_summary(
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
        
        tech_text = ", ".join(repo_structure.get_technology_list())
        
        # Create a custom agent for this specific task
        markdown_agent = BaseAgent[RepoStructureResult, MarkdownSummaryResult](
            config=self.config,
            system_prompt="""You are an expert technical documentation writer.
Your task is to create a comprehensive markdown summary of a repository 
structure that will help new developers understand the codebase.
Include sections for Overview, Architecture, Components, and Getting Started.
            """,
            deps_type=RepoStructureResult,
            result_type=MarkdownSummaryResult
        )
        
        return await markdown_agent.run(
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
    
    async def identify_documentation_needs(
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
        
        # Use a temporary class for documentation needs result
        class DocNeedsResult(AgentResult):
            """Documentation needs analysis result"""
            readme: List[str] = Field(default_factory=list, description="README documentation needs")
            api: List[str] = Field(default_factory=list, description="API documentation needs")
            guides: List[str] = Field(default_factory=list, description="User guide documentation needs")
            components: List[str] = Field(default_factory=list, description="Component documentation needs")
            
            def to_dict(self) -> Dict[str, List[str]]:
                """Convert to dictionary format"""
                return {
                    "README": self.readme,
                    "API Documentation": self.api,
                    "User Guides": self.guides,
                    "Component Documentation": self.components
                }
        
        # Create a custom agent for documentation needs analysis
        needs_agent = BaseAgent[RepoStructureResult, DocNeedsResult](
            config=self.config,
            system_prompt="""You are an expert in technical documentation analysis.
Your task is to identify documentation needs for a repository based on its
structure and existing documentation. Consider different types of documentation
such as README, API docs, user guides, and component-specific documentation.
            """,
            deps_type=RepoStructureResult,
            result_type=DocNeedsResult
        )
        
        result = await needs_agent.run(
            user_prompt=f"""Based on this repository structure, identify documentation needs:

Summary: {repo_structure.summary}
Technologies: {', '.join(repo_structure.get_technology_list())}
Components:
{components}

Existing documentation:
{existing_docs}

Provide a list of documentation that should be created or updated, categorized by type (README, API docs, guides, etc.).
""",
            deps=repo_structure
        )
        
        # Return the results as a dictionary
        return result.to_dict() 