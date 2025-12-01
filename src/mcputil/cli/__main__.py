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

from ..client import StreamableHTTP, Parameters
from .gen import get_tools_and_generate_files


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

    if "url" not in config:
        raise ValueError("Server configuration must include 'url' field")

    server_name = config["name"]
    url = config["url"]
    headers = config.get("headers")
    timeout = config.get("timeout", 30)

    # Create StreamableHTTP parameters (as requested in the user's requirements)
    params = StreamableHTTP(url=url, headers=headers, timeout=timeout)

    return server_name, params


async def main_async():
    """Main async function."""
    parser = argparse.ArgumentParser(
        description="mcputil - Generate Python functions from MCP server tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single server
  mcputil --server='{"name": "math", "url": "http://localhost:8000"}'
  
  # Multiple servers
  mcputil --server='{"name": "math", "url": "http://localhost:8000"}' \\
          --server='{"name": "weather", "url": "http://localhost:8001"}'
  
  # With custom headers and timeout
  mcputil --server='{"name": "api", "url": "http://api.example.com", "headers": {"Authorization": "Bearer token"}, "timeout": 60}'
        """,
    )
    parser.add_argument(
        "--server",
        action="append",
        required=True,
        help='Server configuration as JSON. Format: {"name": "server_name", "url": "server_url", "headers": {...}, "timeout": 30}',
    )
    parser.add_argument(
        "-o",
        "--output",
        default="servers",
        help="Output directory path. Default: '%(default)s'",
    )
    args = parser.parse_args()

    try:
        # Parse server configurations
        servers = []
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
