#!/usr/bin/env python3
"""Verify the exact Service Architect MCP revision shipped by the plugin."""

from __future__ import annotations

import argparse
import anyio
import json
from pathlib import Path
import re
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_CONFIG = ROOT / "plugins" / "service-architect" / ".mcp.json"
PIN_PATTERN = re.compile(r"^git\+https://[^@]+@[0-9a-f]{40}$")


def pinned_source() -> str:
    config = json.loads(PLUGIN_CONFIG.read_text(encoding="utf-8"))

    def strings(value: object):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)

    matches = [value for value in strings(config) if value.startswith("git+")]
    if len(matches) != 1 or not PIN_PATTERN.fullmatch(matches[0]):
        raise RuntimeError("plugin config must contain one immutable git source")
    return matches[0]


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


async def verify_mcp(source: str) -> None:
    parameters = StdioServerParameters(
        command="uvx",
        args=[
            "--refresh",
            "--from",
            source,
            "sa-dsl-mcp",
            "--workspace",
            str(ROOT / "examples" / "processorder"),
        ],
    )
    with anyio.fail_after(60):
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                resources = await session.list_resources()

    tool_names = {tool.name for tool in tools.tools}
    required = {
        "apply_generation",
        "designer_view",
        "doctor",
        "export_project",
        "generate_project",
        "import_yaml_project",
        "inspect_business_tasks",
        "inspect_project",
        "preview_architecture_diff",
        "preview_generation",
        "refresh_capabilities",
        "run_verification",
        "validate_project",
    }
    missing = sorted(required - tool_names)
    if missing:
        raise RuntimeError(f"installed MCP server is missing tools: {missing}")
    if len(resources.resources) < 7:
        raise RuntimeError("installed MCP server did not expose expected resources")
    print(
        f"MCP conformance passed: {len(tool_names)} tools, "
        f"{len(resources.resources)} resources"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    source = pinned_source()
    print(f"Pinned source: {source}")
    if not args.skip_tests:
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    run(["uvx", "--refresh", "--from", source, "sa-dsl", "--help"])
    anyio.run(verify_mcp, source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
