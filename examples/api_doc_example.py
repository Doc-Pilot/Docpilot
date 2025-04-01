"""
API Documentation Generation Example
==================================

This example demonstrates how to generate API documentation using DocPilot's agents.
"""
# Importing Dependencies
import os
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.agents import (
    AgentConfig,
    APIDocGenerator,
    APIDocInput
)

# Example FastAPI code for demonstration
FASTAPI_EXAMPLE = '''
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import uuid

app = FastAPI(title="Task Management API", version="1.0.0")

class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    completed: bool = False

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None

# In-memory database of tasks
tasks_db = {}

@app.get("/tasks", response_model=List[Task])
async def get_tasks(skip: int = 0, limit: int = 10, api_key: str = Header(...)):
    """Get all tasks.
    
    Optional pagination parameters can be provided."""
    if api_key != "secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    return list(tasks_db.values())[skip:skip+limit]

@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(task: TaskCreate, api_key: str = Header(...)):
    """Create a new task."""
    if api_key != "secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    task_id = str(uuid.uuid4())
    new_task = Task(id=task_id, title=task.title, description=task.description)
    tasks_db[task_id] = new_task
    return new_task

@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str, api_key: str = Header(...)):
    """Get a specific task by ID."""
    if api_key != "secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, task: TaskCreate, api_key: str = Header(...)):
    """Update a specific task by ID."""
    if api_key != "secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
        
    tasks_db[task_id].title = task.title
    tasks_db[task_id].description = task.description
    return tasks_db[task_id]

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str, api_key: str = Header(...)):
    """Delete a specific task by ID."""
    if api_key != "secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
        
    del tasks_db[task_id]
    return {"message": "Task deleted successfully"}

@app.patch("/tasks/{task_id}/complete", response_model=Task)
async def complete_task(task_id: str, api_key: str = Header(...)):
    """Mark a task as completed."""
    if api_key != "secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
        
    tasks_db[task_id].completed = True
    return tasks_db[task_id]
'''

def generate_api_documentation():
    """Generate API documentation from example code with enhanced context"""
    print("Generating API Documentation Example with Enhanced Context")
    
    # Configure agent
    agent_config = AgentConfig()
    
    # Create mock directory structure for enhanced context
    mock_directory_structure = """
task_api/
├── app/
│   ├── __init__.py
│   ├── main.py - Main application entry point
│   ├── models.py - Data models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── tasks.py - Task endpoints
│   │   └── auth.py - Authentication
│   └── db/
│       ├── __init__.py
│       └── database.py - Database connection
├── tests/
│   ├── __init__.py
│   └── test_tasks.py - Task API tests
├── docs/
│   └── api_reference.md - API documentation
├── README.md
└── requirements.txt
"""

    # Define usage patterns for enhanced context
    usage_patterns = [
        "Authenticate with API key header for all requests",
        "List all tasks and paginate through results",
        "Create a new task with title and optional description",
        "Retrieve, update, and delete specific tasks by ID",
        "Mark tasks as completed without changing other properties"
    ]
    
    # Define authentication details for enhanced context
    auth_details = {
        "API Key": "Required in header for all endpoints as 'api_key'",
        "Format": "Simple string, no prefix needed",
        "Restrictions": "Rate limited to 100 requests per minute"
    }
    
    # Initialize API documentation generator
    api_doc_generator = APIDocGenerator(config=agent_config)
    
    # Generate API documentation with enhanced context
    print("\nGenerating API documentation with enhanced context...")
    api_doc_result = api_doc_generator.generate_api_docs(
        APIDocInput(
            code=FASTAPI_EXAMPLE,
            api_name="Task Management API",
            language="python",
            framework="FastAPI",
            project_description="A RESTful API for managing tasks with authentication and CRUD operations",
            directory_structure=mock_directory_structure,
            authentication_details=auth_details,
            dependencies=["fastapi", "uvicorn", "pydantic", "python-multipart"],
            usage_patterns=usage_patterns,
            target_audience="Backend developers and frontend consumers needing task management functionality",
            implementation_details={
                "Database": "In-memory for example, would use PostgreSQL in production",
                "Authentication": "API key based, would use OAuth2 in production",
                "Deployment": "Designed to be deployed as a containerized service"
            }
        )
    )
    
    # Print results
    print("\nAPI Documentation Generated:")
    print(f"Title: {api_doc_result.title}")
    print(f"Version: {api_doc_result.version}")
    print(f"Description: {api_doc_result.description}")
    
    print("\nEndpoints:")
    for endpoint in api_doc_result.endpoints:
        print(f"  {endpoint.method} {endpoint.path} - {endpoint.summary}")
    
    # Generate examples with enhanced context
    print("\nGenerating API usage examples with enhanced context...")
    examples_result = api_doc_generator.generate_api_examples(
        api_doc_result,
        languages=["python", "javascript", "curl"],
        usage_patterns=usage_patterns,
        target_audience="Backend developers and frontend consumers",
        implementation_details={
            "Authentication": "API key in header",
            "Response Format": "JSON with consistent error handling"
        }
    )
    
    # Print examples
    print(f"\nGenerated {len(examples_result.examples)} examples")
    
    # Convert to OpenAPI
    print("\nGenerating OpenAPI specification...")
    openapi_spec = api_doc_generator.convert_to_openapi(api_doc_result)
    
    # Create output directory
    output_dir = os.path.join(project_root, "examples", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Save Markdown documentation
    markdown_path = os.path.join(output_dir, "api_documentation.md")
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(api_doc_result.markdown)
    print(f"Saved Markdown documentation to {markdown_path}")
    
    # Save OpenAPI specification
    openapi_path = os.path.join(output_dir, "openapi.json")
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(openapi_spec, f, indent=2)
    print(f"Saved OpenAPI specification to {openapi_path}")
    
    # Save examples
    examples_path = os.path.join(output_dir, "api_examples.md")
    with open(examples_path, "w", encoding="utf-8") as f:
        f.write("# API Usage Examples\n\n")
        for example in examples_result.examples:
            f.write(f"## {example.get('endpoint', 'Example')}\n\n")
            f.write(f"### {example.get('language', 'Code')}\n\n")
            f.write("```\n")
            f.write(example.get('code', '# No code available'))
            f.write("\n```\n\n")
            
            if example.get('response'):
                f.write("### Response\n\n")
                f.write("```\n")
                f.write(example.get('response', '# No response available'))
                f.write("\n```\n\n")
    print(f"Saved API examples to {examples_path}")
    
    # Save the enhanced context as JSON for reference
    context_path = os.path.join(output_dir, "api_enhanced_context.json")
    with open(context_path, "w", encoding="utf-8") as f:
        enhanced_context = {
            "api_name": "Task Management API",
            "project_description": "A RESTful API for managing tasks with authentication and CRUD operations",
            "directory_structure": mock_directory_structure,
            "authentication_details": auth_details,
            "dependencies": ["fastapi", "uvicorn", "pydantic", "python-multipart"],
            "usage_patterns": usage_patterns,
            "target_audience": "Backend developers and frontend consumers needing task management functionality",
            "implementation_details": {
                "Database": "In-memory for example, would use PostgreSQL in production",
                "Authentication": "API key based, would use OAuth2 in production",
                "Deployment": "Designed to be deployed as a containerized service"
            }
        }
        json.dump(enhanced_context, f, indent=2)
    print(f"Saved enhanced context to {context_path}")

if __name__ == "__main__":
    generate_api_documentation() 