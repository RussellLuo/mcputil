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
