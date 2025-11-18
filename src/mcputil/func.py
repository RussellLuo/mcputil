from __future__ import annotations

from inspect import Signature, Parameter
from typing import Any


class ParamName(str):
    """A custom string class for special parameter names.

    This is mainly used to handle parameter names that are Python keywords (e.g. "from").
    """

    prefix = "MCPUTIL__"

    def unwrap(self) -> str:
        if self.startswith(self.prefix):
            return self[len(self.prefix) :]
        return self

    @classmethod
    def wrap(cls, value: str) -> ParamName:
        if value.startswith(cls.prefix):
            # Already wrapped, just return as is.
            return cls(value)
        return cls(f"{cls.prefix}{value}")


# Mapping from JSON schema types to Python types
JSON_TYPE_MAP = {
    "integer": int,
    "number": float,
    "string": str,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def gen_anno_and_sig(
    params_schema: dict[str, Any], return_schema: dict[str, Any] | None = None
) -> tuple[dict[str, Any], Signature]:
    """
    Generate annotations and signature from JSON Schema.

    Args:
        params_schema: Parameter schema, example:
            {
                "x": {"type": "integer"},
                "y": {"type": "string", "optional": True, "default": "hello"}
            }
        return_schema: Return value schema, example: {"type": "string"}

    Returns:
        Tuple of annotations dict and function signature.
    """
    # Generate __annotations__
    annotations = {}
    parameters = []
    for param_name, info in params_schema.items():
        type_value = info.get("type")
        if isinstance(type_value, list) and type_value:
            # An array of strings (e.g. ["number", "string"])
            # See https://json-schema.org/understanding-json-schema/reference/type.
            py_type = JSON_TYPE_MAP.get(type_value[0], Any)
        else:
            py_type = JSON_TYPE_MAP.get(type_value, Any)
        default = info.get("default", Parameter.empty)
        if info.get("optional", False) and "default" not in info:
            default = None
        try:
            param = Parameter(
                param_name,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=py_type,
            )
        except ValueError:
            # ValueError: '<param_name>' is not a valid parameter name
            param_name = ParamName.wrap(param_name)
            param = Parameter(
                param_name,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=py_type,
            )
        parameters.append(param)
        annotations[param_name] = py_type

    # Return value type
    if return_schema:
        annotations["return"] = JSON_TYPE_MAP.get(return_schema.get("type"), Any)
        return_annotation = annotations["return"]
    else:
        return_annotation = Signature.empty

    # Place positional arguments before keyword arguments.
    positional_params = [p for p in parameters if p.default is Parameter.empty]
    keyword_params = [p for p in parameters if p.default is not Parameter.empty]
    sorted_params = positional_params + keyword_params

    sig = Signature(sorted_params, return_annotation=return_annotation)

    return annotations, sig
