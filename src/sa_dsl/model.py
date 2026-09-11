from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml
from .visual_components import normalize_components


class DslValidationError(ValueError):
    """An authoring error that would produce an invalid or ambiguous graph."""


class _ExplicitNull:
    def __repr__(self) -> str:
        return "NULL"


NULL = _ExplicitNull()


class _LocalModule:
    def __repr__(self) -> str:
        return "LOCAL_MODULE"


LOCAL_MODULE = _LocalModule()


@dataclass(frozen=True, slots=True)
class Package:
    path: str = ""

    def __post_init__(self) -> None:
        if self.path.startswith("/"):
            raise DslValidationError("Package.path must be relative")
        parts = self.path.split("/") if self.path else []
        if any(part in {"", ".", ".."} for part in parts):
            raise DslValidationError(
                "Package.path must contain non-empty relative path segments"
            )


ROOT_PACKAGE = Package()


class ProgrammingLanguage(str, Enum):
    GO = "GoLang"
    CPP_USERVER = "CppUserver"
    PYTHON = "Python"
    RUST = "Rust"
    CPP_BOOST = "CppBoost"
    TYPESCRIPT = "TypeScript"


class Environment(str, Enum):
    UNDEFINED = ""
    LOCAL = "local"
    DEBUG = "debug"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    UNDEFINED = ""
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class KubernetesWorkloadType(str, Enum):
    DEPLOYMENT = "Deployment"
    STATEFUL_SET = "StatefulSet"


class ConnectorType(str, Enum):
    HTTP = "HTTP"
    GRPC = "gRPC"
    KAFKA = "Kafka"
    CUSTOM = "Custom"
    CRON = "Cron"
    TEMPORAL = "Temporal"


class DataConnectorImplementation(str, Enum):
    UNDEFINED = ""
    AIOHTTP = "aiohttp"
    AIOKAFKA = "aiokafka"
    ASIO_GRPC = "asio/grpc"
    BOOST_BEAST_HTTP = "boost/beast-http"
    CONFLUENT_KAFKA_JAVASCRIPT = "confluent/kafka-javascript"
    CPP_LIBCRON = "cpp/libcron"
    FUNCTION = "function"
    GO_GOCRON = "go/gocron"
    GOOGLE_GRPC = "google/grpc"
    GRPC_JS = "grpc/grpc-js"
    IBM_SARAMA = "IBM/Sarama"
    LIBRDKAFKA = "librdkafka"
    NET_HTTP = "net/http"
    NODE_CRONER = "node/croner"
    NODE_HTTP = "node/http"
    PYTHON_APSCHEDULER = "python/apscheduler"
    RUST_AXUM = "rust/axum"
    RUST_CRONER = "rust/croner"
    RUST_RDKAFKA = "rust/rdkafka"
    RUST_TONIC = "rust/tonic"
    TEMPORAL_GO = "temporal/go"
    TEMPORAL_PYTHON = "temporal/python"
    TEMPORAL_TYPESCRIPT = "temporal/typescript"
    USERVER_GRPC = "userver/grpc"
    USERVER_HTTP = "userver/http"
    USERVER_KAFKA = "userver/kafka"


class StreamType(str, Enum):
    INPUT = "Input"
    MAP = "Map"
    FILTER = "Filter"
    JOIN = "Join"
    MULTI_JOIN = "MultiJoin"
    PROCESS = "Process"
    FLAT_MAP = "FlatMap"
    FLAT_MAP_ITERABLE = "FlatMapIterable"
    KEY_BY = "KeyBy"
    MERGE = "Merge"
    SPLIT = "Split"
    CASE = "Case"
    SINK = "Sink"
    CYCLE_LINK = "CycleLink"
    ERROR = "Error"
    DELAY = "Delay"
    WHEN = "When"


class CallSemantics(str, Enum):
    INHERITED = "Inherited"
    FUNCTION_CALL = "FunctionCall"
    TASK_POOL = "TaskPool"
    PRIORITY_TASK_POOL = "PriorityTaskPool"
    PARALLEL_CALL = "ParallelCall"


class HTTPMethodType(str, Enum):
    GET = "GET"
    POST = "POST"


class GrpcMethodType(str, Enum):
    NO_STREAMING = "NoStreaming"
    CLIENT_STREAMING = "ClientStreaming"
    SERVER_STREAMING = "ServerStreaming"
    BIDIRECTIONAL_STREAMING = "BidirectionalStreaming"


class JoinType(str, Enum):
    INNER = "Inner"
    LEFT = "Left"
    RIGHT = "Right"
    OUTER = "Outer"


class JoinStorageType(str, Enum):
    HASH_MAP = "HashMap"
    ROCKS_DB = "RocksDB"
    AEROSPIKE = "Aerospike"


class ProcessPattern(str, Enum):
    EXECUTE = "Execute"
    COLLECT = "Collect"


class TypeDefinitionFormat(str, Enum):
    NATIVE = "Native"
    PROTOBUF = "Protobuf"
    FLAT_BUFFERS = "FlatBuffers"
    CAP_N_PROTO = "CapNProto"
    OPEN_API = "OpenAPI"


class KafkaSecurityProtocol(str, Enum):
    PLAINTEXT = "PLAINTEXT"
    SASL_PLAINTEXT = "SASL_PLAINTEXT"
    SASL_SSL = "SASL_SSL"


class KafkaSaslMechanism(str, Enum):
    PLAIN = "PLAIN"
    SCRAM_SHA_256 = "SCRAM-SHA-256"
    SCRAM_SHA_512 = "SCRAM-SHA-512"


class TemporalExecutionType(str, Enum):
    ACTIVITY = "Activity"
    WORKFLOW = "Workflow"


class ScheduleOverlapPolicy(str, Enum):
    ALLOW = "Allow"
    SKIP = "Skip"


class ScheduleMissedRunPolicy(str, Enum):
    SKIP = "Skip"
    FIRE_ONCE = "FireOnce"


class DataType(str, Enum):
    INT = "int"
    UINT = "uint"
    BYTE = "byte"
    CHAR = "char"
    BOOLEAN = "boolean"
    UNICODE_CHAR = "unicode char"
    STRING = "string"
    UNICODE_STRING = "unicode string"
    FLOAT = "float"
    DOUBLE = "double"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    ANY = "any"
    ERROR = "error"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"
    CUSTOM = "custom"


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, TypeDefinition):
        return value.key
    if isinstance(value, Module):
        return value.name
    if value is LOCAL_MODULE:
        return ""
    if isinstance(value, Package):
        return value.path
    return value


def _camel(name: str) -> str:
    if name.endswith("_"):
        name = name[:-1]
    if name == "renew_ttl":
        return "renewTTL"
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _key(value: str | None, name: str) -> str:
    if value is None:
        if not name:
            raise DslValidationError(f"Cannot derive a key from {name!r}")
        value = re.sub(
            r"[\s_-]+(.)",
            lambda match: match.group(1).upper(),
            name,
        )
        value = value[:1].lower() + value[1:]
    if not _IDENTIFIER.fullmatch(value):
        raise DslValidationError(
            f"{value!r} is not a valid graph key; use letters, digits and underscores, "
            "and do not start with a digit"
        )
    return value


def _properties(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        _camel(name): _enum_value(value)
        for name, value in values.items()
        if value is not None or value is NULL
    }


def _document(values: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = OrderedDict()
    for name, value in values.items():
        if value is NULL:
            result[name] = NULL
            continue
        if value is None:
            continue
        if isinstance(value, Enum):
            result[name] = value.value
        elif isinstance(value, Mapping):
            result[name] = _document(value)
        elif isinstance(value, (list, tuple)):
            result[name] = [
                _document(item) if isinstance(item, Mapping) else _enum_value(item)
                for item in value
            ]
        else:
            result[name] = value
    return dict(result)


def _insert_unique(collection: dict[str, Any], key: str, value: Any, kind: str) -> Any:
    if key in collection:
        raise DslValidationError(f"Duplicate {kind} key {key!r}")
    collection[key] = value
    return value


@dataclass(slots=True)
class TypeDefinition:
    key: str
    name: str
    type: DataType | str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        return _document(
            {"name": self.name, "type": _enum_value(self.type), **self.properties}
        )


@dataclass(slots=True)
class Module:
    key: str
    name: str
    module_path: str
    golang_version: str

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "modulePath": self.module_path,
            "golangVersion": self.golang_version,
        }


@dataclass(frozen=True, slots=True)
class InitializerGroup:
    name: str = ""


@dataclass(frozen=True, slots=True)
class Appearance:
    x: float | None = None
    y: float | None = None
    color: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceModule:
    path: str


class ServiceLanguage:
    programming_language: ProgrammingLanguage

    def to_properties(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True, slots=True)
class Golang(ServiceLanguage):
    version: str | None = None
    programming_language = ProgrammingLanguage.GO

    def to_properties(self) -> dict[str, Any]:
        return _properties({"golang_version": self.version})


@dataclass(frozen=True, slots=True)
class CppUserver(ServiceLanguage):
    programming_language = ProgrammingLanguage.CPP_USERVER


@dataclass(frozen=True, slots=True)
class CppBoost(ServiceLanguage):
    programming_language = ProgrammingLanguage.CPP_BOOST


@dataclass(frozen=True, slots=True)
class Python(ServiceLanguage):
    programming_language = ProgrammingLanguage.PYTHON


@dataclass(frozen=True, slots=True)
class Rust(ServiceLanguage):
    programming_language = ProgrammingLanguage.RUST


@dataclass(frozen=True, slots=True)
class TypeScript(ServiceLanguage):
    programming_language = ProgrammingLanguage.TYPESCRIPT


@dataclass(frozen=True, slots=True)
class HttpServer:
    host: str | None = None
    port: int | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties({"http_host": self.host, "http_port": self.port})


@dataclass(frozen=True, slots=True)
class GrpcServer:
    host: str | None = None
    port: int | None = None
    default_timeout: int | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties(
            {
                "grpc_host": self.host,
                "grpc_port": self.port,
                "default_grpc_timeout": self.default_timeout,
            }
        )


@dataclass(frozen=True, slots=True)
class Observability:
    metrics_handler: str | None = None
    status_handler: str | None = None
    startup_handler: str | None = None
    readiness_handler: str | None = None
    liveness_handler: str | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties(
            {
                "metrics_handler": self.metrics_handler,
                "status_handler": self.status_handler,
                "startup_handler": self.startup_handler,
                "readiness_handler": self.readiness_handler,
                "liveness_handler": self.liveness_handler,
            }
        )


@dataclass(frozen=True, slots=True)
class Kubernetes:
    workload_type: KubernetesWorkloadType | str | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties({"kubernetes_workload_type": self.workload_type})


@dataclass(frozen=True, slots=True)
class CronSchedule:
    expression: str
    timezone: str = "UTC"
    overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP
    missed_run_policy: ScheduleMissedRunPolicy = ScheduleMissedRunPolicy.SKIP

    def to_properties(self) -> dict[str, Any]:
        return _properties({"schedule": self.expression, "timezone": self.timezone, "overlap_policy": self.overlap_policy, "missed_run_policy": self.missed_run_policy})


@dataclass(frozen=True, slots=True)
class TemporalSchedule:
    expression: str
    id: str
    timezone: str = "UTC"
    overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP
    missed_run_policy: ScheduleMissedRunPolicy = ScheduleMissedRunPolicy.FIRE_ONCE

    def to_properties(self) -> dict[str, Any]:
        return _properties({"schedule": self.expression, "schedule_id": self.id, "timezone": self.timezone, "overlap_policy": self.overlap_policy, "missed_run_policy": self.missed_run_policy})


@dataclass(frozen=True, slots=True)
class ActivityWorker:
    task_queue: str
    max_concurrent: int

    def to_properties(self) -> dict[str, Any]:
        return _properties({"task_queue": self.task_queue, "max_concurrent_activities": self.max_concurrent})


@dataclass(frozen=True, slots=True)
class WorkflowWorker:
    task_queue: str
    max_concurrent: int

    def to_properties(self) -> dict[str, Any]:
        return _properties({"task_queue": self.task_queue, "max_concurrent_workflow_tasks": self.max_concurrent})


@dataclass(frozen=True, slots=True)
class ActivityTimeouts:
    start_to_close: int
    heartbeat: int | None = None
    workflow_execution: int | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties({"activity_start_to_close_timeout": self.start_to_close, "activity_heartbeat_timeout": self.heartbeat, "workflow_execution_timeout": self.workflow_execution})


@dataclass(frozen=True, slots=True)
class WorkflowTimeouts:
    execution: int | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties({"workflow_execution_timeout": self.execution})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    maximum_attempts: int = 1

    def to_properties(self) -> dict[str, Any]:
        return _properties({"maximum_attempts": self.maximum_attempts})


@dataclass(frozen=True, slots=True)
class KafkaCluster:
    brokers: str
    version: str | None = None
    dial_timeout: float | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties({"brokers": self.brokers, "version": self.version, "dial_timeout": self.dial_timeout})


@dataclass(frozen=True, slots=True)
class KafkaSecurity:
    protocol: KafkaSecurityProtocol
    mechanism: KafkaSaslMechanism | None = None
    username: str | None = None
    password: str | None = None

    def to_properties(self) -> dict[str, Any]:
        return _properties({"security_protocol": self.protocol, "sasl_mechanism": self.mechanism, "username": self.username, "password": self.password})


@dataclass(frozen=True, slots=True)
class LocalType:
    pass


@dataclass(slots=True)
class Function:
    name: str
    package: Package = ROOT_PACKAGE
    description: str = ""
    initializer_group: InitializerGroup = field(default_factory=InitializerGroup)
    module: Module | _LocalModule | None = None
    public: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.package, Package):
            raise DslValidationError("Function.package must be a Package")
        if (
            self.module is not None
            and self.module is not LOCAL_MODULE
            and not isinstance(self.module, Module)
        ):
            raise DslValidationError(
                "Function.module must be a Module, LOCAL_MODULE, or None"
            )

    def to_properties(self) -> dict[str, Any]:
        return _properties(
            {
                "function_name": self.name,
                "function_package": self.package.path,
                "function_description": self.description,
                "function_initializer_group": self.initializer_group.name,
                "function_module": self.module,
                "public_function": self.public,
            }
        )


@dataclass(slots=True)
class Pool:
    key: str
    name: str
    executors_count: int
    queue_capacity: int | None = None

    def to_document(self) -> dict[str, Any]:
        return _document(
            {
                "name": self.name,
                "executorsCount": self.executors_count,
                "queueCapacity": self.queue_capacity,
            }
        )


@dataclass(slots=True)
class Component:
    """A service-local visual group of whole pipelines, not a runtime unit."""

    key: str
    name: str
    service: Service
    description: str | None = None
    appearance: Appearance = field(default_factory=Appearance)

    def pipeline(self, name: str) -> Pipeline:
        return self.service.pipeline(name, component=self)


@dataclass(slots=True)
class Pipeline:
    key: str
    name: str
    service: Service
    streams: dict[str, Stream] = field(default_factory=dict)
    component: Component | None = None

    def _stream(
        self,
        name: str,
        stream_type: StreamType | str,
        *,
        source: Stream | None = None,
        sources: Sequence[Stream] = (),
        endpoint: Endpoint | None = None,
        value_type: TypeDefinition | DataType | str | None = None,
        key_type: TypeDefinition | DataType | str | None = None,
        function: Function | None = None,
        appearance: Appearance | None = None,
        **properties: Any,
    ) -> Stream:
        if appearance is not None and not isinstance(appearance, Appearance):
            raise DslValidationError("Stream appearance must be an Appearance")
        stream_key = _key(None, name)
        all_streams = {
            item.key
            for pipeline in self.service.pipelines.values()
            for item in pipeline.streams.values()
        }
        if stream_key in all_streams:
            raise DslValidationError(
                f"Duplicate stream key {stream_key!r} in service {self.service.key!r}"
            )
        dependencies = ([source] if source else []) + list(sources)
        if any(item.service is not self.service for item in dependencies):
            raise DslValidationError("A stream source must belong to the same service")
        stream = Stream(
            key=stream_key,
            name=name,
            type=str(_enum_value(stream_type)),
            service=self.service,
            pipeline=self,
            source=source,
            sources=list(sources),
            endpoint=endpoint,
            function=function,
            appearance=appearance or Appearance(),
            properties=_properties(
                {
                    "value_type": value_type,
                    "key_type": key_type,
                    **(function.to_properties() if function else {}),
                    **properties,
                }
            ),
        )
        self.streams[stream.key] = stream
        return stream

    def input(
        self,
        name: str,
        *,
        endpoint: Endpoint,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        sources: Sequence[Stream] = (),
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.INPUT,
            endpoint=endpoint,
            value_type=value_type,
            source=source,
            sources=sources,
            appearance=appearance,
        )

    def map(
        self,
        name: str,
        *,
        function: Function,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.MAP,
            function=function,
            value_type=value_type,
            source=source,
            appearance=appearance,
        )

    def filter(
        self,
        name: str,
        *,
        function: Function,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name, StreamType.FILTER, function=function, source=source, appearance=appearance
        )

    def join(
        self,
        name: str,
        *,
        function: Function,
        value_type: TypeDefinition | DataType | str | None = None,
        join_type: JoinType | None = None,
        join_storage: JoinStorageType | None = None,
        ttl: int | None = None,
        renew_ttl: bool | None = None,
        source: Stream | None = None,
        sources: Sequence[Stream] = (),
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.JOIN,
            function=function,
            value_type=value_type,
            source=source,
            sources=sources,
            appearance=appearance,
            join_type=join_type,
            join_storage=join_storage,
            ttl=ttl,
            renew_ttl=renew_ttl,
        )

    def multi_join(
        self,
        name: str,
        *,
        function: Function,
        value_type: TypeDefinition | DataType | str | None = None,
        join_storage: JoinStorageType | None = None,
        ttl: int | None = None,
        renew_ttl: bool | None = None,
        source: Stream | None = None,
        sources: Sequence[Stream] = (),
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.MULTI_JOIN,
            function=function,
            value_type=value_type,
            source=source,
            sources=sources,
            appearance=appearance,
            join_storage=join_storage,
            ttl=ttl,
            renew_ttl=renew_ttl,
        )

    def process(
        self,
        name: str,
        *,
        function: Function,
        pattern: ProcessPattern | None = None,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.PROCESS,
            function=function,
            source=source,
            appearance=appearance,
            pattern=pattern,
            value_type=value_type,
        )

    def delay(
        self,
        name: str,
        *,
        function: Function,
        duration: int,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.DELAY,
            function=function,
            source=source,
            appearance=appearance,
            duration=duration,
        )

    def flat_map(
        self,
        name: str,
        *,
        function: Function,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.FLAT_MAP,
            function=function,
            value_type=value_type,
            source=source,
            appearance=appearance,
        )

    def flat_map_iterable(
        self,
        name: str,
        *,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.FLAT_MAP_ITERABLE,
            value_type=value_type,
            source=source,
            appearance=appearance,
        )

    def key_by(
        self,
        name: str,
        *,
        function: Function,
        key_type: TypeDefinition | DataType | str,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.KEY_BY,
            function=function,
            key_type=key_type,
            value_type=value_type,
            source=source,
            appearance=appearance,
        )

    def merge(
        self, name: str, *, sources: Sequence[Stream] = (), appearance: Appearance | None = None
    ) -> Stream:
        return self._stream(name, StreamType.MERGE, sources=sources, appearance=appearance)

    def split(
        self, name: str, *, source: Stream | None = None, appearance: Appearance | None = None
    ) -> Stream:
        return self._stream(name, StreamType.SPLIT, source=source, appearance=appearance)

    def case(
        self,
        name: str,
        *,
        function: Function,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name, StreamType.CASE, function=function, source=source, appearance=appearance
        )

    def sink(
        self,
        name: str,
        *,
        endpoint: Endpoint,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.SINK,
            endpoint=endpoint,
            value_type=value_type,
            source=source,
            appearance=appearance,
        )

    def cycle_link(
        self, name: str, *, source: Stream | None = None, appearance: Appearance | None = None
    ) -> Stream:
        return self._stream(name, StreamType.CYCLE_LINK, source=source, appearance=appearance)

    def error(
        self,
        name: str,
        *,
        value_type: TypeDefinition | DataType | str | None = None,
        function: Function | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name,
            StreamType.ERROR,
            value_type=value_type,
            function=function,
            source=source,
            appearance=appearance,
        )

    def when(
        self,
        name: str,
        *,
        value_type: TypeDefinition | DataType | str | None = None,
        source: Stream | None = None,
        appearance: Appearance | None = None,
    ) -> Stream:
        return self._stream(
            name, StreamType.WHEN, value_type=value_type, source=source, appearance=appearance
        )


@dataclass(slots=True)
class Endpoint:
    key: str
    name: str
    connector: Connector
    function: Function
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def function_name(self) -> str:
        return self.function.name

    def to_document(self) -> dict[str, Any]:
        return _document(
            {
                "name": self.name,
                **self.function.to_properties(),
                **self.properties,
            }
        )


@dataclass(slots=True)
class Connector:
    key: str
    name: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)
    endpoints: dict[str, Endpoint] = field(default_factory=dict)

    def _endpoint(
        self,
        name: str,
        *,
        function: Function,
        **properties: Any,
    ) -> Endpoint:
        endpoint_key = _key(None, name)
        endpoint = Endpoint(
            key=endpoint_key,
            name=name,
            connector=self,
            function=function,
            properties=_properties(properties),
        )
        return _insert_unique(self.endpoints, endpoint_key, endpoint, "endpoint")

    def to_document(self) -> dict[str, Any]:
        return _document(
            {
                "name": self.name,
                "type": self.type,
                **self.properties,
                "endpoints": {
                    key: endpoint.to_document()
                    for key, endpoint in self.endpoints.items()
                },
            }
        )


class HttpConnector(Connector):
    def _route(
        self,
        name: str,
        *,
        function: Function,
        method: HTTPMethodType,
        path: str,
        tracing_enabled: bool | None = None,
    ) -> Endpoint:
        return self._endpoint(
            name,
            function=function,
            http_method_type=method,
            path=path,
            tracing_enabled=tracing_enabled,
        )

    def get(self, name: str, *, function: Function, path: str, tracing_enabled: bool | None = None) -> Endpoint:
        return self._route(name, function=function, method=HTTPMethodType.GET, path=path, tracing_enabled=tracing_enabled)

    def post(self, name: str, *, function: Function, path: str, tracing_enabled: bool | None = None) -> Endpoint:
        return self._route(name, function=function, method=HTTPMethodType.POST, path=path, tracing_enabled=tracing_enabled)


class GrpcConnector(Connector):
    def _method(
        self,
        name: str,
        *,
        function: Function,
        method_type: GrpcMethodType,
        method_name: str | None = None,
        tracing_enabled: bool | None = None,
    ) -> Endpoint:
        return self._endpoint(
            name,
            function=function,
            grpc_method_type=method_type,
            method_name=method_name or function.name,
            tracing_enabled=tracing_enabled,
        )

    def unary_method(self, name: str, *, function: Function, method_name: str | None = None, tracing_enabled: bool | None = None) -> Endpoint:
        return self._method(name, function=function, method_type=GrpcMethodType.NO_STREAMING, method_name=method_name, tracing_enabled=tracing_enabled)

    def client_streaming_method(self, name: str, *, function: Function, method_name: str | None = None, tracing_enabled: bool | None = None) -> Endpoint:
        return self._method(name, function=function, method_type=GrpcMethodType.CLIENT_STREAMING, method_name=method_name, tracing_enabled=tracing_enabled)

    def server_streaming_method(self, name: str, *, function: Function, method_name: str | None = None, tracing_enabled: bool | None = None) -> Endpoint:
        return self._method(name, function=function, method_type=GrpcMethodType.SERVER_STREAMING, method_name=method_name, tracing_enabled=tracing_enabled)

    def bidirectional_streaming_method(self, name: str, *, function: Function, method_name: str | None = None, tracing_enabled: bool | None = None) -> Endpoint:
        return self._method(name, function=function, method_type=GrpcMethodType.BIDIRECTIONAL_STREAMING, method_name=method_name, tracing_enabled=tracing_enabled)


class KafkaConnector(Connector):
    def topic(
        self,
        name: str,
        *,
        function: Function,
        topic: str,
        enabled: bool = True,
        tracing_enabled: bool | None = None,
        create_topic: bool | None = None,
        partitions: int | None = None,
        consumer_group: str | None = None,
        replication_factor: int | None = None,
        use_partitioner: bool | None = None,
    ) -> Endpoint:
        return self._endpoint(
            name,
            function=function,
            topic=topic,
            enabled=enabled,
            tracing_enabled=tracing_enabled,
            create_topic=create_topic,
            partitions=partitions,
            consumer_group=consumer_group,
            replication_factor=replication_factor,
            use_partitioner=use_partitioner,
        )


class CronConnector(Connector):
    def schedule(
        self,
        name: str,
        *,
        function: Function,
        trigger: CronSchedule,
        enabled: bool = True,
        tracing_enabled: bool | None = None,
    ) -> Endpoint:
        if not isinstance(trigger, CronSchedule):
            raise DslValidationError("Cron trigger must be a CronSchedule")
        return self._endpoint(
            name,
            function=function,
            enabled=enabled,
            tracing_enabled=tracing_enabled,
            **trigger.to_properties(),
        )


class TemporalConnector(Connector):
    def activity(
        self,
        name: str,
        *,
        function: Function,
        worker: ActivityWorker,
        timeouts: ActivityTimeouts,
        retry: RetryPolicy | None = None,
        schedule: TemporalSchedule | None = None,
        enabled: bool = True,
        tracing_enabled: bool | None = None,
    ) -> Endpoint:
        if not isinstance(worker, ActivityWorker):
            raise DslValidationError("Temporal Activity worker must be an ActivityWorker")
        if not isinstance(timeouts, ActivityTimeouts):
            raise DslValidationError("Temporal Activity timeouts must be ActivityTimeouts")
        if retry is not None and not isinstance(retry, RetryPolicy):
            raise DslValidationError("Temporal retry must be a RetryPolicy")
        if schedule is not None and not isinstance(schedule, TemporalSchedule):
            raise DslValidationError("Temporal schedule must be a TemporalSchedule")
        schedule_properties = schedule.to_properties() if schedule else _properties({
            "schedule": "", "schedule_id": "", "timezone": "UTC",
            "overlap_policy": ScheduleOverlapPolicy.SKIP,
            "missed_run_policy": ScheduleMissedRunPolicy.FIRE_ONCE,
        })
        return self._endpoint(
            name,
            function=function,
            temporal_execution_type=TemporalExecutionType.ACTIVITY,
            enabled=enabled,
            tracing_enabled=tracing_enabled,
            **worker.to_properties(),
            **timeouts.to_properties(),
            **(retry or RetryPolicy()).to_properties(),
            **schedule_properties,
        )

    def workflow(
        self,
        name: str,
        *,
        function: Function,
        worker: WorkflowWorker,
        timeouts: WorkflowTimeouts | None = None,
        retry: RetryPolicy | None = None,
        schedule: TemporalSchedule | None = None,
        enabled: bool = True,
        tracing_enabled: bool | None = None,
    ) -> Endpoint:
        if not isinstance(worker, WorkflowWorker):
            raise DslValidationError("Temporal Workflow worker must be a WorkflowWorker")
        if timeouts is not None and not isinstance(timeouts, WorkflowTimeouts):
            raise DslValidationError("Temporal Workflow timeouts must be WorkflowTimeouts")
        if retry is not None and not isinstance(retry, RetryPolicy):
            raise DslValidationError("Temporal retry must be a RetryPolicy")
        if schedule is not None and not isinstance(schedule, TemporalSchedule):
            raise DslValidationError("Temporal schedule must be a TemporalSchedule")
        schedule_properties = schedule.to_properties() if schedule else _properties({
            "schedule": "", "schedule_id": "", "timezone": "UTC",
            "overlap_policy": ScheduleOverlapPolicy.SKIP,
            "missed_run_policy": ScheduleMissedRunPolicy.FIRE_ONCE,
        })
        return self._endpoint(
            name,
            function=function,
            temporal_execution_type=TemporalExecutionType.WORKFLOW,
            enabled=enabled,
            tracing_enabled=tracing_enabled,
            **worker.to_properties(),
            **(timeouts or WorkflowTimeouts()).to_properties(),
            **(retry or RetryPolicy()).to_properties(),
            **schedule_properties,
        )


class CustomConnector(Connector):
    def endpoint(
        self, name: str, *, function: Function, tracing_enabled: bool | None = None
    ) -> Endpoint:
        return self._endpoint(name, function=function, tracing_enabled=tracing_enabled)


@dataclass(slots=True)
class Stream:
    key: str
    name: str
    type: str
    service: Service
    pipeline: Pipeline
    source: Stream | None = None
    sources: list[Stream] = field(default_factory=list)
    endpoint: Endpoint | None = None
    function: Function | None = None
    error_stream: Stream | None = None
    appearance: Appearance = field(default_factory=Appearance)
    properties: dict[str, Any] = field(default_factory=dict)

    def __rshift__(self, target: Stream) -> Stream:
        if not isinstance(target, Stream):
            return NotImplemented
        if target.service is not self.service:
            raise DslValidationError(
                "Connected streams must belong to the same service"
            )
        target.source = self
        return target

    def __lshift__(self, source: Stream) -> Stream:
        if not isinstance(source, Stream):
            return NotImplemented
        if source.service is not self.service:
            raise DslValidationError(
                "All stream sources must belong to the same service"
            )
        self.sources.append(source)
        return self

    def __or__(self, error_stream: Stream) -> Stream:
        self.on_error(error_stream)
        return error_stream

    def from_sources(self, *sources: Stream) -> Stream:
        if any(source.service is not self.service for source in sources):
            raise DslValidationError(
                "All stream sources must belong to the same service"
            )
        self.sources = list(sources)
        return self

    def on_error(self, error_stream: Stream) -> Stream:
        if error_stream.service is not self.service:
            raise DslValidationError("An error stream must belong to the same service")
        if error_stream.type != StreamType.ERROR.value:
            raise DslValidationError("on_error() target must be an Error stream")
        self.error_stream = error_stream
        return self

    def function_call(
        self,
        target: Stream,
        *,
        async_: bool | None = None,
    ) -> Link:
        return self.service._link(
            self,
            target,
            call_semantics=CallSemantics.FUNCTION_CALL,
            async_=async_,
        )

    def task_pool_call(
        self,
        target: Stream,
        *,
        pool: Pool,
    ) -> Link:
        return self.service._link(
            self,
            target,
            call_semantics=CallSemantics.TASK_POOL,
            pool=pool,
        )

    def priority_task_pool_call(
        self,
        target: Stream,
        *,
        pool: Pool,
        priority: int,
    ) -> Link:
        return self.service._link(
            self,
            target,
            call_semantics=CallSemantics.PRIORITY_TASK_POOL,
            pool=pool,
            priority=priority,
        )

    def parallel_call(self, target: Stream) -> Link:
        return self.service._link(
            self,
            target,
            call_semantics=CallSemantics.PARALLEL_CALL,
        )

    def to_document(self) -> dict[str, Any]:
        return _document(
            {
                "name": self.name,
                "type": self.type,
                "source": self.source.key if self.source else None,
                "sources": (
                    [source.key for source in self.sources] if self.sources else None
                ),
                "endpoint": self.endpoint.key if self.endpoint else None,
                "errorStream": self.error_stream.key if self.error_stream else None,
                **self.properties,
            }
        )


@dataclass(slots=True)
class Link:
    key: str
    source: Stream
    target: Stream
    properties: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        return _document(
            {"from": self.source.key, "to": self.target.key, **self.properties}
        )


@dataclass(slots=True)
class Service:
    key: str
    name: str
    programming_language: str
    module_path: str
    appearance: Appearance = field(default_factory=Appearance)
    properties: dict[str, Any] = field(default_factory=dict)
    pipelines: dict[str, Pipeline] = field(default_factory=dict)
    links: dict[str, Link] = field(default_factory=dict)
    components: dict[str, Component] = field(default_factory=dict)

    def component(
        self, name: str, *, description: str | None = None,
        appearance: Appearance | None = None,
    ) -> Component:
        component_key = _key(None, name)
        value = Component(component_key, name, self, description, appearance or Appearance())
        group = {"name": name, "description": description}
        normalize_components({"version": 1, "groups": {component_key: group}, "pipelines": {}}, [])
        return _insert_unique(self.components, component_key, value, "component")

    def pipeline(self, name: str, *, component: Component | None = None) -> Pipeline:
        if component is not None and (
            not isinstance(component, Component)
            or component.service is not self
            or self.components.get(component.key) is not component
        ):
            raise DslValidationError("Component must be registered in this service")
        pipeline_key = _key(None, name)
        value = Pipeline(pipeline_key, name, self, component=component)
        return _insert_unique(self.pipelines, pipeline_key, value, "pipeline")

    def _link(
        self,
        source: Stream,
        target: Stream,
        *,
        call_semantics: CallSemantics | str | None = CallSemantics.INHERITED,
        async_: bool | None = None,
        pool: Pool | None = None,
        priority: int | None = None,
    ) -> Link:
        if source.service is not self or target.service is not self:
            raise DslValidationError(
                "Both ends of a persisted link must belong to this service"
            )
        if target.source is not source and source not in target.sources:
            raise DslValidationError(
                f"Cannot configure link {source.key!r} -> {target.key!r}: "
                "create the graph connection with >> or << first"
            )
        link_key = f"{source.key}_{target.key}"
        if not link_key.strip():
            raise DslValidationError("A persisted link key must not be empty")
        pool_name = pool.name if pool is not None else None
        link = Link(
            key=link_key,
            source=source,
            target=target,
            properties=_properties(
                {
                    "call_semantics": call_semantics,
                    "async_": async_,
                    "pool_name": pool_name,
                    "priority": priority,
                }
            ),
        )
        return _insert_unique(self.links, link_key, link, "link")

    def to_document(self) -> dict[str, Any]:
        service_properties = dict(self.properties)
        appearance = {
            "color": self.appearance.color or "#4A90D9",
            "pipelines": {
                pipeline.key: {
                    key: {
                        "x": stream.appearance.x if stream.appearance.x is not None else 0,
                        "y": stream.appearance.y if stream.appearance.y is not None else 0,
                    }
                    for key, stream in pipeline.streams.items()
                }
                for pipeline in self.pipelines.values()
            },
        }
        if self.components or any(p.component is not None for p in self.pipelines.values()):
            groups = {}
            memberships = {}
            for key, component in self.components.items():
                if component.service is not self or component.key != key:
                    raise DslValidationError("Component identity or service ownership changed")
                group = {"name": component.name}
                if component.description:
                    group["description"] = component.description
                position = {axis: getattr(component.appearance, axis) for axis in ("x", "y")
                            if getattr(component.appearance, axis) is not None}
                if position:
                    group["position"] = position
                output_key = _key(None, component.name)
                if output_key in groups:
                    raise DslValidationError(f"Duplicate component: {output_key}")
                groups[output_key] = group
            for pipeline in self.pipelines.values():
                component = pipeline.component
                if component is not None:
                    if (not isinstance(component, Component) or component.service is not self
                            or self.components.get(component.key) is not component):
                        raise DslValidationError("Pipeline component must belong to its service")
                    memberships[pipeline.key] = _key(None, component.name)
            appearance["components"] = normalize_components(
                {"version": 1, "groups": groups, "pipelines": memberships}, self.pipelines,
            )
        body = {
            "name": self.name,
            "programmingLanguage": self.programming_language,
            "modulePath": self.module_path,
            **service_properties,
            "appearance": appearance,
            "pipelines": {
                pipeline.key: {
                    key: stream.to_document()
                    for key, stream in pipeline.streams.items()
                }
                for pipeline in self.pipelines.values()
            },
        }
        if self.links:
            body["links"] = {
                key: link.to_document() for key, link in self.links.items()
            }
        return _document(body)


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


_NoAliasDumper.add_representer(
    _ExplicitNull,
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", "null"),
)


@dataclass(slots=True)
class Project:
    name: str
    module_version: str | None = None
    repo_path: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    modules: dict[str, Module] = field(default_factory=dict)
    pools: dict[str, Pool] = field(default_factory=dict)
    types: dict[str, TypeDefinition] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    connectors: dict[str, Connector] = field(default_factory=dict)

    def _type(
        self,
        name: str,
        data_type: DataType | str,
        *,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
        **properties: Any,
    ) -> TypeDefinition:
        if isinstance(module, LocalType):
            module = NULL
        if module is not None and module is not NULL and not isinstance(module, Module):
            raise DslValidationError("Type.module must be a Module, LocalType, or None")
        if package is not None and not isinstance(package, Package):
            raise DslValidationError("Type.package must be a Package or None")
        type_key = _key(None, name)
        value = TypeDefinition(
            type_key,
            name,
            data_type,
            _properties({"module": module, "package": package, **properties}),
        )
        return _insert_unique(self.types, type_key, value, "type")

    def _scalar_type(
        self,
        name: str,
        data_type: DataType,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._type(
            name,
            data_type,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def int_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.INT,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def uint_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UINT,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def byte_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.BYTE,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def char_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.CHAR,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def boolean_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.BOOLEAN,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def unicode_char_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UNICODE_CHAR,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def string_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.STRING,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def unicode_string_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UNICODE_STRING,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def float_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.FLOAT,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def double_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.DOUBLE,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def int8_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.INT8,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def int16_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.INT16,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def int32_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.INT32,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def int64_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.INT64,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def uint8_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UINT8,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def uint16_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UINT16,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def uint32_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UINT32,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def uint64_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.UINT64,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def any_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.ANY,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def error_type(
        self,
        name: str,
        *,
        use_alias: bool | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._scalar_type(
            name,
            DataType.ERROR,
            use_alias=use_alias,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def struct_type(
        self,
        name: str,
        *,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
        transfer_by_value: bool | None = None,
        definition_format: TypeDefinitionFormat | None = None,
        type_definition: str | None = None,
        type_import: str | None = None,
    ) -> TypeDefinition:
        return self._type(
            name,
            DataType.STRUCT,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
            transfer_by_value=transfer_by_value,
            definition_format=definition_format,
            type_definition=type_definition,
            type_import=type_import,
        )

    def array_type(
        self,
        name: str,
        *,
        value_type: TypeDefinition | DataType,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._type(
            name,
            DataType.ARRAY,
            value_type=value_type,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def map_type(
        self,
        name: str,
        *,
        key_type: TypeDefinition | DataType,
        value_type: TypeDefinition | DataType,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
    ) -> TypeDefinition:
        return self._type(
            name,
            DataType.MAP,
            key_type=key_type,
            value_type=value_type,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
        )

    def custom_type(
        self,
        name: str,
        *,
        type_definition: str | None = None,
        type_import: str | None = None,
        description: str | None = None,
        public_type: bool | None = None,
        module: Module | LocalType | _ExplicitNull | None = None,
        package: Package | None = None,
        definition_format: TypeDefinitionFormat | None = None,
    ) -> TypeDefinition:
        return self._type(
            name,
            DataType.CUSTOM,
            type_definition=type_definition,
            type_import=type_import,
            description=description,
            public_type=public_type,
            module=module,
            package=package,
            definition_format=definition_format,
        )

    def module(
        self,
        name: str,
        *,
        module_path: str,
        golang_version: str,
    ) -> Module:
        module_key = name
        value = Module(module_key, name, module_path, golang_version)
        return _insert_unique(self.modules, module_key, value, "module")

    def pool(
        self,
        name: str,
        *,
        executors_count: int,
        queue_capacity: int | None = None,
    ) -> Pool:
        pool_key = _key(None, name)
        value = Pool(pool_key, name, executors_count, queue_capacity)
        return _insert_unique(self.pools, pool_key, value, "pool")

    def _connector(
        self,
        name: str,
        connector_type: ConnectorType | str,
        *,
        connector_class: type[Connector] = Connector,
        module: Module | None = None,
        implementation: DataConnectorImplementation | None = None,
        go_implementation: DataConnectorImplementation | None = None,
        cpp_userver_implementation: DataConnectorImplementation | None = None,
        cpp_boost_implementation: DataConnectorImplementation | None = None,
        python_implementation: DataConnectorImplementation | None = None,
        rust_implementation: DataConnectorImplementation | None = None,
        type_script_implementation: DataConnectorImplementation | None = None,
        **properties: Any,
    ) -> Connector:
        if module is not None and not isinstance(module, Module):
            raise DslValidationError("Connector.module must be a Module or None")
        connector_key = _key(None, name)
        value = connector_class(
            connector_key,
            name,
            str(_enum_value(connector_type)),
            _properties(
                {
                    "module": module,
                    "implementation": implementation,
                    "go_implementation": go_implementation,
                    "cpp_userver_implementation": cpp_userver_implementation,
                    "cpp_boost_implementation": cpp_boost_implementation,
                    "python_implementation": python_implementation,
                    "rust_implementation": rust_implementation,
                    "type_script_implementation": type_script_implementation,
                    **properties,
                }
            ),
        )
        return _insert_unique(self.connectors, connector_key, value, "connector")

    def http_connector(
        self,
        name: str,
        *,
        module: Module | None = None,
        host: str | None = None,
        port: int | None = None,
        use_dedicated_listener: bool | None = None,
        go_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.NET_HTTP,
        cpp_userver_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.USERVER_HTTP,
        cpp_boost_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.BOOST_BEAST_HTTP,
        python_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.AIOHTTP,
        rust_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.RUST_AXUM,
        type_script_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.NODE_HTTP,
    ) -> HttpConnector:
        return self._connector(
            name,
            ConnectorType.HTTP,
            connector_class=HttpConnector,
            module=module,
            host=host,
            port=port,
            use_dedicated_listener=use_dedicated_listener,
            go_implementation=go_implementation,
            cpp_userver_implementation=cpp_userver_implementation,
            cpp_boost_implementation=cpp_boost_implementation,
            python_implementation=python_implementation,
            rust_implementation=rust_implementation,
            type_script_implementation=type_script_implementation,
        )

    def grpc_connector(
        self,
        name: str,
        *,
        module: Module | None = None,
        programming_language: ProgrammingLanguage | None = None,
        address: str | None = None,
        connections_count: int | None = None,
        go_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.GOOGLE_GRPC,
        cpp_userver_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.USERVER_GRPC,
        cpp_boost_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.ASIO_GRPC,
        python_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.GOOGLE_GRPC,
        rust_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.RUST_TONIC,
        type_script_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.GRPC_JS,
    ) -> GrpcConnector:
        return self._connector(
            name,
            ConnectorType.GRPC,
            connector_class=GrpcConnector,
            module=module,
            programming_language=programming_language,
            address=address,
            connections_count=connections_count,
            go_implementation=go_implementation,
            cpp_userver_implementation=cpp_userver_implementation,
            cpp_boost_implementation=cpp_boost_implementation,
            python_implementation=python_implementation,
            rust_implementation=rust_implementation,
            type_script_implementation=type_script_implementation,
        )

    def kafka_connector(
        self,
        name: str,
        *,
        cluster: KafkaCluster,
        security: KafkaSecurity | None = None,
        use_partitioner: bool | None = None,
        async_: bool | None = None,
        go_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.IBM_SARAMA,
        cpp_userver_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.USERVER_KAFKA,
        cpp_boost_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.LIBRDKAFKA,
        python_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.AIOKAFKA,
        rust_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.RUST_RDKAFKA,
        type_script_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.CONFLUENT_KAFKA_JAVASCRIPT,
    ) -> KafkaConnector:
        if not isinstance(cluster, KafkaCluster):
            raise DslValidationError("Kafka cluster must be a KafkaCluster")
        if security is not None and not isinstance(security, KafkaSecurity):
            raise DslValidationError("Kafka security must be KafkaSecurity or None")
        return self._connector(
            name,
            ConnectorType.KAFKA,
            connector_class=KafkaConnector,
            use_partitioner=use_partitioner,
            async_=async_,
            **cluster.to_properties(),
            **(security.to_properties() if security else {}),
            go_implementation=go_implementation,
            cpp_userver_implementation=cpp_userver_implementation,
            cpp_boost_implementation=cpp_boost_implementation,
            python_implementation=python_implementation,
            rust_implementation=rust_implementation,
            type_script_implementation=type_script_implementation,
        )

    def cron_connector(
        self,
        name: str,
        *,
        go_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.GO_GOCRON,
        cpp_userver_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.CPP_LIBCRON,
        cpp_boost_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.CPP_LIBCRON,
        python_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.PYTHON_APSCHEDULER,
        rust_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.RUST_CRONER,
        type_script_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.NODE_CRONER,
    ) -> CronConnector:
        return self._connector(
            name,
            ConnectorType.CRON,
            connector_class=CronConnector,
            go_implementation=go_implementation,
            cpp_userver_implementation=cpp_userver_implementation,
            cpp_boost_implementation=cpp_boost_implementation,
            python_implementation=python_implementation,
            rust_implementation=rust_implementation,
            type_script_implementation=type_script_implementation,
        )

    def temporal_connector(
        self,
        name: str,
        *,
        address: str,
        namespace: str,
        identity: str | None = None,
        api_key: str | None = None,
        tls_enabled: bool | None = None,
        tls_server_name: str | None = None,
        tls_ca_file: str | None = None,
        tls_cert_file: str | None = None,
        tls_key_file: str | None = None,
        worker_stop_timeout: int | None = None,
        go_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.TEMPORAL_GO,
        python_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.TEMPORAL_PYTHON,
        type_script_implementation: (
            DataConnectorImplementation | None
        ) = DataConnectorImplementation.TEMPORAL_TYPESCRIPT,
    ) -> TemporalConnector:
        return self._connector(
            name,
            ConnectorType.TEMPORAL,
            connector_class=TemporalConnector,
            address=address,
            namespace=namespace,
            identity=identity,
            api_key=api_key,
            tls_enabled=tls_enabled,
            tls_server_name=tls_server_name,
            tls_ca_file=tls_ca_file,
            tls_cert_file=tls_cert_file,
            tls_key_file=tls_key_file,
            worker_stop_timeout=worker_stop_timeout,
            go_implementation=go_implementation,
            python_implementation=python_implementation,
            type_script_implementation=type_script_implementation,
        )

    def custom_connector(
        self,
        name: str,
        *,
        implementation: DataConnectorImplementation = DataConnectorImplementation.FUNCTION,
        module: Module | None = None,
    ) -> CustomConnector:
        return self._connector(
            name,
            ConnectorType.CUSTOM,
            connector_class=CustomConnector,
            implementation=implementation,
            module=module,
        )

    def service(
        self,
        name: str,
        *,
        language: ServiceLanguage,
        module: ServiceModule,
        appearance: Appearance | None = None,
        http_server: HttpServer | None = None,
        grpc_server: GrpcServer | None = None,
        observability: Observability | None = None,
        kubernetes: Kubernetes | None = None,
        **properties: Any,
    ) -> Service:
        if not isinstance(language, ServiceLanguage):
            raise DslValidationError(
                "Service language must be Golang, CppUserver, CppBoost, Python, Rust, or TypeScript"
            )
        if not isinstance(module, ServiceModule):
            raise DslValidationError("Service module must be a ServiceModule")
        if appearance is not None and not isinstance(appearance, Appearance):
            raise DslValidationError("Service appearance must be an Appearance")
        if "color" in properties:
            raise DslValidationError(
                "Service color must be provided as appearance=Appearance(color=...)"
            )
        groups = (
            ("http_server", http_server, HttpServer),
            ("grpc_server", grpc_server, GrpcServer),
            ("observability", observability, Observability),
            ("kubernetes", kubernetes, Kubernetes),
        )
        for group_name, group, expected_type in groups:
            if group is not None and not isinstance(group, expected_type):
                raise DslValidationError(
                    f"Service {group_name} must be a {expected_type.__name__}"
                )
        grouped_properties = {
            "programming_language",
            "module_path",
            "golang_version",
            "http_host",
            "http_port",
            "grpc_host",
            "grpc_port",
            "default_grpc_timeout",
            "metrics_handler",
            "status_handler",
            "startup_handler",
            "readiness_handler",
            "liveness_handler",
            "kubernetes_workload_type",
        }
        direct_grouped_properties = grouped_properties.intersection(properties)
        if direct_grouped_properties:
            names = ", ".join(sorted(direct_grouped_properties))
            raise DslValidationError(
                f"Grouped service properties must use their configuration objects: {names}"
            )
        service_key = _key(None, name)
        defaults = {
            "default_call_semantics": CallSemantics.FUNCTION_CALL,
            "environment": "",
            "http_host": "0.0.0.0",
            "http_port": 8080,
            "grpc_host": "0.0.0.0",
            "grpc_port": 9090,
            "default_grpc_timeout": 30000,
            "shutdown_timeout": 30000,
            "kubernetes_workload_type": "Deployment",
            "status_handler": "status",
            "metrics_handler": "metrics",
            "startup_handler": "health/startup",
            "readiness_handler": "health/ready",
            "liveness_handler": "health/live",
        }
        defaults.update(properties)
        defaults.update(language.to_properties())
        for group in (http_server, grpc_server, observability, kubernetes):
            if group is not None:
                defaults.update(group.to_properties())
        value = Service(
            key=service_key,
            name=name,
            programming_language=str(_enum_value(language.programming_language)),
            module_path=module.path,
            appearance=appearance or Appearance(),
            properties=_properties(defaults),
        )
        return _insert_unique(self.services, service_key, value, "service")

    def _validate_references(self) -> None:
        endpoint_keys: set[str] = set()
        stream_keys: set[str] = set()
        for connector in self.connectors.values():
            for endpoint in connector.endpoints.values():
                if endpoint.key in endpoint_keys:
                    raise DslValidationError(
                        f"Endpoint key {endpoint.key!r} must be globally unique"
                    )
                endpoint_keys.add(endpoint.key)
        for service in self.services.values():
            for pipeline in service.pipelines.values():
                for stream in pipeline.streams.values():
                    if stream.key in stream_keys:
                        raise DslValidationError(
                            f"Stream key {stream.key!r} must be globally unique"
                        )
                    stream_keys.add(stream.key)
                    if (
                        stream.endpoint is not None
                        and stream.endpoint.key not in endpoint_keys
                    ):
                        raise DslValidationError(
                            f"Stream {stream.key!r} references an endpoint outside this project"
                        )

    def validate(self):
        """Return diagnostics ported from servicegen.ValidateStreamApp."""
        self._validate_references()
        from .validation import validate_project

        return validate_project(self)

    def to_document(self) -> dict[str, Any]:
        self._validate_references()
        settings = {
            "name": self.name,
            "moduleVersion": self.module_version,
            "repoPath": self.repo_path,
            **_properties(self.properties),
        }
        return _document(
            {
                "dataConnectors": {
                    key: connector.to_document()
                    for key, connector in self.connectors.items()
                },
                "modules": {
                    key: module.to_document() for key, module in self.modules.items()
                },
                "pools": {key: pool.to_document() for key, pool in self.pools.items()},
                "services": {
                    key: service.to_document() for key, service in self.services.items()
                },
                "settings": settings,
                "types": {
                    key: type_.to_document() for key, type_ in self.types.items()
                },
            }
        )

    def to_yaml(self) -> str:
        return yaml.dump(
            self.to_document(),
            Dumper=_NoAliasDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=100,
        )

    def generate_code(
        self,
        *,
        id_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        env_file: str = ".env",
        base_url: str | None = None,
        timeout: float = 120,
    ):
        from .code_generation import ServiceArchitectClient

        return ServiceArchitectClient.from_env(
            env_file,
            id_token=id_token,
            username=username,
            password=password,
            base_url=base_url,
            timeout=timeout,
        ).generate_code(self)

    def write_yaml(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_yaml(), encoding="utf-8")
        return destination
