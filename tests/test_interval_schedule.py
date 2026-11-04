import pytest
import yaml

from sa_dsl import CronSchedule, DslValidationError, Function, IntervalSchedule, Project
from sa_dsl.validation import Validator


@pytest.mark.parametrize("milliseconds", [10, 100, 1000, 86_400_000])
def test_interval_typed_factory_and_wire(milliseconds):
    project = Project("interval-test")
    connector = project.cron_connector("Maintenance")
    endpoint = connector.schedule(
        "Sweep", function=Function("Sweep"),
        trigger=IntervalSchedule(milliseconds=milliseconds),
    )
    validator = Validator(project)
    validator.validate_schedule(endpoint, "$.endpoints[0]", temporal=False)
    assert validator.values == []
    document = yaml.safe_load(project.to_yaml())
    wire = next(iter(next(iter(document["dataConnectors"].values()))["endpoints"].values()))
    assert wire["schedule"] == f"@every {milliseconds}ms"
    assert wire["timezone"] == "UTC"
    assert wire["overlapPolicy"] == "Skip"
    assert wire["missedRunPolicy"] == "Skip"


@pytest.mark.parametrize("value", [True, False, 0, 9, -100, 86_400_001, 100.0, "100"])
def test_interval_requires_bounded_integer(value):
    with pytest.raises(DslValidationError):
        IntervalSchedule(milliseconds=value)


@pytest.mark.parametrize("expression,temporal,valid", [
    ("@every 100ms", False, True),
    ("@every 100ms", True, False),
    ("@every 9ms", False, False),
    ("@every 86400001ms", False, False),
    ("@every 010ms", False, False),
    ("@every +10ms", False, False),
    ("@every 1s", False, False),
    ("@every 0.1s", False, False),
    ("@every  100ms", False, False),
    ("@every 100ms ", False, False),
    ("* * * * *", False, True),
    ("* * * * *", True, True),
])
def test_interval_validation_matches_local_not_temporal(expression, temporal, valid):
    project = Project("interval-test")
    endpoint = project.cron_connector("Maintenance").schedule(
        "Sweep", function=Function("Sweep"), trigger=CronSchedule(expression=expression),
    )
    endpoint.properties["scheduleId"] = "sweep"
    validator = Validator(project)
    validator.validate_schedule(endpoint, "$.endpoints[0]", temporal=temporal)
    assert (validator.values == []) == valid, validator.values
