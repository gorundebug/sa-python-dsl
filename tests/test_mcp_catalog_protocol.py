"""Exercise catalogue resources over the real MCP stdio transport."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_catalogues_are_readable_without_executing_project_python(tmp_path):
    (tmp_path / "architecture.py").write_text(
        "raise RuntimeError('catalogue discovery must not execute project code')\n",
        encoding="utf-8",
    )

    async def run():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "sa_dsl.mcp_server", "--workspace", str(tmp_path)],
        )
        async with asyncio.timeout(30):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    async def resource(uri):
                        response = await session.read_resource(uri)
                        assert len(response.contents) == 1
                        document = json.loads(response.contents[0].text)
                        assert document["resource"] == uri
                        return document

                    objects = await resource("servicegen://authoring/object-index")
                    assert len(objects["objects"]) >= 30
                    for item in objects["objects"]:
                        guide = await resource(item["resource"])
                        assert guide["purpose"] == item["purpose"]

                    index = await resource("servicegen://patterns/index")
                    assert len(index["topics"]) == 10
                    for name in index["topics"]:
                        recipe = await resource("servicegen://patterns/" + name)
                        assert recipe["example"]["language"] == "python"
                        assert recipe["example"]["entrypoint"] == "architecture:project"
                        assert recipe["example"]["code"]
                        assert len(recipe["contracts"]) == 6
                        assert recipe["useWhen"] and recipe["avoidWhen"]
                        assert recipe["capabilitiesResource"] == "servicegen://workspace/current/capabilities"
                        assert recipe["validationContractResource"] == "servicegen://workspace/current/validation-contract"

    asyncio.run(run())
