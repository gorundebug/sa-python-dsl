"""Endpoint adapters bind a concrete API, unlike reusable business functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Stream
    from .validation import Validator


def validate_endpoint_function_ownership(validator: Validator) -> None:
    owners: dict[tuple[str, str, str, str], Stream] = {}
    for stream in validator.streams.values():
        if (stream.endpoint is None or stream.type not in {"Input", "Sink"}
                or stream.service.programming_language != "GoLang"):
            continue
        function = validator.function(stream)
        if function is None:
            continue
        name, package, public, module = function
        scope = "module:" + module if public and module.strip() else "service:" + stream.service.key
        identity = (scope, package, name, stream.type)
        previous = owners.get(identity)
        if previous is None:
            owners[identity] = stream
            continue
        assert previous.endpoint is not None
        if previous.endpoint is stream.endpoint:
            # Any number of caller-local Sinks may share the same endpoint.
            continue
        validator.add(
            "SG_SEMANTIC_DUPLICATE_IDENTITY", "semantic",
            f"endpoint adapter {name!r} is assigned to distinct endpoints; generated {stream.type} handlers collide",
            validator.stream_path(stream) + ".endpoint", "function", name,
            identity="endpointHandler", firstEndpoint=previous.endpoint.key,
            secondEndpoint=stream.endpoint.key,
            firstPath=validator.stream_path(previous) + ".endpoint",
            remediation="Give distinct API endpoint adapters distinct function names; keep shared business functions unchanged.",
        )
