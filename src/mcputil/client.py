from __future__ import annotations

from contextlib import AbstractAsyncContextManager, AsyncExitStack
from dataclasses import dataclass
from typing_extensions import TypeAlias

import aiorwlock
from mcp import ClientSession, Tool as McpTool
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
from mcp.shared.session import RequestResponder
import mcp.types as types

from .tool import Tool
from .types import ProgressToken, ProgressEvent, EventBus


# An alias of `mcp.client.stdio.StdioServerParameters`.
Stdio: TypeAlias = StdioServerParameters


@dataclass
class StreamableHTTP:
    """Core parameters from `mcp.client.streamable_http.streamablehttp_client`."""

    url: str
    """The URL of the server."""

    headers: dict[str, str] | None = None
    """The headers to send to the server."""

    timeout: float = 30
    """The timeout for the HTTP request in seconds. Defaults to `30`."""

    def __post_init__(self) -> None:
        if not self.url.endswith("/mcp"):
            self.url = self.url.removesuffix("/") + "/mcp"


@dataclass
class SSE:
    """Core parameters from `mcp.client.sse.sse_client`."""

    url: str
    """The URL of the server."""

    headers: dict[str, str] | None = None
    """The headers to send to the server."""

    timeout: float = 5
    """The timeout for the HTTP request in seconds. Defaults to `5`."""

    def __post_init__(self) -> None:
        if not self.url.endswith("/sse"):
            self.url = self.url.removesuffix("/") + "/sse"


class Client:
    """A client for interacting with an MCP server."""

    def __init__(
        self,
        params: Stdio | StreamableHTTP | SSE,
        enable_cache: bool = True,
    ) -> None:
        """Initialize the Client instance.

        Args:
            params: The parameters to connect to the server.
            enable_cache: Whether to cache the list result. Defaults to `True`.
        """
        self._params: Stdio | StreamableHTTP | SSE = params
        self._cache_enabled: bool = enable_cache
        self._event_bus: EventBus = EventBus()

        # The lock for protecting the following two cache-related variables.
        self._cache_lock: aiorwlock.RWLock = aiorwlock.RWLock()
        self._list_tools_result_cache: list[McpTool] | None = None
        self._cache_invalidated: bool = False

        self._client_session: ClientSession | None = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def __aenter__(self) -> Client:
        """Enter the async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        """Exit the async context manager and clean up resources."""
        await self.close()

    async def connect(self) -> None:
        """Connect to the MCP server."""
        if self._client_session:
            return

        ctx_manager: AbstractAsyncContextManager

        if isinstance(self._params, Stdio):
            ctx_manager = stdio_client(self._params)
        elif isinstance(self._params, StreamableHTTP):
            ctx_manager = streamablehttp_client(
                url=self._params.url,
                headers=self._params.headers,
                timeout=self._params.timeout,
            )
        elif isinstance(self._params, SSE):
            ctx_manager = sse_client(
                url=self._params.url,
                headers=self._params.headers,
                timeout=self._params.timeout,
            )
        else:
            raise TypeError(
                f"Expected Stdio, StreamableHTTP, or SSE parameters, got {type(self._params).__name__}"
            )

        try:
            transport = await self._exit_stack.enter_async_context(ctx_manager)
            # Handle different tuple lengths returned by transport contexts
            # streamablehttp_client returns (read_stream, write_stream, _)
            # sse_client and stdio_client return (read_stream, write_stream)
            if len(transport) == 3:
                read, write, _ = (
                    transport  # Ignore session ID callback for streamable-http
                )
            elif len(transport) == 2:
                read, write = transport
            else:
                raise ValueError(f"Unexpected transport tuple length: {len(transport)}")

            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write, message_handler=self._handle_message)
            )
            await session.initialize()

            self._client_session = session
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        """Close the connection to the MCP server and clean up resources."""
        if not self._client_session:
            return

        try:
            await self._exit_stack.aclose()
            self._client_session = None
        except Exception:
            pass

    async def invalidate_cache(self) -> None:
        """Invalidate the cache of the list tools result."""
        async with self._cache_lock.writer_lock:
            self._cache_invalidated = True

    async def get_tools(
        self, include: list[str] | None = None, exclude: list[str] | None = None
    ) -> list[Tool]:
        """Get the list of tools from the MCP server.

        Args:
            include: The list of tool names to include. If None, all tools are included.
            exclude: The list of tool names to exclude. If None, no tools are excluded.

        Returns:
            The list of callable tools from the server.
        """
        tools_list = await self._list_tools()

        def filter_tool(t: McpTool) -> bool:
            # First check if the tool should be excluded
            if exclude is not None and t.name in exclude:
                return False

            # Then check if the tool should be included
            if include is None:
                return True
            return t.name in include

        tools = [self._make_tool(t) for t in tools_list if filter_tool(t)]
        return tools

    async def _list_tools(self) -> list[McpTool]:
        """Get the list of tools from the MCP server with caching.

        Returns:
            The list of tools from the server.
        """
        if not self._client_session:
            return []

        # Return the cached result if the cache is enabled and not invalidated.
        async with self._cache_lock.reader_lock:
            if (
                self._cache_enabled
                and not self._cache_invalidated
                and self._list_tools_result_cache is not None
            ):
                return self._list_tools_result_cache

        async with self._cache_lock.writer_lock:
            # Reset the cache status.
            self._cache_invalidated = False

            # Fetch the tools from the server.
            result = await self._client_session.list_tools()
            self._list_tools_result_cache = result.tools
            return self._list_tools_result_cache

    def _make_tool(self, t: McpTool) -> Tool:
        return Tool(
            name=t.name,
            description=t.description or "",
            input_schema=t.inputSchema,
            output_schema=t.outputSchema,
            _client_session=self._client_session,
            _event_bus=self._event_bus,
        )

    async def _handle_message(
        self,
        message: RequestResponder[types.ServerRequest, types.ClientResult]
        | types.ServerNotification
        | Exception,
    ) -> None:
        if isinstance(message, Exception):
            raise message

        if isinstance(message, types.ServerNotification):
            if isinstance(message.root, types.ProgressNotification):
                params = message.root.params
                try:
                    progress_token = ProgressToken.load(params.progressToken)
                except ValueError:
                    # Ignore invalid progress token.
                    return

                await self._event_bus.publish(
                    call_id=progress_token.call_id,
                    event=ProgressEvent(
                        progress=params.progress,
                        total=params.total,
                        message=params.message,
                    ),
                )
