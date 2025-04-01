# DocPilot: AI-Powered Documentation Automation

DocPilot is a GitHub App that automatically generates and updates documentation based on code changes. Using advanced AI models, DocPilot helps developers keep their documentation in sync with code, saving time and improving development workflows.

## Key Features

- **Automated Documentation Updates**: Generate and update documentation whenever code changes are pushed
- **AI-Powered Context Understanding**: Parse code, PRs, and commit messages to create relevant documentation
- **Multi-Format Support**: Generate Markdown, OpenAPI specs, and more
- **GitHub Integration**: Seamless workflow integration within GitHub

## Getting Started

### Prerequisites

- Python 3.8+
- GitHub account
- Docker (for local development)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/docpilot.git
   cd docpilot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```
   cp .env.example .env
   ```

4. Run the development server:
   ```
   python src/app.py
   ```

## Architecture

DocPilot is built with:
- FastAPI: Backend web framework
- LangChain: AI agent orchestration
- GPT-4/Claude-3: Primary LLMs for doc generation
- Probot: GitHub App framework

## License

MIT 