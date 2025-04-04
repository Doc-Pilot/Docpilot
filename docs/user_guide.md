# Docpilot: AI-Powered Documentation Generator

Docpilot is an AI-powered documentation generator that analyzes your codebase and creates high-quality documentation, including READMEs, API documentation, and component documentation.

## Features

- **Repository Analysis**: Automatically analyzes your codebase to identify programming languages, frameworks, entry points, and key components.
- **README Generation**: Creates comprehensive README files with project descriptions, installation instructions, usage examples, and more.
- **API Documentation**: Generates detailed API documentation for your endpoints, classes, and functions.
- **Component Documentation**: Produces documentation for your UI components, including props, methods, and usage examples.
- **Flexible Architecture**: Supports multiple LLM providers (OpenAI, Anthropic) and is designed for extensibility.
- **CLI Interface**: Easy-to-use command line interface for generating documentation with various options.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/docpilot.git
cd docpilot

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

## Usage

### Command Line Interface

Docpilot provides a command-line interface for generating documentation:

```bash
# Scan a repository
python -m docpilot.cli scan <repo_path> [--output-dir=<dir>] [--exclude=<dirs>]

# Analyze a repository
python -m docpilot.cli analyze <repo_path> [--output-dir=<dir>] [--exclude=<dirs>]

# Generate documentation
python -m docpilot.cli docs <repo_path> [--output-dir=<dir>] [--exclude=<dirs>] [--readme] [--api] [--components] [--model=<model>] [--temperature=<temp>]

# View metrics from a previous run
python -m docpilot.cli metrics <metrics_file>
```

### Using the OrchestratorAgent

You can also use the `OrchestratorAgent` directly in your Python code:

```python
from docpilot.src.agents.orchestrator import OrchestratorAgent

# Initialize the orchestrator
agent = OrchestratorAgent()

# Run the complete workflow
result = agent.run_workflow(
    repo_path="path/to/your/repo",
    output_dir="path/to/output",
    excluded_dirs=[".git", "node_modules"],
    docs_to_generate=["readme", "api", "component"]
)

# Or run individual steps
scan_result = agent.scan_repository("path/to/your/repo")
analysis_result = agent.analyze_repository()
readme_result = agent.generate_readme()
```

### Example

Check out the example script in `examples/orchestrator_example.py` for a complete usage example.

## Architecture

Docpilot uses a modular agent-based architecture:

1. **BaseAgent**: Abstract base class providing common functionality for all agents.
2. **OrchestratorAgent**: Coordinates the entire documentation workflow.
3. **RepoAnalyzer**: Analyzes the repository structure and codebase.
4. **ReadmeGenerator**: Generates README documentation.
5. **APIDocGenerator**: Generates API documentation.
6. **DocGenerator**: Generates component documentation.
7. **CodeAnalyzer**: Performs deeper code analysis for better documentation.
8. **QualityChecker**: Ensures documentation quality and completeness.

### Workflow

The typical documentation workflow follows these steps:

1. Scan the repository to collect file information
2. Analyze the repository structure and codebase
3. Generate README documentation
4. Generate API documentation for endpoints, classes, or functions
5. Generate component documentation for UI components
6. Perform quality checks and refinements

## Configuration

Docpilot can be configured through the environment variables in your `.env` file:

- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `LLM_PROVIDER`: Which LLM provider to use (openai or anthropic)
- `LLM_MODEL`: The model to use (e.g., gpt-4, claude-3-opus)
- `LLM_TEMPERATURE`: Temperature setting for generation (0.0-1.0)
