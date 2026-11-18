from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import yaml

from sa_dsl import ConnectorType, Function, Golang, JetStreamConnector, NATSConnector, Project, ServiceModule
from sa_dsl.api_catalog import build_connector_capabilities, build_typed_api_catalog
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.code_generation import to_api_document
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.mcp_resources import catalog_resource


def fixture(kind="NATS"):
    project = Project("Broker authoring")
    factory = project.nats_connector if kind == "NATS" else project.jetstream_connector
    connector = factory("Broker", servers=["nats://broker:4222"])
    extra = {"stream_name": "EVENTS", "durable_name": "reader"} if kind == "JetStream" else {"queue_group": "workers"}
    source_ep = connector.subject("Receive", function=Function("Receive"), subject="events.*", **extra)
    extra = {"stream_name": "EVENTS"} if kind == "JetStream" else {}
    sink_ep = connector.subject("Publish", function=Function("Publish"), subject="events.processed", **extra)
    service = project.service("Worker", language=Golang(), module=ServiceModule("example.com/worker"))
    pipeline = service.pipeline("Events")
    text = project.string_type("Text")
    source = pipeline.input("Read", endpoint=source_ep, value_type=text)
    pipeline.sink("Write", endpoint=sink_ep, source=source, value_type=text)
    return project, connector, source_ep, sink_ep


@pytest.mark.parametrize("kind,id_,cls", [("NATS", 7, NATSConnector), ("JetStream", 8, JetStreamConnector)])
def test_typed_graph_yaml_python_yaml_and_api_roundtrip(kind, id_, cls):
    project, connector, source, sink = fixture(kind)
    connector.properties.update(
        connectTimeoutMs=2000, operationTimeoutMs=5000,
        credentialsFile="/run/secrets/nats.creds", tlsEnabled=True,
        tlsServerName="broker", tlsCaFile="/run/tls/ca.pem",
        tlsCertFile="/run/tls/client.pem", tlsKeyFile="/run/tls/client-key.pem",
        implementations={"external": "vendor/transport"},
    )
    if kind == "JetStream":
        source.properties.update(createStream=False, createConsumer=True)
        sink.properties["createStream"] = True
    assert isinstance(connector, cls)
    assert project.validate() == []
    document = project.to_document()
    imported = yaml_to_python_files(project.to_yaml(), "broker_roundtrip")
    code = "\n".join(imported.files.values())
    assert f"project.{'nats' if kind == 'NATS' else 'jetstream'}_connector(" in code
    assert ".subject(" in code
    assert yaml.safe_load(python_files_to_yaml(imported.files, imported.entrypoint)) == document
    api = to_api_document(document)
    assert api["dataConnectors"][0]["type"] == id_
    assert api["dataConnectors"][0]["servers"] == ["nats://broker:4222"]
    assert {endpoint["subject"] for endpoint in api["endpoints"]} == {"events.*", "events.processed"}
    assert ConnectorType(kind).value == kind


def test_existing_only_defaults_remain_omitted_through_import():
    project, connector, source, sink = fixture("JetStream")
    for endpoint in (source, sink):
        assert "createStream" not in endpoint.properties
        assert "createConsumer" not in endpoint.properties
    assert "connectTimeoutMs" not in connector.properties
    assert "implementations" not in connector.properties
    files = yaml_to_python_files(project.to_document(), "broker_defaults")
    assert yaml.safe_load(python_files_to_yaml(files.files, files.entrypoint)) == project.to_document()


@pytest.mark.parametrize("kind", ["NATS", "JetStream"])
@pytest.mark.parametrize("field,value", [
    ("servers", []), ("servers", "nats://broker:4222"), ("servers", [3]),
    ("servers", ["broker:4222"]), ("servers", ["nats://user:secret@broker:4222"]),
    ("connectTimeoutMs", 0), ("connectTimeoutMs", True), ("operationTimeoutMs", 1.5),
    ("tlsEnabled", "true"), ("tlsCertFile", "/run/tls/client.pem"),
    ("credentialsFile", ""), ("token", "test-secret"), ("password", "test-secret"),
    ("brokers", "broker:9092"),
])
def test_invalid_connection_config_reports_field_without_secret(kind, field, value):
    project, connector, _, _ = fixture(kind)
    connector.properties[field] = value
    diagnostics = project.validate()
    expected = "tlsKeyFile" if field == "tlsCertFile" else field
    assert any(d.path.endswith("." + expected) for d in diagnostics)
    assert "test-secret" not in str(diagnostics)
    assert "user:secret" not in str(diagnostics)


@pytest.mark.parametrize("kind,field,value", [
    ("NATS", "streamName", "EVENTS"), ("NATS", "durableName", "reader"),
    ("NATS", "createStream", False), ("NATS", "createConsumer", False),
    ("JetStream", "queueGroup", "workers"), ("JetStream", "createConsumer", "false"),
    ("JetStream", "createStream", 0), ("JetStream", "streamName", "bad.name"),
    ("JetStream", "durableName", "bad/name"), ("NATS", "subject", "events..bad"),
    ("NATS", "subject", "events.>.bad"), ("NATS", "subject", "events.foo*"),
    ("NATS", "topic", "events"), ("JetStream", "taskQueue", "tasks"),
])
def test_strict_endpoint_contract(kind, field, value):
    project, _, source, _ = fixture(kind)
    source.properties[field] = value
    assert any(d.path.endswith("." + field) for d in project.validate())


@pytest.mark.parametrize("kind,field,value", [
    ("NATS", "queueGroup", "workers"), ("NATS", "subject", "events.*"),
    ("JetStream", "durableName", "reader"), ("JetStream", "createConsumer", False),
    ("JetStream", "subject", "events.>"),
])
def test_source_only_settings_and_wildcards_rejected_on_sinks(kind, field, value):
    project, _, _, sink = fixture(kind)
    sink.properties[field] = value
    assert any(d.path.endswith(".publish." + field) for d in project.validate())


def test_jetstream_input_requires_durable_but_sink_does_not():
    project, _, source, _ = fixture("JetStream")
    del source.properties["durableName"]
    assert [d.path for d in project.validate()] == ["$.dataConnectors.broker.endpoints.receive.durableName"]


def test_nats_fields_do_not_leak_into_other_connectors():
    project = Project("Other")
    connector = project.custom_connector("Local")
    connector.properties["servers"] = ["nats://broker:4222"]
    endpoint = connector.endpoint("Local endpoint", function=Function("Local"))
    endpoint.properties["subject"] = "events"
    paths = {d.path.rsplit(".", 1)[-1] for d in project.validate()}
    assert paths == {"servers", "subject"}


def test_factories_are_typed_and_capabilities_do_not_claim_adapters():
    catalog = build_typed_api_catalog()
    capabilities = build_connector_capabilities()
    for method, cls in (("nats_connector", NATSConnector), ("jetstream_connector", JetStreamConnector)):
        signature = inspect.signature(getattr(Project, method))
        assert signature.parameters["servers"].default is inspect.Parameter.empty
        assert "servers" in capabilities["connectors"][method]["requiredParameters"]
        assert "languageAdapters" not in capabilities["connectors"][method]
        assert "supportedTargets" not in capabilities["connectors"][method]
        assert "subject" in catalog["classes"][cls.__name__]["methods"]
        resource = json.loads(catalog_resource("authoring", f"typed-api-{cls.__name__}-subject"))
        assert "subject" in resource["signature"]
    with pytest.raises(TypeError):
        Project("Missing").nats_connector("Broker")
    with pytest.raises(TypeError):
        Project("Core").nats_connector("Broker", servers=["nats://broker:4222"]).subject(
            "Invalid", function=Function("Invalid"), subject="events", stream_name="EVENTS")


def test_connection_server_list_is_copied_and_properties_stay_mutable():
    servers = ["nats://broker:4222"]
    project = Project("Properties")
    connector = project.nats_connector("Broker", servers=servers)
    servers.append("nats://other:4222")
    connector.properties["operationTimeoutMs"] = 6000
    assert connector.to_document()["servers"] == ["nats://broker:4222"]
    assert connector.to_document()["operationTimeoutMs"] == 6000


@pytest.mark.parametrize("field", ["subject", "streamName"])
def test_required_native_endpoint_fields_are_checked_without_stream_usage(field):
    project = Project("Unused")
    connector = project.jetstream_connector("Broker", servers=["nats://broker:4222"])
    endpoint = connector.subject("Events", function=Function("Events"), subject="events", stream_name="EVENTS")
    del endpoint.properties[field]
    assert any(d.path.endswith("." + field) for d in project.validate())


def test_auth_modes_are_exclusive_and_secret_diagnostics_are_capability_errors():
    project, connector, _, _ = fixture()
    connector.properties.update(token="test-secret", credentialsFile="/run/secrets/nats.creds")
    diagnostics = project.validate()
    assert any(d.path.endswith(".credentialsFile") and "mutually exclusive" in d.message for d in diagnostics)
    assert any(d.path.endswith(".token") and d.stage == "capability" for d in diagnostics)
    assert "test-secret" not in str(diagnostics)


def test_core_has_no_jetstream_or_request_reply_factory_options():
    parameters = inspect.signature(NATSConnector.subject).parameters
    assert not set(parameters).intersection({"stream_name", "durable_name", "create_stream", "create_consumer", "reply", "request_reply"})
    assert "queue_group" not in inspect.signature(JetStreamConnector.subject).parameters


def test_mcp_connector_capabilities_are_authoring_only():
    document = json.loads(catalog_resource("authoring", "connector-capabilities"))
    assert "Authoring factory parameters only" in document["scope"]
    for factory in ("nats_connector", "jetstream_connector"):
        assert set(document["connectors"][factory]) == {"selection", "requiredParameters"}


# Byte-identical copies live in the generator and Designer repositories so
# validation can run independently while sharing the same initial TCP profile.
@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/nats-connection-validation.json").read_text()), ids=lambda case: case["name"])
@pytest.mark.parametrize("kind", ["NATS", "JetStream"])
def test_connection_cross_layer_fixtures(case, kind):
    project, connector, _, _ = fixture(kind)
    connector.properties.update(case["config"])
    diagnostics = project.validate()
    if not case["invalidFields"]:
        assert diagnostics == []
    else:
        for field in case["invalidFields"]:
            assert any(d.path.endswith("." + field) for d in diagnostics), diagnostics
        assert "fixture-secret" not in str(diagnostics)
