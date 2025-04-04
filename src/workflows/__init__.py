"""
Workflows Module
===============

This module provides high-level workflows that combine multiple core utilities
to accomplish complex documentation tasks. These workflows are designed to be used
directly by applications or by LLM agents.
"""

import os
import json
from typing import Dict, List, Optional, Union, Any
from pathlib import Path

from ..utils import (
    logger,
    parse_file,
    extract_api_routes,
    RepoScanner,
    DocScanner
)

from ..tools import (
    extract_code_structure,
    find_undocumented_elements,
    analyze_docstring_quality,
    extract_api_documentation,
    generate_api_markdown,
    scan_repository,
    find_documentation_issues
)

# ============================================================================
# API Documentation Workflows
# ============================================================================

def generate_api_docs_for_repo(repo_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Generate API documentation for all API files in a repository.
    
    Args:
        repo_path: Path to the repository
        output_dir: Optional directory to save generated documentation files
        
    Returns:
        Dictionary with results of the documentation generation
    """
    logger.info(f"Generating API docs for repository: {repo_path}")
    
    if not os.path.isdir(repo_path):
        return {"error": f"Not a valid directory: {repo_path}"}
    
    try:
        # Scan repository for files
        scanner = RepoScanner(repo_path)
        stats = scanner.scan()
        
        # Create output directory if specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Look for potential API files (FastAPI or Flask)
        api_files = []
        for file in scanner.files:
            if file.language == "python":
                # Quick check for imports rather than parsing each file
                try:
                    with open(file.path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'fastapi' in content.lower() or 'flask' in content.lower():
                            api_files.append(file.path)
                except Exception:
                    continue
        
        if not api_files:
            return {"warning": "No potential API files found in the repository"}
        
        # Process each potential API file
        results = {
            "repo_path": repo_path,
            "api_files_found": len(api_files),
            "api_docs_generated": 0,
            "api_routes_found": 0,
            "files": []
        }
        
        for file_path in api_files:
            # Extract API documentation
            api_doc = extract_api_documentation(file_path)
            
            if "error" in api_doc or not api_doc.get("routes"):
                continue  # Skip files with no API routes
                
            # Generate Markdown
            markdown_doc = generate_api_markdown(file_path)
            if "error" in markdown_doc:
                continue
                
            # Record result
            rel_path = os.path.relpath(file_path, repo_path)
            file_result = {
                "file": rel_path,
                "routes_count": len(api_doc["routes"]),
                "generated": True
            }
            
            results["api_docs_generated"] += 1
            results["api_routes_found"] += len(api_doc["routes"])
            results["files"].append(file_result)
            
            # Save to file if output directory provided
            if output_dir:
                out_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_api.md"
                out_path = os.path.join(output_dir, out_filename)
                
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_doc["markdown"])
                    
                file_result["output_file"] = out_path
        
        # Generate summary markdown if output directory is provided
        if output_dir and results["api_docs_generated"] > 0:
            summary_path = os.path.join(output_dir, "api_summary.md")
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(f"# API Documentation Summary\n\n")
                f.write(f"Repository: `{os.path.basename(repo_path)}`\n\n")
                f.write(f"Total API Files: {results['api_docs_generated']}\n")
                f.write(f"Total Routes: {results['api_routes_found']}\n\n")
                
                f.write("## API Files\n\n")
                for file_info in results["files"]:
                    out_filename = f"{os.path.splitext(os.path.basename(file_info['file']))[0]}_api.md"
                    f.write(f"- [{file_info['file']}](./{out_filename}) - {file_info['routes_count']} routes\n")
            
            results["summary_file"] = summary_path
        
        return results
    except Exception as e:
        return {"error": f"Error generating API documentation: {str(e)}"}

# ============================================================================
# Documentation Analysis Workflows
# ============================================================================

def analyze_repository_documentation(repo_path: str, output_file: str = None) -> Dict[str, Any]:
    """
    Perform a comprehensive analysis of documentation in a repository.
    
    Args:
        repo_path: Path to the repository
        output_file: Optional file path to save the analysis report
        
    Returns:
        Dictionary with documentation analysis results
    """
    logger.info(f"Analyzing documentation in repository: {repo_path}")
    
    if not os.path.isdir(repo_path):
        return {"error": f"Not a valid directory: {repo_path}"}
    
    try:
        # Scan repository to get stats
        repo_info = scan_repository(repo_path)
        if "error" in repo_info:
            return repo_info
            
        # Find documentation issues
        doc_issues = find_documentation_issues(repo_path)
        if "error" in doc_issues:
            return doc_issues
            
        # Combine results
        results = {
            "repo_path": repo_path,
            "repo_stats": {
                "file_count": repo_info["file_count"],
                "language_stats": repo_info["language_stats"]
            },
            "documentation_issues": doc_issues["summary"] if "summary" in doc_issues else {},
            "files_with_issues": doc_issues.get("files_with_issues", []),
            "documentation_score": _calculate_documentation_score(doc_issues)
        }
        
        # Generate markdown report if output file is specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Documentation Analysis: {os.path.basename(repo_path)}\n\n")
                
                # Overall stats
                f.write("## Overall Statistics\n\n")
                f.write(f"- **Total Files:** {repo_info['file_count']}\n")
                f.write(f"- **Documentation Coverage:** {doc_issues['summary'].get('documentation_coverage', 0)}%\n")
                f.write(f"- **Documentation Score:** {results['documentation_score']}/100\n\n")
                
                # Language breakdown
                f.write("## Language Breakdown\n\n")
                f.write("| Language | Files | Lines | Percentage |\n")
                f.write("|----------|-------|-------|------------|\n")
                
                for lang, stats in repo_info["language_stats"].items():
                    f.write(f"| {lang} | {stats['files']} | {stats['lines']} | {stats['percentage']}% |\n")
                
                f.write("\n")
                
                # Documentation issues
                f.write("## Documentation Issues\n\n")
                summary = doc_issues.get("summary", {})
                
                f.write("### Summary\n\n")
                f.write(f"- **Functions:** {summary.get('undocumented_functions', 0)}/{summary.get('total_functions', 0)} undocumented\n")
                f.write(f"- **Classes:** {summary.get('undocumented_classes', 0)}/{summary.get('total_classes', 0)} undocumented\n")
                f.write(f"- **Methods:** {summary.get('undocumented_methods', 0)}/{summary.get('total_methods', 0)} undocumented\n\n")
                
                # Files with issues
                if doc_issues.get("files_with_issues"):
                    f.write("### Files with Missing Documentation\n\n")
                    
                    for file_issue in doc_issues["files_with_issues"][:10]:  # Show top 10 files
                        f.write(f"#### {file_issue['file']}\n\n")
                        
                        if file_issue.get("undocumented_functions"):
                            f.write("**Undocumented Functions:**\n\n")
                            for func in file_issue["undocumented_functions"]:
                                f.write(f"- `{func}`\n")
                            f.write("\n")
                            
                        if file_issue.get("undocumented_classes"):
                            f.write("**Undocumented Classes:**\n\n")
                            for cls in file_issue["undocumented_classes"]:
                                f.write(f"- `{cls}`\n")
                            f.write("\n")
                            
                        if file_issue.get("undocumented_methods"):
                            f.write("**Undocumented Methods:**\n\n")
                            for method in file_issue["undocumented_methods"]:
                                f.write(f"- `{method}`\n")
                            f.write("\n")
                            
                    if len(doc_issues["files_with_issues"]) > 10:
                        f.write(f"\n*...and {len(doc_issues['files_with_issues']) - 10} more files with issues*\n\n")
                
                # Recommendations
                f.write("## Recommendations\n\n")
                f.write("1. **Focus on Core APIs:** Prioritize documenting public APIs and core functionality\n")
                f.write("2. **Document Classes First:** Classes often represent key abstractions in your codebase\n")
                f.write("3. **Add Examples:** Include usage examples in key function docstrings\n")
                f.write("4. **Follow Consistent Style:** Maintain a consistent docstring style (e.g., Google, NumPy, or reStructuredText)\n")
                
            results["report_file"] = output_file
        
        return results
    except Exception as e:
        return {"error": f"Error analyzing repository documentation: {str(e)}"}

def _calculate_documentation_score(doc_issues: Dict[str, Any]) -> float:
    """Calculate a documentation score from 0-100 based on coverage and issue density."""
    if not doc_issues or "summary" not in doc_issues:
        return 0
        
    summary = doc_issues["summary"]
    
    # Base score is the documentation coverage
    base_score = summary.get("documentation_coverage", 0)
    
    # Penalties for undocumented elements:
    # - Higher penalty for undocumented classes (foundational components)
    # - Medium penalty for undocumented functions
    # - Lower penalty for undocumented methods
    
    total_elements = max(1, (
        summary.get("total_functions", 0) + 
        summary.get("total_classes", 0) + 
        summary.get("total_methods", 0)
    ))
    
    penalty = 0
    
    # Calculate weighted penalties
    if summary.get("total_classes", 0) > 0:
        class_weight = 0.4
        class_penalty = (summary.get("undocumented_classes", 0) / summary.get("total_classes", 1)) * class_weight
        penalty += class_penalty
        
    if summary.get("total_functions", 0) > 0:
        func_weight = 0.3
        func_penalty = (summary.get("undocumented_functions", 0) / summary.get("total_functions", 1)) * func_weight
        penalty += func_penalty
        
    if summary.get("total_methods", 0) > 0:
        method_weight = 0.2
        method_penalty = (summary.get("undocumented_methods", 0) / summary.get("total_methods", 1)) * method_weight
        penalty += method_penalty
    
    # Apply penalty as a percentage reduction
    score = base_score * (1 - penalty)
    
    # Bonus for large codebases with good documentation
    if total_elements > 100 and base_score > 70:
        score += 5
        
    # Ensure score is between 0 and 100
    return max(0, min(100, round(score, 1)))

# ============================================================================
# Combined Workflows
# ============================================================================

def generate_complete_documentation(repo_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Generate complete documentation for a repository, including:
    - API documentation
    - Documentation analysis report
    - README/overview documentation
    
    Args:
        repo_path: Path to the repository
        output_dir: Directory to save generated documentation
        
    Returns:
        Dictionary with results of the documentation generation
    """
    logger.info(f"Generating complete documentation for repository: {repo_path}")
    
    if not os.path.isdir(repo_path):
        return {"error": f"Not a valid directory: {repo_path}"}
        
    if not output_dir:
        return {"error": "Output directory must be specified"}
    
    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        results = {
            "repo_path": repo_path,
            "output_dir": output_dir,
            "api_docs": None,
            "analysis_report": None,
            "overview": None
        }
        
        # Generate API documentation
        api_docs_dir = os.path.join(output_dir, "api")
        os.makedirs(api_docs_dir, exist_ok=True)
        
        api_docs = generate_api_docs_for_repo(repo_path, api_docs_dir)
        results["api_docs"] = api_docs
        
        # Generate documentation analysis report
        analysis_file = os.path.join(output_dir, "documentation_analysis.md")
        analysis = analyze_repository_documentation(repo_path, analysis_file)
        results["analysis_report"] = analysis
        
        # Generate repository overview
        overview_file = os.path.join(output_dir, "overview.md")
        
        with open(overview_file, 'w', encoding='utf-8') as f:
            # Basic information
            repo_name = os.path.basename(repo_path)
            f.write(f"# {repo_name} Documentation\n\n")
            
            # Overview section
            f.write("## Overview\n\n")
            f.write("This documentation was automatically generated by Docpilot.\n\n")
            
            # Summary of repository
            repo_info = scan_repository(repo_path)
            if "error" not in repo_info:
                f.write("## Repository Information\n\n")
                f.write(f"- **Total Files:** {repo_info['file_count']}\n")
                f.write("- **Languages:**\n")
                
                for lang, stats in repo_info["language_stats"].items():
                    if stats["percentage"] > 1:  # Only show languages with >1% representation
                        f.write(f"  - {lang}: {stats['percentage']}% ({stats['files']} files)\n")
                
                f.write("\n")
            
            # Documentation coverage
            if "analysis_report" in results and "error" not in results["analysis_report"]:
                doc_score = results["analysis_report"].get("documentation_score", 0)
                f.write("## Documentation Status\n\n")
                f.write(f"- **Documentation Score:** {doc_score}/100\n")
                f.write(f"- **Analysis Report:** [View Documentation Analysis](./documentation_analysis.md)\n\n")
            
            # API documentation 
            if "api_docs" in results and "error" not in results["api_docs"]:
                api_routes = results["api_docs"].get("api_routes_found", 0)
                if api_routes > 0:
                    f.write("## API Documentation\n\n")
                    f.write(f"- **API Routes:** {api_routes}\n")
                    f.write(f"- **API Documentation:** [View API Documentation](./api/api_summary.md)\n\n")
            
            # Table of contents
            f.write("## Contents\n\n")
            f.write("1. [Overview](./overview.md)\n")
            f.write("2. [Documentation Analysis](./documentation_analysis.md)\n")
            
            if "api_docs" in results and "error" not in results["api_docs"]:
                if results["api_docs"].get("api_routes_found", 0) > 0:
                    f.write("3. [API Documentation](./api/api_summary.md)\n")
        
        results["overview"] = {"file": overview_file}
        
        # Create an index file
        index_file = os.path.join(output_dir, "index.md")
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(f"# {repo_name} Documentation\n\n")
            f.write("Welcome to the automatically generated documentation.\n\n")
            f.write("## Quick Links\n\n")
            f.write("- [Repository Overview](./overview.md)\n")
            f.write("- [Documentation Analysis](./documentation_analysis.md)\n")
            
            if "api_docs" in results and "error" not in results["api_docs"]:
                if results["api_docs"].get("api_routes_found", 0) > 0:
                    f.write("- [API Documentation](./api/api_summary.md)\n")
        
        results["index"] = {"file": index_file}
        
        return results
    except Exception as e:
        return {"error": f"Error generating complete documentation: {str(e)}"}

__all__ = [
    # API Documentation
    "generate_api_docs_for_repo",
    
    # Documentation Analysis
    "analyze_repository_documentation",
    
    # Combined Workflows
    "generate_complete_documentation"
] 