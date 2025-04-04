# Docpilot Agent System

The Docpilot agent system provides a type-safe framework for building AI agents using the [Pydantic AI](https://ai.pydantic.dev/) framework. Our agents use dataclasses for dependencies and Pydantic models for results, with features for cost tracking, error handling, and streaming responses.

## Core Principles

1. **Type Safety**: All inputs and outputs are fully typed
2. **Structured Data**: Dependencies are dataclasses, results are Pydantic models
3. **Composition**: Agents can delegate to other agents for specialized tasks
4. **Instrumentation**: Automatic token usage tracking and cost calculation
5. **Tool Registration**: Easily extend agents with custom functionality

## Available Agents

- **RepoAnalyzer**: Analyze repository structure to identify components and architecture
- **APIDocGenerator**: Generate comprehensive API documentation
- **ReadmeGenerator**: Create or update README files
- **DocGenerator**: Generate documentation for code files
- **QualityChecker**: Check documentation for completeness and accuracy
- **CodeAnalyzer**: Extract information from code for documentation

## BaseAgent

The `BaseAgent` is the foundation of our agent system:

```python
class BaseAgent(Generic[DepsT, ResultT]):
    # Class variables for configuration
    deps_type: ClassVar[Optional[Type[DepsT]]] = None
    result_type: ClassVar[Optional[Type[ResultT]]] = None
    default_system_prompt: ClassVar[str] = ""
    
    # ... implementation ...
```

## Creating a New Agent

1. Define dependencies as a dataclass:

```python
@dataclass
class MyAgentDeps:
    input_text: str
    context: Dict[str, Any] = field(default_factory=dict)
```

2. Define result as a Pydantic model inheriting from AgentResult:

```python
class MyAgentResult(AgentResult):
    summary: str
    key_points: List[str]
```

3. Create your agent class:

```python
class MyAgent(BaseAgent[MyAgentDeps, MyAgentResult]):
    deps_type = MyAgentDeps
    result_type = MyAgentResult
    default_system_prompt = "You are a specialized agent..."
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        @self.tool
        def helper_function(text: str) -> str:
            # Implementation...
            return processed_text
```

## Usage Example

```python
# Create the agent
agent = MyAgent()

# Define dependencies
deps = MyAgentDeps(input_text="Text to analyze")

# Run the agent
result = await agent.run("Analyze this text", deps=deps)

# Access structured results
print(result.summary)
print(result.key_points)
```

For complete examples, see `examples/pydantic_agent_example.py`.

## Advanced Features

- **Dynamic System Prompts**: Use `@agent.system_prompt_fn` to create context-aware prompts
- **Streaming**: Use `agent.stream()` for real-time streaming responses
- **Iteration**: Use `agent.iterate()` to view the agent's thinking process step by step
- **Cost Tracking**: Access token usage and cost via `result.usage` and `result.calculate_cost()` 