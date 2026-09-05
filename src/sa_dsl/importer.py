from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .model import (
    ActivityTimeouts,
    ActivityWorker,
    Appearance,
    CallSemantics,
    CppBoost,
    CppUserver,
    CronSchedule,
    DataConnectorImplementation,
    DataType,
    Environment,
    GrpcMethodType,
    GrpcServer,
    Golang,
    HTTPMethodType,
    HttpServer,
    JoinStorageType,
    JoinType,
    KafkaSaslMechanism,
    KafkaCluster,
    KafkaSecurity,
    KafkaSecurityProtocol,
    KubernetesWorkloadType,
    Kubernetes,
    LogLevel,
    LocalType,
    Observability,
    Python,
    ProcessPattern,
    ProgrammingLanguage,
    ScheduleMissedRunPolicy,
    ScheduleOverlapPolicy,
    Rust,
    RetryPolicy,
    ServiceModule,
    TypeScript,
    TemporalSchedule,
    TypeDefinitionFormat,
    WorkflowTimeouts,
    WorkflowWorker,
)


@dataclass(frozen=True, slots=True)
class _Code:
    text: str


_ENUM_FIELDS = {
    "programmingLanguage": ProgrammingLanguage,
    "environment": Environment,
    "logLevel": LogLevel,
    "kubernetesWorkloadType": KubernetesWorkloadType,
    "defaultCallSemantics": CallSemantics,
    "callSemantics": CallSemantics,
    "implementation": DataConnectorImplementation,
    "goImplementation": DataConnectorImplementation,
    "cppUserverImplementation": DataConnectorImplementation,
    "cppBoostImplementation": DataConnectorImplementation,
    "pythonImplementation": DataConnectorImplementation,
    "rustImplementation": DataConnectorImplementation,
    "typeScriptImplementation": DataConnectorImplementation,
    "httpMethodType": HTTPMethodType,
    "grpcMethodType": GrpcMethodType,
    "securityProtocol": KafkaSecurityProtocol,
    "saslMechanism": KafkaSaslMechanism,
    "overlapPolicy": ScheduleOverlapPolicy,
    "missedRunPolicy": ScheduleMissedRunPolicy,
    "joinType": JoinType,
    "joinStorage": JoinStorageType,
    "pattern": ProcessPattern,
    "definitionFormat": TypeDefinitionFormat,
}

_STREAM_METHODS = {
    "Input": "input",
    "Map": "map",
    "Filter": "filter",
    "Join": "join",
    "MultiJoin": "multi_join",
    "Process": "process",
    "Delay": "delay",
    "FlatMap": "flat_map",
    "FlatMapIterable": "flat_map_iterable",
    "KeyBy": "key_by",
    "Merge": "merge",
    "Split": "split",
    "Case": "case",
    "Sink": "sink",
    "CycleLink": "cycle_link",
    "Error": "error",
    "When": "when",
}

_TYPE_METHODS = {value.value: f"{value.name.lower()}_type" for value in DataType}
_TYPE_METHODS.update(
    {
        DataType.BOOLEAN.value: "boolean_type",
        DataType.UNICODE_CHAR.value: "unicode_char_type",
        DataType.UNICODE_STRING.value: "unicode_string_type",
    }
)


def _snake(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()
    if not value:
        value = "value"
    if value[0].isdigit() or keyword.iskeyword(value):
        value = f"value_{value}"
    return value


def _literal(value: Any) -> str:
    if isinstance(value, _Code):
        return value.text
    return repr(value)


def _enum(field: str, value: Any) -> Any:
    enum_type = _ENUM_FIELDS.get(field)
    if enum_type is None or value is None:
        return value
    try:
        member = enum_type(value)
    except ValueError as error:
        raise ValueError(f"Unsupported {field} value {value!r}") from error
    return _Code(f"{enum_type.__name__}.{member.name}")


def _kw_name(name: str) -> str:
    result = _snake(name)
    return f"{result}_" if keyword.iskeyword(result) else result


def _call(
    target: str, receiver: str, method: str, name: str, values: Mapping[str, Any]
) -> str:
    lines = [f"{target} = {receiver}.{method}(", f"    {name!r},"]
    for field, value in values.items():
        if value is None:
            continue
        rendered = _literal(value)
        if "\n" in rendered:
            rendered = rendered.replace("\n", "\n    ")
        lines.append(f"    {_kw_name(field)}={rendered},")
    lines.append(")")
    return "\n".join(lines)


def _link_call(
    source: str,
    destination: str,
    method: str,
    values: Mapping[str, Any],
) -> str:
    lines = [
        f"{source}.{method}(",
        f"    {destination},",
    ]
    for field, value in values.items():
        lines.append(f"    {_kw_name(field)}={_literal(value)},")
    lines.append(")")
    return "\n".join(lines)


def _object_code(values: dict[str, Any], class_name: str, fields: tuple[tuple[str, str], ...]) -> _Code:
    arguments = [
        f"{argument}={_literal(values.pop(field))}"
        for argument, field in fields
        if field in values
    ]
    return _Code(f"{class_name}({', '.join(arguments)})")


def _dsl_imports(body: str) -> str:
    names = [
        "ActivityTimeouts",
        "ActivityWorker",
        "Appearance",
        "CallSemantics",
        "CppBoost",
        "CppUserver",
        "CronSchedule",
        "DataConnectorImplementation",
        "DataType",
        "Environment",
        "Function",
        "GrpcMethodType",
        "GrpcServer",
        "Golang",
        "HTTPMethodType",
        "HttpServer",
        "JoinStorageType",
        "JoinType",
        "KafkaSaslMechanism",
        "KafkaCluster",
        "KafkaSecurity",
        "KafkaSecurityProtocol",
        "KubernetesWorkloadType",
        "Kubernetes",
        "LOCAL_MODULE",
        "LogLevel",
        "LocalType",
        "NULL",
        "Observability",
        "Python",
        "Package",
        "ProcessPattern",
        "ProgrammingLanguage",
        "Project",
        "ROOT_PACKAGE",
        "ScheduleMissedRunPolicy",
        "ScheduleOverlapPolicy",
        "Rust",
        "RetryPolicy",
        "ServiceModule",
        "TypeScript",
        "TemporalSchedule",
        "TypeDefinitionFormat",
        "WorkflowTimeouts",
        "WorkflowWorker",
    ]
    used = [name for name in names if re.search(rf"\b{re.escape(name)}\b", body)]
    if not used:
        return ""
    if len(used) == 1:
        return f"from sa_dsl import {used[0]}\n\n"
    return (
        "from sa_dsl import (\n" + "".join(f"    {name},\n" for name in used) + ")\n\n"
    )


class _Writer:
    def __init__(self, root: Path | None, package: str):
        self.root = root
        self.package = package
        self.files: dict[str, str] = {}
        self.modules: dict[str, tuple[str, str]] = {}
        self.pools: dict[str, tuple[str, str]] = {}
        self.types: dict[str, tuple[str, str]] = {}
        self.connectors: dict[str, tuple[str, str]] = {}
        self.endpoints: dict[str, tuple[str, str]] = {}
        self.packages: dict[str, tuple[str, str]] = {}
        self.registration_modules: list[str] = []

    def write(self, relative: str, body: str, imports: list[str] | None = None) -> None:
        sections = []
        dsl = _dsl_imports(body)
        if dsl:
            sections.append(dsl.rstrip())
        if imports:
            sections.append("\n".join(sorted(set(imports))))
        sections.append(body.rstrip())
        self.write_raw(
            relative,
            "\n\n".join(section for section in sections if section) + "\n",
        )

    def write_raw(self, relative: str, content: str) -> None:
        normalized = relative.replace("\\", "/").lstrip("/")
        self.files[f"{self.package}/{normalized}"] = content
        if self.root is not None:
            path = self.root / normalized
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def ref_import(
        self, table: Mapping[str, tuple[str, str]], key: str
    ) -> tuple[_Code, str]:
        try:
            module, variable = table[key]
        except KeyError as error:
            raise ValueError(f"Unknown reference {key!r}") from error
        return _Code(variable), f"from {self.package}.{module} import {variable}"


def _function(
    values: dict[str, Any], writer: _Writer, imports: list[str]
) -> _Code | None:
    name = values.pop("functionName", None)
    fields = {
        "name": name,
        "package": values.pop("functionPackage", None),
        "public": values.pop("publicFunction", None),
        "description": values.pop("functionDescription", None),
        "initializer_group": values.pop("functionInitializerGroup", None),
        "module": values.pop("functionModule", None),
    }
    if name is None:
        return None
    package = fields["package"]
    if package == "":
        fields["package"] = _Code("ROOT_PACKAGE")
    elif package is not None:
        reference, imported = writer.ref_import(writer.packages, package)
        fields["package"] = reference
        imports.append(imported)
    module = fields["module"]
    if module == "":
        fields["module"] = _Code("LOCAL_MODULE")
    elif module is not None:
        reference, imported = writer.ref_import(writer.modules, module)
        fields["module"] = reference
        imports.append(imported)
    group = fields.pop("initializer_group")
    if group not in (None, ""):
        fields["initializer_group"] = _Code(f"InitializerGroup({group!r})")
    rendered = ["Function("]
    for field, value in fields.items():
        if value is not None:
            rendered.append(f"    {field}={_literal(value)},")
    rendered.append(")")
    return _Code("\n".join(rendered))


def _property_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {field: _enum(field, value) for field, value in values.items()}


@dataclass(frozen=True)
class PythonProjectFiles:
    """A browser-friendly generated Python workspace with no filesystem dependency."""

    package_name: str
    entrypoint: str
    files: Mapping[str, str]


def yaml_to_python_files(
    source: str | Path | Mapping[str, Any], package_name: str
) -> PythonProjectFiles:
    """Convert Service Architect YAML into an in-memory typed Python project."""
    if isinstance(source, Mapping):
        document = dict(source)
    elif isinstance(source, Path):
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    else:
        candidate = Path(source)
        if "\n" not in source and len(source) < 4096 and candidate.is_file():
            document = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        else:
            document = yaml.safe_load(source)
    if not isinstance(document, dict):
        raise ValueError("Service Architect YAML root must be a mapping")

    package = package_name
    if not package.isidentifier() or keyword.iskeyword(package):
        raise ValueError(
            f"Package name {package!r} must be a Python identifier"
        )
    writer = _Writer(None, package)

    for category in (
        "project",
        "packages",
        "modules",
        "pools",
        "types",
        "connectors",
        "endpoints",
        "services",
    ):
        writer.write_raw(
            f"{category}/__init__.py", f'"""Generated {category}."""\n'
        )

    settings = dict(document.get("settings") or {})
    project_name = settings.pop("name", package)
    project_file = _snake(package)
    project_body = _call(
        "project",
        "",
        "Project".lstrip("."),
        project_name,
        {
            "module_version": settings.pop("moduleVersion", None),
            "repo_path": settings.pop("repoPath", None),
            "properties": settings,
        },
    ).replace(" = .Project(", " = Project(")
    writer.write(f"project/{project_file}.py", project_body)
    project_import = f"from {package}.project.{project_file} import project"

    package_paths: set[str] = set()
    for item in (document.get("types") or {}).values():
        if isinstance(item, dict) and item.get("package"):
            package_paths.add(item["package"])
    for connector in (document.get("dataConnectors") or {}).values():
        for endpoint in (connector.get("endpoints") or {}).values():
            if endpoint.get("functionPackage"):
                package_paths.add(endpoint["functionPackage"])
    for service in (document.get("services") or {}).values():
        for pipeline in (service.get("pipelines") or {}).values():
            for stream in pipeline.values():
                if stream.get("functionPackage"):
                    package_paths.add(stream["functionPackage"])
    for path_value in sorted(package_paths):
        variable = f"{_snake(path_value)}_package"
        module = f"packages.{_snake(path_value)}"
        writer.packages[path_value] = (module, variable)
        writer.write(
            f"{module.replace('.', '/')}.py", f"{variable} = Package({path_value!r})"
        )

    for key, item in (document.get("modules") or {}).items():
        variable = _snake(key)
        module = f"modules.{variable}"
        writer.modules[key] = (module, variable)
        values = dict(item)
        name = values.pop("name", key)
        body = _call(
            variable,
            "project",
            "module",
            name,
            {
                "module_path": values.pop("modulePath", ""),
                "golang_version": values.pop("golangVersion", ""),
            },
        )
        if values:
            raise ValueError(f"Unsupported module fields for {key}: {sorted(values)}")
        writer.write(f"{module.replace('.', '/')}.py", body, [project_import])
        writer.registration_modules.append(module)

    for key, item in (document.get("pools") or {}).items():
        variable = _snake(key)
        module = f"pools.{variable}"
        writer.pools[key] = (module, variable)
        values = dict(item)
        name = values.pop("name", key)
        writer.pools[name] = (module, variable)
        body = _call(
            variable,
            "project",
            "pool",
            name,
            {
                "executors_count": values.pop("executorsCount", None),
                "queue_capacity": values.pop("queueCapacity", None),
            },
        )
        if values:
            raise ValueError(f"Unsupported pool fields for {key}: {sorted(values)}")
        writer.write(f"{module.replace('.', '/')}.py", body, [project_import])
        writer.registration_modules.append(module)

    type_documents = document.get("types") or {}
    for key in type_documents:
        variable = _snake(key)
        writer.types[key] = (f"types.{variable}", variable)
    for key, item in type_documents.items():
        variable = writer.types[key][1]
        module = writer.types[key][0]
        values = dict(item)
        name = values.pop("name", key)
        data_type = values.pop("type")
        try:
            method = _TYPE_METHODS[data_type]
        except KeyError as error:
            raise ValueError(f"Unsupported data type {data_type!r}") from error
        imports = [project_import]
        module_value = values.pop("module", None)
        if module_value is None and "module" in item:
            values["module"] = _Code("LocalType()")
        elif module_value is not None:
            values["module"], imported = writer.ref_import(writer.modules, module_value)
            imports.append(imported)
        package_value = values.pop("package", None)
        if package_value == "":
            values["package"] = _Code("ROOT_PACKAGE")
        elif package_value is not None:
            values["package"], imported = writer.ref_import(
                writer.packages, package_value
            )
            imports.append(imported)
        for field in ("valueType", "keyType"):
            if field not in values:
                continue
            reference = values.pop(field)
            if reference in writer.types:
                values[field], imported = writer.ref_import(writer.types, reference)
                imports.append(imported)
            else:
                try:
                    builtin = DataType(reference)
                except ValueError as error:
                    raise ValueError(f"Unknown type reference {reference!r}") from error
                values[field] = _Code(f"DataType.{builtin.name}")
        values = _property_values(values)
        body = _call(variable, "project", method, name, values)
        writer.write(f"{module.replace('.', '/')}.py", body, imports)
        writer.registration_modules.append(module)

    connector_documents = document.get("dataConnectors") or {}
    for key in connector_documents:
        variable = f"connector_{_snake(key)}"
        writer.connectors[key] = (f"connectors.{_snake(key)}", variable)
    connector_methods = {
        "HTTP": "http_connector",
        "gRPC": "grpc_connector",
        "Kafka": "kafka_connector",
        "Cron": "cron_connector",
        "Temporal": "temporal_connector",
        "Custom": "custom_connector",
    }
    for key, item in connector_documents.items():
        values = dict(item)
        endpoints = values.pop("endpoints", {}) or {}
        name = values.pop("name", key)
        connector_type = values.pop("type")
        imports = [project_import]
        module_value = values.pop("module", None)
        if module_value is not None:
            values["module"], imported = writer.ref_import(writer.modules, module_value)
            imports.append(imported)
        values = _property_values(values)
        if connector_type == "Kafka":
            values["cluster"] = _object_code(
                values,
                "KafkaCluster",
                (("brokers", "brokers"), ("version", "version"), ("dial_timeout", "dialTimeout")),
            )
            security_fields = ("securityProtocol", "saslMechanism", "username", "password")
            if any(field in values for field in security_fields):
                values["security"] = _object_code(
                    values,
                    "KafkaSecurity",
                    (("protocol", "securityProtocol"), ("mechanism", "saslMechanism"), ("username", "username"), ("password", "password")),
                )
        module, variable = writer.connectors[key]
        body = _call(
            variable, "project", connector_methods[connector_type], name, values
        )
        writer.write(f"{module.replace('.', '/')}.py", body, imports)
        writer.registration_modules.append(module)

        endpoint_module = f"endpoints.{_snake(key)}"
        endpoint_blocks = []
        endpoint_imports = [f"from {package}.{module} import {variable}"]
        for endpoint_key, endpoint_item in endpoints.items():
            endpoint_values = dict(endpoint_item)
            endpoint_name = endpoint_values.pop("name", endpoint_key)
            endpoint_variable = f"endpoint_{_snake(endpoint_key)}"
            writer.endpoints[endpoint_key] = (endpoint_module, endpoint_variable)
            function = _function(endpoint_values, writer, endpoint_imports)
            if function is not None:
                endpoint_values["function"] = function
            if connector_type == "HTTP":
                method = {"GET": "get", "POST": "post"}[
                    endpoint_values.pop("httpMethodType")
                ]
            elif connector_type == "gRPC":
                method = {
                    "NoStreaming": "unary_method",
                    "ClientStreaming": "client_streaming_method",
                    "ServerStreaming": "server_streaming_method",
                    "BidirectionalStreaming": "bidirectional_streaming_method",
                }[endpoint_values.pop("grpcMethodType", "NoStreaming")]
            elif connector_type == "Kafka":
                method = "topic"
            elif connector_type == "Cron":
                method = "schedule"
            elif connector_type == "Temporal":
                execution = endpoint_values.pop("temporalExecutionType", None)
                method = "activity" if execution == "Activity" else "workflow"
            else:
                method = "endpoint"
            endpoint_values = _property_values(endpoint_values)
            if connector_type == "Cron":
                endpoint_values["trigger"] = _object_code(
                    endpoint_values,
                    "CronSchedule",
                    (("expression", "schedule"), ("timezone", "timezone"), ("overlap_policy", "overlapPolicy"), ("missed_run_policy", "missedRunPolicy")),
                )
            elif connector_type == "Temporal":
                if method == "activity":
                    endpoint_values["worker"] = _object_code(
                        endpoint_values,
                        "ActivityWorker",
                        (("task_queue", "taskQueue"), ("max_concurrent", "maxConcurrentActivities")),
                    )
                    endpoint_values["timeouts"] = _object_code(
                        endpoint_values,
                        "ActivityTimeouts",
                        (("start_to_close", "activityStartToCloseTimeout"), ("heartbeat", "activityHeartbeatTimeout"), ("workflow_execution", "workflowExecutionTimeout")),
                    )
                else:
                    endpoint_values["worker"] = _object_code(
                        endpoint_values,
                        "WorkflowWorker",
                        (("task_queue", "taskQueue"), ("max_concurrent", "maxConcurrentWorkflowTasks")),
                    )
                    endpoint_values["timeouts"] = _object_code(
                        endpoint_values,
                        "WorkflowTimeouts",
                        (("execution", "workflowExecutionTimeout"),),
                    )
                maximum_attempts = endpoint_values.pop("maximumAttempts", None)
                if maximum_attempts is not None and maximum_attempts != 1:
                    endpoint_values["retry"] = _Code(
                        f"RetryPolicy(maximum_attempts={_literal(maximum_attempts)})"
                    )
                schedule = endpoint_values.pop("schedule", "")
                schedule_id = endpoint_values.pop("scheduleId", "")
                timezone = endpoint_values.pop("timezone", "UTC")
                overlap = endpoint_values.pop("overlapPolicy", _enum("overlapPolicy", ScheduleOverlapPolicy.SKIP.value))
                missed = endpoint_values.pop("missedRunPolicy", _enum("missedRunPolicy", ScheduleMissedRunPolicy.FIRE_ONCE.value))
                if schedule or schedule_id:
                    endpoint_values["schedule"] = _Code(
                        "TemporalSchedule("
                        f"expression={schedule!r}, id={schedule_id!r}, timezone={timezone!r}, "
                        f"overlap_policy={_literal(overlap)}, missed_run_policy={_literal(missed)})"
                    )
            endpoint_blocks.append(
                _call(
                    endpoint_variable, variable, method, endpoint_name, endpoint_values
                )
            )
        writer.write(
            f"{endpoint_module.replace('.', '/')}.py",
            "\n\n".join(endpoint_blocks),
            endpoint_imports,
        )
        writer.registration_modules.append(endpoint_module)

    service_modules = []
    for service_key, service_item in (document.get("services") or {}).items():
        service_values = dict(service_item)
        pipelines = service_values.pop("pipelines", {}) or {}
        links = service_values.pop("links", {}) or {}
        appearance = service_values.pop("appearance", {}) or {}
        coordinates = appearance.get("pipelines", {}) or {}
        if "color" in appearance:
            service_values["appearance"] = _Code(
                f"Appearance(color={appearance['color']!r})"
            )
        service_name = service_values.pop("name", service_key)
        programming_language = service_values.pop("programmingLanguage")
        module_path = service_values.pop("modulePath")
        golang_version = service_values.pop("golangVersion", None)
        language_classes = {
            ProgrammingLanguage.GO.value: "Golang",
            ProgrammingLanguage.CPP_USERVER.value: "CppUserver",
            ProgrammingLanguage.CPP_BOOST.value: "CppBoost",
            ProgrammingLanguage.PYTHON.value: "Python",
            ProgrammingLanguage.RUST.value: "Rust",
            ProgrammingLanguage.TYPESCRIPT.value: "TypeScript",
        }
        try:
            language_class = language_classes[programming_language]
        except KeyError as error:
            raise ValueError(
                f"Unsupported programmingLanguage value {programming_language!r}"
            ) from error
        language_arguments = (
            f"version={golang_version!r}"
            if language_class == "Golang" and golang_version is not None
            else ""
        )
        service_values["language"] = _Code(f"{language_class}({language_arguments})")
        service_values["module"] = _Code(f"ServiceModule(path={module_path!r})")
        default_call_semantics = service_values.get(
            "defaultCallSemantics", CallSemantics.FUNCTION_CALL.value
        )
        service_defaults = {
            "defaultCallSemantics": CallSemantics.FUNCTION_CALL.value,
            "environment": "",
            "httpHost": "0.0.0.0",
            "grpcHost": "0.0.0.0",
            "shutdownTimeout": 30000,
            "kubernetesWorkloadType": "Deployment",
            "statusHandler": "status",
            "metricsHandler": "metrics",
            "startupHandler": "health/startup",
            "readinessHandler": "health/ready",
            "livenessHandler": "health/live",
        }
        for field, default in service_defaults.items():
            if service_values.get(field) == default:
                service_values.pop(field)
        service_variable = _snake(service_key)
        service_module = f"services.{service_variable}.service"
        service_modules.append(service_module)
        service_values = _property_values(service_values)
        service_groups = (
            (
                "http_server",
                "HttpServer",
                (("host", "httpHost"), ("port", "httpPort")),
            ),
            (
                "grpc_server",
                "GrpcServer",
                (
                    ("host", "grpcHost"),
                    ("port", "grpcPort"),
                    ("default_timeout", "defaultGrpcTimeout"),
                ),
            ),
            (
                "observability",
                "Observability",
                (
                    ("metrics_handler", "metricsHandler"),
                    ("status_handler", "statusHandler"),
                    ("startup_handler", "startupHandler"),
                    ("readiness_handler", "readinessHandler"),
                    ("liveness_handler", "livenessHandler"),
                ),
            ),
            (
                "kubernetes",
                "Kubernetes",
                (("workload_type", "kubernetesWorkloadType"),),
            ),
        )
        for parameter, class_name, fields in service_groups:
            arguments = [
                f"{argument}={_literal(service_values.pop(property_name))}"
                for argument, property_name in fields
                if property_name in service_values
            ]
            if arguments:
                service_values[parameter] = _Code(
                    f"{class_name}({', '.join(arguments)})"
                )
        service_body = [
            _call(service_variable, "project", "service", service_name, service_values)
        ]
        pipeline_variables = {}
        stream_refs: dict[str, tuple[str, str, str]] = {}
        declared_edges: set[tuple[str, str]] = set()
        for pipeline_key, stream_items in pipelines.items():
            pipeline_variable = f"{_snake(pipeline_key)}_pipeline"
            pipeline_variables[pipeline_key] = pipeline_variable
            service_body.append(
                f"{pipeline_variable} = {service_variable}.pipeline({pipeline_key!r})"
            )
            for stream_key in stream_items:
                stream_refs[stream_key] = (
                    pipeline_key,
                    f"services.{service_variable}.pipelines.{_snake(pipeline_key)}",
                    _snake(stream_key),
                )

        for stream_key, stream_item in (
            (stream_key, stream_item)
            for stream_items in pipelines.values()
            for stream_key, stream_item in stream_items.items()
        ):
            source_key = stream_item.get("source")
            if source_key:
                declared_edges.add((source_key, stream_key))
            for source_key in stream_item.get("sources") or []:
                declared_edges.add((source_key, stream_key))

        non_default_links: dict[tuple[str, str], dict[str, Any]] = {}
        for link in links.values():
            link_values = dict(link)
            edge = (link_values.pop("from"), link_values.pop("to"))
            if edge not in declared_edges:
                raise ValueError(
                    f"Persisted link {edge[0]!r} -> {edge[1]!r} has no graph connection"
                )
            semantics = link_values.get("callSemantics", CallSemantics.INHERITED.value)
            if semantics in (CallSemantics.INHERITED.value, default_call_semantics):
                continue
            non_default_links[edge] = link_values

        def render_link(
            edge: tuple[str, str],
            imports: list[str],
            *,
            import_service: bool = True,
        ) -> str | None:
            raw_values = non_default_links.pop(edge, None)
            if raw_values is None:
                return None
            link_values = dict(raw_values)
            source_variable = stream_refs[edge[0]][2]
            target_variable = stream_refs[edge[1]][2]
            pool_name = link_values.pop("poolName", None)
            if pool_name is not None:
                link_values["pool"], imported = writer.ref_import(
                    writer.pools, pool_name
                )
                imports.append(imported)
            if import_service:
                imports.append(
                    f"from {package}.{service_module} import {service_variable}"
                )
            semantics = link_values.pop("callSemantics")
            if (
                semantics == CallSemantics.TASK_POOL.value
                and "priority" in link_values
            ):
                semantics = CallSemantics.PRIORITY_TASK_POOL.value
            methods = {
                CallSemantics.FUNCTION_CALL.value: "function_call",
                CallSemantics.TASK_POOL.value: "task_pool_call",
                CallSemantics.PRIORITY_TASK_POOL.value: "priority_task_pool_call",
                CallSemantics.PARALLEL_CALL.value: "parallel_call",
            }
            return _link_call(
                source_variable,
                target_variable,
                methods[semantics],
                _property_values(link_values),
            )

        cross_connections = []
        error_connections = []
        pipeline_files = []
        service_imports = [project_import]
        for pipeline_key, stream_items in pipelines.items():
            pipeline_variable = pipeline_variables[pipeline_key]
            pipeline_module = (
                f"services.{service_variable}.pipelines.{_snake(pipeline_key)}"
            )
            pipeline_imports = [
                f"from {package}.{service_module} import {pipeline_variable}"
            ]
            blocks = []
            connections = []
            for stream_key, stream_item in stream_items.items():
                values = dict(stream_item)
                name = values.pop("name", stream_key)
                stream_type = values.pop("type")
                source = values.pop("source", None)
                sources = values.pop("sources", None) or []
                endpoint = values.pop("endpoint", None)
                error_stream = values.pop("errorStream", None)
                function = _function(values, writer, pipeline_imports)
                if function is not None:
                    values["function"] = function
                if endpoint is not None:
                    values["endpoint"], imported = writer.ref_import(
                        writer.endpoints, endpoint
                    )
                    pipeline_imports.append(imported)
                for field in ("valueType", "keyType"):
                    if field in values:
                        reference = values.pop(field)
                        if reference in writer.types:
                            values[field], imported = writer.ref_import(
                                writer.types, reference
                            )
                            pipeline_imports.append(imported)
                        else:
                            builtin = DataType(reference)
                            values[field] = _Code(f"DataType.{builtin.name}")
                point = (coordinates.get(pipeline_key, {}) or {}).get(
                    stream_key, {}
                ) or {}
                appearance_fields = [
                    f"{field}={point[field]!r}" for field in ("x", "y") if field in point
                ]
                if appearance_fields:
                    values["appearance"] = _Code(
                        f"Appearance({', '.join(appearance_fields)})"
                    )
                values = _property_values(values)
                variable = stream_refs[stream_key][2]
                blocks.append(
                    _call(
                        variable,
                        pipeline_variable,
                        _STREAM_METHODS[stream_type],
                        name,
                        values,
                    )
                )
                if error_stream is not None:
                    if error_stream not in stream_refs:
                        raise ValueError(f"Unknown error stream {error_stream!r}")
                    error_connections.append(
                        (
                            pipeline_module,
                            variable,
                            stream_refs[error_stream][1],
                            stream_refs[error_stream][2],
                        )
                    )
                references = ([source] if source else []) + list(sources)
                for reference in references:
                    if reference not in stream_refs:
                        raise ValueError(f"Unknown stream source {reference!r}")
                    source_pipeline, source_module, source_variable = stream_refs[
                        reference
                    ]
                    expression = (
                        f"{source_variable} >> {variable}"
                        if source
                        else f"{variable} << {source_variable}"
                    )
                    edge = (reference, stream_key)
                    if source_pipeline == pipeline_key:
                        connections.append(expression)
                        link_code = render_link(edge, pipeline_imports)
                        if link_code is not None:
                            connections.append(link_code)
                    else:
                        cross_connections.append(
                            (
                                expression,
                                edge,
                                source_module,
                                source_variable,
                                pipeline_module,
                                variable,
                            )
                        )
            body = "\n\n".join(blocks + connections)
            writer.write(
                f"{pipeline_module.replace('.', '/')}.py", body, pipeline_imports
            )
            pipeline_files.append(pipeline_module)

        for pipeline_module in pipeline_files:
            pipeline_name = pipeline_module.rsplit(".", 1)[-1]
            pipeline_package = pipeline_module.rsplit(".", 1)[0]
            service_body.append(
                f"from {package}.{pipeline_package} import "
                f"{pipeline_name} as _{pipeline_name}_pipeline"
            )
        cross_imports = set()
        for source_module, source_variable, error_module, error_variable in error_connections:
            cross_imports.add(f"from {package}.{source_module} import {source_variable}")
            cross_imports.add(f"from {package}.{error_module} import {error_variable}")
        for (
            _,
            _,
            source_module,
            source_variable,
            target_module,
            target_variable,
        ) in cross_connections:
            cross_imports.add(
                f"from {package}.{source_module} import {source_variable}"
            )
            cross_imports.add(
                f"from {package}.{target_module} import {target_variable}"
            )
        service_body.extend(sorted(cross_imports))

        for _, source_variable, _, error_variable in error_connections:
            service_body.append(f"{source_variable} | {error_variable}")

        for (
            expression,
            edge,
            source_module,
            source_variable,
            target_module,
            target_variable,
        ) in cross_connections:
            service_body.append(expression)
            link_code = render_link(
                edge,
                service_imports,
                import_service=False,
            )
            if link_code is not None:
                service_body.append(link_code)
        if non_default_links:
            missing = ", ".join(
                f"{source} -> {target}" for source, target in non_default_links
            )
            raise ValueError(f"Could not place persisted links: {missing}")
        writer.write(
            f"{service_module.replace('.', '/')}.py",
            "\n\n".join(service_body),
            service_imports,
        )
        writer.write_raw(
            f"services/{service_variable}/__init__.py",
            '"""Generated service."""\n',
        )
        writer.write_raw(
            f"services/{service_variable}/pipelines/__init__.py",
            '"""Generated pipelines."""\n',
        )

    imports = [f"from .project.{project_file} import project"]
    for module in writer.registration_modules:
        imports.append(f"from .{module} import *")
    for module in service_modules:
        imports.append(f"from .{module} import *")
    writer.write_raw(
        "__init__.py",
        '"""Generated Service Architect project."""\n\n'
        + "\n".join(imports)
        + '\n\n__all__ = ["project"]\n',
    )
    writer.write_raw(
        "main.py",
        "import sys\nfrom pathlib import Path\n\n"
        "_examples_dir = str(Path(__file__).resolve().parent.parent)\n"
        "if _examples_dir not in sys.path:\n    sys.path.insert(0, _examples_dir)\n\n"
        f'from {package} import project\n\n__all__ = ["project"]\n',
    )
    return PythonProjectFiles(
        package_name=package,
        entrypoint=f"{package}.main:project",
        files=dict(writer.files),
    )


def yaml_to_python_project(
    source: str | Path | Mapping[str, Any], output_dir: str | Path
) -> Path:
    """Convert Service Architect YAML into an importable typed Python project."""
    root = Path(output_dir)
    package = root.name
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Output directory {root} is not empty")
    generated = yaml_to_python_files(source, package)
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"{package}/"
    for filename, content in generated.files.items():
        relative = filename.removeprefix(prefix)
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return root / "main.py"
