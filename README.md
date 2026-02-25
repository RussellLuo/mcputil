# mcputil

A lightweight library that converts [MCP][1] tools into Python tools (function-like objects).


## Installation

```bash
pip install mcputil
```


## Quickstart

(Check out the [examples](./examples) directory for runnable examples.)

### Basic Usage

Given the following MCP server:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="Basic", log_level="ERROR")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

We can use `mcputil` to call the `add` tool easily:

```python
import inspect
import mcputil


async def main():
    async with mcputil.Client(
        mcputil.Stdio(
            command="python",
            args=["/path/to/server.py"],
        ),
    ) as client:
        tool: mcputil.Tool = (await client.get_tools())[0]
        print(f"tool signature: {tool.name}{inspect.signature(tool)}")

        output = await tool(a=1, b=2)
        print(f"tool output: {output}")

    # Output:
    # tool signature: add(a: int, b: int) -> int
    # tool output: 3
```

### Progress Tracking

Given the following MCP server (see [here](https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/servers/tool_progress.py)):

```python
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

mcp = FastMCP(name="Progress")


@mcp.tool()
async def long_running_task(
    task_name: str, ctx: Context[ServerSession, None], steps: int = 5
) -> str:
    """Execute a task with progress updates."""
    for i in range(steps):
        progress = (i + 1) / steps
        await ctx.report_progress(
            progress=progress,
            total=1.0,
            message=f"Step {i + 1}/{steps}",
        )

    return f"Task '{task_name}' completed"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

```bash
python server.py
```

We can use `mcputil` to track the progress of the `long_running_task` tool:

```python
import inspect
import mcputil


async def main():
    async with mcputil.Client(
        mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as client:
        tool: mcputil.Tool = (await client.get_tools())[0]
        print(f"tool signature: {tool.name}{inspect.signature(tool)}")

        result: mcputil.Result = await tool.call(
            "call_id_0", task_name="example-task", steps=5
        )
        async for event in result.events():
            if isinstance(event, mcputil.ProgressEvent):
                print(f"tool progress: {event}")
            elif isinstance(event, mcputil.OutputEvent):
                print(f"tool output: {event.output}")

    # Output:
    # tool signature: long_running_task(task_name: str, steps: int = 5) -> str
    # tool progress: ProgressEvent(progress=0.2, total=1.0, message='Step 1/5')
    # tool progress: ProgressEvent(progress=0.4, total=1.0, message='Step 2/5')
    # tool progress: ProgressEvent(progress=0.6, total=1.0, message='Step 3/5')
    # tool progress: ProgressEvent(progress=0.8, total=1.0, message='Step 4/5')
    # tool progress: ProgressEvent(progress=1.0, total=1.0, message='Step 5/5')
    # tool output: Task 'example-task' completed
```

### Multiple MCP Servers

`mcputil` also supports managing multiple MCP servers using the `Group` class:

```python
import inspect
import mcputil


async def main():
    async with mcputil.Group(
        math=mcputil.Stdio(
            command="python",
            args=["/path/to/server.py"],
        ),
        progress=mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as group:
        tools: list[mcputil.Tool] = await group.get_tools()
        for tool in tools:
            print(f"tool signature: {tool.name}{inspect.signature(tool)}")
            if tool.name == "add":
                output = await tool(a=1, b=2)
                print(f"tool output: {output}\n")
            elif tool.name == "long_running_task":
                result: mcputil.Result = await tool.call(
                    "call_id_0",  # non-empty call ID for tracking progress
                    task_name="example-task",
                    steps=5,
                )
                async for event in result.events():
                    if isinstance(event, mcputil.ProgressEvent):
                        print(f"tool progress: {event}")
                    elif isinstance(event, mcputil.OutputEvent):
                        print(f"tool output: {event.output}")

    # Output:
    # tool signature: add(a: int, b: int) -> int
    # tool output: 3
    #
    # tool signature: long_running_task(task_name: str, steps: int = 5) -> str
    # tool progress: ProgressEvent(progress=0.2, total=1.0, message='Step 1/5')
    # tool progress: ProgressEvent(progress=0.4, total=1.0, message='Step 2/5')
    # tool progress: ProgressEvent(progress=0.6, total=1.0, message='Step 3/5')
    # tool progress: ProgressEvent(progress=0.8, total=1.0, message='Step 4/5')
    # tool progress: ProgressEvent(progress=1.0, total=1.0, message='Step 5/5')
    # tool output: Task 'example-task' completed
```

Additionally, you can also call tools by their names without fetching them first:

```python
import inspect
import mcputil


async def main():
    async with mcputil.Group(
        math=mcputil.Stdio(
            command="python",
            args=["/path/to/server.py"],
        ),
        progress=mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as group:
        result: mcputil.Result = await group.call_tool("math", "add", a=1, b=2)
        output = await result.output()
        print(f"tool output: {output}\n")

        result: mcputil.Result = await group.call_tool(
            "progress",
            "long_running_task",
            call_id="call_id_0",  # non-empty call ID for tracking progress
            task_name="example-task",
            steps=5,
        )
        async for event in result.events():
            if isinstance(event, mcputil.ProgressEvent):
                print(f"tool progress: {event}")
            elif isinstance(event, mcputil.OutputEvent):
                print(f"tool output: {event.output}")

    # Output:
    # tool output: 3
    #
    # tool progress: ProgressEvent(progress=0.2, total=1.0, message='Step 1/5')
    # tool progress: ProgressEvent(progress=0.4, total=1.0, message='Step 2/5')
    # tool progress: ProgressEvent(progress=0.6, total=1.0, message='Step 3/5')
    # tool progress: ProgressEvent(progress=0.8, total=1.0, message='Step 4/5')
    # tool progress: ProgressEvent(progress=1.0, total=1.0, message='Step 5/5')
    # tool output: Task 'example-task' completed
```


## Agent Framework Integration

Given the following MCP Server:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="Basic")


@mcp.tool()
def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    return f"The weather in {city} is sunny."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

### [LangChain][2]

```python
from langchain.tools import tool
from langchain.agents import create_agent
import mcputil


async def main():
    async with mcputil.Client(
        mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as client:
        mcp_tools: list[mcputil.Tool] = await client.get_tools()

        agent = create_agent(
            "openai:gpt-5",
            tools=[tool(t) for t in mcp_tools],
        )
```

### [OpenAI Agents SDK][3]

```python
from agents import Agent, function_tool
import mcputil


async def main():
    async with mcputil.Client(
        mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as client:
        mcp_tools: list[mcputil.Tool] = await client.get_tools()

        agent = Agent(
            name="Hello world",
            instructions="You are a helpful agent.",
            tools=[function_tool(t) for t in mcp_tools],
        )
```

### [Pydantic AI][4]

```python
import mcputil
from pydantic_ai import Agent


async def main():
    async with mcputil.Client(
        mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as client:
        mcp_tools: list[mcputil.Tool] = await client.get_tools()

        agent = Agent(
            "google-gla:gemini-2.5-flash",
            deps_type=str,
            tools=mcp_tools,
            system_prompt="You are a helpful agent.",
        )
```


## CLI

`mcputil` also comes with a CLI for generating a file tree of all available tools from connected MCP servers, which helps with [Code execution with MCP][5]. Checkout out the [example](./examples/code-execution).

Usage:

```bash
$ mcputil -h
usage: mcputil [-h] [-s SERVER] [-c CONFIG] [-o OUTPUT]

mcputil - Generate Python functions from MCP server tools

options:
  -h, --help            show this help message and exit
  -s SERVER, --server SERVER
                        Server configuration as JSON. Format: {"name": "server_name", "url": "server_url", "headers": {...}, "timeout": 30}
  -c CONFIG, --config CONFIG
                        Path to MCP configuration file (mcp.json format). Default: .mcputil/mcp.json or ~/.mcputil/mcp.json
  -o OUTPUT, --output OUTPUT
                        Output directory path. Default: 'servers'

Examples:
  # Use default configuration file (.mcputil/mcp.json or ~/.mcputil/mcp.json)
  mcputil

  # Single server via --server
  mcputil --server='{"name": "math", "url": "http://localhost:8000"}'

  # Multiple servers via --server
  mcputil --server='{"name": "math", "url": "http://localhost:8000"}' \
          --server='{"name": "weather", "url": "http://localhost:8001"}'

  # With custom headers and timeout via --server
  mcputil --server='{"name": "api", "url": "http://api.example.com", "headers": {"Authorization": "Bearer token"}, "timeout": 60}'

  # Using specific configuration file
  mcputil --config mcp.json

  # Configuration file with custom output directory
  mcputil --config mcp.json --output my_servers
```

> [!NOTE]
> Example [`mcp.json`][6]:
>
> ```json
> {
>   "mcpServers": {
>     "local-server": {
>       "command": "python",
>       "args": ["mcp-server.py"],
>       "env": {
>         "API_KEY": "value"
>       }
>     },
>     "remote-server": {
>       "url": "http://localhost:3000/mcp",
>       "headers": {
>         "API_KEY": "value"
>       }
>     }
>   }
> }


## License

[MIT][7]


[1]: https://modelcontextprotocol.io
[2]: https://docs.langchain.com/oss/python/langchain/agents#defining-tools
[3]: https://github.com/openai/openai-agents-python#functions-example
[4]: https://ai.pydantic.dev/tools/#registering-function-tools-via-agent-argument
[5]: https://www.anthropic.com/engineering/code-execution-with-mcp
[6]: https://cursor.com/docs/context/mcp#using-mcpjson
[7]: http://opensource.org/licenses/MIT
