import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sa_dsl.ide import locate_source
from sa_dsl.model import Pipeline
from sa_dsl.source_locations import (
    INDEX_PATH, capture_source_locations, source_fingerprint, write_source_locations,
)


SOURCE = '''from sa_dsl.model import Service
service = Service("adServer", "Ad Server", "golang", "example/adserver")
pipeline = service.pipeline("Delivery")
def entry(name):
    return pipeline.merge(name)
win = entry("Delivery win request")
click = entry("Delivery click request")
replies = pipeline.merge("Delivery replies")
routes = {}
for index, (kind, target) in enumerate((("win", win), ("click", click))):
    route = pipeline.when(f"Reply to delivery {kind}", source=replies, value_type="string")
    routes[kind] = route
    route >> target
combined = pipeline.merge("All requests")
combined.from_sources(win, click)
errors = pipeline._stream("Delivery error", "Error")
click.on_error(errors)
routes["click"].function_call(click)
'''


def indexed_project(tmp_path):
    file = tmp_path / "delivery.py"
    file.write_text(SOURCE)
    scope = {}
    with capture_source_locations(tmp_path) as index:
        exec(compile(SOURCE, str(file), "exec"), scope)
    project = SimpleNamespace(services={"adServer": scope["service"]})
    canonical = ".service-architect/build/project.yaml"
    (tmp_path / canonical).parent.mkdir(parents=True)
    (tmp_path / canonical).write_text("services: {}\n")
    write_source_locations(tmp_path, index.document(project), source_fingerprint(tmp_path),
                           canonical, "services: {}\n")
    return file


def test_factory_and_reference_loop_locations_are_recorded_without_reexecution(tmp_path):
    file = indexed_project(tmp_path)
    # Nothing is imported/executed on lookup, including factory and f-string code.
    for key in ("deliveryWinRequest", "deliveryClickRequest", "replyToDeliveryWin", "replyToDeliveryClick"):
        result = locate_source(tmp_path, kind="node", service="adServer", key=key)
        assert result["status"] == "success", result
        assert result["location"]["file"] == "delivery.py"
    cases = [
        ("deliveryReplies", "replyToDeliveryClick", '    route = pipeline.when('),
        ("replyToDeliveryWin", "deliveryWinRequest", '    route >> target'),
        ("replyToDeliveryClick", "deliveryClickRequest", 'routes["click"].function_call(click)'),
        ("deliveryClickRequest", "allRequests", 'combined.from_sources(win, click)'),
        ("deliveryClickRequest", "deliveryError", 'click.on_error(errors)'),
    ]
    for source, target, prefix in cases:
        result = locate_source(tmp_path, kind="link", service="adServer", key="", source=source, target=target)
        assert result["status"] == "success", result
        assert result["location"]["line"] == next(i for i, line in enumerate(SOURCE.splitlines(), 1) if line.startswith(prefix))
    assert file.read_text() == SOURCE


@pytest.mark.parametrize("changed", ["source", "canonical", "new-file", "manifest"])
def test_stale_index_requires_refresh_instead_of_guessing(tmp_path, changed):
    file = indexed_project(tmp_path)
    target = {"source": file, "canonical": tmp_path / ".service-architect/build/project.yaml",
              "new-file": tmp_path / "new.py", "manifest": tmp_path / ".service-architect/project.yaml"}[changed]
    target.write_text("# changed\n")
    result = locate_source(tmp_path, kind="link", service="adServer", key="",
                           source="replyToDeliveryClick", target="deliveryClickRequest")
    assert result["status"] == "stale"
    assert "Refresh" in result["message"]


def test_cached_location_cannot_escape_workspace(tmp_path):
    indexed_project(tmp_path)
    path = tmp_path / INDEX_PATH
    data = json.loads(path.read_text())
    data["nodes"]["adServer"]["deliveryClickRequest"]["file"] = "../outside.py"
    path.write_text(json.dumps(data))
    result = locate_source(tmp_path, kind="node", service="adServer", key="deliveryClickRequest")
    assert result["status"] == "stale"


def test_capture_restores_hooks_after_authoring_failure(tmp_path):
    original = Pipeline._stream
    with pytest.raises(RuntimeError):
        with capture_source_locations(tmp_path):
            raise RuntimeError("broken authoring")
    assert Pipeline._stream is original


def test_capture_accepts_keyword_error_target(tmp_path):
    content = SOURCE.replace("click.on_error(errors)", "click.on_error(error_stream=errors)")
    file = tmp_path / "keyword.py"
    file.write_text(content)
    scope = {}
    with capture_source_locations(tmp_path) as index:
        exec(compile(content, str(file), "exec"), scope)
    document = index.document(SimpleNamespace(services={"adServer": scope["service"]}))
    assert document["links"]["adServer"]["deliveryClickRequest"]["deliveryError"]["file"] == "keyword.py"
