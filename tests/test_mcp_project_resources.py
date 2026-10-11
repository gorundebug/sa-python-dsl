import asyncio
import json
import sys
import time
from urllib.parse import quote

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from sa_dsl.operation_audit import record_operation
from tests.test_generation_transaction import project_workspace
from tests.test_mcp_endpoint_authoring import _call
from tests.test_servicegen_capabilities import matrix
from tests.test_servicegen_validation import contract


def test_project_resources_are_explicit_isolated_and_do_not_execute_python(tmp_path):
    projects = {"team/first project": "first", "second": "second"}
    for name, label in projects.items():
        root = tmp_path / name
        root.mkdir(parents=True)
        manifest = project_workspace(root)
        (root / "architecture.py").write_text(
            "from pathlib import Path\nPath('executed-authoring').touch()\nraise RuntimeError('resource executed Python')\n"
        )
        canonical = root / manifest.canonical.output
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(json.dumps({"settings": {"name": name}}))
        record_operation(root, "fixture-" + name, {"status": "success"}, time.monotonic())
        capability = matrix()
        capability["revision"] = "sha256:" + label
        validation = contract(capability_revision=capability["revision"])
        validation["revision"] = "sha256:rules-" + label
        (root / ".service-architect/capabilities.json").write_text(json.dumps(capability))
        (root / ".service-architect/validation-contract.json").write_text(json.dumps(validation))

    async def read(session, uri):
        response = await session.read_resource(uri)
        return json.loads(response.contents[0].text)

    async def exercise():
        params = StdioServerParameters(command=sys.executable, args=["-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path)])
        async with asyncio.timeout(30):
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    for name in (*projects, next(iter(projects))):
                        label = projects[name]
                        inspected = await _call(session, "inspect_project", {"project_path": name})
                        assert inspected["status"] == "success", inspected
                        refs = inspected["resources"]
                        assert quote(name, safe="") in refs["audit"]
                        source = await read(session, refs["source"])
                        assert source["resources"] == refs
                        assert (await read(session, refs["dsl"]))["settings"]["name"] == name
                        assert (await read(session, refs["graph"]))["settings"]["name"] == name
                        tasks = await read(session, refs["tasks"])
                        assert tasks.get("status") != "failed", tasks
                        audit = await read(session, refs["audit"])
                        assert "fixture-" + name in json.dumps(audit)
                        capability = await read(session, refs["capabilities"])
                        assert capability["revision"] == "sha256:" + label
                        validation = await read(session, refs["validation-contract"])
                        assert validation["revision"] == "sha256:rules-" + label
                        language = await read(session, refs["languageCapabilities"].replace("{language}", "golang"))
                        assert language.get("status") != "unavailable", language
                        rule = await read(session, refs["validationRule"].replace("{code}", "SG_SEMANTIC_TYPE_MISMATCH"))
                        assert rule["contractRevision"] == "sha256:rules-" + label
                    for kind in ("source", "dsl", "graph", "tasks", "audit"):
                        missing = await read(session, "servicegen://workspace/current/" + kind)
                        assert missing["status"] == "failed", missing
                    missing_rule = await read(session, "servicegen://validation/rules/SG_UNKNOWN")
                    assert missing_rule["status"] == "unavailable", missing_rule
                    for project in ("../outside", "/tmp", "team/../../outside"):
                        uri = "servicegen://project/" + quote(project, safe="") + "/audit"
                        try:
                            refused = await read(session, uri)
                        except MCPError as error:
                            assert str(error) == "Unknown resource: " + uri, error
                        else:
                            assert refused["status"] == "failed", refused
                            assert refused["diagnostics"][0]["code"] == "SA_WORKSPACE_BOUNDARY_VIOLATION", refused

    asyncio.run(exercise())
    assert not list(tmp_path.rglob("executed-authoring"))


@pytest.mark.parametrize("kind", ["source", "dsl", "graph", "tasks", "audit", "capabilities", "validation-contract"])
def test_resource_handler_rejects_outside_paths_without_sdk_routing(tmp_path, monkeypatch, kind):
    from sa_dsl import mcp_server

    root = tmp_path / "registered"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(root))
    for project in ("../outside", str(outside), "escape"):
        payload = json.loads(mcp_server.project_resource(quote(project, safe=""), kind))
        assert payload["status"] == "failed", payload
        assert payload["diagnostics"][0]["code"] == "SA_WORKSPACE_BOUNDARY_VIOLATION", payload


def test_scoped_diagnostics_link_to_the_projects_rule_cache(tmp_path, monkeypatch):
    from sa_dsl import mcp_server

    project = tmp_path / "my architecture"
    project.mkdir()
    manifest = project_workspace(project)
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    result = mcp_server._attach_project_remediation(
        {"status": "failed", "diagnostics": [{"code": "SG_SEMANTIC_TYPE_MISMATCH", "message": "bad types"}]},
        manifest, "my architecture",
    )
    assert result["diagnostics"][0]["validationRuleUri"] == (
        "servicegen://project/my%20architecture/validation/rules/SG_SEMANTIC_TYPE_MISMATCH"
    )
