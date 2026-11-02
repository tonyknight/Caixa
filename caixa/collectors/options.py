"""Validating a collector's options against its JSON Schema (a useful subset, no dependencies).

Supported: an object schema whose `properties` have `type` (`string`, `integer`, `number`,
`boolean`), `enum`, `minimum`, `maximum` and `default`; `required`; and
`additionalProperties: false` (the default here: unknown options are refused). Every problem is
reported at once, each naming the option.
"""

from __future__ import annotations

from typing import Any, Mapping

_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


class OptionsError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def defaults(schema: Mapping[str, Any]) -> dict[str, Any]:
    """The values the schema supplies for options nobody set."""
    return {
        name: spec["default"]
        for name, spec in schema.get("properties", {}).items()
        if "default" in spec
    }


def validate(
    schema: Mapping[str, Any], options: Mapping[str, Any], subject: str = "this source"
) -> dict[str, Any]:
    """The options with defaults filled in; raises `OptionsError` listing every problem."""
    properties: Mapping[str, Any] = schema.get("properties", {})
    errors: list[str] = []
    cleaned = {**defaults(schema), **options}
    for name in options:
        if name not in properties:
            errors.append(f"'{name}' is not an option of {subject}.")
    for name in schema.get("required", []):
        if name not in cleaned:
            errors.append(f"'{name}' is required.")
    for name, value in cleaned.items():
        spec = properties.get(name)
        if spec is None:
            continue
        kind = spec.get("type")
        if kind in _TYPES:
            is_bool = isinstance(value, bool)
            fits = isinstance(value, _TYPES[kind]) and (is_bool == (kind == "boolean"))
            if kind == "integer" and isinstance(value, float):
                fits = False
            if not fits:
                errors.append(f"'{name}' must be a {kind}.")
                continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"'{name}' must be one of {', '.join(map(str, spec['enum']))}.")
        if "minimum" in spec and isinstance(value, (int, float)) and value < spec["minimum"]:
            errors.append(f"'{name}' must be at least {spec['minimum']}.")
        if "maximum" in spec and isinstance(value, (int, float)) and value > spec["maximum"]:
            errors.append(f"'{name}' must be at most {spec['maximum']}.")
    if errors:
        raise OptionsError(errors)
    return cleaned
