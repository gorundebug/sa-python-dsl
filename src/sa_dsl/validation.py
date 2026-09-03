from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .model import NULL, Connector, Endpoint, Project, Service, Stream


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    stage: str
    message: str
    path: str
    object_kind: str
    object_name: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return f"{self.path}: {self.code}: {self.message}"


REQUIRED = "SG_SCHEMA_REQUIRED_FIELD"
RANGE = "SG_SCHEMA_VALUE_OUT_OF_RANGE"
UNKNOWN_ENUM = "SG_SCHEMA_UNKNOWN_ENUM_VALUE"
DUPLICATE = "SG_SEMANTIC_DUPLICATE_IDENTITY"
INVALID_IDENTIFIER = "SG_SEMANTIC_INVALID_IDENTIFIER"
UNKNOWN_REFERENCE = "SG_SEMANTIC_UNKNOWN_REFERENCE"
MISSING_SOURCE = "SG_SEMANTIC_MISSING_SOURCE"
CARDINALITY = "SG_SEMANTIC_INVALID_SOURCE_CARDINALITY"
DUPLICATE_LINK = "SG_SEMANTIC_DUPLICATE_LINK"
TYPE_MISMATCH = "SG_SEMANTIC_TYPE_MISMATCH"
INVALID_CYCLE = "SG_SEMANTIC_INVALID_CYCLE"
UNSUPPORTED = "SG_CAPABILITY_UNSUPPORTED_FEATURE"

LANGUAGES = {"GoLang", "CppUserver", "Python", "Rust", "CppBoost", "TypeScript"}
ENVIRONMENTS = {"", "local", "debug", "staging", "production"}
LOG_LEVELS = {"", "CRITICAL", "FATAL", "ERROR", "WARNING", "INFO", "DEBUG"}
WORKLOADS = {"Deployment", "StatefulSet"}
CONNECTOR_TYPES = {"HTTP", "gRPC", "Kafka", "Custom", "Cron", "Temporal"}
STREAM_TYPES = {
    "Input",
    "Map",
    "Filter",
    "Join",
    "MultiJoin",
    "Process",
    "FlatMap",
    "FlatMapIterable",
    "KeyBy",
    "Merge",
    "Split",
    "Case",
    "Sink",
    "CycleLink",
    "Error",
    "Delay",
    "When",
}
DATA_TYPES = {
    "int",
    "uint",
    "byte",
    "char",
    "boolean",
    "unicode char",
    "string",
    "unicode string",
    "float",
    "double",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "any",
    "error",
    "array",
    "map",
    "struct",
    "custom",
}
INLINE_TYPES = DATA_TYPES - {"array", "map", "struct", "custom"}
DEFINITION_FORMATS = {
    "Native",
    "Protobuf",
    "FlatBuffers",
    "CapNProto",
    "OpenAPI",
    1,
    2,
    3,
    4,
    5,
}
CALL_SEMANTICS = {
    "Inherited",
    "FunctionCall",
    "TaskPool",
    "PriorityTaskPool",
    "ParallelCall",
}
GRPC_METHODS = {
    "NoStreaming",
    "ClientStreaming",
    "ServerStreaming",
    "BidirectionalStreaming",
    1,
    2,
    4,
    5,
}
HTTP_METHODS = {"GET", "POST"}
JOIN_TYPES = {"Inner", "Left", "Right", "Outer", 1, 2, 3, 4}
JOIN_STORAGES = {"HashMap", "RocksDB", "Aerospike", 1, 2, 3}
PROCESS_PATTERNS = {"Execute", "Collect", 1, 2}
OUTPUT_TYPES = {
    "Input",
    "Map",
    "Join",
    "MultiJoin",
    "Process",
    "FlatMap",
    "FlatMapIterable",
    "KeyBy",
    "Sink",
    "Error",
    "When",
}
FUNCTION_TYPES = {
    "Delay",
    "Filter",
    "FlatMap",
    "Process",
    "Join",
    "KeyBy",
    "Map",
    "MultiJoin",
    "Case",
}
ERROR_OUTPUT_TYPES = {"Input", "Process", "Sink"}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _prop(value: Any, name: str, default: Any = None) -> Any:
    result = value.properties.get(name, default)
    return None if result is NULL else result


def _generated_identifier(value: str) -> str:
    return "".join(part.lower() for part in re.findall(r"[A-Za-z0-9_]+", value))


def _valid_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))


class Validator:
    def __init__(self, project: Project):
        self.project = project
        self.values: list[Diagnostic] = []
        self.streams = {
            stream.key: stream
            for service in project.services.values()
            for pipeline in service.pipelines.values()
            for stream in pipeline.streams.values()
        }
        self.endpoints = {
            endpoint.key: endpoint
            for connector in project.connectors.values()
            for endpoint in connector.endpoints.values()
        }
        self.endpoint_users: dict[str, list[Stream]] = defaultdict(list)
        self.normal_consumers: dict[str, list[Stream]] = defaultdict(list)
        self.error_consumers: dict[str, list[Stream]] = defaultdict(list)
        self.declared_edges: set[tuple[str, str]] = set()

    def add(
        self,
        code: str,
        stage: str,
        message: str,
        path: str,
        kind: str,
        name: str = "",
        **details: Any,
    ) -> None:
        self.values.append(Diagnostic(code, stage, message, path, kind, name, details))

    def required(self, value: Any, path: str, kind: str, name: str, field: str) -> bool:
        if _text(value).strip():
            return True
        self.add(
            REQUIRED,
            "schema",
            f"{kind} {name!r} requires {field}",
            path,
            kind,
            name,
            field=field,
        )
        return False

    def enum(
        self,
        value: Any,
        allowed: set[Any],
        path: str,
        kind: str,
        name: str,
        field: str,
        required: bool = False,
    ) -> None:
        if value is None or value == "":
            if required:
                self.add(
                    REQUIRED,
                    "schema",
                    f"{kind} {name!r} requires {field}",
                    path,
                    kind,
                    name,
                    field=field,
                )
            return
        if value not in allowed:
            self.add(
                UNKNOWN_ENUM,
                "schema",
                f"{kind} {name!r} has unknown {field} {value!r}",
                path,
                kind,
                name,
                field=field,
                actual=value,
            )

    def minimum(
        self,
        value: Any,
        minimum: int,
        path: str,
        kind: str,
        name: str,
        field: str,
        maximum: int | None = None,
    ) -> None:
        if value is None:
            return
        if (
            not isinstance(value, (int, float))
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            details = {"field": field, "actual": value, "minimum": minimum}
            if maximum is not None:
                details["maximum"] = maximum
            self.add(
                RANGE,
                "schema",
                f"{kind} {name!r} {field} is outside its allowed range",
                path,
                kind,
                name,
                **details,
            )

    def duplicate_names(
        self, kind: str, values: Iterable[Any], path_prefix: str
    ) -> None:
        seen: dict[str, str] = {}
        generated: dict[str, str] = {}
        for value in values:
            path = f"{path_prefix}.{value.key}.name"
            self.required(value.name, path, kind, value.name, "name")
            if value.name in seen:
                self.add(
                    DUPLICATE,
                    "semantic",
                    f"duplicate {kind} name: {value.name}",
                    path,
                    kind,
                    value.name,
                    identity="name",
                    value=value.name,
                    firstPath=seen[value.name],
                )
            else:
                seen[value.name] = path
            identifier = _generated_identifier(value.name)
            if not _valid_identifier(identifier):
                self.add(
                    INVALID_IDENTIFIER,
                    "semantic",
                    f"{kind} name {value.name!r} does not produce a valid generated identifier",
                    path,
                    kind,
                    value.name,
                    sourceName=value.name,
                    generatedName=identifier,
                )
            elif identifier in generated and generated[identifier] != value.name:
                self.add(
                    DUPLICATE,
                    "semantic",
                    f"{kind} names produce the same generated identifier {identifier!r}",
                    path,
                    kind,
                    value.name,
                    identity="generatedName",
                    value=identifier,
                )
            else:
                generated[identifier] = value.name

    def validate(self) -> list[Diagnostic]:
        self.required(
            self.project.name, "$.settings.name", "settings", self.project.name, "name"
        )
        self.validate_services()
        self.validate_modules_types_pools()
        self.validate_connectors()
        self.validate_streams()
        self.validate_endpoint_contracts()
        self.validate_endpoint_usage()
        self.validate_functions()
        self.validate_consumers_links_cycles()
        return sorted(
            self.values,
            key=lambda value: (
                value.path,
                value.stage,
                value.code,
                value.object_kind,
                value.object_name,
            ),
        )

    def validate_services(self) -> None:
        self.duplicate_names("service", self.project.services.values(), "$.services")
        for service in self.project.services.values():
            path = f"$.services.{service.key}"
            self.enum(
                service.programming_language,
                LANGUAGES,
                path + ".programmingLanguage",
                "service",
                service.name,
                "programmingLanguage",
                True,
            )
            self.enum(
                _prop(service, "defaultCallSemantics"),
                CALL_SEMANTICS,
                path + ".defaultCallSemantics",
                "service",
                service.name,
                "defaultCallSemantics",
                True,
            )
            self.enum(
                _prop(service, "environment", ""),
                ENVIRONMENTS,
                path + ".environment",
                "service",
                service.name,
                "environment",
            )
            self.enum(
                _prop(service, "logLevel"),
                LOG_LEVELS,
                path + ".logLevel",
                "service",
                service.name,
                "logLevel",
            )
            self.enum(
                _prop(service, "kubernetesWorkloadType"),
                WORKLOADS,
                path + ".kubernetesWorkloadType",
                "service",
                service.name,
                "kubernetesWorkloadType",
                True,
            )
            self.minimum(
                _prop(service, "httpPort"),
                0,
                path + ".httpPort",
                "service",
                service.name,
                "httpPort",
                65535,
            )
            grpc_port = _prop(service, "grpcPort")
            if grpc_port != 0:
                self.minimum(
                    grpc_port,
                    80,
                    path + ".grpcPort",
                    "service",
                    service.name,
                    "grpcPort",
                    65535,
                )
            self.minimum(
                _prop(service, "defaultGrpcTimeout"),
                0,
                path + ".defaultGrpcTimeout",
                "service",
                service.name,
                "defaultGrpcTimeout",
            )
            self.minimum(
                _prop(service, "shutdownTimeout"),
                0,
                path + ".shutdownTimeout",
                "service",
                service.name,
                "shutdownTimeout",
            )

    def validate_modules_types_pools(self) -> None:
        self.duplicate_names("module", self.project.modules.values(), "$.modules")
        paths: dict[str, str] = {}
        for module in self.project.modules.values():
            if module.module_path and module.module_path in paths:
                self.add(
                    DUPLICATE,
                    "semantic",
                    f"duplicate module modulePath: {module.module_path}",
                    f"$.modules.{module.key}.modulePath",
                    "module",
                    module.name,
                    identity="modulePath",
                    value=module.module_path,
                )
            paths[module.module_path] = module.key

        self.duplicate_names("type", self.project.types.values(), "$.types")
        for value in self.project.types.values():
            path = f"$.types.{value.key}"
            data_type = str(getattr(value.type, "value", value.type))
            self.enum(
                data_type, DATA_TYPES, path + ".type", "type", value.name, "type", True
            )
            self.enum(
                _prop(value, "definitionFormat"),
                DEFINITION_FORMATS,
                path + ".definitionFormat",
                "type",
                value.name,
                "definitionFormat",
            )
            module = _prop(value, "module")
            if module and module not in self.project.modules:
                self.add(
                    UNKNOWN_REFERENCE,
                    "semantic",
                    f"type {value.name!r} references unknown module {module}",
                    path + ".module",
                    "type",
                    value.name,
                    referenceKind="module",
                    reference=module,
                )
            for field_name in (
                ["valueType", "keyType"]
                if data_type == "map"
                else ["valueType"] if data_type == "array" else []
            ):
                reference = _prop(value, field_name)
                if not _text(reference).strip():
                    self.add(
                        REQUIRED,
                        "schema",
                        f"{data_type} type {value.name!r} requires {field_name}",
                        path + "." + field_name,
                        "type",
                        value.name,
                        field=field_name,
                        dataType=data_type,
                    )
                elif (
                    reference not in self.project.types
                    and reference not in INLINE_TYPES
                ):
                    self.add(
                        UNKNOWN_REFERENCE,
                        "semantic",
                        f"type {value.name!r} references unknown type {reference}",
                        path + "." + field_name,
                        "type",
                        value.name,
                        referenceKind="type",
                        reference=reference,
                    )

        self.duplicate_names("pool", self.project.pools.values(), "$.pools")
        for pool in self.project.pools.values():
            path = f"$.pools.{pool.key}"
            self.minimum(
                pool.executors_count,
                1,
                path + ".executorsCount",
                "pool",
                pool.name,
                "executorsCount",
            )
            self.minimum(
                pool.queue_capacity,
                1,
                path + ".queueCapacity",
                "pool",
                pool.name,
                "queueCapacity",
            )

    def validate_connectors(self) -> None:
        self.duplicate_names(
            "dataConnector", self.project.connectors.values(), "$.dataConnectors"
        )
        all_endpoints = [
            endpoint
            for connector in self.project.connectors.values()
            for endpoint in connector.endpoints.values()
        ]
        self.duplicate_names("endpoint", all_endpoints, "$.endpoints")
        activity_limits: dict[tuple[str, str], int] = {}
        workflow_limits: dict[tuple[str, str], int] = {}
        for connector in self.project.connectors.values():
            path = f"$.dataConnectors.{connector.key}"
            self.enum(
                connector.type,
                CONNECTOR_TYPES,
                path + ".type",
                "dataConnector",
                connector.name,
                "type",
                True,
            )
            if connector.type == "gRPC":
                self.minimum(
                    _prop(connector, "connectionsCount"),
                    1,
                    path + ".connectionsCount",
                    "dataConnector",
                    connector.name,
                    "connectionsCount",
                    1000,
                )
            if connector.type == "Kafka":
                self.minimum(
                    _prop(connector, "dialTimeout"),
                    0,
                    path + ".dialTimeout",
                    "dataConnector",
                    connector.name,
                    "dialTimeout",
                    3600000,
                )
            if connector.type == "HTTP" and _prop(connector, "useDedicatedListener"):
                self.minimum(
                    _prop(connector, "port"),
                    80,
                    path + ".port",
                    "dataConnector",
                    connector.name,
                    "port",
                    65535,
                )
            module = _prop(connector, "module")
            if module and module not in self.project.modules:
                self.add(
                    UNKNOWN_REFERENCE,
                    "semantic",
                    f"dataConnector {connector.name!r} references unknown module {module}",
                    path + ".module",
                    "dataConnector",
                    connector.name,
                    referenceKind="module",
                    reference=module,
                )
            for endpoint in connector.endpoints.values():
                ep_path = path + f".endpoints.{endpoint.key}"
                self.minimum(
                    _prop(endpoint, "partitions"),
                    1,
                    ep_path + ".partitions",
                    "endpoint",
                    endpoint.name,
                    "partitions",
                    1000,
                )
                self.minimum(
                    _prop(endpoint, "replicationFactor"),
                    1,
                    ep_path + ".replicationFactor",
                    "endpoint",
                    endpoint.name,
                    "replicationFactor",
                    1000,
                )
                function_module = _prop(endpoint, "functionModule")
                if (
                    _prop(endpoint, "publicFunction")
                    and function_module
                    and function_module not in self.project.modules
                ):
                    self.add(
                        UNKNOWN_REFERENCE,
                        "semantic",
                        f"endpoint {endpoint.name!r} references unknown module {function_module}",
                        ep_path + ".functionModule",
                        "endpoint",
                        endpoint.name,
                        referenceKind="module",
                        reference=function_module,
                    )
                if connector.type == "Cron":
                    self.validate_schedule(endpoint, ep_path, False)
                if connector.type == "Temporal":
                    self.required(
                        _prop(endpoint, "taskQueue"),
                        ep_path + ".taskQueue",
                        "endpoint",
                        endpoint.name,
                        "taskQueue",
                    )
                    execution = _prop(endpoint, "temporalExecutionType")
                    self.enum(
                        execution,
                        {"Activity", "Workflow"},
                        ep_path + ".temporalExecutionType",
                        "endpoint",
                        endpoint.name,
                        "temporalExecutionType",
                        True,
                    )
                    queue = _text(_prop(endpoint, "taskQueue")).strip()
                    key = (connector.key, queue)
                    if execution == "Activity":
                        self.required_positive(
                            endpoint, "activityStartToCloseTimeout", ep_path
                        )
                        limit = self.required_positive(
                            endpoint, "maxConcurrentActivities", ep_path
                        )
                        if (
                            limit is not None
                            and key in activity_limits
                            and activity_limits[key] != limit
                        ):
                            self.add(
                                RANGE,
                                "schema",
                                f"Temporal Activity endpoints on Task Queue {queue!r} must use the same maxConcurrentActivities",
                                ep_path + ".maxConcurrentActivities",
                                "endpoint",
                                endpoint.name,
                                actual=limit,
                                expected=activity_limits[key],
                            )
                        elif limit is not None:
                            activity_limits[key] = limit
                    if execution == "Workflow":
                        limit = self.required_positive(
                            endpoint, "maxConcurrentWorkflowTasks", ep_path
                        )
                        if (
                            limit is not None
                            and key in workflow_limits
                            and workflow_limits[key] != limit
                        ):
                            self.add(
                                RANGE,
                                "schema",
                                f"Temporal Workflow endpoints on Task Queue {queue!r} must use the same maxConcurrentWorkflowTasks",
                                ep_path + ".maxConcurrentWorkflowTasks",
                                "endpoint",
                                endpoint.name,
                                actual=limit,
                                expected=workflow_limits[key],
                            )
                        elif limit is not None:
                            workflow_limits[key] = limit
                    self.required_positive(endpoint, "maximumAttempts", ep_path)
                    if _text(_prop(endpoint, "schedule")).strip():
                        self.validate_schedule(endpoint, ep_path, True)

    def required_positive(
        self, endpoint: Endpoint, field_name: str, base_path: str
    ) -> int | None:
        value = _prop(endpoint, field_name)
        if not isinstance(value, int) or value < 1:
            self.add(
                REQUIRED,
                "schema",
                f"Temporal endpoint {endpoint.name!r} requires {field_name}",
                base_path + "." + field_name,
                "endpoint",
                endpoint.name,
                field=field_name,
            )
            return None
        return value

    def validate_schedule(self, endpoint: Endpoint, path: str, temporal: bool) -> None:
        schedule = _text(_prop(endpoint, "schedule"))
        timezone = _prop(endpoint, "timezone")
        self.required(
            schedule, path + ".schedule", "endpoint", endpoint.name, "schedule"
        )
        self.required(
            timezone, path + ".timezone", "endpoint", endpoint.name, "timezone"
        )
        if timezone not in (None, "UTC"):
            self.add(
                RANGE,
                "schema",
                f"scheduled endpoint {endpoint.name!r} requires timezone UTC",
                path + ".timezone",
                "endpoint",
                endpoint.name,
                actual=timezone,
                allowed=["UTC"],
            )
        fields = schedule.split()
        valid = len(fields) == 5 and not any(
            any(char in item for char in "LW#?@") for item in fields
        )
        if valid and fields[2] != "*" and fields[4] != "*":
            valid = False
        if schedule.strip() and not valid:
            self.add(
                RANGE,
                "schema",
                f"scheduled endpoint {endpoint.name!r} requires a portable five-field cron expression",
                path + ".schedule",
                "endpoint",
                endpoint.name,
                contract="portable-five-field",
            )
        if temporal:
            self.required(
                _prop(endpoint, "scheduleId"),
                path + ".scheduleId",
                "endpoint",
                endpoint.name,
                "scheduleId",
            )
        self.enum(
            _prop(endpoint, "overlapPolicy"),
            {"Allow", "Skip"},
            path + ".overlapPolicy",
            "endpoint",
            endpoint.name,
            "overlapPolicy",
            True,
        )
        self.enum(
            _prop(endpoint, "missedRunPolicy"),
            {"Skip", "FireOnce"},
            path + ".missedRunPolicy",
            "endpoint",
            endpoint.name,
            "missedRunPolicy",
            True,
        )

    def validate_streams(self) -> None:
        self.duplicate_names("stream", self.streams.values(), "$.streams")
        for stream in self.streams.values():
            path = self.stream_path(stream)
            self.enum(
                stream.type,
                STREAM_TYPES,
                path + ".type",
                "stream",
                stream.name,
                "type",
                True,
            )
            dependencies = ([stream.source] if stream.source else []) + list(
                stream.sources
            )
            if stream.type not in {"Input", "Merge"} and stream.source is None:
                self.add(
                    MISSING_SOURCE,
                    "semantic",
                    f"stream {stream.name!r} does not have a source stream",
                    path + ".source",
                    "stream",
                    stream.name,
                    transformationType=stream.type,
                )
            if len({item.key for item in stream.sources}) != len(stream.sources):
                self.add(
                    DUPLICATE_LINK,
                    "semantic",
                    f"stream {stream.name!r} lists a source more than once",
                    path + ".sources",
                    "stream",
                    stream.name,
                )
            expected = {"Join": (1, 1), "MultiJoin": (1, None), "Merge": (2, None)}.get(
                stream.type
            )
            if expected and (
                len(stream.sources) < expected[0]
                or (expected[1] is not None and len(stream.sources) > expected[1])
            ):
                self.add(
                    CARDINALITY,
                    "semantic",
                    f"stream {stream.name!r} has an invalid number of additional sources",
                    path + ".sources",
                    "stream",
                    stream.name,
                    actual=len(stream.sources),
                    minimum=expected[0],
                    maximum=expected[1],
                )
            for source in dependencies:
                self.declared_edges.add((source.key, stream.key))
                (
                    self.error_consumers
                    if stream.type == "Error" and source is stream.source
                    else self.normal_consumers
                )[source.key].append(stream)
            if stream.type in OUTPUT_TYPES:
                self.required(
                    _prop(stream, "valueType"),
                    path + ".valueType",
                    "stream",
                    stream.name,
                    "valueType",
                )
            if stream.type == "KeyBy":
                self.required(
                    _prop(stream, "keyType"),
                    path + ".keyType",
                    "stream",
                    stream.name,
                    "keyType",
                )
            self.enum(
                _prop(stream, "joinType"),
                JOIN_TYPES,
                path + ".joinType",
                "stream",
                stream.name,
                "joinType",
                stream.type == "Join",
            )
            self.enum(
                _prop(stream, "joinStorage"),
                JOIN_STORAGES,
                path + ".joinStorage",
                "stream",
                stream.name,
                "joinStorage",
                stream.type in {"Join", "MultiJoin"},
            )
            self.enum(
                _prop(stream, "pattern"),
                PROCESS_PATTERNS,
                path + ".pattern",
                "stream",
                stream.name,
                "pattern",
            )
            self.minimum(
                _prop(stream, "duration"),
                0,
                path + ".duration",
                "stream",
                stream.name,
                "duration",
            )
            self.minimum(
                _prop(stream, "ttl"), 0, path + ".ttl", "stream", stream.name, "ttl"
            )
            if stream.type == "Sink" and stream.endpoint is None:
                self.add(
                    REQUIRED,
                    "schema",
                    f"Sink stream {stream.name!r} requires endpoint",
                    path + ".endpoint",
                    "stream",
                    stream.name,
                    field="endpoint",
                )
            if stream.endpoint is not None and stream.type not in {"Input", "Sink"}:
                self.add(
                    RANGE,
                    "schema",
                    f"stream {stream.name!r} cannot use an endpoint",
                    path + ".endpoint",
                    "stream",
                    stream.name,
                    transformationType=stream.type,
                )
            if stream.type in FUNCTION_TYPES or (
                stream.type == "Input" and stream.endpoint is None
            ):
                self.required(
                    _prop(stream, "functionName"),
                    path + ".functionName",
                    "stream",
                    stream.name,
                    "functionName",
                )
            module = _prop(stream, "functionModule")
            if (
                _prop(stream, "publicFunction")
                and module
                and module not in self.project.modules
            ):
                self.add(
                    UNKNOWN_REFERENCE,
                    "semantic",
                    f"stream {stream.name!r} references unknown module {module}",
                    path + ".functionModule",
                    "stream",
                    stream.name,
                    referenceKind="module",
                    reference=module,
                )
            for field_name in ("valueType", "keyType"):
                reference = _prop(stream, field_name)
                if (
                    reference
                    and reference not in self.project.types
                    and reference not in INLINE_TYPES
                ):
                    self.add(
                        UNKNOWN_REFERENCE,
                        "semantic",
                        f"stream {stream.name!r} references unknown type {reference}",
                        path + "." + field_name,
                        "stream",
                        stream.name,
                        referenceKind="type",
                        reference=reference,
                    )
            if stream.type == "When" and stream.source and stream.source.type != "Case":
                self.add(
                    TYPE_MISMATCH,
                    "semantic",
                    f"When stream {stream.name!r} must consume a Case stream",
                    path + ".source",
                    "stream",
                    stream.name,
                )
            if (
                stream.type == "Error"
                and stream.source
                and stream.source.type not in ERROR_OUTPUT_TYPES
            ):
                self.add(
                    TYPE_MISMATCH,
                    "semantic",
                    f"Error stream {stream.name!r} must consume a stream with an error output",
                    path + ".source",
                    "stream",
                    stream.name,
                )
            self.validate_connection_types(stream, path)

    def stream_path(self, stream: Stream) -> str:
        return f"$.services.{stream.service.key}.pipelines.{stream.pipeline.key}.{stream.key}"

    def output_wire_type(self, stream: Stream | None) -> tuple[bool, str, str] | None:
        seen: set[str] = set()
        while stream is not None and stream.key not in seen:
            seen.add(stream.key)
            if stream.type in OUTPUT_TYPES:
                value_type = _text(_prop(stream, "valueType")).strip()
                if not value_type:
                    return None
                if stream.type == "KeyBy":
                    key_type = _text(_prop(stream, "keyType")).strip()
                    return (True, key_type, value_type) if key_type else None
                return False, "", value_type
            stream = stream.source or (stream.sources[0] if stream.sources else None)
        return None

    def validate_connection_types(self, stream: Stream, path: str) -> None:
        if stream.type in {"Join", "MultiJoin"}:
            expected_key = ""
            for source in ([stream.source] if stream.source else []) + stream.sources:
                wire = self.output_wire_type(source)
                if wire is None:
                    continue
                if not wire[0]:
                    self.add(
                        TYPE_MISMATCH,
                        "semantic",
                        f"{stream.type} stream {stream.name!r} requires KeyValue inputs",
                        path,
                        "stream",
                        stream.name,
                        expected="KeyValue",
                        actualValueType=wire[2],
                    )
                elif expected_key and expected_key != wire[1]:
                    self.add(
                        TYPE_MISMATCH,
                        "semantic",
                        f"{stream.type} stream {stream.name!r} has incompatible input key types",
                        path,
                        "stream",
                        stream.name,
                        expectedKeyType=expected_key,
                        actualKeyType=wire[1],
                    )
                else:
                    expected_key = wire[1]
        if stream.type == "Merge":
            wires = [self.output_wire_type(source) for source in stream.sources]
            resolved = [wire for wire in wires if wire is not None]
            if resolved and any(wire != resolved[0] for wire in resolved[1:]):
                self.add(
                    TYPE_MISMATCH,
                    "semantic",
                    f"Merge stream {stream.name!r} has incompatible input types",
                    path + ".sources",
                    "stream",
                    stream.name,
                )

    def validate_endpoint_contracts(self) -> None:
        http_paths: set[tuple[str, str]] = set()
        grpc_methods: set[tuple[str, str]] = set()
        for stream in self.streams.values():
            if stream.endpoint:
                self.endpoint_users[stream.endpoint.key].append(stream)
        for endpoint in self.endpoints.values():
            users = self.endpoint_users[endpoint.key]
            if not users:
                continue
            connector = endpoint.connector
            path = f"$.dataConnectors.{connector.key}.endpoints.{endpoint.key}"
            connector_path = f"$.dataConnectors.{connector.key}"
            self.required(
                endpoint.function_name,
                path + ".functionName",
                "endpoint",
                endpoint.name,
                "functionName",
            )
            if connector.type == "HTTP":
                self.enum(
                    _prop(endpoint, "httpMethodType"),
                    HTTP_METHODS,
                    path + ".httpMethodType",
                    "endpoint",
                    endpoint.name,
                    "httpMethodType",
                    True,
                )
                route = _prop(endpoint, "path")
                self.required(route, path + ".path", "endpoint", endpoint.name, "path")
                route_key = (connector.key, _text(route))
                if route and route_key in http_paths:
                    self.add(
                        DUPLICATE,
                        "semantic",
                        f"duplicate endpoint httpPath: {route}",
                        path + ".path",
                        "endpoint",
                        endpoint.name,
                        identity="httpPath",
                        value=route,
                    )
                http_paths.add(route_key)
                if _prop(connector, "useDedicatedListener") and any(
                    user.service.programming_language == "CppUserver" for user in users
                ):
                    self.add(
                        UNSUPPORTED,
                        "capability",
                        f"C++ userver data connector {connector.name!r} does not support a dedicated HTTP listener",
                        connector_path + ".useDedicatedListener",
                        "dataConnector",
                        connector.name,
                        feature="dedicatedHttpListener",
                        language="cppUserver",
                    )
            elif connector.type == "gRPC":
                self.required(
                    _prop(connector, "module"),
                    connector_path + ".module",
                    "dataConnector",
                    connector.name,
                    "module",
                )
                if any(user.type == "Sink" for user in users):
                    self.required(
                        _prop(connector, "address"),
                        connector_path + ".address",
                        "dataConnector",
                        connector.name,
                        "address",
                    )
                self.enum(
                    _prop(endpoint, "grpcMethodType"),
                    GRPC_METHODS,
                    path + ".grpcMethodType",
                    "endpoint",
                    endpoint.name,
                    "grpcMethodType",
                    True,
                )
                method = _prop(endpoint, "methodName")
                self.required(
                    method,
                    path + ".methodName",
                    "endpoint",
                    endpoint.name,
                    "methodName",
                )
                method_key = (connector.key, _text(method))
                if method and method_key in grpc_methods:
                    self.add(
                        DUPLICATE,
                        "semantic",
                        f"duplicate endpoint grpcMethod: {method}",
                        path + ".methodName",
                        "endpoint",
                        endpoint.name,
                        identity="grpcMethod",
                        value=method,
                    )
                grpc_methods.add(method_key)
            elif connector.type == "Kafka":
                self.required(
                    _prop(connector, "brokers"),
                    connector_path + ".brokers",
                    "dataConnector",
                    connector.name,
                    "brokers",
                )
                self.required(
                    _prop(endpoint, "topic"),
                    path + ".topic",
                    "endpoint",
                    endpoint.name,
                    "topic",
                )
                self.enum(
                    _prop(connector, "securityProtocol"),
                    {"PLAINTEXT", "SASL_PLAINTEXT", "SASL_SSL"},
                    connector_path + ".securityProtocol",
                    "dataConnector",
                    connector.name,
                    "securityProtocol",
                )
                self.enum(
                    _prop(connector, "saslMechanism"),
                    {"PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"},
                    connector_path + ".saslMechanism",
                    "dataConnector",
                    connector.name,
                    "saslMechanism",
                )
                for field_name in ("username", "password"):
                    if _text(_prop(connector, field_name)).strip():
                        self.add(
                            UNSUPPORTED,
                            "capability",
                            f"Kafka data connector {connector.name!r} must receive {field_name} at runtime",
                            connector_path + "." + field_name,
                            "dataConnector",
                            connector.name,
                            feature="embeddedKafkaCredential",
                            field=field_name,
                        )
                if any(user.type == "Input" for user in users):
                    self.required(
                        _prop(endpoint, "consumerGroup"),
                        path + ".consumerGroup",
                        "endpoint",
                        endpoint.name,
                        "consumerGroup",
                    )
                if _prop(connector, "saslMechanism") == "SCRAM-SHA-256" and any(
                    user.type == "Input"
                    and user.service.programming_language == "CppUserver"
                    for user in users
                ):
                    self.add(
                        UNSUPPORTED,
                        "capability",
                        f"C++ userver Kafka source {connector.name!r} does not support SCRAM-SHA-256",
                        connector_path + ".saslMechanism",
                        "dataConnector",
                        connector.name,
                        feature="kafkaScramSha256",
                        language="cppUserver",
                    )
            elif connector.type == "Temporal":
                self.required(
                    _prop(connector, "address"),
                    connector_path + ".address",
                    "dataConnector",
                    connector.name,
                    "address",
                )
                self.required(
                    _prop(connector, "namespace"),
                    connector_path + ".namespace",
                    "dataConnector",
                    connector.name,
                    "namespace",
                )
                for user in users:
                    if user.service.programming_language not in {
                        "GoLang",
                        "Python",
                        "TypeScript",
                    }:
                        self.add(
                            UNSUPPORTED,
                            "capability",
                            f"service {user.service.name!r} cannot use Temporal without an official production SDK",
                            connector_path + ".type",
                            "dataConnector",
                            connector.name,
                            feature="temporal",
                            language=user.service.programming_language,
                        )
                        break

    def validate_endpoint_usage(self) -> None:
        seen: dict[tuple[str, str, str], Stream] = {}
        inputs: dict[str, list[Stream]] = defaultdict(list)
        sinks: dict[str, list[Stream]] = defaultdict(list)
        for stream in self.streams.values():
            if not stream.endpoint or stream.type not in {"Input", "Sink"}:
                continue
            key = (stream.service.key, stream.endpoint.key, stream.type)
            if key in seen:
                self.add(
                    DUPLICATE,
                    "semantic",
                    f"endpoint {stream.endpoint.key} is used by more than one {stream.type.lower()} stream in service {stream.service.key}",
                    self.stream_path(stream) + ".endpoint",
                    "stream",
                    stream.name,
                    identity="endpointDirection",
                    value=stream.endpoint.key,
                )
            seen[key] = stream
            (inputs if stream.type == "Input" else sinks)[stream.endpoint.key].append(
                stream
            )
        for endpoint_key, endpoint_inputs in inputs.items():
            for input_stream in endpoint_inputs:
                for sink in sinks[endpoint_key]:
                    request_in = self.output_wire_type(input_stream)
                    request_out = self.output_wire_type(sink.source)
                    if request_in and request_out and request_in != request_out:
                        self.add(
                            TYPE_MISMATCH,
                            "semantic",
                            f"symmetric endpoint request types differ for Input {input_stream.name!r} and Sink {sink.name!r}",
                            self.stream_path(sink) + ".endpoint",
                            "stream",
                            sink.name,
                        )
                    response_in = self.output_wire_type(input_stream.source)
                    response_out = self.output_wire_type(sink)
                    if (
                        input_stream.source
                        and response_in
                        and response_out
                        and response_in != response_out
                    ):
                        self.add(
                            TYPE_MISMATCH,
                            "semantic",
                            f"symmetric endpoint response types differ for Input {input_stream.name!r} and Sink {sink.name!r}",
                            self.stream_path(sink) + ".endpoint",
                            "stream",
                            sink.name,
                        )

    def function(self, stream: Stream) -> tuple[str, str, bool, str] | None:
        if stream.endpoint:
            endpoint = stream.endpoint
            return (
                endpoint.function_name,
                _text(_prop(endpoint, "functionPackage")),
                bool(_prop(endpoint, "publicFunction")),
                _text(_prop(endpoint, "functionModule")),
            )
        name = _text(_prop(stream, "functionName"))
        return (
            (
                name,
                _text(_prop(stream, "functionPackage")),
                bool(_prop(stream, "publicFunction")),
                _text(_prop(stream, "functionModule")),
            )
            if name
            else None
        )

    def validate_functions(self) -> None:
        generated: dict[tuple[str, str], tuple[str, str]] = {}
        signatures: dict[tuple[str, str, str], tuple[str, str]] = {}
        processed_endpoints: set[str] = set()
        for stream in self.streams.values():
            if stream.endpoint and stream.endpoint.key in processed_endpoints:
                continue
            if stream.endpoint:
                processed_endpoints.add(stream.endpoint.key)
            function = self.function(stream)
            if not function:
                continue
            name, package, public, module = function
            scope = (
                "module:" + module
                if public and module.strip()
                else "service:" + stream.service.key
            )
            identifier = _generated_identifier(package + " " + name)
            path = self.stream_path(stream) + ".functionName"
            raw = package + "\0" + name
            key = (scope, identifier)
            if not _valid_identifier(identifier):
                self.add(
                    INVALID_IDENTIFIER,
                    "semantic",
                    f"function name {name!r} does not produce a valid generated identifier",
                    path,
                    "function",
                    name,
                    generatedName=identifier,
                )
            elif key in generated and generated[key][0] != raw:
                self.add(
                    DUPLICATE,
                    "semantic",
                    f"functions produce the same generated field {identifier!r}",
                    path,
                    "function",
                    name,
                    identity="generatedName",
                    value=identifier,
                )
            else:
                generated[key] = (raw, path)
            source_wire = self.output_wire_type(
                stream.source or (stream.sources[0] if stream.sources else None)
            )
            signature = (
                "@"
                + _text(_prop(stream, "valueType"))
                + "@"
                + _text(_prop(stream, "keyType"))
                + ("@" + "@".join(map(str, source_wire)) if source_wire else "")
            )
            declaration = (scope, package, name)
            if declaration in signatures and signatures[declaration][0] != signature:
                self.add(
                    TYPE_MISMATCH,
                    "semantic",
                    f"function {name!r} is reused with incompatible signatures",
                    path,
                    "function",
                    name,
                    expectedSignature=signatures[declaration][0],
                    actualSignature=signature,
                    firstPath=signatures[declaration][1],
                )
            else:
                signatures[declaration] = (signature, path)

    def validate_consumers_links_cycles(self) -> None:
        for stream in self.streams.values():
            consumers = self.normal_consumers[stream.key]
            if stream.type == "Split" and len(consumers) < 2:
                self.add(
                    CARDINALITY,
                    "semantic",
                    f"Split stream {stream.name!r} requires at least two consumers",
                    self.stream_path(stream),
                    "stream",
                    stream.name,
                    actual=len(consumers),
                    minimum=2,
                )
            if len(consumers) > 1 and stream.type not in {"Split", "Case"}:
                self.add(
                    CARDINALITY,
                    "semantic",
                    f"non-split stream {stream.name!r} has multiple consumers",
                    self.stream_path(stream),
                    "stream",
                    stream.name,
                    consumers=[item.key for item in consumers],
                    maximum=1,
                )
            if stream.type == "Case":
                for consumer in consumers:
                    if consumer.type != "When":
                        self.add(
                            TYPE_MISMATCH,
                            "semantic",
                            f"Case stream {stream.name!r} may only feed When streams",
                            self.stream_path(consumer) + ".source",
                            "stream",
                            consumer.name,
                        )
            if len(self.error_consumers[stream.key]) > 1:
                self.add(
                    CARDINALITY,
                    "semantic",
                    f"stream {stream.name!r} has multiple error consumers",
                    self.stream_path(stream),
                    "stream",
                    stream.name,
                    maximum=1,
                )

        persisted: set[tuple[str, str]] = set()
        for service in self.project.services.values():
            for link in service.links.values():
                path = f"$.services.{service.key}.links.{link.key}"
                edge = (link.source.key, link.target.key)
                if edge in persisted:
                    self.add(
                        DUPLICATE_LINK,
                        "semantic",
                        f"duplicate link from stream {edge[0]} to stream {edge[1]}",
                        path,
                        "link",
                        link.key,
                    )
                persisted.add(edge)
                if edge not in self.declared_edges:
                    self.add(
                        UNKNOWN_REFERENCE,
                        "semantic",
                        f"link {edge[0]}_{edge[1]} does not correspond to a declared stream source",
                        path,
                        "link",
                        link.key,
                        reason="undeclared-graph-edge",
                    )
                semantics = _prop(link, "callSemantics")
                self.enum(
                    semantics,
                    CALL_SEMANTICS,
                    path + ".callSemantics",
                    "link",
                    link.key,
                    "callSemantics",
                    True,
                )
                if semantics in {"TaskPool", "PriorityTaskPool"}:
                    pool = _prop(link, "poolName")
                    self.required(
                        pool, path + ".poolName", "link", link.key, "poolName"
                    )
                    if pool and all(
                        item.name != pool and item.key != pool
                        for item in self.project.pools.values()
                    ):
                        self.add(
                            UNKNOWN_REFERENCE,
                            "semantic",
                            f"link {link.key!r} references unknown pool {pool}",
                            path + ".poolName",
                            "link",
                            link.key,
                            referenceKind="pool",
                            reference=pool,
                        )
                    if (
                        semantics == "PriorityTaskPool"
                        and _prop(link, "priority") is None
                    ):
                        self.add(
                            REQUIRED,
                            "schema",
                            f"link {link.key!r} requires priority for priority task-pool semantics",
                            path + ".priority",
                            "link",
                            link.key,
                            field="priority",
                        )

        adjacency: dict[str, list[str]] = defaultdict(list)
        for source, target in self.declared_edges:
            source_stream = self.streams[source]
            if source_stream.type not in {"Input", "CycleLink"}:
                adjacency[source].append(target)
        state: dict[str, int] = {}

        def visit(key: str) -> bool:
            if state.get(key) == 1:
                return True
            if state.get(key) == 2:
                return False
            state[key] = 1
            if any(visit(target) for target in adjacency[key]):
                return True
            state[key] = 2
            return False

        if any(visit(key) for key in self.streams):
            self.add(
                INVALID_CYCLE,
                "semantic",
                "execution graph contains an invalid cycle",
                "$.streams",
                "streamGraph",
            )


def validate_project(project: Project) -> list[Diagnostic]:
    return Validator(project).validate()
