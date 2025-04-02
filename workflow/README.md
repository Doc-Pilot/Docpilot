# Docpilot Workflow

This directory contains the modular components for running Docpilot workflows. The modularized architecture makes the code more maintainable, testable, and easier to extend.

## Module Structure

The workflow modules are organized as follows:

- **metrics.py**: Contains the `WorkflowMetrics` class for tracking workflow metrics like duration, cost, and token usage.
- **repository.py**: Provides functions for scanning and analyzing repository structures.
- **documentation.py**: Implements functions for generating various types of documentation.
- **workflow.py**: Orchestrates the complete workflow for repository analysis and documentation generation.

## Usage

The modular workflow can be used in various ways:

1. **Complete Workflow**: Use the `DocpilotWorkflow` class to run a complete analysis and documentation workflow.

```python
from workflow.workflow import DocpilotWorkflow

workflow = DocpilotWorkflow(
    repo_path="path/to/repository",
    output_dir="custom/output/path",  # Optional: defaults to workflow_output/job_timestamp_id
    excluded_dirs=[".git", "node_modules"]
)
results = workflow.run()
```

2. **Individual Components**: Use specific modules for targeted tasks.

```python
from workflow.repository import scan_repository, create_directory_tree
from workflow.metrics import WorkflowMetrics

# Create metrics tracker
metrics = WorkflowMetrics("output_dir", "repo_name")

# Scan repository
repo_data = scan_repository("path/to/repo", [".git"], metrics)

# Generate directory tree
tree = create_directory_tree("path/to/repo", max_depth=3)
```

## Output Directory

By default, all workflow outputs are saved in the `workflow_output` directory at the root of the project. Each workflow run creates a new job directory with a timestamp and unique ID to avoid conflicts. You can specify a custom output directory by passing the `output_dir` parameter to the `DocpilotWorkflow` constructor.

## Key Features

- **Metrics Tracking**: Comprehensive tracking of metrics for performance monitoring and cost estimation.
- **Repository Analysis**: Scanning and analyzing repository structures to identify components, frameworks, and documentation needs.
- **Documentation Generation**: Multiple documentation generators for READMEs, API docs, and component documentation.
- **Error Handling**: Robust error handling throughout the workflow to prevent failures.
- **Configurable Workflows**: Customizable workflow options to tailor the process to specific needs.

## Examples

See the `examples` directory for sample outputs from the workflow.

## Extending the Modules

To add new functionality:

1. Add new functions to the appropriate module or create a new module if needed.
2. Update the `DocpilotWorkflow` class if the new functionality should be part of the standard workflow.
3. Add appropriate metrics tracking to monitor performance.
4. Create examples to demonstrate the new functionality.

## Configuration Options

The `DocpilotWorkflow` class accepts a config dictionary with the following options:

- `analyze_repo`: Whether to analyze the repository structure (default: `True`)
- `generate_readme`: Whether to generate a README.md file (default: `True`)
- `find_api_files`: Whether to search for API files (default: `True`)
- `generate_api_docs`: Whether to generate API documentation (default: `True`)
- `find_component_files`: Whether to search for component files (default: `True`)
- `generate_component_docs`: Whether to generate component documentation (default: `True`)
- `max_directory_depth`: Maximum depth for directory tree representation (default: `3`)
- `save_intermediate_results`: Whether to save intermediate processing results (default: `True`)

## Token Cost Tracking

Docpilot includes a robust token usage and cost tracking system that:

1. **Tracks input and output tokens** for each LLM call
2. **Calculates costs** based on model-specific pricing
3. **Generates detailed metrics** for all workflow operations

### How Token Tracking Works

The `ModelTokenCost` class in `metrics.py` handles token tracking with these key features:

- **Model-specific pricing**: Contains up-to-date pricing for OpenAI and Anthropic models
- **Usage extraction**: Automatically extracts token usage from LLM responses
- **Cost calculation**: Accurately calculates costs based on input and output tokens
- **Agent integration**: Works with the `BaseAgent` to extract usage information

### Metrics Files Generated

When running a workflow, the following metrics files are created:

- `metrics_summary.json`: Summary of all metrics including total costs and tokens
- `metrics_log.csv`: Detailed log of all events with token usage and costs
- `detailed_log.txt`: Human-readable log file with detailed workflow information

### Example Usage

To view token cost metrics after running a workflow:

```python
from workflow.metrics import ModelTokenCost

# Calculate cost for a specific model
cost = ModelTokenCost.calculate_cost(
    model_name="gpt-4-turbo",
    input_tokens=1500,
    output_tokens=500
)
print(f"Cost: ${cost:.6f}")

# Or access the metrics summary after a workflow run
with open("workflow_output/job_123/metrics_summary.json", "r") as f:
    metrics = json.load(f)
    print(f"Total cost: ${metrics['total_cost']}")
    print(f"Total tokens: {metrics['total_tokens']}")
```

The example script `examples/complete_workflow_example.py` includes a function `display_token_cost_breakdown()` that demonstrates how to access and display the token usage metrics. 