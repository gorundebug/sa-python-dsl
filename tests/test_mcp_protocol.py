import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def tool_payload(result) -> dict:
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError("MCP tool returned no structured or JSON text content")


class McpProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_discovery_workspace_boundary_and_designer_view(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-dsl-mcp-") as temporary:
            workspace = Path(temporary)
            (workspace / "architecture.py").write_text(
                "from sa_dsl import Project\nproject = Project('Protocol Test')\n",
                encoding="utf-8",
            )
            manifest = workspace / ".service-architect" / "project.yaml"
            manifest.parent.mkdir()
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "version": 1,
                        "project": {"name": "Protocol Test"},
                        "authoring": {"mode": "python", "entrypoint": "architecture:project"},
                        "canonical": {"output": ".service-architect/build/architecture.yaml"},
                        "generation": {"targets": ["go"]},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "sa_dsl.mcp_server", "--workspace", str(workspace)],
                cwd=workspace,
            )

            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    self.assertEqual(
                        {
                            "inspect_project",
                            "validate_project",
                            "export_project",
                            "generate_project",
                            "preview_generation",
                            "apply_generation",
                            "import_yaml_project",
                            "preview_architecture_diff",
                            "designer_view",
                        },
                        {tool.name for tool in tools.tools},
                    )
                    designer_tool = next(
                        tool for tool in tools.tools if tool.name == "designer_view"
                    )
                    self.assertEqual(
                        "ui://service-architect/designer",
                        designer_tool.meta["ui"]["resourceUri"],
                    )

                    resources = await session.list_resources()
                    designer_resource = next(
                        resource
                        for resource in resources.resources
                        if str(resource.uri) == "ui://service-architect/designer"
                    )
                    self.assertEqual("text/html;profile=mcp-app", designer_resource.mime_type)
                    self.assertIn("resourceDomains", designer_resource.meta["ui"]["csp"])
                    ui = await session.read_resource("ui://service-architect/designer")
                    self.assertIn("/mcp-ui/0.1.0/designer.js", ui.contents[0].text)

                    inspected = tool_payload(await session.call_tool("inspect_project", {"project_path": "."}))
                    self.assertEqual("Protocol Test", inspected["project"]["name"])

                    preview = tool_payload(
                        await session.call_tool(
                            "preview_architecture_diff", {"project_path": "."}
                        )
                    )
                    self.assertEqual("success", preview["status"])
                    self.assertFalse(preview["preview"]["hasBaseline"])
                    self.assertTrue(
                        preview["preview"]["candidateRevision"].startswith("sha256:")
                    )
                    self.assertFalse(
                        (workspace / ".service-architect/build/architecture.yaml").exists()
                    )

                    rejected = tool_payload(await session.call_tool("inspect_project", {"project_path": "../outside"}))
                    self.assertEqual("failed", rejected["status"])
                    self.assertEqual(
                        "SA_WORKSPACE_BOUNDARY_VIOLATION",
                        rejected["diagnostics"][0]["code"],
                    )

                    view = tool_payload(await session.call_tool("designer_view", {"project_path": "."}))
                    self.assertEqual("success", view["status"])
                    self.assertEqual("read-only", view["snapshot"]["mode"])
                    self.assertTrue(view["snapshot"]["revision"].startswith("sha256:"))
                    self.assertTrue(view["ui"]["fallbackUrl"].startswith("http://127.0.0.1:"))


if __name__ == "__main__":
    unittest.main()
