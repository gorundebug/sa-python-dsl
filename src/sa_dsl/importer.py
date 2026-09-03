from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .model import (
    CallSemantics,
    DataConnectorImplementation,
    DataType,
    Environment,
    GrpcMethodType,
    HTTPMethodType,
    JoinStorageType,
    JoinType,
    KafkaSaslMechanism,
    KafkaSecurityProtocol,
    KubernetesWorkloadType,
    LogLevel,
    ProcessPattern,
    ProgrammingLanguage,
    ScheduleMissedRunPolicy,
    ScheduleOverlapPolicy,
    TypeDefinitionFormat,
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
    values: Mapping[str, Any],
) -> str:
    lines = [
        f"{source}.link(",
        f"    {destination},",
    ]
    for field, value in values.items():
        lines.append(f"    {_kw_name(field)}={_literal(value)},")
    lines.append(")")
    return "\n".join(lines)


def _dsl_imports(body: str) -> str:
    names = [
        "CallSemantics",
        "DataConnectorImplementation",
        "DataType",
        "Environment",
        "Function",
        "GrpcMethodType",
        "HTTPMethodType",
        "JoinStorageType",
        "JoinType",
        "KafkaSaslMechanism",
        "KafkaSecurityProtocol",
        "KubernetesWorkloadType",
        "LOCAL_MODULE",
        "LogLevel",
        "NULL",
        "Package",
        "ProcessPattern",
        "ProgrammingLanguage",
        "Project",
        "ROOT_PACKAGE",
        "ScheduleMissedRunPolicy",
        "ScheduleOverlapPolicy",
        "TypeDefinitionFormat",
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
    def __init__(self, root: Path, package: str):
        self.root = root
        self.package = package
        self.modules: dict[str, tuple[str, str]] = {}
        self.pools: dict[str, tuple[str, str]] = {}
        self.types: dict[str, tuple[str, str]] = {}
        self.connectors: dict[str, tuple[str, str]] = {}
        self.endpoints: dict[str, tuple[str, str]] = {}
        self.packages: dict[str, tuple[str, str]] = {}
        self.registration_modules: list[str] = []

    def write(self, relative: str, body: str, imports: list[str] | None = None) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        sections = []
        dsl = _dsl_imports(body)
        if dsl:
            sections.append(dsl.rstrip())
        if imports:
            sections.append("\n".join(sorted(set(imports))))
        sections.append(body.rstrip())
        path.write_text(
            "\n\n".join(section for section in sections if section) + "\n",
            encoding="utf-8",
        )

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


def yaml_to_python_project(
    source: str | Path | Mapping[str, Any], output_dir: str | Path
) -> Path:
    """Convert Service Architect YAML into an importable typed Python project."""
    if isinstance(source, Mapping):
        document = dict(source)
    else:
        source_path = Path(source)
        document = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Service Architect YAML root must be a mapping")

    root = Path(output_dir)
    package = root.name
    if not package.isidentifier() or keyword.iskeyword(package):
        raise ValueError(
            f"Output directory name {package!r} must be a Python identifier"
        )
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Output directory {root} is not empty")
    root.mkdir(parents=True, exist_ok=True)
    writer = _Writer(root, package)

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
        (root / category).mkdir(exist_ok=True)
        (root / category / "__init__.py").write_text(
            f'"""Generated {category}."""\n', encoding="utf-8"
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
            values["module"] = _Code("NULL")
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
                method = "route"
                endpoint_values["method"] = endpoint_values.pop("httpMethodType", None)
            elif connector_type == "gRPC":
                method = "method"
                endpoint_values["methodType"] = endpoint_values.pop(
                    "grpcMethodType", None
                )
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
            service_values.setdefault("color", appearance["color"])
        service_name = service_values.pop("name", service_key)
        default_call_semantics = service_values.get(
            "defaultCallSemantics", CallSemantics.FUNCTION_CALL.value
        )
        service_variable = _snake(service_key)
        service_module = f"services.{service_variable}.service"
        service_modules.append(service_module)
        service_values = _property_values(service_values)
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
            return _link_call(
                source_variable,
                target_variable,
                _property_values(link_values),
            )

        cross_connections = []
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
                values["x"] = point.get("x", 0)
                values["y"] = point.get("y", 0)
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
        service_root = root / "services" / service_variable
        (service_root / "__init__.py").write_text(
            '"""Generated service."""\n', encoding="utf-8"
        )
        (service_root / "pipelines" / "__init__.py").write_text(
            '"""Generated pipelines."""\n', encoding="utf-8"
        )

    imports = [f"from .project.{project_file} import project"]
    for module in writer.registration_modules:
        imports.append(f"from .{module} import *")
    for module in service_modules:
        imports.append(f"from .{module} import *")
    (root / "__init__.py").write_text(
        '"""Generated Service Architect project."""\n\n'
        + "\n".join(imports)
        + '\n\n__all__ = ["project"]\n',
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "import sys\nfrom pathlib import Path\n\n"
        "_examples_dir = str(Path(__file__).resolve().parent.parent)\n"
        "if _examples_dir not in sys.path:\n    sys.path.insert(0, _examples_dir)\n\n"
        f'from {package} import project\n\n__all__ = ["project"]\n',
        encoding="utf-8",
    )
    return root / "main.py"
