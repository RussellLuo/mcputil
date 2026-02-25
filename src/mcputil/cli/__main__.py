#!/usr/bin/env python3
"""
mcputil - A command-line utility for MCP (Model Context Protocol) servers.

This tool allows you to connect to multiple MCP servers, retrieve their tools,
and generate Python function definitions for those tools.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ..client import StreamableHTTP, Stdio, Parameters
from .gen import get_tools_and_generate_files


def parse_single_server(
    server_name: str, server_config: dict
) -> tuple[str, Parameters]:
    """
    Parse a single server configuration dictionary and return server parameters.

    Args:
        server_name: Name of the server
        server_config: Dictionary containing server configuration

    Returns:
        Tuple of (server_name, Parameters object)

    Raises:
        ValueError: If the server configuration is invalid or missing required fields
    """
    if not isinstance(server_config, dict):
        raise ValueError(
            f"Server configuration for '{server_name}' must be a JSON object"
        )

    # Determine if this is a local (stdio) or remote (HTTP) server
    if "command" in server_config:
        # Local server using stdio
        command = server_config["command"]
        args = server_config.get("args", [])
        env = server_config.get("env")

        params = Stdio(command=command, args=args, env=env)
    elif "url" in server_config:
        # Remote server using HTTP
        url = server_config["url"]
        headers = server_config.get("headers")
        timeout = server_config.get("timeout", 30)

        params = StreamableHTTP(url=url, headers=headers, timeout=timeout)
    else:
        raise ValueError(
            f"Server '{server_name}' must have either 'command' (for Stdio) or 'url' (for HTTP-Streamable or SSE)"
        )

    return server_name, params


def parse_config_file(config_path: str) -> list[tuple[str, Parameters]]:
    """
    Parse MCP configuration file and return list of servers.

    Args:
        config_path: Path to the mcp.json configuration file

    Returns:
        List of (server_name, Parameters) tuples

    Raises:
        ValueError: If the config file is invalid or missing required fields
        FileNotFoundError: If the config file doesn't exist
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")

    if not isinstance(config, dict):
        raise ValueError("Configuration file must contain a JSON object")

    if "mcpServers" not in config:
        raise ValueError("Configuration file must contain 'mcpServers' field")

    mcp_servers = config["mcpServers"]
    if not isinstance(mcp_servers, dict):
        raise ValueError("'mcpServers' must be a JSON object")

    servers = []
    for server_name, server_config in mcp_servers.items():
        server_name, params = parse_single_server(server_name, server_config)
        servers.append((server_name, params))

    return servers


def parse_server_config(server_json: str) -> tuple[str, Parameters]:
    """
    Parse server configuration from JSON string.

    Args:
        server_json: JSON string containing server configuration

    Returns:
        Tuple of (server_name, Parameters object)

    Raises:
        ValueError: If the JSON is invalid or missing required fields
    """
    try:
        config = json.loads(server_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in server configuration: {e}")

    if not isinstance(config, dict):
        raise ValueError("Server configuration must be a JSON object")

    if "name" not in config:
        raise ValueError("Server configuration must include 'name' field")

    server_name = config["name"]

    # Remove the name field from config before passing to parse_single_server
    server_config = {k: v for k, v in config.items() if k != "name"}

    return parse_single_server(server_name, server_config)


async def main_async():
    """Main async function."""
    parser = argparse.ArgumentParser(
        description="mcputil - Generate Python functions from MCP server tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default configuration file (.mcputil/mcp.json or ~/.mcputil/mcp.json)
  mcputil

  # Single server via --server
  mcputil --server='{"name": "math", "url": "http://localhost:8000"}'

  # Multiple servers via --server
  mcputil --server='{"name": "math", "url": "http://localhost:8000"}' \\
          --server='{"name": "weather", "url": "http://localhost:8001"}'

  # With custom headers and timeout via --server
  mcputil --server='{"name": "api", "url": "http://api.example.com", "headers": {"Authorization": "Bearer token"}, "timeout": 60}'

  # Using specific configuration file
  mcputil --config mcp.json

  # Configuration file with custom output directory
  mcputil --config mcp.json --output my_servers
        """,
    )
    parser.add_argument(
        "-s",
        "--server",
        action="append",
        help='Server configuration as JSON. Format: {"name": "server_name", "url": "server_url", "headers": {...}, "timeout": 30}',
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Path to MCP configuration file (mcp.json format). Default: .mcputil/mcp.json or ~/.mcputil/mcp.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="servers",
        help="Output directory path. Default: '%(default)s'",
    )
    args = parser.parse_args()

    try:
        # Validate arguments
        if args.server and args.config:
            parser.error("Cannot specify both --server and --config")

        # Parse server configurations
        servers = []

        if args.config:
            # Parse from configuration file specified by user
            servers = parse_config_file(args.config)
        elif not args.server:
            # Try default config paths if no --server is provided
            default_paths = [
                Path.cwd() / ".mcputil" / "mcp.json",
                Path.home() / ".mcputil" / "mcp.json",
            ]

            config_found = False
            for default_path in default_paths:
                if default_path.exists():
                    print(f"Using configuration file: {default_path}", file=sys.stderr)
                    servers = parse_config_file(str(default_path))
                    config_found = True
                    break

            if not config_found:
                parser.error(
                    "No server configuration found. Either:\n"
                    "  - Use --server to specify server(s)\n"
                    "  - Use --config to specify a configuration file\n"
                    "  - Create a configuration file at .mcputil/mcp.json or ~/.mcputil/mcp.json"
                )
        else:
            # Parse from --server arguments
            for server_json in args.server:
                server_name, params = parse_server_config(server_json)
                servers.append((server_name, params))

        print(f"Connecting to {len(servers)} server(s)...", file=sys.stderr)

        # Generate Python files
        await get_tools_and_generate_files(servers, args.output)

        print(f"Generated files written to {args.output}/", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
