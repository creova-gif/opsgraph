#!/usr/bin/env python3
"""
OpsGraph — Minimal JSON-Schema Subset Validator
Zero-dependency validation for company profiles against
schema/company-profile.schema.json. Supports the subset of JSON Schema
actually used by OpsGraph schemas: type, required, properties, items,
minItems, enum, const, minimum. Returns a list of human-readable error
strings; empty list means valid.
"""

from __future__ import annotations

from typing import Any, Dict, List

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(instance: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Validate `instance` against a JSON-Schema subset; return error strings."""
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        check = _TYPE_CHECKS.get(expected_type)
        if check is not None and not check(instance):
            errors.append(f"{path}: expected {expected_type}, got {type(instance).__name__}")
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']!r}")

    if expected_type == "integer" and "minimum" in schema and instance < schema["minimum"]:
        errors.append(f"{path}: {instance} below minimum {schema['minimum']}")

    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}.{req}: required field missing")
        for key, subschema in props.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: {len(instance)} items below minItems {min_items}")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{i}]"))

    return errors
