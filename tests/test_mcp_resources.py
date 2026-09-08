import json
import tempfile
import unittest
from pathlib import Path

import yaml

from sa_dsl.mcp_resources import catalog_resource
from sa_dsl.mcp_server import configure_workspace, workspace_dsl_resource, workspace_source_resource


class McpResourcesTest(unittest.TestCase):
    def test_catalog_resources_are_focused_and_versioned(self) -> None:
        operators = json.loads(catalog_resource("semantics", "operators"))
        self.assertEqual("1.0", operators["schemaVersion"])
        self.assertIn("MultiJoin", operators["operators"])
        with self.assertRaisesRegex(ValueError, "available"):
            catalog_resource("semantics", "missing")

    def test_workspace_resources_do_not_execute_python(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-resource-") as temporary:
            workspace = Path(temporary)
            marker = workspace / "executed.marker"
            (workspace / "architecture.py").write_text(
                "from pathlib import Path\nPath('executed.marker').write_text('executed')\n",
                encoding="utf-8",
            )
            manifest = workspace / ".service-architect/project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(yaml.safe_dump({
                "version": 1,
                "project": {"name": "Resources"},
                "authoring": {"mode": "python", "entrypoint": "architecture:project"},
                "canonical": {"output": ".service-architect/build/architecture.yaml"},
                "generation": {"targets": ["go"]},
            }, sort_keys=False), encoding="utf-8")
            canonical = workspace / ".service-architect/build/architecture.yaml"
            canonical.parent.mkdir()
            canonical.write_text("settings:\n  name: Resources\n", encoding="utf-8")
            configure_workspace(workspace)

            source = json.loads(workspace_source_resource())
            rendered = workspace_dsl_resource()

            self.assertEqual("Resources", source["project"]["name"])
            self.assertIn("name: Resources", rendered)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
