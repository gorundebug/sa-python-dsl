import json
from pathlib import Path

import pytest

from sa_dsl.execution import execute_project
from sa_dsl.pattern_recipes import PATTERN_RECIPES
from sa_dsl.mcp_resources import catalog_resource
from tests.test_generation_transaction import project_workspace


@pytest.mark.parametrize("name", sorted(PATTERN_RECIPES))
def test_recipe_builds_a_valid_typed_python_model(tmp_path: Path, name: str):
    manifest = project_workspace(tmp_path)
    recipe = json.loads(catalog_resource("patterns", name))
    (tmp_path / "architecture.py").write_text(recipe["example"]["code"], encoding="utf-8")
    result = execute_project(manifest, "export")
    assert result.succeeded, result.to_payload()
    assert result.rendered_yaml
    assert recipe["example"]["entrypoint"] == manifest.authoring.entrypoint
    assert recipe["useWhen"] and recipe["avoidWhen"]
    assert set(recipe["contracts"]) == {"types", "cardinality", "execution", "correlation", "completion", "failure"}
    assert recipe["authoring"]["apply"] == "apply_python_changes"
    for uri in recipe["objects"]:
        guide = json.loads(catalog_resource("authoring", uri.rsplit("/", 1)[1]))
        assert guide.get("purpose"), guide


def test_every_published_pattern_has_a_runnable_recipe():
    index = json.loads(catalog_resource("patterns", "index"))
    assert set(index["topics"]) == set(PATTERN_RECIPES)
    assert len(index["topics"]) == 10


def test_scheduled_and_on_demand_workflows_are_distinct():
    on_demand = PATTERN_RECIPES["temporal-sequential"]["example"]["code"]
    scheduled = PATTERN_RECIPES["temporal-scheduled"]["example"]["code"]
    assert "schedule=TemporalSchedule(" not in on_demand
    assert 'id="daily-quote-reminder"' in scheduled
    assert 'timezone="UTC"' in scheduled
