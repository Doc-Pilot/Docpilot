# Docpilot

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Overview
Docpilot is a robust FastAPI application designed for document generation and analysis through an agent-based architecture. It provides various modules that collaborate to enable seamless integration with GitHub APIs, analysis of code, and generation of documentation. Additionally, Docpilot includes example scripts and comprehensive testing to ensure reliability and facilitate easy onboarding for developers.

## Table of Contents
- [Installation](#installation)  
- [Usage](#usage)  
- [Examples](#examples)  
- [API](#api)  
- [Configuration](#configuration)  
- [Troubleshooting](#troubleshooting)  
- [Contributing](#contributing)  
- [License](#license)

## Installation
To get started with Docpilot, follow these steps:  

1. **Clone the repository**:  
   ```bash  
   git clone https://github.com/yourusername/docpilot.git  
   cd docpilot  
   ```  

2. **Set up a virtual environment (optional but recommended)**:  
   ```bash  
   python -m venv venv  
   source venv/bin/activate # On Windows use `venv\Scripts\activate`  
   ```  

3. **Install the required dependencies**:  
   ```bash  
   pip install -r requirements.txt  
   ```  

4. **Run the application**:  
   ```bash  
   uvicorn src.api.app:app --reload  
   ```  
   Note: Ensure that `uvicorn` is installed as part of the requirements, and the entry point is correctly pointed to your FastAPI application.

## Usage
Once the application is running, you can interact with the Docpilot API by sending HTTP requests. Here are a couple of common scenarios:  

- **Analyzing code**:  
   ```bash  
   curl -X POST "http://localhost:8000/analyze" -H "Content-Type: application/json" -d '{"code": "print('Hello, World!')"}'  
   ```  

- **Generating documentation**:  
   ```bash  
   curl -X POST "http://localhost:8000/generate-doc" -H "Content-Type: application/json" -d '{"project": "my_project"}'  
   ```  

Explore other functionalities by checking the API documentation included in the `docs` directory.

## Examples
In the `examples` directory, you will find a variety of scripts demonstrating how to work with the Docpilot API:  

- `api_doc_example.py`: Example of generating API documentation.  
- `greeting_example.py`: A sample illustrating a simple greeting functionality.  
- `repo_analyzer_example.py`: Shows how to analyze a GitHub repository.  

Run these examples directly after activating your environment:  
```bash  
python examples/api_doc_example.py  
python examples/greeting_example.py  
python examples/repo_analyzer_example.py  
```

## API
### Endpoints  
- **POST /analyze**: Analyzes the provided code snippet.  
  - **Request Body**: `{ "code": "<your_code_here>" }`  
  - **Response**: JSON containing analysis results.  

- **POST /generate-doc**: Generates documentation for the specified project.  
  - **Request Body**: `{ "project": "<project_name>" }`  
  - **Response**: JSON with generated documentation details.

## Configuration
You can configure Docpilot using environment variables or directly in the configuration files. Here are some options:  
- **API_HOST**: Set the host address for the API service.  
- **API_PORT**: Set the port for the API service to listen on (default: 8000).  
- **DEBUG_MODE**: Adjust log output verbosity for debugging purposes.

## Troubleshooting
If you encounter issues while using Docpilot, consider these troubleshooting steps:  
- **Application won't start**: Check for any errors in the terminal output when running `uvicorn`. Make sure all dependencies are installed accurately.  
- **API requests fail**: Ensure that you are sending requests to the correct endpoint and that the server is up and running. Validate the request body formatting and required fields.

## Contributing
We welcome contributions to Docpilot! Here’s how you can contribute:  
1. Fork this repository and create a new branch for your feature or fix.  
2. Make your changes and run tests to ensure nothing is broken.  
3. Submit a pull request explaining your modifications and the goal of the changes.  

**Note**: Please adhere to coding standards and provide test cases for any new functionalities.

## License
Docpilot is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.