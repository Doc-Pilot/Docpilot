from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentConfig
from .repo_analyzer import RepoStructureResult
from ..prompts.agent_prompts import README_GENERATOR_PROMPT

@dataclass
class ReadmeInput:
    """Input for README generation"""
    repo_name: str
    repo_description: str
    repo_structure: Optional[RepoStructureResult] = None
    existing_readme: Optional[str] = None
    include_sections: List[str] = field(default_factory=lambda: [
        "overview", "installation", "usage", "examples", "api", "configuration", "contributing", "license"
    ])
    badges: List[Dict[str, str]] = field(default_factory=list)
    license_type: str = "MIT"
    
    def __post_init__(self):
        """Validate the input after initialization"""
        if not self.repo_name or not self.repo_name.strip():
            raise ValueError("Repository name cannot be empty")

class ReadmeSection(BaseModel):
    """Represents a section in the README"""
    title: str = Field(description="Section title")
    content: str = Field(description="Section content")
    level: int = Field(1, description="Heading level (1-6)")

class ReadmeResult(BaseModel):
    """Result of README generation"""
    title: str = Field(description="README title")
    introduction: str = Field(description="Introduction paragraph")
    badges: List[str] = Field(default_factory=list, description="Badge markdown")
    sections: List[ReadmeSection] = Field(default_factory=list, description="README sections")
    toc: List[str] = Field(default_factory=list, description="Table of contents entries")
    markdown: str = Field(description="Complete README in markdown format")
    
class ReadmeGenerator(BaseAgent[ReadmeResult]):
    """Agent for generating README documentation"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(
            config=config or AgentConfig(),
            system_prompt=README_GENERATOR_PROMPT,
            model_type=ReadmeResult
        )
    
    def generate_readme(
        self,
        input_data: ReadmeInput
    ) -> ReadmeResult:
        """Generate a README for the repository"""
        # Validate input
        if not input_data.repo_name or not input_data.repo_name.strip():
            raise ValueError("Repository name cannot be empty")
            
        # Build the prompt with repository structure if available
        repo_structure_text = ""
        if input_data.repo_structure:
            components = "\n".join([
                f"- {comp.name}: {comp.description}" 
                for comp in input_data.repo_structure.components
            ])
            
            technologies = ", ".join(input_data.repo_structure.technologies)
            
            repo_structure_text = f"""
Repository Structure:
- Summary: {input_data.repo_structure.summary}
- Technologies: {technologies}
- Architecture: {input_data.repo_structure.architecture_pattern or 'Not detected'}
- Components:
{components}
"""
        
        # Include existing README if available
        existing_readme_text = ""
        if input_data.existing_readme:
            existing_readme_text = f"""
Existing README:
```markdown
{input_data.existing_readme}
```
"""
        
        # Include sections to include
        sections_text = ", ".join(input_data.include_sections)
        
        return self.run_sync(
            user_prompt=f"""Generate a comprehensive README for {input_data.repo_name}.

Repository Description: {input_data.repo_description}
License: {input_data.license_type}
Sections to include: {sections_text}
{repo_structure_text}
{existing_readme_text}

Create a well-structured, comprehensive README that helps users understand, install, and use the project effectively.
""",
            deps=input_data
        )
    
    def update_readme(
        self,
        input_data: ReadmeInput
    ) -> ReadmeResult:
        """Update an existing README"""
        # Validate input
        if not input_data.repo_name or not input_data.repo_name.strip():
            raise ValueError("Repository name cannot be empty")
        if not input_data.existing_readme:
            return self.generate_readme(input_data)
            
        # Build the prompt with repository structure if available
        repo_structure_text = ""
        if input_data.repo_structure:
            components = "\n".join([
                f"- {comp.name}: {comp.description}" 
                for comp in input_data.repo_structure.components
            ])
            
            technologies = ", ".join(input_data.repo_structure.technologies)
            
            repo_structure_text = f"""
Repository Structure:
- Summary: {input_data.repo_structure.summary}
- Technologies: {technologies}
- Architecture: {input_data.repo_structure.architecture_pattern or 'Not detected'}
- Components:
{components}
"""
        
        return self.run_sync(
            user_prompt=f"""Update this README for {input_data.repo_name}.

Repository Description: {input_data.repo_description}
License: {input_data.license_type}
{repo_structure_text}

Existing README:
```markdown
{input_data.existing_readme}
```

Improve this README by updating outdated information, enhancing existing sections, and adding missing information. Maintain the overall structure and style, but make it more comprehensive and user-friendly.
""",
            deps=input_data
        )
    
    def generate_section(
        self,
        repo_name: str,
        section_name: str,
        repo_structure: Optional[RepoStructureResult] = None
    ) -> ReadmeSection:
        """Generate a specific section for a README"""
        if not repo_name or not repo_name.strip():
            raise ValueError("Repository name cannot be empty")
        if not section_name or not section_name.strip():
            raise ValueError("Section name cannot be empty")
            
        # Build context based on the section type
        context = ""
        if repo_structure:
            if section_name.lower() == "installation":
                # Include dependencies for installation section
                dependencies = ", ".join(repo_structure.technologies)
                context = f"Dependencies: {dependencies}"
            elif section_name.lower() == "architecture" or section_name.lower() == "overview":
                # Include architecture info
                components = "\n".join([
                    f"- {comp.name}: {comp.description}" 
                    for comp in repo_structure.components
                ])
                context = f"""
Repository Structure:
- Summary: {repo_structure.summary}
- Architecture: {repo_structure.architecture_pattern or 'Not detected'}
- Components:
{components}
"""
        
        result = self.run_sync(
            user_prompt=f"""Generate the '{section_name}' section for the README of {repo_name}.

{context}

Create a comprehensive, well-written section that provides valuable information to users.
""",
            deps=ReadmeInput(
                repo_name=repo_name,
                repo_description="",
                repo_structure=repo_structure
            )
        )
        
        # Handle the case where we get a ReadmeResult instead of a ReadmeSection
        if isinstance(result, ReadmeResult):
            # Find the matching section or create a new one
            for section in result.sections:
                if section.title.lower() == section_name.lower():
                    return section
            
            # If not found, create from the markdown
            return ReadmeSection(
                title=section_name,
                content=result.markdown,
                level=2
            )
        
        # Convert string result to ReadmeSection if needed
        if isinstance(result, str):
            return ReadmeSection(
                title=section_name,
                content=result,
                level=2
            )
            
        return result 