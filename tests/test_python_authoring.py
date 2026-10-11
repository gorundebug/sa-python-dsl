from pathlib import Path

import pytest

from sa_dsl.execution import execute_project
from sa_dsl.python_authoring import (
    AuthoringError,
    _expression,
    _insert,
    _statements,
    apply_python_changes,
    inspect_python_authoring,
    preview_python_changes,
)
from tests.test_generation_transaction import project_workspace


SOURCE = '''from sa_dsl import Project, Golang, ServiceModule, Function

# This comment and the user's formatting must survive.
project = Project("Example")
value = project.string_type("Value")
service = project.service("OrderService", language=Golang(), module=ServiceModule("example.com/order"))
pipeline = service.pipeline("Quote")
api_module = project.module("Order API", module_path="example.com/orderapi", golang_version="1.25.4")
http = project.http_connector("Order API", module=api_module)
endpoint = http.post("Quote", function=Function("ReadQuote"), path="/quote")
entry = pipeline.input("Read Quote", endpoint=endpoint, value_type=value)
'''


def authoring_project(tmp_path: Path, source: str = SOURCE):
    manifest = project_workspace(tmp_path)
    (tmp_path / "architecture.py").write_text(source)
    return manifest


def preview_node(manifest, **overrides):
    info = inspect_python_authoring(manifest.workspace, "architecture.py")
    arguments = {
        "source_file": "architecture.py",
        "source_revision": info["sourceRevision"],
        "before_line": info["insertionSites"][-1]["beforeLine"],
        "operations": [{"kind": "add_node", "receiver": "pipeline", "factory": "map",
                        "symbol": "quote", "name": "Calculate Quote",
                        "arguments": {"function": "Function('CalculateQuote')", "source": "entry", "value_type": "value"}}],
    }
    arguments.update(overrides)
    return preview_python_changes(manifest.workspace, **arguments)


def apply(manifest, preview):
    return apply_python_changes(manifest.workspace, preview_id=preview["previewId"],
                                preview_revision=preview["previewRevision"])


def test_inspection_never_executes_python(tmp_path):
    manifest = authoring_project(tmp_path, "raise RuntimeError('must not execute')\n")
    info = inspect_python_authoring(manifest.workspace, "architecture.py")
    assert info["status"] == "success"
    assert "must not execute" in info["source"]


def test_preview_apply_preserves_source_and_rejects_replay(tmp_path):
    manifest = authoring_project(tmp_path)
    before = (tmp_path / "architecture.py").read_bytes()
    preview = preview_node(manifest)
    assert preview["status"] == "success", preview
    assert (tmp_path / "architecture.py").read_bytes() == before
    assert "+quote = pipeline.map" in preview["sourceDiff"]
    result = apply(manifest, preview)
    assert result["status"] == "success", result
    assert (tmp_path / "architecture.py").read_bytes().startswith(before)
    assert execute_project(manifest, "validate").succeeded
    with pytest.raises(AuthoringError, match="already been applied"):
        apply(manifest, preview)


def test_batch_endpoint_nodes_and_response_connection(tmp_path):
    manifest = authoring_project(tmp_path)
    preview = preview_node(manifest, operations=[
        {"kind": "add_endpoint", "receiver": "http", "factory": "post", "symbol": "new_endpoint",
         "name": "Alternative Quote", "arguments": {"function": "Function('AlternativeRequest')", "path": "'/quote/alternative'"}},
        {"kind": "add_node", "receiver": "pipeline", "factory": "input", "symbol": "request",
         "name": "Read Alternative", "arguments": {"endpoint": "new_endpoint", "value_type": "value"}},
        {"kind": "add_node", "receiver": "pipeline", "factory": "map", "symbol": "alternative",
         "name": "Calculate Alternative", "arguments": {"function": "Function('AlternativeQuote')", "source": "request", "value_type": "value"}},
        {"kind": "connect_ports", "source": "alternative", "target": "request", "role": "data"},
    ])
    assert preview["status"] == "success", preview
    assert apply(manifest, preview)["status"] == "success"
    rendered = execute_project(manifest, "export")
    assert rendered.succeeded
    assert "Alternative Quote" in rendered.rendered_yaml


def test_invalid_factory_arguments_never_change_original(tmp_path):
    manifest = authoring_project(tmp_path)
    preview = preview_node(manifest, operations=[{
        "kind": "add_node", "receiver": "pipeline", "factory": "map", "symbol": "bad", "name": "Bad",
        "arguments": {"unknown_parameter": "True"},
    }])
    assert preview["status"] == "failed"
    assert preview["phase"] == "candidate"
    assert (tmp_path / "architecture.py").read_text() == SOURCE


def test_stale_sources_and_tampered_candidate_are_rejected(tmp_path):
    manifest = authoring_project(tmp_path)
    preview = preview_node(manifest)
    assert preview["status"] == "success", preview
    (tmp_path / "architecture.py").write_text(SOURCE + "# external edit\n")
    with pytest.raises(AuthoringError, match="inputs changed"):
        apply(manifest, preview)
    (tmp_path / "architecture.py").write_text(SOURCE)
    candidate = tmp_path / ".service-architect" / "edits" / preview["previewId"] / "candidate.py"
    candidate.write_text("raise RuntimeError('altered preview')\n")
    with pytest.raises(AuthoringError, match="content changed"):
        apply(manifest, preview)
    assert (tmp_path / "architecture.py").read_text() == SOURCE


def test_unexecuted_factory_edit_reports_no_effect(tmp_path):
    source = SOURCE + "\ndef unused():\n    return project\n"
    manifest = authoring_project(tmp_path, source)
    info = inspect_python_authoring(tmp_path, "architecture.py")
    site = next(site for site in info["insertionSites"] if site["scope"] == "unused")
    with pytest.raises(AuthoringError, match="did not change"):
        preview_node(manifest, before_line=site["beforeLine"])


def test_shadow_excludes_credentials_and_source_symlinks_are_rejected(tmp_path):
    manifest = authoring_project(tmp_path)
    linked = tmp_path / "linked.py"
    linked.symlink_to(tmp_path / "architecture.py")
    with pytest.raises(AuthoringError, match="symlinks"):
        inspect_python_authoring(manifest.workspace, "linked.py")


@pytest.mark.parametrize("expression", ["__import__('os')", "value.__class__", "[x for x in values]", "Function(**values)", "open('/tmp/x')"])
def test_expressions_do_not_accept_arbitrary_python_calls(expression):
    with pytest.raises(AuthoringError):
        _expression(expression, {"Function"})


def test_source_insertion_preserves_crlf_and_rejects_control_flow_blocks():
    import ast

    text = "def build():\r\n    if True:\r\n        pass\r\n    return project\r\n"
    tree = ast.parse(text)
    candidate = _insert(text, tree, 4, ["source >> target"])
    assert candidate == text.replace("    return", "    source >> target\r\n    return")
    with pytest.raises(AuthoringError, match="insertion site"):
        _insert(text, tree, 3, ["source >> target"])


def test_unknown_operation_fields_are_not_silently_ignored():
    import ast

    with pytest.raises(AuthoringError, match="unknown connection fields"):
        _statements(ast.parse(""), [{"kind": "connect_ports", "source": "a", "target": "b", "port": 2}], [])
