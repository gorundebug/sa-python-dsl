from sa_dsl import Project, Function


def test_custom_endpoint_defaults_enabled_and_supports_disabling():
    connector = Project("custom-source").custom_connector("Sources")
    active = connector.endpoint("Active", function=Function("ReadActive"))
    inactive = connector.endpoint("Inactive", function=Function("ReadInactive"), enabled=False)
    assert active.to_document()["enabled"] is True
    assert inactive.to_document()["enabled"] is False
