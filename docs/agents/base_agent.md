# Base Agent

The `BaseAgent` class is the foundation of Docpilot's agent system, implementing the Pydantic AI Agent framework with typed dependencies and structured outputs.

## Overview

The `BaseAgent` provides a generic implementation that all specialized agents extend. It leverages Pydantic AI's Agent framework to provide:

1. **Type Safety**: Strong typing with generics for dependencies and results
2. **Structured I/O**: Dataclasses for dependencies and Pydantic models for results
3. **Dynamic System Prompts**: Support for context-aware system prompts
4. **Tool Registration**: Register functions that the agent can call
5. **Cost Tracking**: Automatic token usage tracking and cost calculation

## Key Components

### AgentConfig

Configuration class for agent behavior:

```python
@dataclass
class AgentConfig:
    model_name: str = settings.default_model
    temperature: float = settings.model_temperature
    max_tokens: int = settings.max_tokens
    retry_attempts: int = settings.retry_attempts
```

### AgentResult

Container class for agent results that includes both the result data and usage metrics:

```python
class AgentResult(Generic[ResultT], BaseModel):
    data: ResultT  # The agent-specific result data
    usage: Usage   # Token usage information
    
    def calculate_cost(self) -> float:
        """Calculate the cost of this agent run"""
        return self.usage.calculate_cost(self.model)
    
    @property
    def total_tokens(self) -> int:
        """Get the total tokens used"""
        return self.usage.total_tokens
```

### BaseAgent

Generic base class that handles dependency injection and structured outputs:

```python
class BaseAgent(Generic[DepsT, ResultT]):
    # Class variables
    deps_type: ClassVar[Optional[Type[DepsT]]] = None
    result_type: ClassVar[Optional[Type[ResultT]]] = None
    default_system_prompt: ClassVar[str] = ""
    
    async def run(self, user_prompt: str, deps: Optional[DepsT] = None, **kwargs) -> AgentResult[ResultT]:
        """Run the agent and return a result with usage metrics"""
        # Implementation...
```

## Usage Pattern

### 1. Define Dependencies as a Dataclass

```python
@dataclass
class AnalysisDeps:
    text: str
    language: str = "English"
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.text:
            raise ValueError("Text cannot be empty")
```

### 2. Define Result Data as a Pydantic Model

Unlike before, your result model should **not** inherit from AgentResult. The BaseAgent will automatically wrap your result in an AgentResult:

```python
class AnalysisData(BaseModel):
    summary: str
    key_points: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    
    @property
    def has_key_findings(self) -> bool:
        return len(self.key_points) > 0
```

### 3. Create a Specialized Agent

```python
class TextAnalyzer(BaseAgent[AnalysisDeps, AnalysisData]):
    deps_type = AnalysisDeps
    result_type = AnalysisData
    default_system_prompt = "You are an expert text analyzer..."
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Register tools
        @self.tool
        def count_words(text: str) -> int:
            """Count words in text"""
            return len(text.split())
```

### 4. Use the Agent and Access Results

The agent's `run()` method now returns an `AgentResult` that contains both your result data and usage metrics:

```python
# Run the agent
result = await agent.run("Analyze this text", deps=deps)

# Access the result data
print(result.data.summary)
print(f"Points found: {len(result.data.key_points)}")

# Access usage metrics
print(f"Tokens used: {result.usage.total_tokens}")
print(f"Cost: ${result.usage.cost:.6f}")
```

## Advanced Features

### Dynamic System Prompts

Create context-aware system prompts that change based on dependencies:

```python
@agent.system_prompt_fn
async def add_context(ctx: RunContext[AnalysisDeps]) -> str:
    """Add custom context to the system prompt"""
    if not ctx.deps:
        return ""
    
    language = ctx.deps.language
    return f"Analyze this text in {language}. "
```

### Streaming Responses

Get real-time streaming output from the agent:

```python
async for chunk in agent.stream("Generate a long response", deps=deps):
    print(chunk, end="", flush=True)
```

### Iterating Through Thinking Steps

View the agent's thinking process step by step:

```python
async for step in agent.iterate("Solve this problem", deps=deps):
    print(f"Step: {step}")
```

## Complete Example

See the complete example in `examples/pydantic_agent_example.py` which demonstrates:

1. Defining dependencies and a result data model
2. Creating an agent with tools and dynamic system prompts
3. Running the agent and accessing both result data and usage metrics
4. Tracking token usage and costs across multiple runs 