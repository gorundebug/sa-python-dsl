"""Validate packaging policy against the packaged shared API, not graph rules."""
from __future__ import annotations

import re
from copy import deepcopy

from ._deployment_contract import SCHEMAS


def validate_deployment(value, *, effective=False):
    def check(schema, item):
        if "$ref" in schema:
            return check(SCHEMAS[schema["$ref"].rsplit("/", 1)[1]], item)
        if "oneOf" in schema:
            matches = 0
            for choice in schema["oneOf"]:
                try:
                    check(choice, item)
                    matches += 1
                except ValueError:
                    pass
            if matches != 1:
                raise ValueError("Deployment scalar does not match its supported types")
            return
        kind = schema.get("type")
        if kind == "object":
            if not isinstance(item, dict):
                raise ValueError("Deployment setting must be an object")
            required = schema.get("required", []) + (schema.get("x-effective-required", []) if effective else [])
            if any(key not in item for key in required):
                raise ValueError("Effective deployment setting lacks a required field")
            properties = schema.get("properties", {})
            extra = schema.get("additionalProperties")
            for key, child in item.items():
                if key in properties:
                    check(properties[key], child)
                elif isinstance(extra, dict):
                    check(extra, child)
                else:
                    raise ValueError("Deployment setting contains an unsupported field")
        elif kind == "array":
            if not isinstance(item, list):
                raise ValueError("Deployment setting must be a list")
            for child in item:
                check(schema["items"], child)
        elif kind == "boolean":
            if type(item) is not bool:
                raise ValueError("Deployment setting must be boolean")
        elif kind in ("integer", "number"):
            if type(item) not in ((int,) if kind == "integer" else (int, float)):
                raise ValueError("Deployment setting must be numeric")
            if ("minimum" in schema and item < schema["minimum"]) or ("maximum" in schema and item > schema["maximum"]):
                raise ValueError("Deployment number is outside its allowed range")
        elif kind == "string":
            if not isinstance(item, str):
                raise ValueError("Deployment setting must be text")
            if ("minLength" in schema and len(item) < schema["minLength"]) or ("maxLength" in schema and len(item) > schema["maxLength"]):
                raise ValueError("Deployment text has an invalid length")
            if "pattern" in schema and re.search(schema["pattern"], item) is None:
                raise ValueError("Deployment text has an invalid format")
        if "enum" in schema and item not in schema["enum"]:
            raise ValueError("Deployment setting must use a supported choice")

    # Diagnostics intentionally contain no submitted keys or values.
    check(SCHEMAS["KubernetesDeploymentSettings"], value)


def resolve_deployment(inherited, override):
    if override is None:
        return deepcopy(inherited)
    if isinstance(override, dict):
        if not override:
            return {}
        base = inherited if isinstance(inherited, dict) else {}
        return {key: resolve_deployment(base.get(key), override[key]) if key in override else deepcopy(base[key])
                for key in base.keys() | override.keys()}
    return deepcopy(override)
