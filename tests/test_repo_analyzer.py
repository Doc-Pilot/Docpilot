import pytest
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.agents.base import AgentConfig
from src.agents.repo_analyzer import (
    RepoAnalyzer,
    RepoStructureInput,
    RepoStructureResult,
    MarkdownSummaryResult,
    FileNode,
    DirectoryNode,
    RepoComponent
)
from src.utils.repo_scanner import RepoScanner

@pytest.fixture
def sample_repo_structure_input() -> RepoStructureInput:
    """
    Fixture for a sample repository structure input.
    
    Returns:
        RepoStructureInput: Sample repository structure input
    """
    return RepoStructureInput(
        repo_path="sample/repo",
        files=[
            "README.md",
            "setup.py",
            "requirements.txt",
            "src/app.py",
            "src/models.py",
            "src/api/routes.py",
            "src/utils/helpers.py",
            "tests/test_app.py",
            "docs/api.md",
            "docs/usage.md"
        ]
    )

@pytest.fixture
def sample_repo_structure_result() -> RepoStructureResult:
    """
    Fixture for a sample repository structure result.
    
    Returns:
        RepoStructureResult: Sample repository structure result
    """
    return RepoStructureResult(
        language_breakdown={"python": 70.0, "markdown": 30.0},
        top_level_directories=[
            DirectoryNode(
                path="src",
                purpose="Contains source code",
                is_module=True,
                subdirectories=["api", "utils"]
            ),
            DirectoryNode(
                path="tests",
                purpose="Contains tests",
                is_module=False,
                subdirectories=[]
            ),
            DirectoryNode(
                path="docs",
                purpose="Contains documentation",
                is_module=False,
                subdirectories=[]
            )
        ],
        components=[
            RepoComponent(
                name="Core Application",
                description="Main application code",
                paths=["src/app.py"],
                dependencies=["fastapi"]
            ),
            RepoComponent(
                name="API Layer",
                description="API endpoints and routes",
                paths=["src/api/routes.py"],
                dependencies=["fastapi"]
            ),
            RepoComponent(
                name="Data Models",
                description="Data models and schemas",
                paths=["src/models.py"],
                dependencies=["pydantic"]
            )
        ],
        entry_points=["src/app.py"],
        summary="A Python web application using FastAPI with a structured architecture.",
        technologies=["FastAPI", "Python", "Pydantic"],
        architecture_pattern="MVC",
        documentation_files=["README.md", "docs/api.md", "docs/usage.md"]
    )

@pytest.mark.rewrite
def test_repo_analyzer_init(sample_repo_structure_input):
    """Test initializing the repository analyzer"""
    analyzer = RepoAnalyzer()
    assert analyzer.system_prompt is not None
    assert analyzer.model_type == RepoStructureResult

@pytest.mark.rewrite
def test_analyze_repo_structure(monkeypatch, sample_repo_structure_input, sample_repo_structure_result):
    """Test analyzing repository structure"""
    # Mock the run_sync method
    def mock_run_sync(*args, **kwargs):
        return sample_repo_structure_result
    
    analyzer = RepoAnalyzer()
    monkeypatch.setattr(analyzer, "run_sync", mock_run_sync)
    
    # Run the analysis
    result = analyzer.analyze_repo_structure(sample_repo_structure_input)
    
    # Verify the result
    assert isinstance(result, RepoStructureResult)
    assert result.summary == "A Python web application using FastAPI with a structured architecture."
    assert len(result.components) == 3
    assert "FastAPI" in result.technologies
    assert result.architecture_pattern == "MVC"

@pytest.mark.rewrite
def test_generate_markdown_summary(monkeypatch, sample_repo_structure_result):
    """Test generating markdown summary"""
    # Mock the run_sync method
    def mock_run_sync(*args, **kwargs):
        return MarkdownSummaryResult(
            content="# Repository Structure\n\nA Python web application using FastAPI.",
            toc=["Repository Structure", "Components"]
        )
    
    analyzer = RepoAnalyzer()
    monkeypatch.setattr(analyzer, "run_sync", mock_run_sync)
    
    # Generate markdown summary
    result = analyzer.generate_markdown_summary(sample_repo_structure_result)
    
    # Verify the result
    assert isinstance(result, MarkdownSummaryResult)
    assert "Repository Structure" in result.content
    assert "FastAPI" in result.content
    assert "Repository Structure" in result.toc

@pytest.mark.rewrite
def test_identify_documentation_needs(monkeypatch, sample_repo_structure_result):
    """Test identifying documentation needs"""
    # Mock the run_sync method
    def mock_run_sync(*args, **kwargs):
        return {
            "README": ["Update the project overview"],
            "API Documentation": ["Document the API endpoints"],
            "Usage Guides": ["Create a detailed usage guide"]
        }
    
    analyzer = RepoAnalyzer()
    monkeypatch.setattr(analyzer, "run_sync", mock_run_sync)
    
    # Identify documentation needs
    result = analyzer.identify_documentation_needs(sample_repo_structure_result)
    
    # Verify the result
    assert isinstance(result, dict)
    assert "README" in result
    assert "API Documentation" in result
    assert "Usage Guides" in result

@pytest.mark.rewrite
def test_repo_scanner():
    """Test the repository scanner"""
    # Use the current directory for testing
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Initialize scanner
    scanner = RepoScanner(test_dir)
    
    # Scan files
    files = scanner.scan_files()
    
    # The scan should return some files
    assert len(files) > 0
    
    # Test file extension breakdown
    extensions = scanner.get_file_extension_breakdown(files)
    assert len(extensions) > 0
    
    # Test language identification
    # Create a sample Python file path
    sample_python_file = "test_file.py"
    language = scanner.identify_language(sample_python_file)
    assert language == "Python"
    
    # Test identifying documentation files
    doc_files = scanner.identify_documentation_files(files)
    # There should be at least this test file
    assert len(doc_files) >= 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 