# Code Execution

This example demonstrates how to implement [Code execution with MCP][1] by leveraging `mcputil` and [deepagents][2].


## Why

As MCP usage scales, there are two common patterns that can increase agent cost and latency:

1. Tool definitions overload the context window;
2. Intermediate tool results consume additional tokens.

As a solution, Code execution with MCP thus came into being:

1. Present MCP servers as code APIs rather than direct tool calls;
2. The agent can then write code to interact with MCP servers.

This approach addresses both challenges: agents can load only the tools they need and process data in the execution environment before passing results back to the model.


## Prerequisites

Install `mcputil`:

```bash
pip install mcputil
```

Install dependencies:

```bash
pip install deepagents
pip install langchain-community
pip install langchain-experimental
```


## Quickstart

Run the MCP servers:

```bash
python examples/code-execution/google_drive.py

# In another terminal
python examples/code-execution/salesforce.py
```

Generate a file tree of all available tools from MCP servers:

```bash
mcputil \
    --server='{"name": "google_drive", "url": "http://localhost:8000"}' \
    --server='{"name": "salesforce", "url": "http://localhost:8001"}' \
    -o examples/code-execution/output/servers
```

Run the example agent:

```bash
export ANTHROPIC_API_KEY="your-api-key"
python examples/code-execution/agent.py
```


[1]: https://www.anthropic.com/engineering/code-execution-with-mcp
[2]: https://github.com/langchain-ai/deepagents