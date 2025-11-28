import asyncio
import inspect
from pathlib import Path

import mcputil


CWD = Path(__file__).parent.resolve()
BASIC_PATH = CWD.parent / "basic"


async def main():
    async with mcputil.Group(
        math=mcputil.Stdio(
            command="python",
            args=[str(BASIC_PATH / "server.py")],
        ),
        progress=mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as group:
        tools: dict[str, list[mcputil.Tool]] = await group.get_all_tools()
        for name, tool_list in tools.items():
            print(f"MCP server '{name}':")
            for tool in tool_list:
                print(f"    tool signature: {tool.name}{inspect.signature(tool)}")

        result: mcputil.Result = await group.call_tool("math", "add", a=1, b=2)
        output = await result.output()
        print(f"\ntool output: {output}\n")

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


if __name__ == "__main__":
    asyncio.run(main())
