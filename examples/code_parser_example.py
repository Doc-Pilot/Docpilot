#!/usr/bin/env python3
"""
Simple Code Parser Example
=========================

A minimal example to test the code parser functionality.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path to make imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Check if tree-sitter is available
try:
    from tree_sitter import Parser, Language
    print("✓ tree-sitter is available")
except ImportError:
    print("✗ Error: tree-sitter is not installed")
    print("  Please install with: pip install tree-sitter==0.21.3 tree-sitter-languages")
    sys.exit(1)

# Import just what we need from code_parser directly
from src.utils.code_parser import parse_file, detect_language

def main():
    # Get path to code_parser.py itself
    target_file = os.path.join(project_root, "src", "utils", "code_parser.py")
    print(f"Target file: {target_file}")
    
    # Make sure the file exists
    if not os.path.exists(target_file):
        print(f"Error: File not found: {target_file}")
        return
    
    # Detect the language
    language = detect_language(target_file)
    print(f"Detected language: {language}")
    
    # Parse the file
    print("Parsing file...")
    module = parse_file(target_file)
    
    # Check if parsing was successful
    if not module:
        print("Error: Failed to parse file")
        return
    
    # Print basic information about what was found
    print(f"\nSuccessfully parsed {module.path}")
    print(f"  Functions: {len(module.functions)}")
    print(f"  Classes: {len(module.classes)}")
    
    # Print function names
    print("\nFunctions:")
    for i, func in enumerate(module.functions, 1):
        print(f"  {i}. {func.name}")
    
    # Print class names
    print("\nClasses:")
    for i, cls in enumerate(module.classes, 1):
        print(f"  {i}. {cls.name} ({len(cls.methods)} methods)")

if __name__ == "__main__":
    main() 