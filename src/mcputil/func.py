from inspect import Signature, Parameter
from typing import Any

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
        py_type = JSON_TYPE_MAP.get(info.get("type"), Any)
        default = info.get("default", Parameter.empty)
        if info.get("optional", False) and "default" not in info:
            default = None
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

    sig = Signature(parameters, return_annotation=return_annotation)

    return annotations, sig
