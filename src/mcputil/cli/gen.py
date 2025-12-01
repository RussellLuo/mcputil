import os
import sys
from typing import Any

from ..client import StreamableHTTP, Parameters
from ..group import Group
from ..tool import Tool


def json_type_to_python_type(json_type: str) -> str:
    """
    Convert JSON schema type to Python type annotation.

    Args:
        json_type: The JSON schema type (string, integer, number, boolean, array, object)

    Returns:
        Python type annotation as string
    """
    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict[str, Any]",
        "null": "None",
    }

    return type_mapping.get(json_type, "Any")


def extract_return_type_from_output_schema(output_schema: dict[str, Any] | None) -> str:
    """
    Extract return type from tool output schema.

    Args:
        output_schema: The tool's output schema

    Returns:
        Python type annotation as string, defaults to "Any" if no schema or result property
    """
    if not output_schema:
        return "Any"

    result_schema = output_schema.get("properties", {}).get("result")
    if not result_schema:
        return "Any"

    result_type = result_schema.get("type")
    if not result_type:
        return "Any"

    return json_type_to_python_type(result_type)


def extract_parameters_from_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract parameter information from JSON schema.

    Args:
        schema: JSON schema dictionary

    Returns:
        List of parameter dictionaries with name, type, description, required info, and default value
    """
    parameters = []
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")
        python_type = json_type_to_python_type(param_type)

        parameter = {
            "name": param_name,
            "type": python_type,
            "description": param_info.get("description", ""),
            "required": param_name in required_fields,
        }

        # Extract default value if present
        if "default" in param_info:
            parameter["default"] = param_info["default"]

        parameters.append(parameter)

    return parameters


def _get_default_value(param: dict[str, Any]) -> str:
    """Get formatted default value for a parameter."""
    if "default" in param:
        return repr(param["default"])

    # Type-based defaults
    type_defaults = {
        "int": "0",
        "str": '""',
        "bool": "False",
        "list": "None",
        "dict[str, Any]": "None",
    }
    return type_defaults.get(param["type"], "None")


def generate_function_signature(
    function_name: str, parameters: list[dict[str, Any]], return_type: str = "Any"
) -> str:
    """
    Generate Python function signature with type hints.

    Args:
        function_name: Name of the function
        parameters: List of parameter dictionaries
        return_type: Return type annotation

    Returns:
        Function signature as string
    """
    param_strings = []

    for param in parameters:
        param_str = f"{param['name']}: {param['type']}"
        if not param["required"]:
            param_str += f" = {_get_default_value(param)}"
        param_strings.append(param_str)

    params = ", ".join(param_strings)
    return f"async def {function_name}({params}) -> {return_type}:"


def generate_function_body(
    server_name: str,
    function_name: str,
    parameters: list[dict[str, Any]],
    description: str,
) -> str:
    """
    Generate the function body that calls group.call_tool.

    Args:
        server_name: Name of the MCP server
        function_name: Name of the function/tool
        parameters: List of parameter dictionaries
        description: Function description

    Returns:
        Complete function body as string
    """
    # Generate docstring
    docstring_lines = [f'    """{description}']

    if parameters:
        docstring_lines.append("")
        docstring_lines.append("    Args:")
        for param in parameters:
            required_str = " (required)" if param["required"] else " (optional)"
            description = param["description"].strip() if param["description"] else ""
            docstring_lines.append(
                f"        {param['name']}: {description}{required_str}"
            )

    docstring_lines.append('    """')
    docstring = "\n".join(docstring_lines)

    # Generate parameter arguments for call_tool
    param_args = []
    for param in parameters:
        param_args.append(f'"{param["name"]}": {param["name"]}')

    if param_args:
        args_str = "{\n        " + ",\n        ".join(param_args) + "\n    }"
    else:
        args_str = "{}"

    # Generate function body
    body = f"""    arguments = {args_str}
    result = await group.call_tool("{server_name}", "{function_name}", **arguments)
    return await result.output()"""

    return f"{docstring}\n{body}"


def generate_python_function(server_name: str, tool: Tool) -> str:
    """
    Generate complete Python function code from server name and tool.

    Args:
        server_name: Name of the MCP server
        tool: Tool object containing schema information

    Returns:
        Complete Python function code as string
    """
    # Extract function information
    function_name = tool.name
    description = tool.description or f"Call {function_name} function"

    # Extract parameters from input schema
    parameters = extract_parameters_from_schema(tool.input_schema)

    # Extract return type from output schema
    return_type = extract_return_type_from_output_schema(tool.output_schema)

    # Generate function signature
    signature = generate_function_signature(function_name, parameters, return_type)

    # Generate function body
    body = generate_function_body(server_name, function_name, parameters, description)

    # Combine signature and body
    complete_function = f"{signature}\n{body}"

    return complete_function


def generate_group_file(servers: list[tuple[str, Parameters]]) -> str:
    """
    Generate the group.py file content.

    Args:
        servers: List of (server_name, Parameters) tuples

    Returns:
        Group file content as string
    """
    lines = [
        "import mcputil",
        "",
        "# Initialize group with servers",
        "params = {",
    ]

    for server_name, params in servers:
        if isinstance(params, StreamableHTTP):
            lines.extend(
                [
                    f'    "{server_name}": mcputil.StreamableHTTP(',
                    f'        url="{params.url}",',
                    f"        headers={params.headers},",
                    f"        timeout={params.timeout},",
                    f"    ),",
                ]
            )

    lines.extend(["}", "group = mcputil.Group(**params)"])

    return "\n".join(lines)


def generate_tool_file(server_name: str, tool: Tool) -> str:
    """
    Generate individual tool file content.

    Args:
        server_name: Name of the MCP server
        tool: Tool object containing schema information

    Returns:
        Tool file content as string
    """
    # Extract function information
    function_name = tool.name
    description = tool.description or f"Call {function_name} function"

    # Extract parameters from input schema
    parameters = extract_parameters_from_schema(tool.input_schema)

    # Extract return type from output schema
    return_type = extract_return_type_from_output_schema(tool.output_schema)

    # Generate function signature
    signature = generate_function_signature(function_name, parameters, return_type)

    # Generate function body
    body = generate_function_body(server_name, function_name, parameters, description)

    # Create complete file content
    file_content = [
        "from typing import Any",
        "from ..group import group",
        "",
        "",
        f"{signature}",
        f"{body}",
    ]

    return "\n".join(file_content)


async def get_tools_and_generate_files(
    servers: list[tuple[str, Parameters]], output_dir: str
):
    """
    Connect to servers, get their tools, and generate separate Python files.

    Args:
        servers: List of (server_name, Parameters) tuples
        output_dir: Directory to write the generated files
    """
    # Create group with all servers
    group_params = {name: params for name, params in servers}

    async with Group(**group_params) as group:
        # Get tools from all servers
        tools_by_server = await group.get_tools_grouped_by_server()

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Create an empty __init__.py to make the output as a package
        init_file_path = os.path.join(output_dir, "__init__.py")
        with open(init_file_path, "w") as f:
            f.write("")

        # Generate group.py file
        group_content = generate_group_file(servers)
        group_file_path = os.path.join(output_dir, "group.py")
        with open(group_file_path, "w") as f:
            f.write(group_content)
        print(f"Generated {group_file_path}", file=sys.stderr)

        # Generate individual tool files
        for server_name, tools in tools_by_server.items():
            if tools:
                # Create server directory
                server_dir = os.path.join(output_dir, server_name)
                os.makedirs(server_dir, exist_ok=True)

                # Create an empty __init__.py for the server package
                init_file_path = os.path.join(server_dir, "__init__.py")
                with open(init_file_path, "w") as f:
                    f.write("")

                # Generate individual tool files
                for tool in tools:
                    tool_content = generate_tool_file(server_name, tool)
                    tool_file_path = os.path.join(server_dir, f"{tool.name}.py")
                    with open(tool_file_path, "w") as f:
                        f.write(tool_content)
                    print(f"Generated {tool_file_path}", file=sys.stderr)
