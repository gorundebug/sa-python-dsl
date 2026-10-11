import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.test_generation_transaction import project_workspace
from tests.test_mcp_endpoint_authoring import _call
from tests.test_servicegen_capabilities import matrix
from tests.test_servicegen_validation import contract


def test_public_metadata_refresh_cache_and_resources_over_stdio(tmp_path):
    project_workspace(tmp_path)
    secret = "mcp-metadata-must-not-send-this-test-secret"
    (tmp_path / ".env").write_text("SERVICE_ARCHITECT_API_KEY=" + secret + "\n", encoding="utf-8")
    state = {
        "/v1/capabilities": matrix(),
        "/v1/validation-contract": contract(capability_revision="sha256:abc"),
    }
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, dict(self.headers.items())))
            payload = state.get(self.path)
            if payload is None:
                self.send_error(404)
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = "http://127.0.0.1:" + str(server.server_port)
    (tmp_path / ".env").write_text(
        "SERVICE_ARCHITECT_API_KEY=" + secret + "\nSERVICE_ARCHITECT_API_URL=" + base_url + "\n",
        encoding="utf-8",
    )

    async def run():
        process = StdioServerParameters(
            command=sys.executable,
            args=["-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path)],
            env={"SERVICE_ARCHITECT_API_KEY": secret, "SERVICE_ARCHITECT_ID_TOKEN": secret},
        )
        async with asyncio.timeout(30):
            async with stdio_client(process) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    async def resource(uri):
                        response = await session.read_resource(uri)
                        text = response.contents[0].text
                        assert secret not in text
                        return json.loads(text)

                    for name in ("refresh_capabilities", "refresh_validation_contract"):
                        result = await _call(session, name, {"project_path": "."})
                        assert result["status"] == "success", result
                        assert secret not in json.dumps(result)

                    capabilities = await resource("servicegen://workspace/current/capabilities")
                    validation = await resource("servicegen://workspace/current/validation-contract")
                    assert capabilities["revision"] == "sha256:abc"
                    assert validation["revision"] == "sha256:rules"
                    language = await resource("servicegen://capabilities/golang")
                    assert "golang" in json.dumps(language)
                    rule = await resource("servicegen://validation/rules/SG_SEMANTIC_TYPE_MISMATCH")
                    assert "Align the wire types." in json.dumps(rule)

                    state["/v1/capabilities"] = matrix(schema="2.0")
                    rejected = await _call(session, "refresh_capabilities", {"base_url": base_url})
                    assert rejected["status"] == "failed", rejected
                    assert await resource("servicegen://workspace/current/capabilities") == capabilities

                    invalid = contract(capability_revision="sha256:abc")
                    invalid["diagnostics"][0]["evaluation"] = "python"
                    state["/v1/validation-contract"] = invalid
                    rejected = await _call(session, "refresh_validation_contract", {"base_url": base_url})
                    assert rejected["status"] == "failed", rejected
                    assert await resource("servicegen://workspace/current/validation-contract") == validation

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert len(requests) == 4
    for path, headers in requests:
        assert path in state
        assert secret not in json.dumps(headers)
        assert not {name.lower() for name in headers} & {"authorization", "x-service-architect-key"}
