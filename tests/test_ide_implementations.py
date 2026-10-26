import pytest

from sa_dsl.ide_implementations import implementation_targets


@pytest.mark.parametrize("language", ["GoLang", "CppUserver", "CppCoro", "Python", "Rust", "TypeScript"])
def test_function_and_transport_roles(language):
    document = {
        "dataConnectors": {"http": {"endpoints": {"request": {
            "functionName": "HandleHTTP", "functionPackage": "a/b/c",
        }}}},
        "services": {"orders": {"programmingLanguage": language, "pipelines": {"main": {
            "map": {"type": "Map", "functionName": "ValidateOrder", "functionModule": "shared"},
            "input": {"type": "Input", "endpoint": "request"},
            "sink": {"type": "Sink", "endpoint": "request"},
            "split": {"type": "Split"},
        }}}},
    }
    nodes = implementation_targets(document)["orders"]
    assert nodes["map"][0]["owner"] == "shared"
    assert nodes["map"][0]["language"] == language
    assert nodes["input"][0]["symbols"] == ["HandleHTTPSource", "handle_http_source"]
    assert nodes["sink"][0]["symbols"] == ["HandleHTTPSink", "handle_http_sink"]
    assert nodes["input"][0]["package"] == "a/b/c"
    assert "split" not in nodes


def test_same_node_keys_are_scoped_by_service_and_missing_endpoints_have_no_action():
    services = {name: {"pipelines": {"p": {
        "work": {"functionName": function}, "missing": {"type": "Input", "endpoint": "absent"},
    }}} for name, function in [("first", "One"), ("second", "Two")]}
    targets = implementation_targets({"services": services})
    assert targets["first"]["work"][0]["name"] == "One"
    assert targets["second"]["work"][0]["name"] == "Two"
    assert "missing" not in targets["first"]
