from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import runpy
from uuid import uuid4

import pytest
import yaml

from sa_dsl import IntervalSchedule
from sa_dsl.importer import yaml_to_python_files, yaml_to_python_project
from sa_dsl.mcp_resources import catalog_resource


def interval_document():
    example = Path(__file__).parents[1] / "examples/local-interval/project.py"
    project = runpy.run_path(str(example))["project"]
    return yaml.safe_load(project.to_yaml())


def endpoint(document):
    connector = next(iter(document["dataConnectors"].values()))
    return next(iter(connector["endpoints"].values()))


def import_project(document, tmp_path, monkeypatch):
    package = "interval_" + uuid4().hex
    yaml_to_python_project(document, tmp_path / package)
    monkeypatch.syspath_prepend(str(tmp_path))
    return importlib.import_module(package + ".main").project


@pytest.mark.parametrize("milliseconds", [10, 100, 86_400_000])
@pytest.mark.parametrize("overlap,missed", [("Skip", "Skip"), ("Allow", "FireOnce")])
def test_interval_import_preview_and_roundtrip(milliseconds, overlap, missed, tmp_path, monkeypatch):
    document = interval_document()
    endpoint(document).update(schedule=f"@every {milliseconds}ms", overlapPolicy=overlap, missedRunPolicy=missed)
    preview = yaml_to_python_files(document, "preview_interval")
    source = "\n".join(preview.files.values())
    assert f"IntervalSchedule(milliseconds={milliseconds}" in source
    assert "CronSchedule(" not in source
    rebuilt = import_project(document, tmp_path, monkeypatch)
    assert rebuilt.validate() == []
    assert yaml.safe_load(rebuilt.to_yaml()) == document


def test_calendar_import_is_unchanged(tmp_path, monkeypatch):
    document = interval_document()
    endpoint(document)["schedule"] = "*/5 * * * *"
    source = "\n".join(yaml_to_python_files(document, "preview_calendar").files.values())
    assert "CronSchedule(" in source
    assert "IntervalSchedule(" not in source
    rebuilt = import_project(document, tmp_path, monkeypatch)
    assert rebuilt.validate() == []
    assert yaml.safe_load(rebuilt.to_yaml()) == document


@pytest.mark.parametrize("schedule,timezone,field", [("@every 1ms", "UTC", "schedule"), ("@every 010ms", "UTC", "schedule"), ("@every 100ms", "Europe/Moscow", "timezone")])
def test_invalid_interval_is_not_silently_normalized(schedule, timezone, field, tmp_path, monkeypatch):
    document = interval_document()
    endpoint(document).update(schedule=schedule, timezone=timezone)
    source = "\n".join(yaml_to_python_files(document, "preview_invalid").files.values())
    assert "CronSchedule(" in source
    assert "IntervalSchedule(" not in source
    rebuilt = import_project(document, tmp_path, monkeypatch)
    diagnostics = rebuilt.validate()
    assert [(item.code, item.path.rsplit(".", 1)[-1]) for item in diagnostics] == [
        ("SG_SCHEMA_VALUE_OUT_OF_RANGE", field)
    ]
    restored = endpoint(rebuilt.to_document())
    assert restored["schedule"] == schedule
    assert restored["timezone"] == timezone


def test_mcp_exposes_interval_contract_and_matching_factory():
    resource = json.loads(catalog_resource("semantics", "local-scheduling"))
    fields = resource["interval"]["fields"]
    signature = inspect.signature(IntervalSchedule)
    assert set(fields) == set(signature.parameters)
    for name in ("overlap_policy", "missed_run_policy"):
        assert fields[name]["default"] == signature.parameters[name].default.value
    assert fields["milliseconds"]["minimum"] == 10
    assert fields["milliseconds"]["maximum"] == 86_400_000
    for uri in resource["apiResources"]:
        reference = json.loads(catalog_resource("authoring", uri.removeprefix("servicegen://authoring/")))
        assert "signature" in reference
    schedule = json.loads(catalog_resource("authoring", "typed-api-CronConnector-schedule"))
    assert "IntervalSchedule" in schedule["signature"]
    assert len(json.dumps(resource).encode()) < 16000
