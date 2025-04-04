#!/usr/bin/env python
"""
Docpilot CLI Entry Point
========================

This is the main entry point for the Docpilot command-line interface.
It provides a command-line tool for generating documentation for software projects
using AI-powered analysis and generation.

Usage:
    docpilot scan <repo_path> [--output-dir=<dir>] [--exclude=<dirs>]
    docpilot analyze <repo_path> [--output-dir=<dir>] [--exclude=<dirs>]
    docpilot docs <repo_path> [--output-dir=<dir>] [--exclude=<dirs>] [--readme] [--api] [--components] [--model=<model>] [--temperature=<temp>]
    docpilot metrics <metrics_file>
"""

# Importing Dependencies
import os
import sys
import json
import logging
import argparse
import traceback
from typing import Dict, Any, Optional, List, Union

# Add parent directory to sys.path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import OrchestratorAgent
from src.agents.orchestrator import OrchestratorAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def setup_argument_parser() -> argparse.ArgumentParser:
    """
    Set up the argument parser for the CLI
    
    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Docpilot - AI-powered documentation generation"
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Scan repository command
    scan_parser = subparsers.add_parser(
        "scan", help="Scan a repository structure"
    )
    scan_parser.add_argument(
        "repo_path", help="Path to the repository to scan"
    )
    scan_parser.add_argument(
        "--output-dir", help="Directory to save output (default: {repo_path}/docpilot_output)"
    )
    scan_parser.add_argument(
        "--exclude", nargs="+", help="Directories to exclude from scanning (space-separated)"
    )
    
    # Analyze repository command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze a repository structure and codebase"
    )
    analyze_parser.add_argument(
        "repo_path", help="Path to the repository to analyze"
    )
    analyze_parser.add_argument(
        "--output-dir", help="Directory to save output (default: {repo_path}/docpilot_output)"
    )
    analyze_parser.add_argument(
        "--exclude", nargs="+", help="Directories to exclude from analysis (space-separated)"
    )
    
    # Generate documentation command
    docs_parser = subparsers.add_parser(
        "docs", help="Generate documentation for a repository"
    )
    docs_parser.add_argument(
        "repo_path", help="Path to the repository to document"
    )
    docs_parser.add_argument(
        "--output-dir", help="Directory to save documentation (default: {repo_path}/docpilot_output)"
    )
    docs_parser.add_argument(
        "--exclude", nargs="+", help="Directories to exclude from documentation (space-separated)"
    )
    docs_parser.add_argument(
        "--readme", action="store_true", help="Generate README documentation only"
    )
    docs_parser.add_argument(
        "--api", action="store_true", help="Generate API documentation only"
    )
    docs_parser.add_argument(
        "--components", action="store_true", help="Generate component documentation only"
    )
    docs_parser.add_argument(
        "--model", help="LLM model to use (default: gpt-4)"
    )
    docs_parser.add_argument(
        "--temperature", type=float, help="Temperature setting for model (default: 0.1)"
    )
    
    # Show metrics command
    metrics_parser = subparsers.add_parser(
        "metrics", help="Show metrics from a previous run"
    )
    metrics_parser.add_argument(
        "metrics_file", help="Path to metrics JSON file"
    )
    
    # Global options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    
    return parser

def scan_repo_handler(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Handle the scan repository command
    
    Args:
        args: Command-line arguments
    
    Returns:
        Dictionary with results
    """
    # Create orchestrator agent
    agent = OrchestratorAgent()
    
    # Execute scan command
    return agent.scan_repository(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        excluded_dirs=args.exclude or None
    )

def analyze_repo_handler(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Handle the analyze repository command
    
    Args:
        args: Command-line arguments
    
    Returns:
        Dictionary with results
    """
    # Create orchestrator agent
    agent = OrchestratorAgent()
    
    # Scan repository first
    scan_result = agent.scan_repository(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        excluded_dirs=args.exclude or None
    )
    
    if not scan_result.get("success", False):
        return scan_result
    
    # Then analyze repository
    return agent.analyze_repository()

def generate_docs_handler(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Handle the generate documentation command
    
    Args:
        args: Command-line arguments
    
    Returns:
        Dictionary with results
    """
    # Create orchestrator agent with model config if specified
    config = {}
    if args.model:
        config["model"] = args.model
    if args.temperature is not None:
        config["temperature"] = args.temperature
        
    agent = OrchestratorAgent(config=config)
    
    # Configure which docs to generate
    docs_to_generate = []
    if args.readme:
        docs_to_generate.append("readme")
    if args.api:
        docs_to_generate.append("api")
    if args.components:
        docs_to_generate.append("component")
    
    # If none specified, generate all
    if not docs_to_generate:
        docs_to_generate = ["readme", "api", "component"]
    
    # Run complete workflow
    return agent.run_workflow(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        excluded_dirs=args.exclude or None,
        docs_to_generate=docs_to_generate
    )

def show_metrics_handler(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Handle the show metrics command
    
    Args:
        args: Command-line arguments
    
    Returns:
        Dictionary with results
    """
    try:
        # Load metrics file
        with open(args.metrics_file, 'r') as f:
            metrics = json.load(f)
        
        # Display metrics
        print("\nDocpilot Workflow Metrics")
        print("========================")
        print(f"Repository: {metrics.get('repo_name', 'Unknown')}")
        print(f"Total Duration: {metrics.get('total_duration', 0):.2f} seconds")
        print(f"Total Tokens: {metrics.get('total_tokens', 0)}")
        print(f"Total Cost: ${metrics.get('total_cost', 0):.6f}")
        
        # Display workflow steps
        print("\nWorkflow Steps:")
        for step_name, step_data in metrics.get("workflows", {}).items():
            print(f"- {step_name}: {step_data.get('duration', 0):.2f}s, " +
                  f"{step_data.get('tokens', 0)} tokens, " +
                  f"${step_data.get('cost', 0):.6f}")
        
        return {"success": True}
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read metrics file: {str(e)}"
        }

def main() -> int:
    """
    Main entry point for the Docpilot CLI
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Setup argument parser
    parser = setup_argument_parser()
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if command is specified
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Handle commands
        if args.command == "scan":
            result = scan_repo_handler(args)
        elif args.command == "analyze":
            result = analyze_repo_handler(args)
        elif args.command == "docs":
            result = generate_docs_handler(args)
        elif args.command == "metrics":
            result = show_metrics_handler(args)
        else:
            parser.print_help()
            return 1
        
        # Check result
        if not result.get("success", False):
            error_message = result.get("error", "Unknown error")
            logger.error(f"Command failed: {error_message}")
            print(f"\nError: {error_message}")
            return 1
        
        # Success
        return 0
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"\nAn unexpected error occurred: {str(e)}")
        
        # Show debugging info in verbose mode
        if "--verbose" in sys.argv or "-v" in sys.argv:
            print("\nStack trace:")
            traceback.print_exc()
        else:
            print("Run with --verbose for more details.")
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 