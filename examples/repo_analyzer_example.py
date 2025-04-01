"""
Repository Analysis and Documentation Example
============================================

This example demonstrates how to analyze a repository structure and generate documentation
using DocPilot's agents.
"""
# Importing Dependencies
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.utils.repo_scanner import RepoScanner
from src.agents import (
    AgentConfig,
    RepoAnalyzer,
    RepoStructureInput,
    ReadmeGenerator,
    ReadmeInput
)

def analyze_repository(repo_path: str):
    """Analyze a repository and generate documentation"""
    print(f"Analyzing repository at: {repo_path}")
    
    # Configure agents
    agent_config = AgentConfig()
    
    # Initialize repository scanner
    scanner = RepoScanner(repo_path)
    
    # Scan the repository
    print("Scanning repository files...")
    files = scanner.scan_files()
    print(f"Found {len(files)} files")
    
    # Analyze file extensions
    extension_breakdown = scanner.get_file_extension_breakdown(files)
    print("\nFile Extension Breakdown:")
    for ext, count in sorted(extension_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {ext}: {count}")
    
    # Detect frameworks
    print("\nDetecting frameworks...")
    frameworks = scanner.detect_framework_patterns(files)
    if frameworks:
        print("Detected frameworks:", ", ".join(frameworks))
    else:
        print("No frameworks detected")
    
    # Identify documentation files
    doc_files = scanner.identify_documentation_files(files)
    print(f"\nFound {len(doc_files)} documentation files:")
    for doc_file in doc_files[:5]:  # Show first 5
        print(f"  {doc_file}")
    if len(doc_files) > 5:
        print(f"  ... and {len(doc_files) - 5} more")
    
    # Identify entry points
    entry_points = scanner.identify_entry_points(files)
    print(f"\nFound {len(entry_points)} potential entry points:")
    for entry_point in entry_points:
        print(f"  {entry_point}")
    
    # Initialize repository analyzer agent
    repo_analyzer = RepoAnalyzer(config=agent_config)
    
    # Perform repository structure analysis
    print("\nAnalyzing repository structure...")
    repo_structure = repo_analyzer.analyze_repo_structure(
        RepoStructureInput(
            repo_path=repo_path,
            files=files
        )
    )
    
    # Print analysis results
    print("\nRepository Analysis Results:")
    print(f"Summary: {repo_structure.summary}")
    print(f"Technologies: {', '.join(repo_structure.technologies)}")
    if repo_structure.architecture_pattern:
        print(f"Architecture Pattern: {repo_structure.architecture_pattern}")
    
    print("\nComponents:")
    for component in repo_structure.components:
        print(f"  {component.name}: {component.description}")
    
    # Generate markdown summary
    print("\nGenerating markdown summary...")
    markdown_summary = repo_analyzer.generate_markdown_summary(repo_structure)
    
    # Save markdown summary to file
    summary_path = os.path.join(repo_path, "examples/output/STRUCTURE.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(markdown_summary.content)
    print(f"Saved repository structure summary to {summary_path}")
    
    # Identify documentation needs
    print("\nIdentifying documentation needs...")
    doc_needs = repo_analyzer.identify_documentation_needs(repo_structure)
    for category, needs in doc_needs.items():
        print(f"\n{category}:")
        for need in needs:
            print(f"  - {need}")
    
    # Generate or update README if needed
    readme_path = os.path.join(repo_path, "examples/output/README.md")
    existing_readme = None
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            existing_readme = f.read()
        print("\nExisting README.md found")
    
    # Initialize README generator
    readme_generator = ReadmeGenerator(config=agent_config)
    
    # Prepare README input
    repo_name = os.path.basename(os.path.abspath(repo_path))
    
    if existing_readme:
        # Update existing README
        print("\nUpdating README.md...")
        readme_result = readme_generator.update_readme(
            ReadmeInput(
                repo_name=repo_name,
                repo_description=repo_structure.summary,
                repo_structure=repo_structure,
                existing_readme=existing_readme
            )
        )
    else:
        # Generate new README
        print("\nGenerating new README.md...")
        readme_result = readme_generator.generate_readme(
            ReadmeInput(
                repo_name=repo_name,
                repo_description=repo_structure.summary,
                repo_structure=repo_structure
            )
        )
    
    # Save README
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_result.markdown)
    print(f"Saved README.md to {readme_path}")

if __name__ == "__main__":
    # If a path is provided as an argument, use it; otherwise use the current directory
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        repo_path = os.getcwd()
    
    analyze_repository(repo_path) 