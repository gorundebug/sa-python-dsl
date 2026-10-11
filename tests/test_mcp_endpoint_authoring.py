import asyncio
import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sa_dsl.pattern_recipes import PATTERN_RECIPES
from tests.test_generation_transaction import project_workspace


CASES = [
    (name, 'project.grpc_connector("Extra RPC", module=contracts)', name,
     {"method_name": "'ReceiveExtra'"})
    for name in ("unary_method", "client_streaming_method", "server_streaming_method", "bidirectional_streaming_method")
] + [
    ("kafka", 'project.kafka_connector("Extra Events", cluster=KafkaCluster(brokers="redpanda:9092"))',
     "topic", {"topic": "'extra-events'", "consumer_group": "'extra-consumers'"}),
    ("cron", 'project.cron_connector("Extra Schedule")', "schedule",
     {"trigger": "CronSchedule(expression='*/5 * * * *', timezone='UTC')"}),
    ("activity", 'project.temporal_connector("Extra Temporal", address="temporal:7233", namespace="default")',
     "activity", {"worker": "ActivityWorker(task_queue='extra', max_concurrent=2)",
                  "timeouts": "ActivityTimeouts(start_to_close=30000)"}),
    ("workflow", 'project.temporal_connector("Extra Temporal", address="temporal:7233", namespace="default")',
     "workflow", {"worker": "WorkflowWorker(task_queue='extra', max_concurrent=2)",
                  "timeouts": "WorkflowTimeouts(execution=60000)"}),
]


async def _call(session, name, arguments):
    response = await session.call_tool(name, arguments)
    wire = response.model_dump(by_alias=True)
    assert not wire.get("isError", False), wire
    payload = wire.get("structuredContent")
    if payload is None:
        payload = json.loads(next(item["text"] for item in wire["content"] if item["type"] == "text"))
    return payload


def _project(root, connector):
    project_workspace(root)
    source = (
        "from sa_dsl import CronSchedule\n"
        + PATTERN_RECIPES["http-request-response"]["example"]["code"]
        + f"\nextra = {connector}\n# Keep this user-owned explanation.\n"
    )
    path = root / "architecture.py"
    path.write_text(source, encoding="utf-8")
    return path, source


@pytest.mark.parametrize("case,connector,factory,arguments", CASES, ids=[case[0] for case in CASES])
def test_endpoint_preview_apply_and_validate_over_stdio(tmp_path, case, connector, factory, arguments):
    path, source = _project(tmp_path, connector)

    async def run():
        server = StdioServerParameters(command=sys.executable, args=[
            "-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path),
        ])
        async with asyncio.timeout(30):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    inspected = await _call(session, "inspect_python_authoring", {"source_file": "architecture.py"})
                    assert inspected["status"] == "success", inspected
                    prepared = await _call(session, "add_endpoint", {
                        "source_file": "architecture.py",
                        "source_revision": inspected["sourceRevision"],
                        "before_line": len(source.splitlines()) + 1,
                        "receiver": "extra", "factory": factory,
                        "symbol": "extra_endpoint", "name": "Extra Endpoint",
                        "arguments": {"function": "Function('ReceiveExtra', public=False)", **arguments},
                    })
                    assert prepared["status"] == "success", prepared
                    assert path.read_text(encoding="utf-8") == source
                    preview = prepared.get("preview", prepared)
                    assert preview["sourceDiff"]
                    applied = await _call(session, "apply_python_changes", {
                        "preview_id": preview["previewId"],
                        "preview_revision": preview["previewRevision"],
                    })
                    assert applied["status"] == "success", applied
                    changed = path.read_text(encoding="utf-8")
                    assert changed.startswith(source)
                    assert "extra_endpoint = extra." + factory + "(" in changed
                    edits = [
                        ("add_node", {
                            "receiver": "pipeline", "factory": "input",
                            "symbol": "extra_input", "name": "Receive Extra Endpoint",
                            "arguments": {"endpoint": "extra_endpoint", "value_type": "value"},
                        }),
                        ("add_node", {
                            "receiver": "pipeline", "factory": "map",
                            "symbol": "extra_result", "name": "Handle Extra Endpoint",
                            "arguments": {
                                "source": "extra_input", "value_type": "value",
                                "function": "Function('ForwardExtra', module=LOCAL_MODULE)",
                            },
                        }),
                        ("connect_ports", {"source": "extra_result", "target": "extra_input", "role": "data"}),
                    ]
                    for tool, edit_arguments in edits:
                        inspected = await _call(session, "inspect_python_authoring", {"source_file": "architecture.py"})
                        prepared = await _call(session, tool, {
                            "source_file": "architecture.py",
                            "source_revision": inspected["sourceRevision"],
                            "before_line": len(inspected["source"].splitlines()) + 1,
                            **edit_arguments,
                        })
                        assert prepared["status"] == "success", prepared
                        preview = prepared.get("preview", prepared)
                        applied = await _call(session, "apply_python_changes", {
                            "preview_id": preview["previewId"], "preview_revision": preview["previewRevision"],
                        })
                        assert applied["status"] == "success", applied
                    assert path.read_text(encoding="utf-8").startswith(source)
                    validated = await _call(session, "validate_project", {"project_path": "."})
                    assert validated["status"] == "success", validated

    asyncio.run(run())


def test_unsupported_endpoint_argument_is_diagnostic_and_preserves_source(tmp_path):
    path, source = _project(tmp_path, 'project.grpc_connector("Extra RPC", module=contracts)')

    async def run():
        server = StdioServerParameters(command=sys.executable, args=[
            "-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path),
        ])
        async with asyncio.timeout(30):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    inspected = await _call(session, "inspect_python_authoring", {"source_file": "architecture.py"})
                    result = await _call(session, "add_endpoint", {
                        "source_file": "architecture.py",
                        "source_revision": inspected["sourceRevision"],
                        "before_line": len(source.splitlines()) + 1,
                        "receiver": "extra", "factory": "unary_method",
                        "symbol": "extra_endpoint", "name": "Extra Endpoint",
                        "arguments": {"function": "Function('ReceiveExtra', public=False)", "type_definition": "'not-an-endpoint-argument'"},
                    })
                    assert result["status"] == "failed", result
                    assert result["diagnostics"]
                    assert path.read_text(encoding="utf-8") == source

    asyncio.run(run())
