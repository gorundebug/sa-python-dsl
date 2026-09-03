from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import yaml

from .auth import CognitoAuthenticator, load_env


DEFAULT_API_URL = "https://0pc6ljy0hg.execute-api.us-east-1.amazonaws.com/test"
GENERATE_CODE_PATH = "/service_architect/generateCode"
_OMIT = object()

_ENUM_VALUES = {
    "streamType": {
        "Input": 1, "Map": 2, "Filter": 3, "Join": 4, "MultiJoin": 5,
        "Process": 6, "FlatMap": 7, "FlatMapIterable": 8, "KeyBy": 9,
        "Merge": 10, "Split": 11, "Case": 12, "Sink": 13, "CycleLink": 14,
        "Error": 15, "Delay": 16, "When": 17,
    },
    "callSemantics": {
        "Inherited": 1, "FunctionCall": 2, "TaskPool": 3,
        "PriorityTaskPool": 4, "ParallelCall": 5,
    },
    "programmingLanguage": {
        "GoLang": 1, "CppUserver": 2, "Python": 3, "Rust": 4,
        "CppBoost": 5, "TypeScript": 6,
    },
    "connectorType": {"HTTP": 1, "gRPC": 2, "Kafka": 3, "Custom": 4, "Cron": 5, "Temporal": 6},
    "joinType": {"Inner": 1, "Left": 2, "Right": 3, "Outer": 4},
    "joinStorage": {"HashMap": 1, "RocksDB": 2, "Aerospike": 3},
    "processPattern": {"Execute": 1, "Collect": 2},
    "definitionFormat": {"Native": 1, "Protobuf": 2, "FlatBuffers": 3, "CapNProto": 4, "OpenAPI": 5},
    "grpcMethodType": {"NoStreaming": 1, "ClientStreaming": 2, "ServerStreaming": 4, "BidirectionalStreaming": 5},
}


class _Response(Protocol):
    headers: Mapping[str, str]
    status: int

    def read(self) -> bytes: ...

    def __enter__(self) -> _Response: ...

    def __exit__(self, *args: object) -> None: ...


class CodeGenerationError(RuntimeError):
    """A rejected request or malformed response from Service Architect."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


@dataclass(frozen=True, slots=True)
class GeneratedProjectArchive:
    filename: str
    content: bytes

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.content)
        return destination


def _header(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            return value
    return None


def _archive_filename(content_disposition: str | None) -> str:
    if not content_disposition:
        return "download.zip"
    encoded = re.search(
        r"filename\*\s*=\s*UTF-8''([^;]+)", content_disposition, re.IGNORECASE
    )
    if encoded:
        return Path(urllib.parse.unquote(encoded.group(1).strip())).name
    regular = re.search(
        r'filename\s*=\s*(?:"([^"]+)"|([^;]+))',
        content_disposition,
        re.IGNORECASE,
    )
    if regular:
        return Path((regular.group(1) or regular.group(2)).strip()).name
    return "download.zip"


def _json_or_text(content: bytes) -> Any:
    text = content.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _json_compatible(value: Any) -> Any:
    if type(value).__name__ == "_ExplicitNull":
        return _OMIT
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            converted = _json_compatible(item)
            if converted is not _OMIT:
                result[key] = converted
        return result
    if isinstance(value, (list, tuple)):
        return [converted for item in value if (converted := _json_compatible(item)) is not _OMIT]
    return value


def _enum(group: str, value: Any) -> Any:
    return _ENUM_VALUES[group].get(value, value)


def to_api_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convert the symbolic YAML document to the designer's flat JSON API model."""
    document = _json_compatible(document)
    stream_ids: dict[str, int] = {}
    endpoint_ids: dict[str, int] = {}
    type_names = {
        key: value.get("name", key)
        for key, value in (document.get("types") or {}).items()
    }

    services = []
    streams = []
    links = []
    next_stream_id = 0
    for service_id, (_, service) in enumerate(
        (document.get("services") or {}).items(), start=1
    ):
        appearance = service.get("appearance") or {}
        service_value = {"id": service_id, "color": "#D2E5FF"}
        for key, value in service.items():
            if key in {"links", "pipelines", "appearance"}:
                continue
            if key == "defaultCallSemantics":
                value = _enum("callSemantics", value)
            elif key == "programmingLanguage":
                value = _enum("programmingLanguage", value)
            service_value[key] = value
        if "color" in appearance:
            service_value["color"] = appearance["color"]
        services.append(service_value)

        for pipeline_name, pipeline in (service.get("pipelines") or {}).items():
            for stream_key, stream in pipeline.items():
                next_stream_id += 1
                stream_ids[stream_key] = next_stream_id
                position = (
                    ((appearance.get("pipelines") or {}).get(pipeline_name) or {}).get(stream_key)
                    or {}
                )
                streams.append(
                    {
                        "id": next_stream_id,
                        "idService": service_id,
                        "idSource": 0,
                        "xPos": position.get("x", 0),
                        "yPos": position.get("y", 0),
                        **({"pipeline": pipeline_name} if pipeline_name != "default" else {}),
                        "_raw": stream,
                    }
                )
        links.extend((service.get("links") or {}).values())

    data_connectors = []
    endpoints = []
    next_endpoint_id = 0
    for connector_id, (_, connector) in enumerate(
        (document.get("dataConnectors") or {}).items(), start=1
    ):
        connector_value = {"id": connector_id}
        for key, value in connector.items():
            if key == "endpoints":
                continue
            connector_value[key] = (
                _enum("connectorType", value) if key == "type" else value
            )
        data_connectors.append(connector_value)
        for endpoint_key, endpoint in (connector.get("endpoints") or {}).items():
            next_endpoint_id += 1
            endpoint_ids[endpoint_key] = next_endpoint_id
            endpoint_value = {
                "id": next_endpoint_id,
                "idDataConnector": connector_id,
            }
            for key, value in endpoint.items():
                endpoint_value[key] = (
                    _enum("grpcMethodType", value)
                    if key == "grpcMethodType"
                    else value
                )
            endpoints.append(endpoint_value)

    resolved_streams = []
    for stream in streams:
        raw = stream.pop("_raw")
        for key, value in raw.items():
            if key == "type":
                stream["type"] = _enum("streamType", value)
            elif key == "source":
                stream["idSource"] = stream_ids.get(value, 0)
            elif key == "sources":
                stream["idSources"] = [stream_ids.get(item, 0) for item in value]
            elif key == "endpoint":
                stream["idEndpoint"] = endpoint_ids.get(value, 0)
            elif key == "errorStream":
                stream["idErrorConsumer"] = stream_ids.get(value, 0)
            elif key in {"valueType", "keyType"}:
                stream[key] = type_names.get(value, value)
            elif key == "joinType":
                stream[key] = _enum("joinType", value)
            elif key == "joinStorage":
                stream[key] = _enum("joinStorage", value)
            elif key == "pattern":
                stream[key] = _enum("processPattern", value)
            else:
                stream[key] = value
        resolved_streams.append(stream)

    resolved_links = []
    for link in links:
        resolved = {}
        for key, value in link.items():
            if key in {"from", "to"}:
                resolved[key] = stream_ids.get(value, value)
            elif key == "callSemantics":
                resolved[key] = _enum("callSemantics", value)
            else:
                resolved[key] = value
        resolved_links.append(resolved)

    types = []
    for key, value in (document.get("types") or {}).items():
        converted = {"name": value.get("name", key)}
        for field, field_value in value.items():
            if field == "name":
                continue
            converted[field] = (
                _enum("definitionFormat", field_value)
                if field == "definitionFormat"
                else field_value
            )
        types.append(converted)

    return {
        "settings": document.get("settings") or {},
        "streams": resolved_streams,
        "services": services,
        "dataConnectors": data_connectors,
        "endpoints": endpoints,
        "types": types,
        "links": resolved_links,
        "pools": list((document.get("pools") or {}).values()),
        "modules": list((document.get("modules") or {}).values()),
    }


def yaml_to_api_document(
    source: str | Path | Mapping[str, Any],
) -> dict[str, Any]:
    """Port of the designer's fromYaml(...).toJSON() conversion."""
    if isinstance(source, Mapping):
        document = source
    elif isinstance(source, Path):
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    else:
        candidate = Path(source)
        if "\n" not in source and candidate.is_file():
            document = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        else:
            document = yaml.safe_load(source)
    if not isinstance(document, Mapping):
        raise ValueError("Service Architect YAML root must be a mapping")
    return to_api_document(document)


def _error_message(payload: Any) -> str:
    if isinstance(payload, Mapping):
        for key in ("message", "error", "body"):
            value = payload.get(key)
            if value:
                if isinstance(value, str):
                    try:
                        decoded = json.loads(value)
                    except json.JSONDecodeError:
                        return value
                    return _error_message(decoded)
                return _error_message(value)
    if payload not in (None, ""):
        return str(payload)
    return "Service Architect code generation failed"


class ServiceArchitectClient:
    def __init__(
        self,
        *,
        id_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        base_url: str | None = None,
        timeout: float = 120,
        opener: Callable[..., _Response] | None = None,
    ) -> None:
        if id_token is not None and not id_token.strip():
            id_token = None
        if id_token is None and (not username or not password):
            raise ValueError("provide id_token or Cognito username and password")
        self.id_token = id_token
        self.username = username
        self.password = password
        self.base_url = (
            base_url
            or os.environ.get("SERVICE_ARCHITECT_API_URL")
            or DEFAULT_API_URL
        ).rstrip("/")
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen

    @classmethod
    def from_env(
        cls,
        env_file: str | Path = ".env",
        **overrides: Any,
    ) -> ServiceArchitectClient:
        values = load_env(env_file)
        options = {
            "id_token": values.get("SERVICE_ARCHITECT_ID_TOKEN") or None,
            "username": values.get("SERVICE_ARCHITECT_USERNAME") or None,
            "password": values.get("SERVICE_ARCHITECT_PASSWORD") or None,
            "base_url": values.get("SERVICE_ARCHITECT_API_URL") or None,
        }
        options.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**options)

    def _token(self) -> str:
        if self.id_token is None:
            self.id_token = CognitoAuthenticator(
                username=self.username or "",
                password=self.password or "",
            ).authenticate()
        return self.id_token

    def generate_code(self, project: Any) -> GeneratedProjectArchive:
        if not hasattr(project, "to_document"):
            raise TypeError("project must provide to_document()")
        request = urllib.request.Request(
            f"{self.base_url}{GENERATE_CODE_PATH}",
            data=json.dumps(yaml_to_api_document(project.to_yaml())).encode("utf-8"),
            headers={
                "Accept": "application/json, application/zip",
                "Authorization": self._token(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                status_code = getattr(response, "status", 200)
                response_headers = dict(response.headers.items())
                content = response.read()
        except urllib.error.HTTPError as error:
            details = _json_or_text(error.read())
            raise CodeGenerationError(
                _error_message(details),
                status_code=error.code,
                details=details,
            ) from error
        except urllib.error.URLError as error:
            raise CodeGenerationError(
                f"Cannot reach Service Architect: {error.reason}",
                details=str(error.reason),
            ) from error

        if not 200 <= status_code < 300:
            details = _json_or_text(content)
            raise CodeGenerationError(
                _error_message(details),
                status_code=status_code,
                details=details,
            )

        content_type = _header(response_headers, "Content-Type") or ""
        if "application/zip" in content_type.casefold():
            archive_content = content
            filename = _archive_filename(
                _header(response_headers, "Content-Disposition")
            )
        else:
            payload = _json_or_text(content)
            if not isinstance(payload, Mapping):
                raise CodeGenerationError(
                    "Service Architect returned a non-JSON response",
                    status_code=status_code,
                    details=payload,
                )
            payload_status = payload.get("statusCode")
            if isinstance(payload_status, int) and not 200 <= payload_status < 300:
                raise CodeGenerationError(
                    _error_message(payload),
                    status_code=payload_status,
                    details=payload,
                )
            headers = payload.get("headers") or {}
            encoded_body = payload.get("body")
            disposition = (
                _header(headers, "Content-Disposition")
                if isinstance(headers, Mapping)
                else None
            )
            if not disposition or not isinstance(encoded_body, str):
                raise CodeGenerationError(
                    _error_message(payload),
                    status_code=status_code,
                    details=payload,
                )
            try:
                archive_content = base64.b64decode(encoded_body, validate=True)
            except (ValueError, binascii.Error) as error:
                raise CodeGenerationError(
                    "Service Architect returned an invalid base64 archive",
                    status_code=status_code,
                    details=payload,
                ) from error
            filename = _archive_filename(disposition)

        if not zipfile.is_zipfile(io.BytesIO(archive_content)):
            raise CodeGenerationError(
                "Service Architect response is not a valid ZIP archive",
                status_code=status_code,
            )
        return GeneratedProjectArchive(filename=filename, content=archive_content)
