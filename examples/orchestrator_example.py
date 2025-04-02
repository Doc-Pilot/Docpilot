#!/usr/bin/env python3
"""
Orchestrator Agent Example
=========================

This example demonstrates how to use the OrchestratorAgent to run
the complete documentation generation workflow using a single agent
rather than the modular workflow system.
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the orchestrator agent
from src.agents import AgentConfig, OrchestratorAgent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_orchestrator(repo_path, output_dir, exclude=None, model=None, temperature=None):
    """
    Run the orchestrator agent on a repository
    
    Args:
        repo_path: Path to the repository
        output_dir: Directory to save the output
        exclude: Comma-separated list of directories to exclude
        model: Optional model name to use
        temperature: Optional temperature setting
        
    Returns:
        Dictionary with workflow results
    """
    start_time = time.time()
    
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Parse excluded directories
    excluded_dirs = exclude.split(",") if exclude else None
    
    # Set up custom model configuration if provided
    model_params = {}
    if model:
        model_params["model_name"] = model
    if temperature is not None:
        model_params["temperature"] = float(temperature)
    
    # Create agent configuration if needed
    agent_config = AgentConfig(**model_params) if model_params else None
    
    # Initialize the orchestrator agent
    orchestrator = OrchestratorAgent(config=agent_config, excluded_dirs=excluded_dirs)
    
    logger.info(f"Starting documentation generation for {repo_path}")
    
    # Run the orchestrator
    result = orchestrator.run(
        repo_path=repo_path,
        output_dir=output_dir,
        options={
            "generate_readme": True,
            "generate_api_docs": True,
            "generate_component_docs": True,
            "save_intermediate_results": True
        }
    )
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Display results
    if result["success"]:
        logger.info(f"Documentation generation completed successfully in {total_time:.2f} seconds")
        logger.info(f"Output saved to {output_dir}")
        
        # Display metrics summary
        metrics = result["metrics"]
        logger.info(f"Total token usage: {metrics['token_usage']['total']} tokens")
        logger.info(f"Total cost: {metrics['cost_summary']['total']}")
        
        # Write summary to file
        summary_file = os.path.join(output_dir, "orchestrator_summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        return result
    else:
        logger.error(f"Documentation generation failed: {result.get('error', 'Unknown error')}")
        return result

def display_metrics(metrics):
    """
    Display detailed metrics from the orchestrator
    
    Args:
        metrics: Metrics dictionary from the orchestrator
    """
    print("\n---- ORCHESTRATOR METRICS SUMMARY ----")
    print(f"Total execution time: {metrics['duration']:.2f} seconds ({metrics.get('total_time_minutes', 0):.2f} minutes)")
    print(f"Total tokens used: {metrics['token_usage']['total']} tokens")
    print(f"Total cost: {metrics['cost_summary']['total']}")
    
    print("\nCost by operation:")
    for op, cost in metrics['cost_summary']['by_operation'].items():
        print(f"  - {op}: {cost}")
    
    print("\nCost by agent:")
    for agent, cost in metrics['cost_summary']['by_agent'].items():
        print(f"  - {agent}: {cost}")
    
    print("\nToken usage by agent:")
    for agent, tokens in metrics['token_usage']['by_agent'].items():
        print(f"  - {agent}: {tokens} tokens")
    
    print("\nOperations:")
    for op in metrics['operations']:
        print(f"  - {op['name']} ({op['duration']:.2f}s): {op.get('agent', 'N/A')}")
        if op.get('usage'):
            print(f"    Tokens: {op['usage'].get('total_tokens', 0)}")

def main():
    """Main entry point for the orchestrator example script"""
    parser = argparse.ArgumentParser(description="Run Docpilot's OrchestratorAgent on a repository")
    
    parser.add_argument(
        "--repo-path", "-r",
        required=True,
        help="Path to the repository to analyze"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        default="orchestrator_output",
        help="Directory to save generated documentation (default: orchestrator_output)"
    )
    
    parser.add_argument(
        "--exclude", "-e",
        default=None,
        help="Comma-separated list of directories to exclude"
    )
    
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model to use for generation (default: from environment or AgentConfig default)"
    )
    
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=None,
        help="Temperature setting for model (default: from AgentConfig)"
    )
    
    args = parser.parse_args()
    
    # Run the orchestrator
    result = run_orchestrator(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        exclude=args.exclude,
        model=args.model,
        temperature=args.temperature
    )
    
    # Display detailed metrics
    if result["success"] and result.get("metrics"):
        display_metrics(result["metrics"])

if __name__ == "__main__":
    main() 