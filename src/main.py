#!/usr/bin/env python3
"""
Docpilot Main Module
===================

This is the main entry point for the Docpilot application.
It provides a CLI interface and initializes the core components.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from .utils import logger
from .tools import (
    extract_code_structure,
    analyze_docstring_quality,
    extract_api_documentation,
    generate_api_markdown,
    scan_repository,
    find_documentation_issues
)
from .workflows import (
    generate_api_docs_for_repo,
    analyze_repository_documentation,
    generate_complete_documentation
)

def setup_logging(verbose: bool = False) -> None:
    """
    Set up logging configuration.
    
    Args:
        verbose: Whether to enable verbose logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)
    
    # Add console handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Docpilot - AI-powered code documentation toolkit")
    
    # Common arguments
    parser.add_argument('--verbose', '-v', action='store_true', help="Enable verbose output")
    parser.add_argument('--output-dir', '-o', type=str, default="docpilot_output", help="Output directory for generated files")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze code and documentation')
    analyze_parser.add_argument('path', type=str, help="Path to file or directory to analyze")
    analyze_parser.add_argument('--type', '-t', choices=['code', 'docs', 'api', 'repo'], default='repo',
                               help="Type of analysis to perform")
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate documentation')
    generate_parser.add_argument('path', type=str, help="Path to file or directory")
    generate_parser.add_argument('--type', '-t', choices=['api', 'full'], default='full',
                                help="Type of documentation to generate")
    
    # Structure command
    structure_parser = subparsers.add_parser('structure', help='Extract code structure')
    structure_parser.add_argument('path', type=str, help="Path to file to extract structure from")
    structure_parser.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                                 help="Output format")

    return parser.parse_args()

def handle_analyze_command(args: argparse.Namespace) -> int:
    """
    Handle the analyze command.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    path = os.path.abspath(args.path)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(path):
        logger.error(f"Path does not exist: {path}")
        return 1
    
    if args.type == 'code':
        if os.path.isfile(path):
            result = extract_code_structure(path)
            if "error" in result:
                logger.error(f"Error analyzing code: {result['error']}")
                return 1
                
            logger.info(f"Analyzed file: {path}")
            logger.info(f"Found {len(result['functions'])} functions and {len(result['classes'])} classes")
            return 0
        else:
            logger.error("Code analysis requires a file path")
            return 1
            
    elif args.type == 'docs':
        if os.path.isfile(path):
            result = analyze_docstring_quality(path)
            if "error" in result:
                logger.error(f"Error analyzing docstrings: {result['error']}")
                return 1
                
            logger.info(f"Documentation coverage: {result['coverage_percent']}%")
            logger.info(f"Documentation quality score: {result['quality_score']}/100")
            return 0
        else:
            # Analyze repository documentation
            output_file = os.path.join(output_dir, "documentation_analysis.md")
            result = analyze_repository_documentation(path, output_file)
            
            if "error" in result:
                logger.error(f"Error analyzing repository documentation: {result['error']}")
                return 1
                
            logger.info(f"Documentation analysis saved to {output_file}")
            if "documentation_score" in result:
                logger.info(f"Documentation score: {result['documentation_score']}/100")
            return 0
            
    elif args.type == 'api':
        if os.path.isfile(path):
            result = extract_api_documentation(path)
            if "error" in result:
                logger.error(f"Error analyzing API: {result['error']}")
                return 1
                
            logger.info(f"Found {len(result['routes'])} API routes")
            
            # Generate Markdown
            markdown_result = generate_api_markdown(path)
            if "error" not in markdown_result:
                output_file = os.path.join(output_dir, f"{os.path.basename(path)}_api.md")
                with open(output_file, 'w') as f:
                    f.write(markdown_result["markdown"])
                logger.info(f"API documentation saved to {output_file}")
            
            return 0
        else:
            # Generate API docs for repository
            api_output_dir = os.path.join(output_dir, "api")
            os.makedirs(api_output_dir, exist_ok=True)
            
            result = generate_api_docs_for_repo(path, api_output_dir)
            if "error" in result:
                logger.error(f"Error generating API docs: {result['error']}")
                return 1
                
            if "warning" in result:
                logger.warning(result["warning"])
                
            if result.get("api_routes_found", 0) > 0:
                logger.info(f"Generated documentation for {result['api_routes_found']} API routes")
                logger.info(f"API documentation saved to {api_output_dir}")
            else:
                logger.info("No API routes found in the repository")
                
            return 0
            
    elif args.type == 'repo':
        if not os.path.isdir(path):
            logger.error("Repository analysis requires a directory path")
            return 1
            
        result = scan_repository(path)
        if "error" in result:
            logger.error(f"Error scanning repository: {result['error']}")
            return 1
            
        logger.info(f"Repository contains {result['file_count']} files")
        
        # Show language breakdown
        logger.info("Language breakdown:")
        for lang, stats in result["language_stats"].items():
            if stats["percentage"] > 1:  # Only show languages with >1% representation
                logger.info(f"  {lang}: {stats['percentage']}% ({stats['files']} files)")
                
        # Find documentation issues
        issues = find_documentation_issues(path)
        if "error" not in issues:
            if "summary" in issues:
                summary = issues["summary"]
                logger.info(f"Documentation coverage: {summary.get('documentation_coverage', 0)}%")
                logger.info(f"Undocumented functions: {summary.get('undocumented_functions', 0)}/{summary.get('total_functions', 0)}")
                logger.info(f"Undocumented classes: {summary.get('undocumented_classes', 0)}/{summary.get('total_classes', 0)}")
                logger.info(f"Undocumented methods: {summary.get('undocumented_methods', 0)}/{summary.get('total_methods', 0)}")
        
        return 0
    
    return 1

def handle_generate_command(args: argparse.Namespace) -> int:
    """
    Handle the generate command.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    path = os.path.abspath(args.path)
    output_dir = os.path.abspath(args.output_dir)
    
    if not os.path.exists(path):
        logger.error(f"Path does not exist: {path}")
        return 1
    
    if args.type == 'api':
        if os.path.isfile(path):
            # Generate API docs for a single file
            result = generate_api_markdown(path)
            if "error" in result:
                logger.error(f"Error generating API docs: {result['error']}")
                return 1
                
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{os.path.basename(path)}_api.md")
            
            with open(output_file, 'w') as f:
                f.write(result["markdown"])
                
            logger.info(f"API documentation saved to {output_file}")
            return 0
        else:
            # Generate API docs for repository
            api_output_dir = os.path.join(output_dir, "api")
            os.makedirs(api_output_dir, exist_ok=True)
            
            result = generate_api_docs_for_repo(path, api_output_dir)
            if "error" in result:
                logger.error(f"Error generating API docs: {result['error']}")
                return 1
                
            if "warning" in result:
                logger.warning(result["warning"])
                
            if result.get("api_docs_generated", 0) > 0:
                logger.info(f"Generated documentation for {result['api_routes_found']} API routes in {result['api_docs_generated']} files")
                logger.info(f"API documentation saved to {api_output_dir}")
                
                if "summary_file" in result:
                    logger.info(f"Summary available at {result['summary_file']}")
            else:
                logger.info("No API routes found in the repository")
                
            return 0
            
    elif args.type == 'full':
        if not os.path.isdir(path):
            logger.error("Full documentation generation requires a directory path")
            return 1
            
        result = generate_complete_documentation(path, output_dir)
        if "error" in result:
            logger.error(f"Error generating documentation: {result['error']}")
            return 1
            
        logger.info(f"Documentation generated in {output_dir}")
        logger.info(f"  - Overview: {os.path.relpath(result['overview']['file'], os.getcwd())}")
        logger.info(f"  - Documentation Analysis: {os.path.relpath(result['analysis_report']['report_file'], os.getcwd()) if 'report_file' in result['analysis_report'] else 'N/A'}")
        
        # Check if API docs were generated
        api_docs = result.get("api_docs", {})
        if api_docs and api_docs.get("api_routes_found", 0) > 0:
            logger.info(f"  - API Documentation: {api_docs.get('api_routes_found', 0)} routes documented")
            
        return 0
    
    return 1

def handle_structure_command(args: argparse.Namespace) -> int:
    """
    Handle the structure command.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    path = os.path.abspath(args.path)
    
    if not os.path.isfile(path):
        logger.error(f"Path must be a file: {path}")
        return 1
    
    result = extract_code_structure(path)
    if "error" in result:
        logger.error(f"Error extracting code structure: {result['error']}")
        return 1
    
    if args.format == 'json':
        import json
        print(json.dumps(result, indent=2))
    else:
        # Print as formatted text
        print(f"File: {result['file_path']}")
        print(f"Language: {result['language']}")
        
        if result.get("docstring"):
            print(f"\nModule Docstring:")
            print(f"  {result['docstring'].split('. ')[0]}...")
        
        print(f"\nFunctions ({len(result['functions'])}):")
        for func in result['functions']:
            print(f"  - {func['name']}({func['params']})")
            if func.get("docstring"):
                first_line = func["docstring"].split("\n")[0].strip()
                print(f"    {first_line}")
        
        print(f"\nClasses ({len(result['classes'])}):")
        for cls in result['classes']:
            print(f"  - {cls['name']}")
            if cls.get("docstring"):
                first_line = cls["docstring"].split("\n")[0].strip()
                print(f"    {first_line}")
            
            if cls.get("methods"):
                print(f"    Methods ({len(cls['methods'])}):")
                for method in cls['methods']:
                    print(f"      - {method['name']}({method['params']})")
    
    return 0

def main() -> int:
    """
    Main entry point for the Docpilot application.
    
    Returns:
        Exit code
    """
    args = parse_args()
    setup_logging(args.verbose)
    
    try:
        if args.command == 'analyze':
            return handle_analyze_command(args)
        elif args.command == 'generate':
            return handle_generate_command(args)
        elif args.command == 'structure':
            return handle_structure_command(args)
        else:
            # No command specified, show help
            print("Please specify a command. Use --help for more information.")
            return 1
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 