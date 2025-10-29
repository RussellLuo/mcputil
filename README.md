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
            args=["/path/to/server.py")],
        ),
    ) as client:
        tool: mcputil.Tool = (await client.get_tools())[0]
        print(f"tool: {tool.name}{inspect.signature(tool)}")

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


## License

[MIT][2]


[1]: https://modelcontextprotocol.io
[2]: http://opensource.org/licenses/MIT