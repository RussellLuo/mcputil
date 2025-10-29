import asyncio
import inspect
from pathlib import Path

import mcputil

CWD = Path(__file__).parent.resolve()


async def main():
    async with mcputil.Client(
        mcputil.Stdio(
            command="python",
            args=[str(CWD / "server.py")],
        ),
    ) as client:
        tool: mcputil.Tool = (await client.get_tools())[0]
        print(f"tool signature: {tool.name}{inspect.signature(tool)}")

        output = await tool(a=1, b=2)
        print(f"tool output: {output}")


if __name__ == "__main__":
    asyncio.run(main())
