# Task Management API

## Overview
This is a simple Task Management API built with FastAPI. It allows users to create, read, update, and delete tasks.

## Authentication
All endpoints require the use of a valid API key. Include the API key in the request headers.

### Example Header
```http
api-key: secret-api-key
```

## Endpoints

### Get All Tasks
**GET /tasks**  
Retrieve all tasks with optional pagination.

#### Parameters
- `skip` (int): The number of tasks to skip for pagination (default: 0)
- `limit` (int): The maximum number of tasks to return (default: 10)

#### Responses
- `200 OK`: A list of tasks.
- `401 Unauthorized`: Invalid API key.

### Create a New Task
**POST /tasks**  
Create a new task.

#### Request Body
```json
{
  "title": "Task Title",
  "description": "Optional description"
}
```

#### Responses
- `201 Created`: The created task object.
- `401 Unauthorized`: Invalid API key.

### Get a Task by ID
**GET /tasks/{task_id}**  
Retrieve a task by its ID.

#### Responses
- `200 OK`: The task object.
- `404 Not Found`: Task not found.
- `401 Unauthorized`: Invalid API key.

### Update a Task by ID
**PUT /tasks/{task_id}**  
Update a task's details.

#### Request Body
```json
{
  "title": "Updated Task Title",
  "description": "Updated description"
}
```

#### Responses
- `200 OK`: The updated task object.
- `404 Not Found`: Task not found.
- `401 Unauthorized`: Invalid API key.

### Delete a Task by ID
**DELETE /tasks/{task_id}**  
Delete a task by its ID.

#### Responses
- `200 OK`: Success message.
- `404 Not Found`: Task not found.
- `401 Unauthorized`: Invalid API key.

### Complete a Task by ID
**PATCH /tasks/{task_id}/complete**  
Mark a task as completed.

#### Responses
- `200 OK`: The updated task object.
- `404 Not Found`: Task not found.
- `401 Unauthorized`: Invalid API key.

## Error Codes
- `401 Unauthorized`: Returned when the API key is invalid or missing.
- `404 Not Found`: Returned when the requested task does not exist.

## Performance Considerations
- The API has basic rate limiting based on the use of headers that you can implement as needed for your application.

## Implementation Examples
### Python Example
```python
import requests

url = "http://localhost:8000/tasks"
headers = {"api-key": "secret-api-key"}

# Get all tasks
response = requests.get(url, headers=headers)
print(response.json())

# Create a task
response = requests.post(url, json={"title": "New Task"}, headers=headers)
print(response.json())
```