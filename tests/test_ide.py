from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from sa_dsl.ide import graph_snapshot, locate_source
from sa_dsl.manifest import load_manifest


def test_snapshot_is_a_read_only_projection(tmp_path: Path) -> None:
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
    manifest = SimpleNamespace(name="sample", workspace=tmp_path)
    with patch("sa_dsl.ide.execute_project", return_value=SimpleNamespace(
        succeeded=True, rendered_yaml=rendered)):
        snapshot = graph_snapshot(manifest)
    assert snapshot["status"] == "success"
    assert snapshot["snapshot"]["mode"] == "read-only"
    assert snapshot["snapshot"]["canonicalYaml"] == rendered
    assert list(tmp_path.iterdir()) == []


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


def test_canonical_example_all_nodes_and_links_have_python_locations() -> None:
    workspace = Path(__file__).resolve().parents[1] / "examples" / "processorder"
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
        for key, link in (service.get("links") or {}).items():
            found = locate_source(workspace, kind="link", service=service_key, key=key,
                                  source=link["from"], target=link["to"])
            assert found["status"] == "success", (service_key, key)
            checked_links += 1
    assert checked_nodes > 0 and checked_links > 0
