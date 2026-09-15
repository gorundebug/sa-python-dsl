"""Validate canonical components using inert, typed model objects only.

This boundary never evaluates Python or replaces full schema/capability checks.
"""
from __future__ import annotations

from collections.abc import Iterable

from .component_validation import _JSONValue, _json_object, validate_components
from .model import Appearance, Connector, Endpoint, Function, Link, Pipeline, Project, Service, Stream
from .validation import Diagnostic, Validator
from .visual_components import ComponentMetadata, _mapping, normalize_components


class ComponentValidationError(ValueError):
    def __init__(self, diagnostics: Iterable[Diagnostic]) -> None:
        values = tuple(diagnostics)
        self.diagnostics: tuple[dict[str, _JSONValue], ...] = tuple(_json_object(item.to_dict()) for item in values)
        super().__init__("; ".join(str(item) for item in values))


def _string(value: object, path: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    return value


def _properties(raw: dict[str, object], excluded: set[str]) -> dict[str, _JSONValue]:
    return _json_object({key: value for key, value in raw.items() if key not in excluded})


def _stream_reference(value: object, streams: dict[str, Stream], path: str) -> Stream | None:
    key = _string(value, path)
    if not key:
        return None
    if key not in streams:
        raise ValueError(f"Unknown stream reference at {path}: {key}")
    return streams[key]


def _connectors(document: dict[str, object], project: Project) -> dict[str, Endpoint]:
    endpoints: dict[str, Endpoint] = {}
    for key, value in _mapping(document.get("dataConnectors", {}), "dataConnectors").items():
        raw = _mapping(value, f"dataConnectors.{key}")
        connector = Connector(key, _string(raw.get("name"), "connector.name", key), _string(raw.get("type"), "connector.type"))
        project.connectors[key] = connector
        for endpoint_key, endpoint_value in _mapping(raw.get("endpoints", {}), "connector.endpoints").items():
            if endpoint_key in endpoints:
                raise ValueError(f"Duplicate endpoint key: {endpoint_key}")
            endpoint_raw = _mapping(endpoint_value, f"endpoints.{endpoint_key}")
            endpoint = Endpoint(endpoint_key, _string(endpoint_raw.get("name"), "endpoint.name", endpoint_key), connector, Function(""))
            endpoints[endpoint_key] = endpoint
            connector.endpoints[endpoint_key] = endpoint
    return endpoints


def _service(
    key: str, raw: dict[str, object], metadata: ComponentMetadata,
    pipelines: dict[str, object], endpoints: dict[str, Endpoint],
) -> Service:
    service = Service(
        key, _string(raw.get("name"), "service.name", key),
        _string(raw.get("programmingLanguage"), "service.programmingLanguage"),
        _string(raw.get("modulePath"), "service.modulePath"),
        properties=_properties(raw, {"name", "programmingLanguage", "modulePath", "appearance", "pipelines", "links"}),
    )
    streams: dict[str, Stream] = {}
    records: dict[str, dict[str, object]] = {}
    members: dict[tuple[str, str], Stream] = {}
    for pipeline_key, pipeline_value in pipelines.items():
        pipeline = Pipeline(pipeline_key, pipeline_key, service)
        service.pipelines[pipeline_key] = pipeline
        for stream_key, stream_value in _mapping(pipeline_value, f"pipelines.{pipeline_key}").items():
            if stream_key in streams:
                raise ValueError(f"Duplicate stream key in service {key}: {stream_key}")
            stream_raw = _mapping(stream_value, f"pipelines.{pipeline_key}.{stream_key}")
            stream = Stream(
                stream_key, _string(stream_raw.get("name"), "stream.name", stream_key),
                _string(stream_raw.get("type"), "stream.type"), service, pipeline,
                properties=_properties(stream_raw, {"name", "type", "source", "sources", "errorStream", "endpoint", "appearance"}),
            )
            streams[stream_key] = stream
            records[stream_key] = stream_raw
            members[pipeline_key, stream_key] = stream
            pipeline.streams[stream_key] = stream
    for stream_key, stream in streams.items():
        stream_raw = records[stream_key]
        path = f"services.{key}.pipelines.{stream.pipeline.key}.{stream_key}"
        stream.source = _stream_reference(stream_raw.get("source"), streams, path + ".source")
        stream.error_stream = _stream_reference(stream_raw.get("errorStream"), streams, path + ".errorStream")
        sources = stream_raw.get("sources")
        if sources is not None:
            if not isinstance(sources, list):
                raise ValueError(f"{path}.sources must be an array")
            for source_key in sources:
                source = _stream_reference(source_key, streams, path + ".sources")
                if source is None:
                    raise ValueError(f"{path}.sources must contain non-empty stream references")
                stream.sources.append(source)
        endpoint_key = _string(stream_raw.get("endpoint"), path + ".endpoint")
        if endpoint_key:
            if endpoint_key not in endpoints:
                raise ValueError(f"Unknown endpoint reference at {path}: {endpoint_key}")
            stream.endpoint = endpoints[endpoint_key]
    for link_key, link_value in _mapping(raw.get("links", {}), "service.links").items():
        link_raw = _mapping(link_value, f"links.{link_key}")
        source = _stream_reference(link_raw.get("from"), streams, f"links.{link_key}.from")
        target = _stream_reference(link_raw.get("to"), streams, f"links.{link_key}.to")
        if source is None or target is None:
            raise ValueError(f"Link {link_key} must reference its source and target")
        service.links[link_key] = Link(link_key, source, target, _properties(link_raw, {"from", "to"}))
    for definition in metadata["groups"].values():
        component = service.component(definition["name"], description=definition.get("description"))
        for fragment in definition["fragments"]:
            position = fragment.get("position", {})
            component.fragment(
                *(members[pipeline, stream] for pipeline, stream in fragment["streams"]),
                appearance=Appearance(x=position.get("x"), y=position.get("y")),
            )
    return service


def validate_canonical_components(value: object) -> list[Diagnostic]:
    document = _mapping(value, "document")
    services = _mapping(document.get("services", {}), "services")
    selected: list[tuple[str, dict[str, object], object]] = []
    for key, service_value in services.items():
        raw = _mapping(service_value, f"services.{key}")
        appearance = _mapping(raw.get("appearance") or {}, "service.appearance")
        if appearance.get("components") is not None:
            selected.append((key, raw, appearance["components"]))
    if not selected:
        return []
    project = Project("Canonical components")
    endpoints = _connectors(document, project)
    for key, raw, metadata_value in selected:
        pipelines = _mapping(raw.get("pipelines", {}), "service.pipelines")
        references = [(pipeline, stream) for pipeline, records in pipelines.items()
                      for stream in _mapping(records, f"pipelines.{pipeline}")]
        metadata = normalize_components(metadata_value, references)
        project.services[key] = _service(key, raw, metadata, pipelines, endpoints)
    validator = Validator(project)
    validate_components(validator)
    return sorted(validator.values, key=lambda item: (item.path, item.code, item.message))


def require_canonical_components(document: object) -> None:
    diagnostics = validate_canonical_components(document)
    if diagnostics:
        raise ComponentValidationError(diagnostics)
