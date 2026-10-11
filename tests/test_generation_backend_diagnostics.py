import asyncio
import copy
import io
import json
import sys
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sa_dsl import CodeGenerationError, Project, ServiceArchitectClient
from sa_dsl.generation import generate_project_archive
from sa_dsl.generation_transaction import preview_generation_transaction
from tests.test_code_generation import FakeResponse
from tests.test_generation_transaction import project_workspace
from tests.test_mcp_endpoint_authoring import _call
from tests.test_servicegen_validation import contract


DIAGNOSTIC = {
    "code": "SG_SEMANTIC_TYPE_MISMATCH",
    "severity": "error",
    "stage": "semantic",
    "message": "Connected stream types differ",
    "source": {
        "uri": "request://generateCode",
        "path": "$.services.orders.pipelines.default.calculate",
        "range": {"start": {"line": 12, "column": 3}},
    },
    "details": {"actualType": "Order", "expectedType": "Quote"},
}
PROBLEM = {
    "type": "https://gorundebug.com/problems/servicegen-operation-failed",
    "status": 422,
    "title": "ServiceGen operation failed",
    "detail": "Resolve the returned diagnostics before generation.",
    "diagnostics": [DIAGNOSTIC],
}
EXPECTED = {**DIAGNOSTIC, "path": DIAGNOSTIC["source"]["path"]}


@pytest.mark.parametrize("wrapper", [
    lambda value: value,
    lambda value: {"statusCode": 422, "body": json.dumps(value)},
    lambda value: {"problem": value},
    lambda value: {"job": {"error": value}},
])
def test_error_preserves_structured_backend_diagnostics(wrapper):
    original = copy.deepcopy(PROBLEM)
    error = CodeGenerationError("rejected", details=wrapper(original))
    assert error.diagnostics == (EXPECTED,)
    error.diagnostics[0]["validationRuleUri"] = "servicegen://validation/rules/SG_SEMANTIC_TYPE_MISMATCH"
    assert original == PROBLEM


@pytest.mark.parametrize("details", [
    None, "not JSON", [], {"diagnostics": "invalid"},
    {"diagnostics": [None, {}, {"code": "SG_INVALID", "message": None}]},
    {"diagnostics": [{"code": "not a rule URI", "message": "bad"}]},
])
def test_malformed_backend_diagnostics_leave_generic_error_available(details):
    error = CodeGenerationError("original failure", details=details)
    assert error.diagnostics == ()
    assert str(error) == "original failure"


@pytest.mark.parametrize("transport", ["http-error", "http-status", "legacy-envelope", "failed-job"])
def test_client_keeps_diagnostics_across_response_formats(transport):
    def opener(request, *, timeout):
        if transport == "http-error":
            raise urllib.error.HTTPError(request.full_url, 422, "Unprocessable Entity", {}, io.BytesIO(json.dumps(PROBLEM).encode()))
        if transport == "http-status":
            return FakeResponse(PROBLEM, status=422)
        if transport == "legacy-envelope":
            return FakeResponse({"statusCode": 422, "body": json.dumps(PROBLEM)})
        return FakeResponse({
            "job": {"id": "test-job", "status": "FAILED", "errorCode": "INVALID_ARCHITECTURE", "diagnostics": [DIAGNOSTIC]},
            "statusUrl": "/v1/generation-jobs/test-job",
        }, status=202)

    credentials = {"id_token": "test-token"} if transport == "legacy-envelope" else {"api_key": "test-key"}
    client = ServiceArchitectClient(**credentials, opener=opener)
    with pytest.raises(CodeGenerationError) as raised:
        client.generate_code(Project("Example"))
    assert raised.value.diagnostics == (EXPECTED,)
    if transport != "failed-job":
        assert str(raised.value) == PROBLEM["detail"]


@pytest.mark.parametrize("structured", [True, False])
def test_generation_and_preview_keep_backend_diagnostics(tmp_path, monkeypatch, structured):
    manifest = project_workspace(tmp_path)
    client = ServiceArchitectClient(
        api_key="test-key",
        opener=lambda request, **kwargs: FakeResponse(PROBLEM if structured else {"message": "offline"}, status=422),
    )
    monkeypatch.setattr(ServiceArchitectClient, "from_env", lambda *args, **kwargs: client)
    generated = generate_project_archive(manifest).to_payload()
    preview = preview_generation_transaction(manifest, client_factory=lambda _: client)
    for payload, fallback in ((generated, "SA_CODE_GENERATION_FAILED"), (preview, "SA_GENERATION_PREVIEW_FAILED")):
        assert payload["status"] == "failed"
        if structured:
            assert payload["diagnostics"] == [EXPECTED]
        else:
            assert payload["diagnostics"][0]["code"] == fallback
            assert payload["diagnostics"][0]["message"] == "offline"
    assert not (tmp_path / "dist").exists()
    assert not (tmp_path / ".service-architect/previews").exists()


def test_mcp_generation_errors_include_cached_remediation_over_http_and_stdio(tmp_path):
    project_workspace(tmp_path)
    key = "local-fixture-key-must-not-appear-in-diagnostics"
    validation = contract()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, value, status):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            requests.append(("GET", self.path))
            assert self.path == "/v1/validation-contract"
            assert self.headers.get("X-Service-Architect-Key") is None
            self.respond(validation, 200)

        def do_POST(self):
            requests.append(("POST", self.path))
            assert self.path == "/v1/generation-jobs"
            assert self.headers.get("X-Service-Architect-Key") == key
            self.rfile.read(int(self.headers["Content-Length"]))
            self.respond(PROBLEM, 422)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    (tmp_path / ".env").write_text(
        f"SERVICE_ARCHITECT_API_KEY={key}\nSERVICE_ARCHITECT_API_URL=http://127.0.0.1:{server.server_port}\n"
    )

    async def exercise():
        params = StdioServerParameters(command=sys.executable, args=["-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path)])
        async with asyncio.timeout(30):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    refreshed = await _call(session, "refresh_validation_contract", {})
                    assert refreshed["status"] == "success", refreshed
                    for name in ("generate_project", "preview_generation"):
                        result = await _call(session, name, {})
                        assert result["status"] == "failed", result
                        diagnostic = result["diagnostics"][0]
                        for field, value in EXPECTED.items():
                            assert diagnostic[field] == value
                        assert diagnostic["validationRuleUri"] == "servicegen://validation/rules/SG_SEMANTIC_TYPE_MISMATCH"
                        assert diagnostic["validationRule"]["contractRevision"] == validation["revision"]
                        assert diagnostic["validationRule"]["remediation"] == "Align the wire types."
                        assert key not in json.dumps(result)

    try:
        asyncio.run(exercise())
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert requests == [("GET", "/v1/validation-contract"), ("POST", "/v1/generation-jobs"), ("POST", "/v1/generation-jobs")]
