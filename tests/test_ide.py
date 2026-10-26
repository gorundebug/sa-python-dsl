from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from sa_dsl.ide import graph_snapshot, locate_source
from sa_dsl.manifest import load_manifest
from tests.test_manifest_workflow import write_manifest


def test_snapshot_is_read_only_and_saves_the_canonical_artifact(tmp_path: Path) -> None:
    rendered = """services:
  sampleService:
    name: Sample Service
    pipelines:
      main:
        sourceNode: {name: Source Node, type: Input}
        targetNode: {name: Target Node, type: Map, source: sourceNode}
    links:
      sourceNode_targetNode: {from: sourceNode, to: targetNode, callSemantics: 4}
"""
    write_manifest(tmp_path, name="sample")
    manifest = load_manifest(tmp_path)
    source = tmp_path / "architecture.py"
    source.write_text("# User-owned Python remains unchanged\n", encoding="utf-8")
    with patch("sa_dsl.ide.execute_project", return_value=SimpleNamespace(
        succeeded=True, rendered_yaml=rendered)):
        snapshot = graph_snapshot(manifest)
    assert snapshot["status"] == "success"
    assert snapshot["snapshot"]["mode"] == "read-only"
    assert snapshot["snapshot"]["canonicalYaml"] == rendered
    assert (tmp_path / manifest.canonical.output).read_text(encoding="utf-8") == rendered
    assert source.read_text(encoding="utf-8") == "# User-owned Python remains unchanged\n"
    assert ".service-architect/build/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_lookup_node_and_chained_links(tmp_path: Path) -> None:
    service = tmp_path / "services" / "sample_service"
    service.mkdir(parents=True)
    source = service / "pipeline.py"
    source.write_text(
        'a = pipeline.input("Source Node")\n'
        'b = pipeline.map("Middle Node")\n'
        'c = pipeline.sink("Final Node")\n'
        'a >> b >> c\n', encoding="utf-8"
    )
    node = locate_source(tmp_path, kind="node", service="sampleService", key="middleNode")
    first = locate_source(tmp_path, kind="link", service="sampleService",
                          key="sourceNode_middleNode", source="sourceNode", target="middleNode")
    second = locate_source(tmp_path, kind="link", service="sampleService",
                           key="middleNode_finalNode", source="middleNode", target="finalNode")
    assert node["location"] == {"file": "services/sample_service/pipeline.py", "line": 2, "column": 5}
    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["location"]["line"] == 4


def test_lookup_fails_closed_on_ambiguous_names(tmp_path: Path) -> None:
    for name in ("one.py", "two.py"):
        (tmp_path / name).write_text('x = pipeline.input("Same Node")\n', encoding="utf-8")
    result = locate_source(tmp_path, kind="node", service="sampleService", key="sameNode")
    assert result["status"] == "ambiguous"


def test_lookup_literal_route_table_nodes_and_links_without_execution(tmp_path: Path) -> None:
    source = tmp_path / "routes.py"
    content = (
        'raise RuntimeError("source navigation must not execute this module")\n'
        'reply_destination = pipeline.case("Reply to originating API")\n'
        'reply_routes = {}\n'
        'for index, (path, name) in enumerate((("/ad", "Reply to Direct ad"),\n'
        '                                    ("/resource", "Reply to Direct resource"))):\n'
        '    reply_routes[path] = pipeline.when(name, source=reply_destination)\n'
        'entry = pipeline.input("Direct resource")\n'
        'reply_routes["/resource"] >> entry\n'
    )
    source.write_text(content, encoding="utf-8")
    node = locate_source(tmp_path, kind="node", service="adServer", key="replyToDirectResource")
    branch = locate_source(tmp_path, kind="link", service="adServer", key="",
                           source="replyToOriginatingAPI", target="replyToDirectResource")
    result = locate_source(tmp_path, kind="link", service="adServer", key="",
                           source="replyToDirectResource", target="directResource")
    assert node["status"] == branch["status"] == result["status"] == "success"
    assert node["location"]["line"] == branch["location"]["line"] == 6
    assert result["location"]["line"] == 8
    assert source.read_text(encoding="utf-8") == content


def test_lookup_literal_loop_keeps_duplicate_definitions_ambiguous(tmp_path: Path) -> None:
    (tmp_path / "routes.py").write_text(
        'for name in ("Same Node", "Same Node"):\n'
        '    node = pipeline.map(name)\n', encoding="utf-8")
    found = locate_source(tmp_path, kind="node", service="sample", key="sameNode")
    assert found["status"] == "ambiguous"


def test_lookup_does_not_guess_dynamic_or_modified_loop_bindings(tmp_path: Path) -> None:
    cases = (
        'for name in get_names():\n    node = pipeline.map(name)\n',
        'for name in ("Candidate",):\n    name = rename(name)\n    node = pipeline.map(name)\n',
        'enumerate = custom_iterator\nfor index, name in enumerate(("Candidate",)):\n    node = pipeline.map(name)\n',
        'for name in ("Candidate",):\n    if allowed():\n        node = pipeline.map(name)\n',
        'for name in ("Candidate",):\n    break\n    node = pipeline.map(name)\n',
    )
    for content in cases:
        (tmp_path / "routes.py").write_text(content, encoding="utf-8")
        found = locate_source(tmp_path, kind="node", service="sample", key="candidate")
        assert found["status"] == "not-found"


def test_lookup_limits_literal_loop_expansion(tmp_path: Path) -> None:
    names = repr(tuple("Candidate" for _ in range(257)))
    (tmp_path / "routes.py").write_text(
        f'for name in {names}:\n    node = pipeline.map(name)\n', encoding="utf-8")
    found = locate_source(tmp_path, kind="node", service="sample", key="candidate")
    assert found["status"] == "not-found"


def test_canonical_example_all_nodes_and_links_have_python_locations(tmp_path: Path) -> None:
    original = Path(__file__).resolve().parents[1] / "examples" / "processorder"
    workspace = tmp_path / "processorder"
    shutil.copytree(original, workspace, ignore=shutil.ignore_patterns("__pycache__", ".venv"))
    manifest = load_manifest(workspace)
    snapshot = graph_snapshot(manifest)
    assert snapshot["status"] == "success"
    document = yaml.safe_load(snapshot["snapshot"]["canonicalYaml"])
    checked_nodes = checked_links = 0
    for service_key, service in document["services"].items():
        streams = {
            key: stream for pipeline in service["pipelines"].values()
            for key, stream in pipeline.items()
        }
        for key in streams:
            found = locate_source(workspace, kind="node", service=service_key, key=key)
            assert found["status"] == "success", (service_key, key)
            checked_nodes += 1
        links = {(link["from"], link["to"]) for link in (service.get("links") or {}).values()}
        for key, stream in streams.items():
            if stream.get("source"):
                links.add((stream["source"], key))
            links.update((source, key) for source in stream.get("sources", []))
            if stream.get("errorStream"):
                links.add((key, stream["errorStream"]))
        for source, target in links:
            found = locate_source(workspace, kind="link", service=service_key, key=key,
                                  source=source, target=target)
            assert found["status"] == "success", (service_key, source, target, found)
            checked_links += 1
    assert checked_nodes > 0 and checked_links > 0
