import asyncio
import inspect
from pathlib import Path

import mcputil


CWD = Path(__file__).parent.resolve()
BASIC_PATH = CWD.parent / "basic"


async def call_directly(group: mcputil.Group) -> None:
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


async def call_via_group(group: mcputil.Group) -> None:
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


async def main():
    async with mcputil.Group(
        math=mcputil.Stdio(
            command="python",
            args=[str(BASIC_PATH / "server.py")],
        ),
        progress=mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as group:
        print("[Calling directly]")
        await call_directly(group)

        print("\n[Calling via group]")
        await call_via_group(group)


if __name__ == "__main__":
    asyncio.run(main())
