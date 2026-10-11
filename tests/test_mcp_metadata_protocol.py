import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.test_generation_transaction import project_workspace


def test_all_indexed_metadata_resources_are_readable_without_project_execution(tmp_path):
    project_workspace(tmp_path)
    executed = tmp_path / "authoring-was-executed"
    (tmp_path / "architecture.py").write_text(
        "from pathlib import Path\n"
        + f"Path({str(executed)!r}).touch()\n"
        + "raise RuntimeError('metadata must not execute authoring')\n",
        encoding="utf-8",
    )

    async def run():
        server = StdioServerParameters(command=sys.executable, args=[
            "-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path),
        ])
        async with asyncio.timeout(30):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    visited = set()
                    for category in ("semantics", "authoring", "schema", "examples"):
                        base = "servicegen://" + category + "/"
                        index = await session.read_resource(base + "index")
                        catalogue = json.loads(index.contents[0].text)
                        assert catalogue["resources"]
                        assert catalogue["resources"] == [base + topic for topic in catalogue["topics"]]
                        for uri in catalogue["resources"]:
                            resource = await session.read_resource(uri)
                            document = json.loads(resource.contents[0].text)
                            assert document["resource"] == uri
                            assert document["schemaVersion"] == "1.0"
                            assert document.get("status") != "failed", document
                            visited.add(uri)
                    assert "servicegen://schema/manifest" in visited
                    assert "servicegen://schema/dsl" in visited
                    assert "servicegen://examples/http-grpc" in visited
                    assert "servicegen://authoring/typed-api-Project-struct_type" in visited
                    assert "servicegen://authoring/typed-api-TemporalConnector-workflow" in visited
        return len(visited)

    count = asyncio.run(run())
    assert count >= 100
    assert not executed.exists()
