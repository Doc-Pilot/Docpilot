# DocPilot User Guide

DocPilot is an AI-powered tool that automatically generates and updates documentation for your code. This guide will help you get started with DocPilot and make the most of its features.

## Table of Contents

- [Installation](#installation)
- [Setting Up GitHub Integration](#setting-up-github-integration)
- [How DocPilot Works](#how-docpilot-works)
- [Supported Event Types](#supported-event-types)
- [Documentation Types](#documentation-types)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## Installation

### Option 1: GitHub App (Recommended)

1. Visit the GitHub Marketplace and search for "DocPilot"
2. Click "Install it for free"
3. Select the repositories you want DocPilot to have access to
4. Complete the installation process

### Option 2: Self-Hosting

1. Clone the DocPilot repository:
   ```bash
   git clone https://github.com/yourusername/docpilot.git
   cd docpilot
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

3. Start DocPilot with Docker:
   ```bash
   docker-compose up -d
   ```

4. Create a GitHub App and configure it to use your self-hosted instance
   (See [Setting Up GitHub Integration](#setting-up-github-integration) for details)

## Setting Up GitHub Integration

### Creating a GitHub App

1. Go to your GitHub account settings
2. Navigate to "Developer settings" > "GitHub Apps" > "New GitHub App"
3. Fill in the required information:
   - Name: "DocPilot" (or your preferred name)
   - Homepage URL: Your DocPilot instance URL or GitHub repo
   - Webhook URL: `https://your-docpilot-instance.com/webhook/github`
   - Webhook secret: Generate a secure random string
   
4. Set the required permissions:
   - Repository permissions:
     - Contents: Read & Write
     - Pull requests: Read & Write
     - Issues: Read & Write
   
5. Subscribe to events:
   - Push
   - Pull request
   - Issues

6. Create the app and note the App ID
7. Generate a private key and download it
8. Update your `.env` file with the App ID and path to the private key

## How DocPilot Works

DocPilot integrates with your GitHub workflow and automatically generates documentation based on code changes:

1. **Push Events**: When code is pushed to the repository, DocPilot analyzes the changed files and updates or creates documentation accordingly.

2. **Pull Request Events**: When a PR is opened or updated, DocPilot suggests documentation updates as comments.

3. **Issue Events**: When an issue related to documentation is created or updated, DocPilot can suggest documentation improvements.

## Supported Event Types

DocPilot responds to the following GitHub events:

### Push Events
- Automatically updates documentation when code is pushed to the main branch
- Creates/updates standalone documentation files in the `docs/` directory
- Creates pull requests with documentation changes for review

### Pull Request Events
- Analyzes code changes in PRs
- Adds comments with documentation suggestions
- Highlights undocumented code or outdated documentation

### Issue Events
- Responds to issues labeled with "documentation"
- Generates documentation for files mentioned in the issue
- Suggests documentation improvements based on issue content

## Documentation Types

DocPilot supports multiple documentation formats:

### Inline Documentation
- **Python**: Docstrings (Google style, reST, or NumPy format)
- **JavaScript/TypeScript**: JSDoc comments
- **Java/Kotlin**: Javadoc comments
- **Go**: GoDoc comments
- **Ruby**: RDoc
- **C/C++**: Doxygen

### Standalone Documentation
- **Markdown**: README files, API documentation, guides
- **OpenAPI/Swagger**: For REST API documentation
- **Reference documentation**: Function/class references

## Customization

### Configuration File

Create a `.docpilot.yml` file in your repository root to customize DocPilot behavior:

```yaml
# .docpilot.yml
docpilot:
  # General settings
  doc_style: google  # or 'numpy', 'rest', 'jsdoc'
  
  # Documentation directory
  docs_dir: docs/
  
  # Branch settings
  branches:
    - main
    - develop
  
  # File patterns to include/exclude
  include:
    - "src/**/*.py"
    - "app/**/*.js"
  exclude:
    - "**/__test__/**"
    - "**/vendor/**"
    
  # Custom documentation templates
  templates:
    function: |
      /**
       * {{function_name}}
       * {{description}}
       * @param {{{param_type}}} {{param_name}} - {{param_description}}
       * @returns {{{return_type}}} {{return_description}}
       */
```

## Troubleshooting

### Common Issues

#### Documentation Not Generating
- Check that DocPilot has access to the repository
- Verify that the file types are supported
- Check for errors in the DocPilot logs

#### PR Comments Not Appearing
- Ensure DocPilot has the correct permissions
- Check webhook delivery status in GitHub App settings

#### Self-Hosted Instance Problems
- Verify environment variables are correctly set
- Ensure GitHub App is properly configured with the right webhook URL
- Check that your instance is accessible from GitHub

## FAQ

### How does DocPilot handle existing documentation?

DocPilot tries to preserve existing documentation while suggesting improvements or additions. It will only update sections that are missing or outdated.

### Can I customize the AI model used?

Yes, self-hosted instances can be configured to use different LLM providers by updating the settings.

### Is my code secure?

DocPilot only processes the code that's already on GitHub. For the GitHub App version, we never store your code permanently and all processing is done securely.

### How much does it cost?

Check our [pricing page](https://docpilot.ai/pricing) for the latest information on free and paid tiers. 