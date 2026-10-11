import inspect

import pytest
import yaml

from sa_dsl import Function, Golang, Pipeline, Project, ServiceModule
from sa_dsl.api_catalog import describe_typed_factory


def test_error_factory_does_not_advertise_unsupported_function():
    assert "function" not in inspect.signature(Pipeline.error).parameters
    assert "function" not in describe_typed_factory("Pipeline", "error")["signature"]
    project = Project("Example")
    value = project.string_type("Value")
    service = project.service("Worker", language=Golang(), module=ServiceModule("example.com/worker"))
    pipeline = service.pipeline("Work")
    with pytest.raises(TypeError, match="function"):
        pipeline.error("Invalid Error", value_type=value, function=Function("InvalidHandler"))
    owner = pipeline.process("Reserve", value_type=value, function=Function("Reserve"))
    failure = pipeline.error("Reservation Failed", value_type=value, source=owner)
    owner.on_error(failure)
    document = yaml.safe_load(project.to_yaml())
    streams = document["services"]["worker"]["pipelines"]["work"]
    assert streams["reservationFailed"]["source"] == "reserve"
    assert "functionName" not in streams["reservationFailed"]
    assert streams["reserve"]["errorStream"] == "reservationFailed"
