"""New-project discovery reaches guidance over MCP without executing user code."""
import asyncio
import json
import re
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_guidance_is_discoverable_from_handshake_project_and_object(tmp_path):
    marker = tmp_path / 'executed'
    (tmp_path / 'architecture.py').write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('must not execute')\n"
    )
    manifest = tmp_path / '.service-architect/project.yaml'
    manifest.parent.mkdir()
    manifest.write_text('''version: 1
project:
  name: New project
authoring:
  mode: python
  entrypoint: architecture:project
canonical:
  output: build/project.yaml
generation:
  targets: [go]
''')

    async def run():
        server = StdioServerParameters(command=sys.executable,
            args=['-m', 'sa_dsl.mcp_server', '--workspace', str(tmp_path)])
        async with asyncio.timeout(30):
            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    uris = set(re.findall(r'servicegen://authoring/[a-z-]+', initialized.instructions or ''))
                    assert 'servicegen://authoring/implementation-guidelines' in uris
                    documents = {}
                    for uri in uris:
                        result = await session.read_resource(uri)
                        assert len(result.contents) == 1
                        document = json.loads(result.contents[0].text)
                        assert document['resource'] == uri and document.get('status') != 'not_found'
                        documents[uri] = document

                    def payload(result):
                        assert not result.is_error
                        return result.structured_content or json.loads(result.content[0].text)

                    project = payload(await session.call_tool('inspect_project', {'project_path': '.'}))
                    assert set(project['guidance'].values()) == uris
                    for kind in ['index', 'pipeline', 'input', 'sink', 'substream', 'type']:
                        guide = payload(await session.call_tool('describe_architecture_object', {'kind': kind}))
                        assert guide['guidance'] == project['guidance']

                    index = json.loads((await session.read_resource('servicegen://authoring/index')).contents[0].text)
                    assert uris <= set(index['resources'])
                    implementation = documents[project['guidance']['implementation']]
                    assert implementation['modelingResource'] in documents
                    assert implementation['reviewResource'] in documents
                    assert not marker.exists()

    asyncio.run(run())
