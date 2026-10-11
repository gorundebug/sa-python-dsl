import pytest

from sa_dsl import mcp_server
from tests.test_generation_transaction import project_workspace
from tests.test_servicegen_capabilities import matrix
from tests.test_servicegen_validation import contract


@pytest.mark.parametrize("operation,fetch,payload", [
    ("refresh_capabilities", "fetch_capabilities", matrix()),
    ("refresh_validation_contract", "fetch_validation_contract", contract()),
])
def test_metadata_uses_the_project_generation_backend(tmp_path, monkeypatch, operation, fetch, payload):
    project_workspace(tmp_path)
    (tmp_path / ".env").write_text(
        "SERVICE_ARCHITECT_API_URL=https://project-api.example.test/stage\n"
        "SERVICE_ARCHITECT_API_KEY=must-not-pass-to-public-metadata\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SERVICE_ARCHITECT_API_URL", raising=False)
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    requested = []

    def fake_fetch(base_url=None):
        requested.append(base_url)
        return payload

    monkeypatch.setattr(mcp_server, fetch, fake_fetch)
    result = getattr(mcp_server, operation)()
    assert result["status"] == "success", result
    assert requested == ["https://project-api.example.test/stage"]
    assert "must-not-pass-to-public-metadata" not in str(result)


@pytest.mark.parametrize("environment,explicit,env_file,expected", [
    ("https://environment.example.test", None, ".env", "https://environment.example.test"),
    ("https://environment.example.test", "https://explicit.example.test", ".env", "https://explicit.example.test"),
    (None, None, "local.env", "https://custom.example.test"),
    (None, None, "missing.env", None),
    ("", None, ".env", None),
])
def test_metadata_url_precedence(tmp_path, monkeypatch, environment, explicit, env_file, expected):
    project_workspace(tmp_path)
    (tmp_path / ".env").write_text("SERVICE_ARCHITECT_API_URL=https://project.example.test\n", encoding="utf-8")
    (tmp_path / "local.env").write_text("SERVICE_ARCHITECT_API_URL=https://custom.example.test\n", encoding="utf-8")
    if environment is None:
        monkeypatch.delenv("SERVICE_ARCHITECT_API_URL", raising=False)
    else:
        monkeypatch.setenv("SERVICE_ARCHITECT_API_URL", environment)
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    requested = []

    def fake_fetch(base_url=None):
        requested.append(base_url)
        return matrix()

    monkeypatch.setattr(mcp_server, "fetch_capabilities", fake_fetch)
    result = mcp_server.refresh_capabilities(base_url=explicit, env_file=env_file)
    assert result["status"] == "success", result
    assert requested == [expected]


@pytest.mark.parametrize("env_file", ["../outside.env", "/outside.env", "nested\\outside.env", "bad\x00path"])
def test_metadata_env_path_is_confined_to_authoring_project(tmp_path, monkeypatch, env_file):
    project_workspace(tmp_path)
    monkeypatch.delenv("SERVICE_ARCHITECT_API_URL", raising=False)
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))

    def unexpected_fetch(*args, **kwargs):
        pytest.fail("metadata requested after an invalid env path")

    monkeypatch.setattr(mcp_server, "fetch_capabilities", unexpected_fetch)
    result = mcp_server.refresh_capabilities(env_file=env_file)
    assert result["status"] == "failed", result
    assert result["diagnostics"][0]["code"] == "SA_WORKSPACE_BOUNDARY_VIOLATION"


def test_metadata_does_not_follow_env_symlink_outside_authoring(tmp_path, monkeypatch):
    project = tmp_path / "authoring"
    project.mkdir()
    project_workspace(project)
    external = tmp_path / "outside.env"
    external.write_text("SERVICE_ARCHITECT_API_URL=https://outside.example.test\n", encoding="utf-8")
    alias = project / "linked.env"
    alias.symlink_to(external)
    monkeypatch.delenv("SERVICE_ARCHITECT_API_URL", raising=False)
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    result = mcp_server.refresh_validation_contract(project_path="authoring", env_file="linked.env")
    assert result["status"] == "failed", result
    assert result["diagnostics"][0]["code"] == "SA_WORKSPACE_BOUNDARY_VIOLATION"
