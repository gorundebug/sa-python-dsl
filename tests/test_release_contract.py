import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTest(unittest.TestCase):
    def test_plugin_uses_immutable_server_commit(self) -> None:
        config = json.loads(
            (ROOT / "plugins/service-architect/.mcp.json").read_text(encoding="utf-8")
        )
        source = config["mcpServers"]["service-architect"]["args"][1]
        revision = source.rsplit("@", 1)[-1]
        self.assertRegex(revision, re.compile(r"^[0-9a-f]{40}$"))

    def test_direct_runtime_dependencies_are_exactly_pinned(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"mcp==2.1.1"', pyproject)
        self.assertIn('"PyYAML==6.0.3"', pyproject)
        self.assertNotRegex(pyproject, r'"(?:mcp|PyYAML)[><~]')


if __name__ == "__main__":
    unittest.main()
