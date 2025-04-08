#!/usr/bin/env python3
"""
API Documentation Generator Example
=================================

A practical example showing how to:
1. Identify API components in a repository
2. Analyze their code structure
3. Generate/update API documentation based on code
4. Monitor for future changes
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add the project root to the path to make imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the tools we need
from src.tools.doc_tools import scan_docs, find_docs_to_update
from src.tools.code_tools import get_code_structure, get_function_details, get_class_details
from src.tools.repo_tools import identify_api_components

# Example template for API documentation (Markdown)
API_DOC_TEMPLATE = """# {title}

> Generated by Docpilot on {date}

{description}

## API Reference

{endpoints}

## Data Models

{models}

## Usage Examples

```python
# Example code will be generated based on endpoints
{example}
```
"""

ENDPOINT_TEMPLATE = """
### `{method} {path}`

{description}

**Parameters:**
{parameters}

**Returns:**
{returns}
"""

MODEL_TEMPLATE = """
### {name}

{description}

**Fields:**
{fields}
"""

def main():
    # Configure the repository to analyze
    repo_path = str(project_root)
    output_dir = os.path.join(repo_path, "docs", "api")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 80)
    print("API Documentation Generator".center(80))
    print("=" * 80)
    
    # Step 1: Identify API components in the repository
    print("\n1. Identifying API components...")
    api_info = identify_api_components(repo_path)
    
    if not api_info.get("success"):
        print(f"Error: {api_info.get('message', 'Failed to identify API components')}")
        return
    
    # Extract API-related files by category
    api_components = api_info.get("api_components", {})
    routers = api_components.get("routers", [])
    handlers = api_components.get("handlers", [])
    schemas = api_components.get("schemas", [])
    entry_points = api_components.get("entry_points", [])
    
    print(f"Found {len(routers)} router files, {len(handlers)} handler files, {len(schemas)} schema files")
    
    # If no API files found, use a sample file to demonstrate functionality
    if not routers and not handlers:
        print("No API files found. Using a sample file for demonstration...")
        # Use code_tools.py as a sample "API" file for demonstration
        sample_file = os.path.join(repo_path, "src", "tools", "code_tools.py")
        routers = [os.path.relpath(sample_file, repo_path)]
    
    # Step 2: Analyze the code structure of API files
    print("\n2. Analyzing code structure of API files...")
    
    # Process router files to extract endpoints
    endpoints = []
    for router_file in routers:
        file_path = os.path.join(repo_path, router_file)
        print(f"  Analyzing {router_file}...")
        
        # Get the code structure
        code_info = get_code_structure(file_path)
        
        if not code_info.get("success"):
            print(f"  Failed to analyze {router_file}: {code_info.get('error')}")
            continue
        
        # Extract functions (potential API endpoints)
        functions = code_info.get("functions", [])
        for func in functions:
            function_name = func.get("name")
            # Get detailed function information
            func_details = get_function_details(file_path, function_name)
            
            if func_details.get("success"):
                # For demonstration, treat each function as an API endpoint
                endpoint = {
                    "name": function_name,
                    "method": "GET",  # Default method for demo
                    "path": f"/api/{function_name.replace('_', '/')}",  # Example path
                    "description": func_details.get("docstring", ""),
                    "parameters": func_details.get("params", []),
                    "returns": "JSON response",
                    "file": router_file,
                    "line_range": (func_details.get("start_line"), func_details.get("end_line"))
                }
                
                # Look for API method indicators in the function body
                body = func_details.get("body", "")
                if "post" in body.lower():
                    endpoint["method"] = "POST"
                elif "put" in body.lower():
                    endpoint["method"] = "PUT"
                elif "delete" in body.lower():
                    endpoint["method"] = "DELETE"
                
                endpoints.append(endpoint)
    
    # Process schema files to extract data models
    models = []
    for schema_file in schemas:
        file_path = os.path.join(repo_path, schema_file)
        print(f"  Analyzing {schema_file}...")
        
        # Get the code structure
        code_info = get_code_structure(file_path)
        
        if not code_info.get("success"):
            print(f"  Failed to analyze {schema_file}: {code_info.get('error')}")
            continue
        
        # Extract classes (potential data models)
        classes = code_info.get("classes", [])
        for cls in classes:
            class_name = cls.get("name")
            # Get detailed class information
            cls_details = get_class_details(file_path, class_name)
            
            if cls_details.get("success"):
                model = {
                    "name": class_name,
                    "description": cls_details.get("docstring", ""),
                    "fields": [],
                    "file": schema_file,
                    "line_range": (cls_details.get("start_line"), cls_details.get("end_line"))
                }
                
                # Extract fields from class methods
                for method in cls_details.get("methods", []):
                    if method.get("name") == "__init__":
                        # Extract parameters from init as fields
                        params = method.get("params", [])
                        for param in params:
                            if param != "self":
                                model["fields"].append(param)
                
                models.append(model)
    
    # Step 3: Generate API documentation
    print(f"\n3. Generating API documentation for {len(endpoints)} endpoints and {len(models)} models...")
    
    # Format endpoints for documentation
    endpoints_md = ""
    for endpoint in endpoints:
        # Format parameters
        params_md = ""
        for param in endpoint.get("parameters", []):
            params_md += f"- `{param}`\n"
        if not params_md:
            params_md = "None\n"
        
        # Format endpoint documentation
        endpoints_md += ENDPOINT_TEMPLATE.format(
            method=endpoint.get("method", "GET"),
            path=endpoint.get("path"),
            description=endpoint.get("description", "").strip() if endpoint.get("description") else "_No description available_",
            parameters=params_md,
            returns=endpoint.get("returns", "JSON response")
        )
    
    # Format models for documentation
    models_md = ""
    for model in models:
        # Format fields
        fields_md = ""
        for field in model.get("fields", []):
            fields_md += f"- `{field}`\n"
        if not fields_md:
            fields_md = "_No fields documented_\n"
        
        # Format model documentation
        models_md += MODEL_TEMPLATE.format(
            name=model.get("name"),
            description=model.get("description", "").strip() if model.get("description") else "_No description available_",
            fields=fields_md
        )
    
    # Generate an example for the most complete endpoint
    example = "# No endpoints available for example generation"
    if endpoints:
        # Safely get description length, handling None values
        def get_desc_len(endpoint):
            desc = endpoint.get("description", "")
            return len(desc) if desc else 0
        
        try:
            endpoint = max(endpoints, key=get_desc_len)
            example = f"""
# Example for {endpoint.get('path')}
import requests

response = requests.{endpoint.get('method', 'get').lower()}(
    "https://api.example.com{endpoint.get('path')}"
)
print(response.json())
"""
        except (ValueError, TypeError):
            # Fall back to first endpoint if there's an issue
            if endpoints:
                endpoint = endpoints[0]
                example = f"""
# Example for {endpoint.get('path')}
import requests

response = requests.{endpoint.get('method', 'get').lower()}(
    "https://api.example.com{endpoint.get('path')}"
)
print(response.json())
"""
    
    # Generate the full documentation
    api_doc = API_DOC_TEMPLATE.format(
        title="API Reference Documentation",
        date=datetime.now().strftime("%Y-%m-%d"),
        description=f"This document provides reference for {len(endpoints)} API endpoints and {len(models)} data models.",
        endpoints=endpoints_md or "_No endpoints documented_",
        models=models_md or "_No data models documented_",
        example=example.strip()
    )
    
    # Write to the output file
    output_file = os.path.join(output_dir, "api-reference.md")
    with open(output_file, "w") as f:
        f.write(api_doc)
    
    print(f"Documentation generated: {output_file}")
    
    # Step 4: Set up monitoring for future changes
    print("\n4. Setting up monitoring for future changes...")
    
    # Scan for existing documentation
    doc_scan = scan_docs(repo_path)
    
    if doc_scan.get("success"):
        doc_files = doc_scan.get("doc_files", [])
        print(f"Currently monitoring {len(doc_files)} documentation files")
        
        # Check if our new documentation file should be marked for updates
        api_files = routers + handlers + schemas
        docs_to_update = find_docs_to_update(
            repo_path=repo_path, 
            base_ref="HEAD~10",  # Look at changes in last 10 commits
            target_ref="HEAD"
        )
        
        if docs_to_update.get("success"):
            update_list = docs_to_update.get("docs_to_update", [])
            if update_list:
                print("\nThe following documentation files need updating:")
                for doc in update_list:
                    print(f"  - {doc.get('path')}")
                    
                print("\nTo automatically keep API documentation updated:")
                print("1. Run this script after significant API changes")
                print("2. Set up a Git hook to detect changes to API files")
                print("3. Configure a CI/CD pipeline to regenerate documentation on push")
    
    print("\n" + "=" * 80)
    print("API Documentation Generator Complete".center(80))
    print("=" * 80)

if __name__ == "__main__":
    main() 