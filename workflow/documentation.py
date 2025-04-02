"""
Documentation Generation Module
==============================

This module provides functions for generating different types of documentation.
"""
import os
import json
import time
import logging
from typing import Dict, Any, List, Optional

# Import Docpilot components
from src.agents import (
    AgentConfig, 
    ReadmeGenerator, 
    ReadmeInput,
    APIDocGenerator, 
    APIDocInput
)

# Import token cost tracker
from .metrics import ModelTokenCost

logger = logging.getLogger(__name__)

def generate_readme(
    repo_path: str, 
    repo_data: Dict[str, Any], 
    analysis_data: Dict[str, Any],
    metrics
) -> Dict[str, Any]:
    """
    Generate a README.md file for the repository
    
    Args:
        repo_path: Path to the repository
        repo_data: Data from repository scanning
        analysis_data: Data from repository analysis
        metrics: Metrics tracking object
        
    Returns:
        Dictionary with readme generation results
    """
    logger.info("Generating README file...")
    repo_name = repo_data["repo_name"]
    repo_structure = analysis_data["repo_structure"]
    
    # Configure agents
    agent_config = AgentConfig()
    
    # Get the model name for cost calculation
    model_name = agent_config.model_name
    
    # Initialize README generator
    readme_generator = ReadmeGenerator(config=agent_config)
    
    # Start time for the LLM call
    llm_start = time.time()
    
    # Generate README content
    readme_input = ReadmeInput(
        repo_name=repo_name,
        repo_path=repo_path,
        summary=repo_structure.summary,
        technologies=list(repo_structure.technologies),
        architecture_pattern=repo_structure.architecture_pattern,
        components=[
            {"name": c.name, "description": c.description} 
            for c in repo_structure.components
        ],
        entry_points=repo_data["entry_points"],
        documentation_needs=analysis_data["doc_needs"],
        framework_info=repo_data["frameworks"],
        file_stats=repo_data["file_stats"],
        directory_structure=repo_data.get("directory_tree", "")
    )
    readme_content = readme_generator.generate_readme(readme_input)
    
    # Calculate LLM time
    llm_duration = time.time() - llm_start
    
    # Get the result context if available
    result_context = getattr(readme_content, "_context", None)
    
    # Log event with important stats
    metrics.log_event(
        "readme_generation", 
        "LLM_CALL_COMPLETED", 
        {
            "duration": llm_duration,
            "components_count": len(repo_structure.components)
        },
        model=model_name,
        result=result_context,
        agent=readme_generator
    )
    
    # Save README content to file
    readme_file = os.path.join(metrics.output_dir, "README.md")
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(readme_content)
    logger.info(f"README saved to {readme_file}")
    
    return {
        "content": readme_content,
        "file_path": readme_file
    }

def generate_api_documentation(
    repo_path: str,
    api_files: List[str],
    repo_data: Dict[str, Any],
    analysis_data: Dict[str, Any],
    metrics
) -> Dict[str, Any]:
    """
    Generate API documentation for the repository
    
    Args:
        repo_path: Path to the repository
        api_files: List of API files to document
        repo_data: Data from repository scanning
        analysis_data: Data from repository analysis
        metrics: Metrics tracking object
        
    Returns:
        Dictionary with API documentation results
    """
    if not api_files:
        logger.info("No API files provided for documentation")
        return {
            "content": "",
            "openapi_spec": {},
            "examples": [],
            "cost": 0,
            "tokens": 0
        }
    
    logger.info(f"Generating API documentation for {len(api_files)} files")
    
    # Configure agents
    agent_config = AgentConfig()
    
    # Get the model name for cost calculation
    model_name = agent_config.model_name
    
    # Initialize API documentation generator
    api_doc_generator = APIDocGenerator(config=agent_config)
    
    # Start time for the LLM call
    llm_start = time.time()
    
    # Create enhanced context for API documentation
    repo_structure = analysis_data["repo_structure"]
    directory_structure = repo_data.get("directory_tree", "")
    
    # Process API files to extract routes and descriptions
    all_api_files = []
    for api_file in api_files:
        # Read the file content
        try:
            with open(os.path.join(repo_path, api_file), "r", encoding="utf-8") as f:
                content = f.read()
            all_api_files.append({"path": api_file, "content": content})
        except Exception as e:
            logger.error(f"Error reading API file {api_file}: {e}")
    
    # Generate API documentation using enhanced context
    api_doc_input = APIDocInput(
        repo_name=repo_data["repo_name"],
        api_files=all_api_files,
        project_description=repo_structure.summary,
        directory_structure=directory_structure,
        dependencies=repo_data["frameworks"].get("dependencies", []),
        target_audience="developers",
        usage_patterns=[
            "Authentication and authorization",
            "Data retrieval and manipulation",
            "Integration with other systems"
        ]
    )
    
    # Generate documentation
    api_docs = api_doc_generator.generate_api_docs(api_doc_input)
    
    # Generate OpenAPI specification
    openapi_spec = api_doc_generator.convert_to_openapi(
        api_doc_input, 
        api_docs,
        title=f"{repo_data['repo_name']} API",
        version="1.0.0"
    )
    
    # Generate examples
    examples = api_doc_generator.generate_api_examples(
        api_doc_input,
        api_docs,
        usage_patterns=api_doc_input.usage_patterns,
        target_audience=api_doc_input.target_audience
    )
    
    # Calculate LLM time
    llm_duration = time.time() - llm_start
    
    # Get the result context if available
    api_docs_context = getattr(api_docs, "_context", None)
    
    # Log event with important stats
    metrics.log_event(
        "api_documentation", 
        "LLM_CALL_COMPLETED", 
        {
            "duration": llm_duration,
            "file_count": len(api_files),
            "api_file_size": sum(len(f.get("content", "")) for f in all_api_files)
        },
        model=model_name,
        result=api_docs_context,
        agent=api_doc_generator
    )
    
    # Save API documentation content to files
    api_docs_file = os.path.join(metrics.output_dir, "API_DOCUMENTATION.md")
    with open(api_docs_file, "w", encoding="utf-8") as f:
        f.write(api_docs)
    
    openapi_file = os.path.join(metrics.output_dir, "openapi_spec.json")
    with open(openapi_file, "w", encoding="utf-8") as f:
        json.dump(openapi_spec, f, indent=2)
    
    examples_file = os.path.join(metrics.output_dir, "api_examples.md")
    with open(examples_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(examples))
    
    logger.info(f"API documentation saved to {api_docs_file}")
    logger.info(f"OpenAPI specification saved to {openapi_file}")
    logger.info(f"API examples saved to {examples_file}")
    
    return {
        "content": api_docs,
        "openapi_spec": openapi_spec,
        "examples": examples,
        "api_docs_file": api_docs_file,
        "openapi_file": openapi_file,
        "examples_file": examples_file
    }

def generate_component_documentation(
    repo_path: str,
    component_files: List[str],
    repo_data: Dict[str, Any],
    analysis_data: Dict[str, Any],
    metrics
) -> Dict[str, Any]:
    """
    Generate documentation for specific components in the repository
    
    Args:
        repo_path: Path to the repository
        component_files: List of component files to document
        repo_data: Data from repository scanning
        analysis_data: Data from repository analysis
        metrics: Metrics tracking object
        
    Returns:
        Dictionary with component documentation results
    """
    if not component_files:
        logger.info("No component files provided for documentation")
        return {
            "content": {},
            "component_files": []
        }
    
    logger.info(f"Generating component documentation for {len(component_files)} files")
    
    # Configure agents
    agent_config = AgentConfig()
    
    # Get the model name for cost calculation
    model_name = agent_config.model_name
    
    # Initialize documentation generator
    # For this example, we'll use the ReadmeGenerator with a custom template
    # In a real implementation, you might want a dedicated ComponentDocGenerator
    doc_generator = ReadmeGenerator(config=agent_config)
    
    # Group components by type/directory
    component_groups = {}
    for file_path in component_files:
        directory = os.path.dirname(file_path)
        if directory not in component_groups:
            component_groups[directory] = []
        component_groups[directory].append(file_path)
    
    # Generate documentation for each component group
    results = {}
    
    for group_name, files in component_groups.items():
        logger.info(f"Generating documentation for {group_name} components")
        
        # Read component files
        component_contents = []
        for file_path in files:
            try:
                with open(os.path.join(repo_path, file_path), "r", encoding="utf-8") as f:
                    content = f.read()
                component_contents.append({"path": file_path, "content": content})
            except Exception as e:
                logger.error(f"Error reading component file {file_path}: {e}")
        
        # Start time for the LLM call
        llm_start = time.time()
        
        # Generate documentation for this component group
        # Using generate_section rather than generate_readme for more focused docs
        section_content = doc_generator.generate_section(
            ReadmeInput(
                repo_name=repo_data["repo_name"],
                repo_path=repo_path,
                summary=f"Documentation for {group_name} components",
                components=[{
                    "name": os.path.basename(file["path"]),
                    "description": "Component file"
                } for file in component_contents],
                technologies=list(analysis_data["repo_structure"].technologies),
                file_contents=component_contents
            ),
            section_name=f"{group_name} Components"
        )
        
        # Calculate LLM time
        llm_duration = time.time() - llm_start
        
        # Get the result context if available
        section_context = getattr(section_content, "_context", None)
        
        # Log event with important stats
        metrics.log_event(
            "component_documentation",
            "LLM_CALL_COMPLETED",
            {
                "duration": llm_duration,
                "group": group_name,
                "file_count": len(files),
                "content_size": sum(len(file.get("content", "")) for file in component_contents)
            },
            model=model_name,
            result=section_context,
            agent=doc_generator
        )
        
        # Save component documentation to file
        file_name = group_name.replace("/", "_").replace("\\", "_")
        if not file_name:
            file_name = "root_components"
        doc_file = os.path.join(metrics.output_dir, f"{file_name}_documentation.md")
        with open(doc_file, "w", encoding="utf-8") as f:
            f.write(section_content)
        
        # Store results
        results[group_name] = {
            "content": section_content,
            "file_path": doc_file,
            "files": files
        }
    
    return {
        "content": results,
        "component_files": component_files
    } 