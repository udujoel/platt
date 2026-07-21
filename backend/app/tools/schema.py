"""A minimal JSON-schema subset validator for tool call arguments.

Only the shapes actually used by tool schemas in this codebase are supported:
object roots, ``required``, ``additionalProperties: False``, primitive
``type``s, ``minLength``/``maxLength`` for strings, ``minimum``/``maximum``
for numbers, and ``enum``. This intentionally does not pull in a general
JSON-schema dependency for that small a surface.
"""

from __future__ import annotations

from typing import Any

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class SchemaValidationError(ValueError):
    """Raised when tool call arguments do not match the tool's declared schema."""


def validate_arguments(arguments: Any, schema: dict[str, Any]) -> None:
    if schema.get("type", "object") != "object":
        raise SchemaValidationError("tool schema root must be an object")
    if not isinstance(arguments, dict):
        raise SchemaValidationError("arguments must be a JSON object")

    properties: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])
    additional_allowed = schema.get("additionalProperties", True)

    missing = [name for name in required if name not in arguments]
    if missing:
        raise SchemaValidationError(f"missing required argument(s): {', '.join(missing)}")

    if not additional_allowed:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise SchemaValidationError(f"unexpected argument(s): {', '.join(unknown)}")

    for key, value in arguments.items():
        property_schema = properties.get(key)
        if property_schema is not None:
            _validate_value(key, value, property_schema)


def _validate_value(key: str, value: Any, property_schema: dict[str, Any]) -> None:
    expected_type = property_schema.get("type")
    if expected_type is not None:
        if expected_type not in _TYPE_MAP:
            raise SchemaValidationError(f"unsupported schema type for {key!r}: {expected_type}")
        if expected_type == "boolean":
            if not isinstance(value, bool):
                raise SchemaValidationError(f"{key!r} must be a boolean")
        elif expected_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise SchemaValidationError(f"{key!r} must be an integer")
        elif not isinstance(value, _TYPE_MAP[expected_type]):
            raise SchemaValidationError(f"{key!r} must be of type {expected_type}")

    if isinstance(value, str):
        min_length = property_schema.get("minLength")
        max_length = property_schema.get("maxLength")
        if min_length is not None and len(value) < min_length:
            raise SchemaValidationError(f"{key!r} must be at least {min_length} characters")
        if max_length is not None and len(value) > max_length:
            raise SchemaValidationError(f"{key!r} must be at most {max_length} characters")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = property_schema.get("minimum")
        maximum = property_schema.get("maximum")
        if minimum is not None and value < minimum:
            raise SchemaValidationError(f"{key!r} must be >= {minimum}")
        if maximum is not None and value > maximum:
            raise SchemaValidationError(f"{key!r} must be <= {maximum}")

    enum_values = property_schema.get("enum")
    if enum_values is not None and value not in enum_values:
        raise SchemaValidationError(f"{key!r} must be one of {enum_values}")
