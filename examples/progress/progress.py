import asyncio
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


if __name__ == "__main__":
    asyncio.run(main())
