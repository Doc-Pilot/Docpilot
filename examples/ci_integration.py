#!/usr/bin/env python3
"""
CI/CD Integration Example
=======================

A practical example showing how to integrate Docpilot with CI/CD pipelines
to automatically update documentation when code changes.

This script:
1. Detects code changes in a recent commit
2. Identifies documentation that needs updating
3. Automatically generates update PRs or reports

Designed to be run in CI environments like GitHub Actions, GitLab CI, or Jenkins.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add the project root to the path to make imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the tools we need
from src.tools.doc_tools import scan_docs, find_docs_to_update, get_doc_update_suggestions
from src.tools.code_tools import get_code_structure
from src.tools.repo_tools import identify_api_components

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Docpilot CI Integration")
    parser.add_argument("--repo-path", type=str, default=".",
                        help="Path to the repository (default: current directory)")
    parser.add_argument("--base-ref", type=str, default="HEAD~1",
                        help="Base git reference (default: HEAD~1)")
    parser.add_argument("--target-ref", type=str, default="HEAD",
                        help="Target git reference (default: HEAD)")
    parser.add_argument("--output", type=str, default="docpilot-report.md",
                        help="Output file for the report (default: docpilot-report.md)")
    parser.add_argument("--update-threshold", type=int, default=2,
                        help="Minimum number of changes to trigger doc updates (default: 2)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    return parser.parse_args()

def log(message, verbose_only=False, args=None):
    """Log a message to the console."""
    if verbose_only and not args.verbose:
        return
    print(message)

def write_markdown_report(output_file, docs_to_update, changed_files, suggestions):
    """Write a Markdown report of documentation that needs updating."""
    with open(output_file, "w") as f:
        f.write(f"# Docpilot Documentation Update Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- {len(changed_files)} files changed\n")
        f.write(f"- {len(docs_to_update)} documentation files need updating\n\n")
        
        f.write("## Changed Files\n\n")
        for file in changed_files[:10]:
            f.write(f"- `{file}`\n")
        if len(changed_files) > 10:
            f.write(f"- ...and {len(changed_files) - 10} more\n")
        f.write("\n")
        
        f.write("## Documentation Updates Needed\n\n")
        for doc in docs_to_update:
            f.write(f"### {doc.get('path')}\n\n")
            f.write(f"**Type:** {doc.get('type', 'Unknown')}\n\n")
            f.write(f"**Related Files:**\n\n")
            
            for rel_file in doc.get('related_files', [])[:5]:
                f.write(f"- `{rel_file}`\n")
            if len(doc.get('related_files', [])) > 5:
                f.write(f"- ...and {len(doc.get('related_files', [])) - 5} more\n")
            
            # Add suggestions if available
            doc_path = doc.get('path')
            if doc_path in suggestions:
                f.write("\n**Suggested Updates:**\n\n")
                
                doc_suggestions = suggestions[doc_path]
                for suggestion in doc_suggestions.get('suggestions', []):
                    f.write(f"- {suggestion.get('suggestion')}\n")
                
                if doc_suggestions.get('has_significant_changes'):
                    f.write("\n**Significant Changes:**\n\n")
                    for change in doc_suggestions.get('change_details', [])[:3]:
                        f.write(f"- In `{change.get('file')}`: {change.get('type')} `{change.get('name')}`\n")
            
            f.write("\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Review the documentation files listed above\n")
        f.write("2. Update documentation to reflect code changes\n")
        f.write("3. Consider automating documentation updates with Docpilot\n")

def get_doc_suggestions_batched(repo_path, docs_to_update):
    """Get update suggestions for a batch of documents."""
    suggestions = {}
    for doc in docs_to_update:
        doc_path = doc.get('path')
        related_files = doc.get('related_files', [])
        
        if not doc_path or not related_files:
            continue
            
        result = get_doc_update_suggestions(
            repo_path=repo_path,
            doc_path=doc_path,
            related_files=related_files
        )
        
        if result.get('success'):
            suggestions[doc_path] = result
    
    return suggestions

def main():
    args = parse_args()
    repo_path = os.path.abspath(args.repo_path)
    
    log(f"Docpilot CI Integration", verbose_only=False, args=args)
    log(f"Repository: {repo_path}", verbose_only=False, args=args)
    log(f"Comparing: {args.base_ref} → {args.target_ref}", verbose_only=False, args=args)
    
    # Step 1: Find docs that need updating based on recent changes
    log("Finding documentation that needs updating...", verbose_only=False, args=args)
    docs_result = find_docs_to_update(
        repo_path=repo_path,
        base_ref=args.base_ref,
        target_ref=args.target_ref
    )
    
    if not docs_result.get('success'):
        log(f"Error: {docs_result.get('error', 'Failed to find docs to update')}", verbose_only=False, args=args)
        sys.exit(1)
    
    docs_to_update = docs_result.get('docs_to_update', [])
    changed_files = docs_result.get('changed_files', [])
    
    log(f"Found {len(changed_files)} changed files", verbose_only=False, args=args)
    log(f"Found {len(docs_to_update)} documentation files that need updating", verbose_only=False, args=args)
    
    if not docs_to_update:
        log("No documentation needs updating. Exiting.", verbose_only=False, args=args)
        sys.exit(0)
    
    # Step 2: Generate update suggestions for each document
    log("Generating update suggestions...", verbose_only=False, args=args)
    suggestions = get_doc_suggestions_batched(repo_path, docs_to_update)
    
    log(f"Generated suggestions for {len(suggestions)} documentation files", verbose_only=False, args=args)
    
    # Step 3: Check if any API files changed
    api_files_changed = False
    api_info = identify_api_components(repo_path)
    
    if api_info.get('success'):
        api_components = api_info.get('api_components', {})
        api_files = []
        
        for category, files in api_components.items():
            api_files.extend(files)
        
        # Check if any API files changed
        api_files_changed = any(changed_file in api_files for changed_file in changed_files)
        
        if api_files_changed:
            log("API files changed - may require API documentation updates", verbose_only=False, args=args)
    
    # Step 4: Write the report
    log(f"Writing report to {args.output}...", verbose_only=False, args=args)
    write_markdown_report(args.output, docs_to_update, changed_files, suggestions)
    
    # Step 5: Set exit code based on significant changes
    significant_changes = 0
    for doc_path, suggestion in suggestions.items():
        if suggestion.get('has_significant_changes'):
            significant_changes += 1
    
    if significant_changes >= args.update_threshold:
        log(f"Found {significant_changes} docs with significant changes (threshold: {args.update_threshold})", 
            verbose_only=False, args=args)
        log("Documentation updates are required! Please review the report.", verbose_only=False, args=args)
        sys.exit(1)  # Non-zero exit to signal CI that action is needed
    else:
        log(f"Found {significant_changes} docs with significant changes (below threshold: {args.update_threshold})", 
            verbose_only=False, args=args)
        log("Documentation updates may be needed. Please review the report.", verbose_only=False, args=args)
        sys.exit(0)  # Zero exit means no critical updates needed

if __name__ == "__main__":
    main() 