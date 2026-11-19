from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
from urllib.parse import urlsplit

from .query_validation import POSTGRES_TARGETS, validate_query_bindings, validate_query_connector
from .pulsar_validation import validate_connector as validate_pulsar_connector, validate_endpoint as validate_pulsar_endpoint
from .model import NULL, Connector, Endpoint, Project, Service, Stream
from .retired_backends import CPP_BOOST_RETIREMENT, is_retired_language
from .connector_bindings import REMOVED_CONNECTOR_FIELDS, normalize_connector_implementations
from .native_bindings import NativeTypeBindingError, require_type_fields


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
UNKNOWN_FIELD = "SG_SCHEMA_UNKNOWN_FIELD"
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

LANGUAGES = {"GoLang", "CppUserver", "Python", "Rust", "CppCoro", "TypeScript"}
ENVIRONMENTS = {"", "local", "debug", "staging", "production"}
LOG_LEVELS = {"", "CRITICAL", "FATAL", "ERROR", "WARNING", "INFO", "DEBUG"}
WORKLOADS = {"Deployment", "StatefulSet"}
CONNECTOR_TYPES = {"HTTP", "gRPC", "Kafka", "Custom", "Cron", "Temporal", "NATS", "JetStream", "RabbitMQ", "RedisStreams", "Pulsar", "PostgreSQLBun", "PostgreSQLKysely", "PostgreSQLSQLAlchemy", "PostgreSQLSQLx", "PostgreSQLUserver", "PostgreSQLLibpq", "S3AWS", "S3Userver"}
STREAM_TYPES = {
    "Input",
    "SubStream",
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
    "Query",
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
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}
JOIN_TYPES = {"Inner", "Left", "Right", "Outer", 1, 2, 3, 4}
JOIN_STORAGES = {"HashMap", "RocksDB", "Aerospike", 1, 2, 3}
PROCESS_PATTERNS = {"Execute", "Collect", 1, 2}
OUTPUT_TYPES = {
    "Input",
    "SubStream",
    "Map",
    "Join",
    "MultiJoin",
    "Process",
    "FlatMap",
    "FlatMapIterable",
    "KeyBy",
    "Sink",
    "Query",
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
ERROR_OUTPUT_TYPES = {"Input", "Process", "Sink", "Query"}


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
        from .connector_directions import unsupported_direction
        for stream in self.streams.values():
            direction = {"Input": "source", "Sink": "sink", "Query": "query"}.get(stream.type)
            if not direction or stream.endpoint is None:
                continue
            reason = unsupported_direction(stream.service.programming_language, stream.endpoint.connector.type, direction)
            if reason:
                self.add(UNSUPPORTED, "capability", reason, self.stream_path(stream) + ".endpoint",
                         "stream", stream.name, feature=direction, direction=direction,
                         connector=stream.endpoint.connector.type, language=stream.service.programming_language)
        self.required(
            self.project.name, "$.settings.name", "settings", self.project.name, "name"
        )
        self.validate_services()
        self.validate_modules_types_pools()
        self.validate_connectors()
        self.validate_streams()
        self.validate_substreams()
        self.validate_endpoint_contracts()
        self.validate_endpoint_usage()
        self.validate_functions()
        from .type_usage_validation import validate_type_generation_contracts

        validate_type_generation_contracts(self)
        self.validate_consumers_links_cycles()
        from .component_validation import validate_components

        validate_components(self)
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
            if is_retired_language(service.programming_language):
                self.add(UNSUPPORTED, "capability", CPP_BOOST_RETIREMENT,
                         path + ".programmingLanguage", "service", service.name)
            else:
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
            try:
                require_type_fields(value.properties)
            except NativeTypeBindingError as error:
                stage = "semantic" if error.code.startswith("SG_SEMANTIC_") else "schema"
                self.add(error.code, stage, str(error), f"{path}.{error.field}", "type", value.name)
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

    def validate_redis_connector(self, connector: Connector, path: str) -> None:
        def invalid(key: str, message: str, code: str = RANGE) -> None:
            self.add(code, "schema", message, path + "." + key, "dataConnector", connector.name)
        if connector.type != "RedisStreams":
            if "redisDatabase" in connector.properties:
                invalid("redisDatabase", "redisDatabase requires RedisStreams", UNKNOWN_FIELD)
            return
        servers = _prop(connector, "servers")
        tls_url, plain_url = False, False
        if not isinstance(servers, list) or len(servers) != 1:
            invalid("servers", "RedisStreams requires an exactly one standalone server URL", REQUIRED)
        else:
            for server in servers:
                try:
                    url = urlsplit(server) if isinstance(server, str) else None
                    valid = (url is not None and url.scheme in {"redis", "rediss"}
                             and server.startswith(("redis://", "rediss://"))
                             and bool(url.hostname) and url.username is None and url.password is None
                             and not url.path and "?" not in server and "#" not in server
                             and not url.netloc.endswith(":")
                             and not any(c.isspace() or unicodedata.category(c) == "Cc" for c in server))
                    if url is not None:
                        valid = valid and (url.port is None or 1 <= url.port <= 65535)
                except ValueError:
                    valid = False
                if not valid:
                    invalid("servers", "Expected redis:// or rediss:// without credentials, path, query, fragment or controls; port must be 1..65535")
                    break
                tls_url |= url.scheme == "rediss"
                plain_url |= url.scheme == "redis"
        if "redisDatabase" in connector.properties:
            value = _prop(connector, "redisDatabase")
            if type(value) is not int or value < 0:
                invalid("redisDatabase", "Database index must be a nonnegative integer")
        for key in ("connectTimeoutMs", "operationTimeoutMs"):
            if key in connector.properties and (type(_prop(connector, key)) is not int or not 1 <= _prop(connector, key) <= 9223372036854):
                invalid(key, "Timeout must be an integer between 1 and 9223372036854 milliseconds")
        for key in ("username", "password"):
            if key in connector.properties:
                invalid(key, "Credentials must be supplied by runtime overrides, never topology", UNSUPPORTED)
        for key in ("tlsServerName", "tlsCaFile", "tlsCertFile", "tlsKeyFile"):
            if key in connector.properties:
                value = _prop(connector, key)
                if not isinstance(value, str) or not value or any(unicodedata.category(c) == "Cc" for c in value):
                    invalid(key, "Expected nonempty string without control characters")
        if "tlsEnabled" in connector.properties and type(_prop(connector, "tlsEnabled")) is not bool:
            invalid("tlsEnabled", "tlsEnabled must be boolean")
        if bool(_prop(connector, "tlsCertFile")) != bool(_prop(connector, "tlsKeyFile")):
            invalid("tlsKeyFile", "TLS client certificate and key must be supplied together")
        if _prop(connector, "tlsEnabled") is not True:
            if tls_url and plain_url:
                invalid("servers", "Mixed TLS/plain servers require tlsEnabled")
            if not tls_url and any(k in connector.properties for k in ("tlsServerName", "tlsCaFile", "tlsCertFile", "tlsKeyFile")):
                invalid("tlsEnabled", "TLS settings require tlsEnabled or rediss://")
        for key in ("brokers", "version", "dialTimeout", "securityProtocol", "saslMechanism", "usePartitioner", "async", "address", "host", "port", "namespace", "identity", "apiKey", "workerStopTimeout", "connectionsCount", "useDedicatedListener", "module"):
            if key in connector.properties:
                invalid(key, "Field does not apply to RedisStreams", UNKNOWN_FIELD)

    def validate_rabbitmq_connector(self, connector: Connector, path: str) -> None:
        def invalid(key: str, message: str, code: str = RANGE) -> None:
            self.add(code, "schema", message, path + "." + key, "dataConnector", connector.name)
        if connector.type != "RabbitMQ":
            if "virtualHost" in connector.properties:
                invalid("virtualHost", "virtualHost requires RabbitMQ", UNKNOWN_FIELD)
            return
        servers = _prop(connector, "servers")
        tls_url, plain_url = False, False
        if not isinstance(servers, list) or not servers:
            invalid("servers", "RabbitMQ requires an explicit nonempty server URL list", REQUIRED)
        else:
            for server in servers:
                try:
                    url = urlsplit(server) if isinstance(server, str) else None
                    valid = (url is not None and url.scheme in {"amqp", "amqps"}
                             and server.startswith(("amqp://", "amqps://"))
                             and bool(url.hostname) and url.username is None and url.password is None
                             and not url.path and "?" not in server and "#" not in server
                             and not url.netloc.endswith(":")
                             and not any(c.isspace() or unicodedata.category(c) == "Cc" for c in server))
                    if url is not None:
                        valid = valid and (url.port is None or 1 <= url.port <= 65535)
                except ValueError:
                    valid = False
                if not valid:
                    invalid("servers", "Expected amqp:// or amqps:// without credentials, path, query, fragment or controls; port must be 1..65535")
                    break
                tls_url |= url.scheme == "amqps"
                plain_url |= url.scheme == "amqp"
        for key in ("connectTimeoutMs", "operationTimeoutMs"):
            if key in connector.properties and (type(_prop(connector, key)) is not int or not 1 <= _prop(connector, key) <= 9223372036854):
                invalid(key, "Timeout must be an integer between 1 and 9223372036854 milliseconds")
        for key in ("username", "password"):
            if key in connector.properties:
                invalid(key, "Credentials must be supplied by runtime overrides, never topology", UNSUPPORTED)
        for key in ("virtualHost", "tlsServerName", "tlsCaFile", "tlsCertFile", "tlsKeyFile"):
            if key in connector.properties:
                value = _prop(connector, key)
                if not isinstance(value, str) or not value or any(unicodedata.category(c) == "Cc" for c in value):
                    invalid(key, "Expected nonempty string without control characters")
        if "tlsEnabled" in connector.properties and type(_prop(connector, "tlsEnabled")) is not bool:
            invalid("tlsEnabled", "tlsEnabled must be boolean")
        if bool(_prop(connector, "tlsCertFile")) != bool(_prop(connector, "tlsKeyFile")):
            invalid("tlsKeyFile", "TLS client certificate and key must be supplied together")
        if _prop(connector, "tlsEnabled") is not True:
            if tls_url and plain_url:
                invalid("servers", "Mixed TLS/plain servers require tlsEnabled")
            if not tls_url and any(k in connector.properties for k in ("tlsServerName", "tlsCaFile", "tlsCertFile", "tlsKeyFile")):
                invalid("tlsEnabled", "TLS settings require tlsEnabled or amqps://")
        for key in ("brokers", "version", "dialTimeout", "securityProtocol", "saslMechanism", "usePartitioner", "async", "address", "host", "port", "namespace", "identity", "apiKey", "workerStopTimeout", "connectionsCount", "useDedicatedListener", "module"):
            if key in connector.properties:
                invalid(key, "Field does not apply to RabbitMQ", UNKNOWN_FIELD)

    def validate_rabbitmq_typescript(self, endpoint: Endpoint, path: str, connector_path: str) -> None:
        connector = endpoint.connector

        def unsupported(obj, obj_path, kind, field, reason):
            self.add(UNSUPPORTED, "capability", reason, obj_path + "." + field, kind, obj.name)

        if _prop(connector, "virtualHost") not in (None, "/"):
            unsupported(connector, connector_path, "dataConnector", "virtualHost",
                        "Official RabbitMQ JS client supports only the default virtual host")
        for field in ("connectTimeoutMs", "operationTimeoutMs"):
            value = _prop(connector, field)
            if isinstance(value, int) and value > 2147483647:
                unsupported(connector, connector_path, "dataConnector", field,
                            "Node timers support at most 2147483647 milliseconds")
        tls_name = _prop(connector, "tlsServerName")
        servers = _prop(connector, "servers")
        if tls_name and isinstance(servers, list):
            for server in servers:
                try:
                    hostname = urlsplit(server).hostname
                except (ValueError, TypeError, AttributeError):
                    continue  # Generic URI validation owns malformed URLs.
                if hostname != tls_name:
                    unsupported(connector, connector_path, "dataConnector", "tlsServerName",
                                "Official RabbitMQ JS client requires TLS name matching each server hostname")
                    break
        for field in ("queueName", "exchangeName", "routingKey"):
            value = _prop(endpoint, field)
            if isinstance(value, str) and any(char in value for char in "/?#%"):
                unsupported(endpoint, path, "endpoint", field,
                            "Official RabbitMQ JS resource addresses cannot contain URI delimiters")

    def validate_redis_endpoint(self, endpoint: Endpoint, path: str) -> None:
        unique = {"streamKey", "consumerName", "createConsumerGroup", "groupStartId", "readCount", "readBlockMs", "claimIdleMs", "claimIntervalMs"}
        def invalid(key, message, code=RANGE):
            self.add(code, "schema", message, path + "." + key, "endpoint", endpoint.name)
        if endpoint.connector.type != "RedisStreams":
            for key in sorted(unique.intersection(endpoint.properties)):
                invalid(key, "Field requires RedisStreams", UNKNOWN_FIELD)
            return
        for key in ("streamKey", "consumerName", "consumerGroup"):
            value = _prop(endpoint, key)
            if key == "streamKey" or key in endpoint.properties:
                if not isinstance(value, str) or not value or any(unicodedata.category(c) == "Cc" for c in value):
                    invalid(key, "Expected nonempty name without controls")
        for key in ("createStream", "createConsumerGroup"):
            if key in endpoint.properties and type(_prop(endpoint, key)) is not bool:
                invalid(key, "Creation flag must be boolean")
        for key, maximum in (("readCount",4096),("readBlockMs",60000),("claimIdleMs",2147483647),("claimIntervalMs",2147483647),("publisherMaxInFlight",4096)):
            if key in endpoint.properties:
                value = _prop(endpoint, key)
                if type(value) is not int or not 1 <= value <= maximum:
                    invalid(key, f"Expected integer in 1..{maximum}")
        if "groupStartId" in endpoint.properties:
            if _prop(endpoint, "groupStartId") not in ("0-0", "$"):
                invalid("groupStartId", "Creation position must be 0-0 or $")
            if _prop(endpoint, "createConsumerGroup") is not True:
                invalid("groupStartId", "Requires explicit consumer group creation")
        for key in ("topic", "createTopic", "partitions", "replicationFactor"):
            if key in endpoint.properties:
                invalid(key, "Kafka field does not apply to RedisStreams", UNKNOWN_FIELD)

    def validate_rabbitmq_endpoint(self, endpoint: Endpoint, path: str) -> None:
        fields = {"queueName", "exchangeName", "routingKey", "queueType", "exchangeType", "createQueue", "createExchange", "createBinding", "consumerCredits", "publisherMaxInFlight"}
        def invalid(key: str, message: str, code: str = RANGE) -> None:
            self.add(code, "schema", message, path + "." + key, "endpoint", endpoint.name)
        if endpoint.connector.type != "RabbitMQ":
            if endpoint.connector.type in {"RedisStreams", "Pulsar"}:
                fields -= {"publisherMaxInFlight"}
            for key in fields.intersection(endpoint.properties):
                invalid(key, "Field requires RabbitMQ", UNKNOWN_FIELD)
            return
        for key in ("queueName", "exchangeName", "routingKey"):
            if key in endpoint.properties:
                value = _prop(endpoint, key)
                if not isinstance(value, str) or (key != "routingKey" and not value) or any(unicodedata.category(c) == "Cc" for c in value):
                    invalid(key, "Invalid entity name or routing key")
        for key in ("createQueue", "createExchange", "createBinding"):
            if key in endpoint.properties and type(_prop(endpoint, key)) is not bool:
                invalid(key, "Creation flags must be boolean; omitted means false")
        for key in ("consumerCredits", "publisherMaxInFlight"):
            if key in endpoint.properties and (type(_prop(endpoint, key)) is not int or not 1 <= _prop(endpoint, key) <= 4096):
                invalid(key, "Native admission limit must be an integer between 1 and 4096")
        for key, allowed in (("queueType", {"quorum", "classic"}), ("exchangeType", {"direct", "topic", "fanout"})):
            if key in endpoint.properties and (not isinstance(_prop(endpoint, key), str) or _prop(endpoint, key) not in allowed):
                invalid(key, "Unsupported RabbitMQ resource type")
        if (_prop(endpoint, "createQueue") or "queueType" in endpoint.properties) and not _prop(endpoint, "queueName"):
            invalid("queueName", "Queue settings require queueName", REQUIRED)
        if (_prop(endpoint, "createExchange") or "exchangeType" in endpoint.properties or _prop(endpoint, "routingKey")) and not _prop(endpoint, "exchangeName"):
            invalid("exchangeName", "Exchange settings require exchangeName", REQUIRED)
        if _prop(endpoint, "createBinding") and not (_prop(endpoint, "queueName") and _prop(endpoint, "exchangeName")):
            invalid("createBinding", "Binding requires queueName and exchangeName")
        if "exchangeType" in endpoint.properties and _prop(endpoint, "createExchange") is not True:
            invalid("exchangeType", "Exchange type is a creation setting and requires createExchange")
        for key in ("topic", "consumerGroup", "createTopic", "partitions", "replicationFactor", "httpMethodType", "path", "grpcMethodType", "methodName", "schedule", "taskQueue", "temporalExecutionType"):
            if key in endpoint.properties:
                invalid(key, "Field does not apply to RabbitMQ", UNKNOWN_FIELD)

    def validate_nats_connector(self, connector: Connector, path: str) -> None:
        native_fields = {"servers", "connectTimeoutMs", "operationTimeoutMs", "token", "credentialsFile"}
        if connector.type in {"RabbitMQ", "RedisStreams", "Pulsar"}:
            native_fields -= {"servers", "connectTimeoutMs", "operationTimeoutMs"}
        if connector.type in POSTGRES_TARGETS:
            native_fields -= {"connectTimeoutMs", "operationTimeoutMs"}
        if connector.type == "Pulsar":
            native_fields -= {"token"}
        if connector.type not in {"NATS", "JetStream"}:
            for key in sorted(native_fields.intersection(connector.properties)):
                self.add(UNKNOWN_FIELD, "schema", f"{key} requires NATS or JetStream",
                         path + "." + key, "dataConnector", connector.name)
            return

        def invalid(key: str, message: str, code: str = RANGE) -> None:
            self.add(code, "capability" if code == UNSUPPORTED else "schema", message,
                     path + "." + key, "dataConnector", connector.name)

        servers = _prop(connector, "servers")
        tls_url, plain_url = False, False
        if not isinstance(servers, list) or not servers:
            invalid("servers", "NATS/JetStream requires an explicit nonempty server URL list", REQUIRED)
        else:
            for server in servers:
                try:
                    url = urlsplit(server) if isinstance(server, str) else None
                    valid = (url is not None and url.scheme in {"nats", "tls"}
                             and server.startswith(("nats://", "tls://"))
                             and bool(url.hostname) and url.username is None and url.password is None
                             and not url.path and "?" not in server and "#" not in server
                             and not url.netloc.endswith(":")
                             and not any(c.isspace() or unicodedata.category(c) == "Cc" for c in server))
                    if url is not None:
                        valid = valid and (url.port is None or 1 <= url.port <= 65535)
                except ValueError:
                    valid = False
                if not valid:
                    invalid("servers", "Each server must be a nats:// or tls:// URI without credentials, path, query, fragment, empty port, whitespace or controls; ports must be 1..65535")
                    break
                tls_url = tls_url or url.scheme == "tls"
                plain_url = plain_url or url.scheme == "nats"
        for key in ("connectTimeoutMs", "operationTimeoutMs"):
            if key in connector.properties:
                value = _prop(connector, key)
                if type(value) is not int or not 1 <= value <= 9223372036854:
                    invalid(key, f"{key} must be an integer between 1 and 9223372036854 milliseconds")
        if "tlsEnabled" in connector.properties and type(_prop(connector, "tlsEnabled")) is not bool:
            invalid("tlsEnabled", "tlsEnabled must be a boolean")
        for key in ("username", "password", "token", "credentialsFile", "tlsServerName", "tlsCaFile", "tlsCertFile", "tlsKeyFile"):
            if key in connector.properties:
                value = _prop(connector, key)
                if not isinstance(value, str) or not value.strip():
                    invalid(key, f"{key} must be a nonempty string")
        # Match the existing Kafka contract: topology artifacts cannot hold secrets.
        for key in ("username", "password", "token"):
            if _prop(connector, key):
                invalid(key, f"{key} must be supplied through a runtime override, not topology source", UNSUPPORTED)
        auth_modes = [bool(_prop(connector, "token")), bool(_prop(connector, "credentialsFile")),
                      bool(_prop(connector, "username") or _prop(connector, "password"))]
        if sum(auth_modes) > 1:
            invalid("credentialsFile", "NATS authentication modes are mutually exclusive")
        if bool(_prop(connector, "username")) != bool(_prop(connector, "password")):
            invalid("password", "username and password must be supplied together")
        if bool(_prop(connector, "tlsCertFile")) != bool(_prop(connector, "tlsKeyFile")):
            invalid("tlsKeyFile", "tlsCertFile and tlsKeyFile must be supplied together")
        tls_enabled = _prop(connector, "tlsEnabled") is True
        if tls_url and plain_url and not tls_enabled:
            invalid("servers", "Mixed TLS and plain URLs require tlsEnabled to prevent a downgrade")
        if not tls_enabled and not tls_url and any(
            key in connector.properties for key in ("tlsServerName", "tlsCaFile", "tlsCertFile", "tlsKeyFile")
        ):
            invalid("tlsEnabled", "TLS settings require tlsEnabled or a tls:// server URI")
        for key in ("brokers", "version", "dialTimeout", "securityProtocol", "saslMechanism",
                    "usePartitioner", "async", "address", "host", "port", "namespace", "identity",
                    "apiKey", "workerStopTimeout", "connectionsCount", "useDedicatedListener", "module"):
            if key in connector.properties:
                invalid(key, f"{key} is not a NATS/JetStream connection field", UNKNOWN_FIELD)

    def validate_nats_endpoint(self, endpoint: Endpoint, path: str) -> None:
        kind = endpoint.connector.type
        native_fields = {"subject", "queueGroup", "streamName", "durableName", "createStream", "createConsumer"}
        if kind not in {"NATS", "JetStream"}:
            forbidden = native_fields - ({"createStream"} if kind == "RedisStreams" else set())
        else:
            forbidden = {"topic", "consumerGroup", "createTopic", "partitions", "replicationFactor",
                         "httpMethodType", "path", "grpcMethodType", "methodName", "schedule", "scheduleId",
                         "taskQueue", "temporalExecutionType", "timezone", "overlapPolicy", "missedRunPolicy",
                         "maxConcurrentActivities", "maxConcurrentWorkflowTasks", "workflowExecutionTimeout",
                         "activityStartToCloseTimeout", "activityHeartbeatTimeout", "maximumAttempts"}
            forbidden |= ({"streamName", "durableName", "createStream", "createConsumer"}
                          if kind == "NATS" else {"queueGroup"})
        for key in sorted(forbidden.intersection(endpoint.properties)):
            self.add(UNKNOWN_FIELD, "schema", f"{key} does not apply to {kind} endpoints",
                     path + "." + key, "endpoint", endpoint.name)
        if kind not in {"NATS", "JetStream"}:
            return

        def invalid(key: str, message: str, code: str = RANGE) -> None:
            self.add(code, "schema", message, path + "." + key, "endpoint", endpoint.name)

        for key in ("subject", "streamName") if kind == "JetStream" else ("subject",):
            value = _prop(endpoint, key)
            if not isinstance(value, str) or not value.strip():
                invalid(key, f"{kind} requires {key}", REQUIRED)
        subject = _prop(endpoint, "subject")
        if isinstance(subject, str):
            tokens = subject.split(".")
            if (any(c.isspace() or ord(c) < 32 for c in subject) or any(not token for token in tokens)
                or any(("*" in token and token != "*") or (">" in token and (token != ">" or i != len(tokens)-1))
                       for i, token in enumerate(tokens))):
                invalid("subject", "Subject tokens must be nonempty; wildcards occupy a whole token and > must be last")
        for key in ("streamName", "durableName", "queueGroup"):
            if key in endpoint.properties:
                value = _prop(endpoint, key)
                forbidden_chars = "*>" if key == "queueGroup" else ".*>/\\"
                if (not isinstance(value, str) or not value
                    or any(c.isspace() or ord(c) < 32 or c in forbidden_chars for c in value)):
                    invalid(key, f"{key} must be a nonempty native name without whitespace or wildcards")
        for key in ("createStream", "createConsumer"):
            if key in endpoint.properties and type(_prop(endpoint, key)) is not bool:
                invalid(key, f"{key} must be a boolean; omitted means false")

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
            try:
                normalize_connector_implementations(connector.properties.get("implementations"))
            except ValueError as error:
                self.add(RANGE, "schema", str(error), path + ".implementations", "dataConnector", connector.name)
            for field_name in sorted(REMOVED_CONNECTOR_FIELDS.intersection(connector.properties)):
                self.add(UNKNOWN_FIELD, "schema", "Removed connector field; use implementations or the template pack default",
                         path + "." + field_name, "dataConnector", connector.name)
            if "cppBoostImplementation" in connector.properties:
                self.add(UNSUPPORTED, "capability", CPP_BOOST_RETIREMENT,
                         path + ".cppBoostImplementation", "dataConnector", connector.name)
            self.enum(
                connector.type,
                CONNECTOR_TYPES,
                path + ".type",
                "dataConnector",
                connector.name,
                "type",
                True,
            )
            for field, message in validate_query_connector(connector):
                self.add(RANGE, "schema", message, path + "." + field, "dataConnector", connector.name)
            self.validate_nats_connector(connector, path)
            self.validate_rabbitmq_connector(connector, path)
            self.validate_redis_connector(connector, path)
            validate_pulsar_connector(connector, lambda key, msg: self.add(RANGE, "schema", msg, path + "." + key, "dataConnector", connector.name))
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
                self.validate_nats_endpoint(endpoint, ep_path)
                self.validate_rabbitmq_endpoint(endpoint, ep_path)
                self.validate_redis_endpoint(endpoint, ep_path)
                validate_pulsar_endpoint(endpoint, None, lambda key, msg: self.add(RANGE, "schema", msg, ep_path + "." + key, "endpoint", endpoint.name))
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
        interval = re.fullmatch(r"@every ([1-9][0-9]{0,7})ms", schedule)
        if not temporal and interval is not None:
            valid = 10 <= int(interval.group(1)) <= 86_400_000
        if schedule.strip() and not valid:
            self.add(
                RANGE,
                "schema",
                f"scheduled endpoint {endpoint.name!r} requires a portable five-field cron expression"
                + ("" if temporal else " or @every <10..86400000>ms"),
                path + ".schedule",
                "endpoint",
                endpoint.name,
                contract="portable-five-field" if temporal else "portable-local-schedule",
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
        for stream in self.streams.values():
            for field, message in validate_query_bindings(stream):
                self.add(RANGE, "schema", message, self.stream_path(stream) + "." + field,
                         "stream", stream.name)
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
            if stream.type not in {"Input", "SubStream", "Merge"} and stream.source is None:
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
            if stream.type in {"Sink", "Query"} and stream.endpoint is None:
                self.add(
                    REQUIRED,
                    "schema",
                    f"{stream.type} stream {stream.name!r} requires endpoint",
                    path + ".endpoint",
                    "stream",
                    stream.name,
                    field="endpoint",
                )
            if stream.endpoint is not None and stream.type not in {"Input", "Sink", "Query"}:
                self.add(
                    RANGE,
                    "schema",
                    f"stream {stream.name!r} cannot use an endpoint",
                    path + ".endpoint",
                    "stream",
                    stream.name,
                    transformationType=stream.type,
                )
            if stream.type == "Error" and (
                stream.function is not None or _prop(stream, "functionName")
            ):
                self.add(
                    RANGE,
                    "schema",
                    f"Error stream {stream.name!r} is a passive error output and cannot "
                    "execute a function; move the conversion into a following Map stream",
                    path + ".functionName",
                    "stream",
                    stream.name,
                    transformationType=stream.type,
                    field="functionName",
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

    def validate_substreams(self) -> None:
        for entry in self.streams.values():
            if entry.type != "SubStream":
                continue
            path = self.stream_path(entry)
            if entry.service.programming_language not in {"GoLang", "Python", "TypeScript", "Rust", "CppCoro", "CppUserver"}:
                self.add(
                    UNSUPPORTED, "capability",
                    "SubStream requires a supported service language",
                    path + ".type", "stream", entry.name,
                    programmingLanguage=entry.service.programming_language,
                )
            if entry.endpoint is not None:
                self.add(
                    RANGE, "schema", "SubStream does not use a transport endpoint",
                    path + ".endpoint", "stream", entry.name,
                )
            if entry.sources:
                self.add(
                    CARDINALITY, "semantic",
                    "SubStream accepts one result source; combine multiple result producers explicitly",
                    path + ".sources", "stream", entry.name,
                    maximum=0, actual=len(entry.sources),
                )
            if entry.function is not None or _prop(entry, "functionName"):
                self.add(
                    RANGE, "schema",
                    "SubStream is a callable graph entry, not an input business function",
                    path + ".functionName", "stream", entry.name,
                )
            if len(self.normal_consumers[entry.key]) != 1:
                self.add(
                    CARDINALITY, "semantic",
                    f"SubStream {entry.name!r} requires one body consumer; use Split for branching",
                    path, "stream", entry.name, minimum=1, maximum=1,
                    actual=len(self.normal_consumers[entry.key]),
                )
            result = entry.source
            if result is None:
                self.add(
                    MISSING_SOURCE, "semantic",
                    f"SubStream {entry.name!r} requires a result source",
                    path + ".source", "stream", entry.name,
                )
                continue
            if self.streams.get(result.key) is not result:
                self.add(
                    UNKNOWN_REFERENCE, "semantic",
                    "SubStream result source is not part of this project",
                    path + ".source", "stream", entry.name,
                    reference=result.key,
                )
                continue
            if result.service is not entry.service:
                self.add(
                    TYPE_MISMATCH, "semantic",
                    "SubStream result source must belong to its service",
                    path + ".source", "stream", entry.name,
                )
                continue

            # The return edge terminates the invocation rather than re-entering
            # the body. Follow error branches too: recovery can produce results.
            reachable: set[str] = set()
            pending = list(self.normal_consumers[entry.key])
            while pending:
                stream = pending.pop()
                if stream is entry or stream.key in reachable:
                    continue
                reachable.add(stream.key)
                if stream.service is not entry.service or stream.type == "SubStream":
                    self.add(
                        TYPE_MISMATCH, "semantic",
                        "SubStream body must stay in its service and return to its own entry",
                        self.stream_path(stream), "stream", stream.name,
                        substream=entry.key,
                    )
                    continue
                # An Input's incoming source is a result binding, not an
                # execution entry. Do not follow its outgoing request body.
                if stream.type == "Input":
                    reachable.remove(stream.key)
                    continue
                pending.extend(self.normal_consumers[stream.key])
                pending.extend(self.error_consumers[stream.key])
            if result is entry or result.key not in reachable:
                self.add(
                    TYPE_MISMATCH, "semantic",
                    "SubStream result source must be reachable from its body",
                    path + ".source", "stream", entry.name,
                    source=result.key,
                )

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
        checked_http_modules: set[str] = set()
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
                if connector.key not in checked_http_modules:
                    checked_http_modules.add(connector.key)
                    self.required(
                        _prop(connector, "module"),
                        connector_path + ".module",
                        "dataConnector",
                        connector.name,
                        "module",
                    )
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
            elif connector.type == "Pulsar":
                for user in users:
                    validate_pulsar_endpoint(endpoint, user.type == "Input", lambda key, msg: self.add(RANGE, "semantic", msg, path + "." + key, "endpoint", endpoint.name))
            elif connector.type == "RedisStreams":
                if any(user.service.programming_language == "TypeScript" for user in users):
                    for key in ("connectTimeoutMs", "operationTimeoutMs", "redisDatabase"):
                        value = _prop(connector, key)
                        if type(value) is int and value > 2147483647:
                            self.add(UNSUPPORTED, "capability", "Value exceeds TypeScript runtime limit 2147483647", connector_path + "." + key, "dataConnector", connector.name)
                source = any(user.type == "Input" for user in users)
                sink = any(user.type == "Sink" for user in users)
                if source:
                    self.required(_prop(endpoint, "consumerGroup"), path + ".consumerGroup", "endpoint", endpoint.name, "consumerGroup")
                source_fields = {"consumerGroup", "consumerName", "createConsumerGroup", "groupStartId", "readCount", "readBlockMs", "claimIdleMs", "claimIntervalMs"}
                forbidden = (source_fields if sink else set()) | ({"createStream", "publisherMaxInFlight"} if source else set())
                for key in sorted(forbidden.intersection(endpoint.properties)):
                    self.add(RANGE, "semantic", "Redis setting applies to the opposite endpoint direction", path + "." + key, "endpoint", endpoint.name)
            elif connector.type == "RabbitMQ":
                if any(user.service.programming_language == "TypeScript" for user in users):
                    self.validate_rabbitmq_typescript(endpoint, path, connector_path)
                source = any(user.type == "Input" for user in users)
                sink = any(user.type == "Sink" for user in users)
                if source and not _prop(endpoint, "queueName"):
                    self.required(None, path + ".queueName", "endpoint", endpoint.name, "queueName")
                if sink and not (_prop(endpoint, "queueName") or _prop(endpoint, "exchangeName")):
                    self.required(None, path + ".queueName", "endpoint", endpoint.name, "queueName or exchangeName")
                for field_name, forbidden in (("consumerCredits", sink), ("publisherMaxInFlight", source)):
                    if forbidden and field_name in endpoint.properties:
                        self.add(RANGE, "semantic", "Native admission setting applies to the opposite endpoint direction", path + "." + field_name, "endpoint", endpoint.name)
            elif connector.type in {"NATS", "JetStream"}:
                source = any(user.type == "Input" for user in users)
                sink = any(user.type == "Sink" for user in users)
                if source and connector.type == "JetStream":
                    self.required(_prop(endpoint, "durableName"), path + ".durableName",
                                  "endpoint", endpoint.name, "durableName")
                if sink:
                    for field_name in ("queueGroup", "durableName", "createConsumer"):
                        if field_name in endpoint.properties:
                            self.add(RANGE, "semantic", f"{field_name} is source-only",
                                     path + "." + field_name, "endpoint", endpoint.name)
                    subject = _prop(endpoint, "subject")
                    if isinstance(subject, str) and any(char in subject for char in "*>"):
                        self.add(RANGE, "semantic", "Sink requires a concrete publish subject",
                                 path + ".subject", "endpoint", endpoint.name)
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
            if not stream.endpoint or stream.type not in {"Input", "Sink", "Query"}:
                continue
            key = (stream.service.key, stream.endpoint.key, stream.type)
            if stream.type == "Input" and key in seen:
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
            if stream.type == "Input":
                seen[key] = stream
            (inputs if stream.type == "Input" else sinks)[stream.endpoint.key].append(
                stream
            )
        # Shared outbound API declarations do not join caller execution graphs.
        # Check caller contracts even if no remote Input is modeled locally.
        for endpoint_sinks in sinks.values():
            request_type: tuple[bool, str, str] | None = None
            response_type: tuple[bool, str, str] | None = None
            for sink in endpoint_sinks:
                request = self.output_wire_type(sink.source)
                response = self.output_wire_type(sink)
                for direction, expected, actual in (
                    ("request", request_type, request),
                    ("response", response_type, response),
                ):
                    if expected is not None and actual is not None and expected != actual:
                        self.add(
                            TYPE_MISMATCH,
                            "semantic",
                            f"shared endpoint {direction} types differ for {sink.type} {sink.name!r}",
                            self.stream_path(sink) + ".endpoint",
                            "stream",
                            sink.name,
                            direction=direction,
                            expected=expected,
                            actual=actual,
                        )
                if request_type is None and request is not None:
                    request_type = request
                if response_type is None and response is not None:
                    response_type = response
        for endpoint_key, endpoint_inputs in inputs.items():
            for input_stream in endpoint_inputs:
                endpoint = input_stream.endpoint
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
            properties = endpoint.function.to_properties()
            return (
                endpoint.function_name,
                _text(properties.get("functionPackage")),
                bool(properties.get("publicFunction")),
                _text(properties.get("functionModule")),
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

    def function_error_contract(self, stream: Stream) -> str:
        """Return the generated error type, including the implicit native error."""
        if stream.type not in ERROR_OUTPUT_TYPES:
            return "none"
        consumers = self.error_consumers.get(stream.key, [])
        if not consumers:
            return "error"
        wire = self.output_wire_type(consumers[0])
        if wire is None:
            return "unknown"
        definition = self.project.types.get(wire[2])
        if definition is not None and definition.type == "error" and not definition.properties.get("useAlias"):
            return "error"
        return repr(wire)

    def validate_functions(self) -> None:
        from .endpoint_function_validation import validate_endpoint_function_ownership

        validate_endpoint_function_ownership(self)
        generated: dict[tuple[str, str], tuple[str, str]] = {}
        signatures: dict[tuple[str, str, str], tuple[str, str]] = {}
        for stream in self.streams.values():
            # Error is a passive result stream, not a generated business function.
            if stream.type == "Error":
                continue
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
            signature += "@operator=" + stream.type + "@error=" + self.function_error_contract(stream)
            # Input and Sink endpoint handlers are different generated functions.
            role_scope = scope + ":" + stream.type if stream.endpoint else scope
            declaration = (role_scope, package, name)
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
            if source_stream.type not in {"Input", "SubStream", "CycleLink"}:
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
