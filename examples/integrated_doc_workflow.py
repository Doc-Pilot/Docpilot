#!/usr/bin/env python3
"""
Integrated Documentation Workflow Example
=======================================

This example demonstrates a complete workflow that:
1. Analyzes a repository for code structure
2. Identifies documentation that needs updating
3. Suggests updates based on code changes
4. Shows how the three tool modules integrate
"""

# Importing Dependencies
import os
import sys
from pathlib import Path
from pprint import pprint

# Add the project root to the path to make imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the tools we need
from src.tools.doc_tools import scan_docs, find_docs_to_update, get_doc_update_suggestions
from src.tools.code_tools import get_code_structure
from src.tools.repo_tools import scan_repository, identify_api_components

def print_section(title):
    """Print a section header for better readability"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def format_output(data):
    """Format a dictionary output for display"""
    if isinstance(data, dict) and data.get("success") is False:
        print(f"❌ Error: {data.get('error', 'Unknown error')}")
        return
        
    if isinstance(data, dict):
        # Remove or truncate large nested data to keep output manageable
        clean_data = data.copy()
        for key in data:
            if isinstance(data[key], list) and len(data[key]) > 5:
                clean_data[key] = f"{data[key][:5]} + {len(data[key])-5} more items..."
        
        # Use pprint for nice formatting
        pprint(clean_data)
    else:
        print(data)

def main():
    # Configure the repository to analyze
    # By default, use the Docpilot repo itself
    repo_path = str(project_root)
    
    print_section("1. Repository Analysis")
    
    # First, scan the repository to get an overview
    print("Scanning repository...")
    repo_info = scan_repository(
        repo_path=repo_path,
        use_gitignore=True
    )
    print("Repository scan complete")
    print(f"Files found: {repo_info.get('file_count', 0)}")
    
    # Identify API components that may need documentation
    print("\nIdentifying API components...")
    api_info = identify_api_components(repo_path)
    
    if api_info.get("success"):
        print(f"Found {api_info.get('metrics', {}).get('total_api_files', 0)} API-related files")
        
        # Print API directories
        api_dirs = api_info.get("api_components", {}).get("api_directories", [])
        if api_dirs:
            print("\nAPI Directories:")
            for directory in api_dirs[:3]:  # Show a few examples
                print(f"  - {directory}")
            if len(api_dirs) > 3:
                print(f"  - ...and {len(api_dirs) - 3} more")
    
    print_section("2. Documentation Analysis")
    
    # Scan for existing documentation
    print("Scanning for documentation files...")
    doc_scan = scan_docs(repo_path)
    
    if doc_scan.get("success"):
        doc_files = doc_scan.get("doc_files", [])
        print(f"Found {len(doc_files)} documentation files")
        
        # Print a few documentation files
        if doc_files:
            print("\nDocumentation files:")
            for doc in doc_files[:3]:  # Show a few examples
                print(f"  - {doc.get('path')} ({doc.get('type')})")
            if len(doc_files) > 3:
                print(f"  - ...and {len(doc_files) - 3} more")
    
    # Find documentation that needs updating
    print("\nFinding documentation that needs updating...")
    docs_to_update = find_docs_to_update(
        repo_path=repo_path,
        base_ref="HEAD~5",  # Look at changes in last 5 commits
        target_ref="HEAD"
    )
    
    # If we found documentation to update
    update_candidates = []
    if docs_to_update.get("success"):
        update_candidates = docs_to_update.get("docs_to_update", [])
        print(f"Found {len(update_candidates)} documentation files that need updating")
        
        # Show what files changed
        changed_files = docs_to_update.get("changed_files", [])
        if changed_files:
            print("\nRecent code changes:")
            for file in changed_files[:5]:  # Show a few examples
                print(f"  - {file}")
            if len(changed_files) > 5:
                print(f"  - ...and {len(changed_files) - 5} more")
    
    print_section("3. Code Structure Analysis")
    
    # Select a Python file to analyze (either a changed file or a key file)
    target_file = None
    if changed_files and any(f.endswith('.py') for f in changed_files):
        target_file = next(f for f in changed_files if f.endswith('.py'))
    else:
        # Fall back to a known Python file in the project
        target_file = "src/utils/code_parser.py"
    
    target_path = os.path.join(repo_path, target_file)
    if os.path.exists(target_path):
        print(f"Analyzing code structure of: {target_file}")
        
        # Get the code structure
        code_structure = get_code_structure(target_path)
        
        if code_structure.get("success"):
            print(f"Language: {code_structure.get('language', 'unknown')}")
            
            # Show functions
            functions = code_structure.get("functions", [])
            print(f"\nFunctions ({len(functions)}):")
            for func in functions[:3]:  # Show a few examples
                print(f"  - {func.get('name')}")
                if func.get('docstring'):
                    doc_summary = func.get('docstring').split('\n')[0]
                    print(f"    {doc_summary}")
            if len(functions) > 3:
                print(f"  - ...and {len(functions) - 3} more")
            
            # Show classes
            classes = code_structure.get("classes", [])
            print(f"\nClasses ({len(classes)}):")
            for cls in classes[:2]:  # Show a few examples
                print(f"  - {cls.get('name')}")
                # Show methods
                methods = cls.get("methods", [])
                if methods:
                    for method in methods[:2]:
                        print(f"    └─ {method.get('name')}")
                    if len(methods) > 2:
                        print(f"    └─ ...and {len(methods) - 2} more methods")
            if len(classes) > 2:
                print(f"  - ...and {len(classes) - 2} more classes")
    
    print_section("4. Documentation Update Suggestions")
    
    # If we found docs to update, generate update suggestions for one of them
    if update_candidates:
        doc_to_update = update_candidates[0]
        doc_path = doc_to_update.get("path")
        related_files = doc_to_update.get("related_files", [])
        
        print(f"Generating update suggestions for: {doc_path}")
        print(f"Related files: {', '.join(related_files[:3])}")
        if len(related_files) > 3:
            print(f"  ...and {len(related_files) - 3} more")
        
        # Get update suggestions
        suggestions = get_doc_update_suggestions(
            repo_path=repo_path,
            doc_path=doc_path,
            related_files=related_files
        )
        
        if suggestions.get("success"):
            update_needed = suggestions.get("update_needed", False)
            print(f"\nUpdate needed: {'Yes' if update_needed else 'No'}")
            
            if update_needed:
                print("\nSuggestions:")
                for suggestion in suggestions.get("suggestions", []):
                    print(f"  - {suggestion.get('suggestion')}")
                
                if suggestions.get("has_significant_changes"):
                    print("\nSignificant changes detected:")
                    for detail in suggestions.get("change_details", [])[:3]:
                        print(f"  - In {detail.get('file')}: {detail.get('type')} '{detail.get('name')}'")
    
    print_section("Summary")
    print("This example demonstrated a complete documentation workflow:")
    print("1. Repository analysis identified API components and structure")
    print("2. Documentation scanning found existing docs and update candidates")
    print("3. Code structure analysis provided detailed function/class information")
    print("4. Document update suggestions were generated based on code changes")
    print("\nThis integrated workflow shows how the three tool modules work together")
    print("to maintain documentation aligned with code.")

if __name__ == "__main__":
    main() 