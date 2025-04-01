# Docpilot

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Overview
Docpilot is a powerful API service that leverages the capabilities of FastAPI to analyze code and generate relevant documentation. With its modular architecture and agent-based system, users can efficiently utilize a range of functionalities pertaining to software documentation. The service comes equipped with example scripts to help you get started quickly and includes a robust testing suite to ensure reliability and performance.

## Installation
To install Docpilot, follow the steps below:

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
   uvicorn main:app --reload
   ```

## Usage
To use the Docpilot API, you can start by sending HTTP requests to the endpoints provided by the FastAPI application. Some common scenarios include:

- Analyzing code:
   ```bash
   curl -X POST "http://localhost:8000/analyze" -H "Content-Type: application/json" -d '{"code": "print('Hello, World!')"}'
   ```
- Generating documentation:
   ```bash
   curl -X POST "http://localhost:8000/generate-doc" -H "Content-Type: application/json" -d '{"project": "my_project"}'
   ```

## Examples
The `examples` directory contains scripts that demonstrate how to interact with the API:

- `example_analyze.py`: Shows how to analyze a piece of code.
- `example_generate_doc.py`: Illustrates the documentation generation process.

You can run these examples directly after activating your environment:
```bash
python examples/example_analyze.py
python examples/example_generate_doc.py
```

## API
### Endpoints
- **POST /analyze**: Analyzes the provided code snippet.
  - **Request Body**: `{ "code": "<your_code_here>" }`
  - **Response**: Analysis result in JSON format.

- **POST /generate-doc**: Generates documentation based on the project name provided.
  - **Request Body**: `{ "project": "<project_name>" }`
  - **Response**: Documentation in JSON format containing generated details.

## Configuration
Docpilot can be configured through environment variables or direct modifications inside the configuration file. Here are some configuration options:

- **API_HOST**: Define the host address for the API service.
- **API_PORT**: Define the port on which the API service runs.
- **DEBUG_MODE**: Enable or disable debug mode for more verbose logging.

## Contributing
Contributions to Docpilot are welcome! To contribute:
1. Fork the repository and create a new branch for your feature/fix.
2. Make your changes and test thoroughly.
3. Submit a pull request detailing your changes and the issues addressed.

Please make sure to follow the coding conventions and to write test cases for new functionalities where applicable.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.