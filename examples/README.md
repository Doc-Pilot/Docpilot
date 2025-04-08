# Docpilot Examples

This directory contains example scripts demonstrating how to use Docpilot's core functionality. These examples show how different modules can be combined to create automated documentation workflows.

## Available Examples

### 1. `integrated_doc_workflow.py`

A comprehensive example that demonstrates the full Docpilot workflow:
- Repository analysis
- Documentation scanning
- Code structure analysis
- Documentation update suggestions

This example shows how `doc_tools.py`, `code_tools.py`, and `repo_tools.py` integrate to maintain documentation aligned with code.

**Run with:**
```bash
python examples/integrated_doc_workflow.py
```

### 2. `api_doc_generator.py`

A focused example that automatically generates API documentation:
- Identifies API components in the repository
- Analyzes code structure to extract endpoints and models
- Generates Markdown documentation based on code analysis
- Sets up monitoring for future API changes

This example demonstrates how Docpilot can be used to automate the creation and maintenance of API documentation.

**Run with:**
```bash
python examples/api_doc_generator.py
```

### 3. `ci_integration.py`

A CI/CD pipeline integration example that automates documentation updates:
- Detects code changes between git references (e.g., commits or branches)
- Identifies documentation files that need updating
- Generates detailed reports with update suggestions
- Provides exit codes for CI pipeline integration

Perfect for setting up automated documentation checks in GitHub Actions, GitLab CI, or Jenkins.

**Run with:**
```bash
python examples/ci_integration.py --repo-path /path/to/repo --base-ref HEAD~5 --target-ref HEAD
```

### 4. `code_parser_example.py`

A minimal example showing the basic functionality of the code parser:
- Detects programming language
- Parses code files to extract structure
- Identifies functions and classes
- A simple demonstration of the core parsing capabilities

**Run with:**
```bash
python examples/code_parser_example.py
```

## Using These Examples

These examples are designed to demonstrate how Docpilot can be used to automate documentation workflows. They can be:

1. **Run as is**: The examples work on the Docpilot repository itself to demonstrate functionality
2. **Modified for your project**: Adapt the examples to work with your own repositories
3. **Used as reference**: Learn from the examples to build your own documentation tooling

## Integration Patterns

The examples demonstrate several key integration patterns:

1. **Scan → Analyze → Update**: Find documentation, analyze related code, suggest updates
2. **Identify → Extract → Generate**: Find API components, extract structure, generate documentation
3. **Monitor → Detect → Notify**: Monitor repository, detect significant changes, notify about needed updates
4. **CI/CD Integration**: Automate documentation checks and updates in continuous integration workflows

## Next Steps

After exploring these examples, you can:

1. Create a custom documentation workflow specific to your project
2. Set up automation using Git hooks or CI/CD pipelines
3. Extend Docpilot with additional functionality for your specific needs 