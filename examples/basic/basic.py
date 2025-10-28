import asyncio

import mcputil


async def main():
    async with mcputil.Client(
        mcputil.StreamableHTTP(url="http://localhost:8000"),
    ) as client:
        tool: mcputil.Tool = (await client.get_tools())[0]
        print(f"tool name: {tool.name}")

        output = await tool(a=1, b=2)
        print(f"tool output: {output}")


if __name__ == "__main__":
    asyncio.run(main())
