import pytest
import os
import sys
from typing import List, Dict, Any, Optional

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import the agents and their types
from src.agents.base import AgentConfig
from src.agents.code_analyzer import (
    CodeAnalyzer,
    CodeElement,
    CodeAnalysisResult,
    DocstringResult,
    ComplexityResult
)
from src.agents.doc_generator import (
    DocGenerator,
    DocGeneratorInput,
    DocumentationResult,
    ExamplesResult,
    ImprovementsResult
)
from src.agents.quality_checker import (
    QualityChecker,
    QualityCheckInput,
    QualityResult,
    QualityIssue,
    CompletenessResult,
    ConsistencyResult
)

# Example code for testing
EXAMPLE_CODE = '''
def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number.
    
    Args:
        n: The position in the Fibonacci sequence
        
    Returns:
        The nth Fibonacci number
        
    Raises:
        ValueError: If n is negative
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

class DataProcessor:
    def process_data(self, data: list) -> dict:
        """Process input data and return statistics."""
        return {
            "count": len(data),
            "sum": sum(data),
            "average": sum(data) / len(data) if data else 0
        }
'''

@pytest.fixture
def agent_config() -> AgentConfig:
    """Fixture for agent configuration.
    
    Returns:
        AgentConfig: A configured agent configuration instance.
    """
    return AgentConfig()

@pytest.fixture
def example_code_element() -> CodeElement:
    """Fixture for example code element.
    
    Returns:
        CodeElement: A configured code element instance.
    """
    return CodeElement(
        name="process_data",
        code=EXAMPLE_CODE,
        element_type="method",
        language="python"
    )

@pytest.mark.rewrite
def test_code_analyzer(agent_config: AgentConfig, example_code_element: CodeElement) -> None:
    """Test the CodeAnalyzer agent.
    
    Args:
        agent_config: The agent configuration fixture.
        example_code_element: The example code element fixture.
    """
    analyzer = CodeAnalyzer(config=agent_config)
    
    # Analyze the example code
    result = analyzer.analyze_code(example_code_element)
    
    # Verify basic properties
    assert isinstance(result, CodeAnalysisResult)
    assert result.language.lower() == "python"  # Case-insensitive comparison
    assert result.complexity > 0
    assert result.summary
    assert result.purpose
    
    # Test docstring parsing
    docstring = example_code_element.code.split('"""')[1]
    parsed = analyzer.parse_docstring(docstring)
    assert isinstance(parsed, DocstringResult)
    assert parsed.description
    assert isinstance(parsed.params, list)
    assert parsed.returns is not None
    
    # Test complexity calculation
    complexity = analyzer.calculate_complexity(example_code_element.code)
    assert isinstance(complexity, ComplexityResult)
    assert 1 <= complexity.score <= 10
    assert isinstance(complexity.factors, list)
    assert isinstance(complexity.suggestions, list)

@pytest.mark.rewrite
def test_doc_generator(agent_config: AgentConfig, example_code_element: CodeElement) -> None:
    """Test the DocGenerator agent.
    
    Args:
        agent_config: The agent configuration fixture.
        example_code_element: The example code element fixture.
    """
    generator = DocGenerator(config=agent_config)
    
    # Create input for documentation generation
    input_data = DocGeneratorInput(
        code=example_code_element.code,
        element_name=example_code_element.name,
        language=example_code_element.language,
        element_type=example_code_element.element_type
    )
    
    # Generate documentation
    result = generator.generate_docstring(input_data)
    
    # Verify result structure
    assert isinstance(result, DocumentationResult)
    assert result.docstring
    assert result.language.lower() == "python"  # Case-insensitive comparison
    assert result.style == "google"
    assert result.includes_params
    assert result.includes_returns
    assert result.includes_examples
    
    # Test example generation
    examples = generator.generate_examples(input_data)
    assert isinstance(examples, ExamplesResult)
    assert isinstance(examples.examples, list)
    assert examples.explanation
    
    # Test improvement suggestions
    improvements = generator.suggest_improvements(input_data)
    assert isinstance(improvements, ImprovementsResult)
    assert isinstance(improvements.suggestions, list)
    assert isinstance(improvements.rationale, list)

@pytest.mark.rewrite
def test_quality_checker(agent_config: AgentConfig, example_code_element: CodeElement) -> None:
    """Test the QualityChecker agent.
    
    Args:
        agent_config: The agent configuration fixture.
        example_code_element: The example code element fixture.
    """
    checker = QualityChecker(config=agent_config)
    
    # Create input for quality checking
    input_data = QualityCheckInput(
        code_element_name=example_code_element.name,
        docstring=example_code_element.code.split('"""')[1],
        code=example_code_element.code,
        language=example_code_element.language
    )
    
    # Check documentation quality
    result = checker.check_quality(input_data)
    
    # Verify result structure
    assert isinstance(result, QualityResult)
    assert 0 <= result.score <= 10
    assert isinstance(result.strengths, list)
    assert isinstance(result.issues, list)
    assert isinstance(result.improvements, list)
    
    # Verify issues structure
    for issue in result.issues:
        assert isinstance(issue, QualityIssue)
        assert issue.category
        assert issue.severity in ["low", "medium", "high"]
        assert issue.description
        assert issue.suggestion
    
    # Test completeness analysis
    completeness = checker.analyze_completeness(input_data)
    assert isinstance(completeness, CompletenessResult)
    assert isinstance(completeness.missing_elements, list)
    assert 0 <= completeness.completeness_score <= 1
    
    # Test consistency check
    consistency = checker.check_consistency(input_data)
    assert isinstance(consistency, ConsistencyResult)
    assert isinstance(consistency.inconsistencies, list)
    assert 0 <= consistency.consistency_score <= 1
    assert isinstance(consistency.style_guide_violations, list)

@pytest.mark.rewrite
def test_error_handling(agent_config: AgentConfig) -> None:
    """Test error handling in agents.
    
    Args:
        agent_config: The agent configuration fixture.
    """
    analyzer = CodeAnalyzer(config=agent_config)
    
    # Test with invalid code element
    with pytest.raises(ValueError, match="Code element name cannot be empty"):
        analyzer.analyze_code(CodeElement(name="", code=""))
    
    # Test with invalid docstring
    with pytest.raises(ValueError, match="Docstring cannot be empty"):
        analyzer.parse_docstring("")
    
    # Test with invalid code
    with pytest.raises(ValueError, match="Code cannot be empty"):
        analyzer.calculate_complexity("")
    
    # Test doc generator with invalid input
    generator = DocGenerator(config=agent_config)
    with pytest.raises(ValueError, match="Code cannot be empty"):
        generator.generate_docstring(DocGeneratorInput(code="", element_name=""))
    
    # Test quality checker with invalid input
    checker = QualityChecker(config=agent_config)
    with pytest.raises(ValueError, match="Code element name cannot be empty"):
        checker.check_quality(QualityCheckInput(code_element_name="", docstring=""))

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 