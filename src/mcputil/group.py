from __future__ import annotations

import asyncio
from typing import Any

import aiorwlock

from .client import Client, Parameters
from .tool import Result, Tool


class Group:
    """A group of MCP servers that can be managed collectively."""

    def __init__(self, **params: Parameters) -> None:
        """Initialize the Group with named server parameters.

        Args:
            **params: Named server parameters where the key is the server_name and value is the Parameters instance.
                     Example: Group(name1=stdio_params, name2=streamablehttp_params)
        """
        self._clients: dict[str, Client] = {}
        for server_name, param in params.items():
            self._clients[server_name] = Client(param)

        # The lock for protecting the tools cache
        self._cache_lock: aiorwlock.RWLock = aiorwlock.RWLock()
        self._tools_cache: dict[str, dict[str, Tool]] = {}

    async def __aenter__(self) -> Group:
        """Enter the async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        """Exit the async context manager and clean up resources."""
        await self.close()

    async def connect(self) -> None:
        """Connect to all MCP servers in the group."""
        tasks = []
        for client in self._clients.values():
            tasks.append(client.connect())

        # Connect all clients concurrently
        await asyncio.gather(*tasks)

        # Clear tools cache after connecting
        async with self._cache_lock.writer_lock:
            self._tools_cache.clear()

    async def close(self) -> None:
        """Close connections to all MCP servers in the group."""
        tasks = []
        for client in self._clients.values():
            tasks.append(client.close())

        # Close all clients concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Clear tools cache after closing
        async with self._cache_lock.writer_lock:
            self._tools_cache.clear()

    @property
    def clients(self) -> dict[str, Client]:
        """Get the dictionary of clients in the group."""
        return self._clients.copy()  # Return a copy to prevent external modifications

    async def get_tools(self, server_name: str | None = None) -> list[Tool]:
        """Get all tools available on a specific server or from all servers.

        Args:
            server_name: The name of the server to get tools from.
            If None, get tools from all servers. Defaults to None.

        Returns:
            List of tools available on the server.

        Raises:
            KeyError: If the server_name is not found in the group.
        """
        if server_name is not None:
            tools_dict = await self._get_tools(server_name)
            return list(tools_dict.values())

        tools_grouped = await self.get_tools_grouped_by_server()
        tools = [tool for sublist in tools_grouped.values() for tool in sublist]
        return tools

    async def get_tools_grouped_by_server(self) -> dict[str, list[Tool]]:
        """Get all tools from all servers grouped by server name.

        Returns:
            Dictionary mapping server names to their available tools.
        """
        result: dict[str, list[Tool]] = {}

        for server_name in self._clients:
            tools_dict = await self._get_tools(server_name)
            result[server_name] = list(tools_dict.values())

        return result

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        call_id: str | None = None,
        **kwargs: Any,
    ) -> Result:
        """Call a tool on a specific server.

        Args:
            server_name: The name of the server to call the tool on.
            tool_name: The name of the tool to call.
            call_id: Optional call ID for tracking progress.
            **kwargs: Arguments to pass to the tool.

        Returns:
            The result of the tool call.

        Raises:
            KeyError: If the server_name is not found in the group.
            ValueError: If the tool_name is not found on the specified server.
        """
        tools_dict = await self._get_tools(server_name)
        tool = tools_dict.get(tool_name)
        if tool is None:
            available_tools = list(tools_dict.keys())
            raise ValueError(
                f"Tool '{tool_name}' not found on server '{server_name}'. Available tools: {available_tools}"
            )

        return await tool.call(call_id=call_id, **kwargs)

    async def _get_tools(self, server_name: str) -> dict[str, Tool]:
        """Get all tools available on a specific server with caching. Used internally.

        Args:
            server_name: The name of the server to get tools from.

        Returns:
            Dictionary mapping tool names to Tool objects.

        Raises:
            KeyError: If the server_name is not found in the group.
        """
        if server_name not in self._clients:
            raise KeyError(
                f"Server '{server_name}' not found in group. Available servers: {list(self._clients.keys())}"
            )

        # Check cache first with reader lock
        async with self._cache_lock.reader_lock:
            server_tools = self._tools_cache.get(server_name)
            if server_tools is not None:
                return server_tools

        # Cache miss, fetch from client and update cache with writer lock
        async with self._cache_lock.writer_lock:
            # Double-check: another coroutine might have updated the cache
            server_tools = self._tools_cache.get(server_name)
            if server_tools is not None:
                return server_tools

            # Fetch from client and update cache
            client = self._clients[server_name]
            tools = await client.get_tools()

            server_tools = {tool.name: tool for tool in tools}
            self._tools_cache[server_name] = server_tools
            return server_tools

    async def invalidate_cache(self, server_name: str | None = None) -> None:
        """Invalidate the tools cache for a specific server or all servers.

        Args:
            server_name: The name of the server to invalidate cache for.
                        If None, invalidates cache for all servers.
        """
        if server_name is None:
            # Invalidate cache for all servers
            async with self._cache_lock.writer_lock:
                self._tools_cache.clear()

            tasks = []
            for client in self._clients.values():
                tasks.append(client.invalidate_cache())
            await asyncio.gather(*tasks)
        else:
            if server_name not in self._clients:
                raise KeyError(
                    f"Server '{server_name}' not found in group. Available servers: {list(self._clients.keys())}"
                )

            # Invalidate cache for specific server
            async with self._cache_lock.writer_lock:
                self._tools_cache.pop(server_name, None)

            await self._clients[server_name].invalidate_cache()
