import asyncio
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.messages import HumanMessage
from langchain_community.tools import ShellTool


CURRENT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = CURRENT_DIR / "output"


agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    # model="anthropic:claude-sonnet-4-5-20250929",
    tools=[ShellTool()],
    backend=FilesystemBackend(root_dir=CURRENT_DIR),
    system_prompt=f"""\
IMPORTANT NOTES:
1. To finish the task, you can write and execute Python code to interact with MCP servers.
2. The MCP servers are available in the `{OUTPUT_DIR / "servers"}` directory.
3. You can use tools such as `ls` and `read_file` to explore the filesystem and read files.
4. Generate code into a Python script and save it to the `{OUTPUT_DIR}` directory.

Example for generated code:

```python
from servers.group import group
from servers.server1.tool1 import tool1
from servers.server2.tool2 import tool2

async def main():
    async with group:
        ...
```
""",
)


async def main():
    query = "Download my meeting transcript abc123 from Google Drive and attach it to the Salesforce lead 00Q5f000001abcXYZ."
    messages = [HumanMessage(content=query)]
    result = agent.astream({"messages": messages}, stream_mode="updates")
    async for chunk in result:
        if "model" in chunk:
            msgs = chunk["model"]["messages"]
        elif "tools" in chunk:
            msgs = chunk["tools"]["messages"]
        else:
            msgs = []

        for m in msgs:
            m.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
