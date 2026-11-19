"""Storage authoring through the stdio tools used by agents."""
import asyncio
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sa_dsl.code_generation import to_api_document
from tests.test_generation_transaction import project_workspace
from tests.test_mcp_endpoint_authoring import _call
from tests.test_query_authoring import PROFILES


CASES = [
    (profile, language.__name__, connector_id, operation)
    for profile, language, connector_id in PROFILES
    for operation in (('Rows', 'Execute') if profile.startswith('postgresql_') else
                      ('GetObject', 'HeadObject', 'ListObjects', 'PutObject', 'DeleteObject'))
]


@pytest.mark.parametrize('profile,language,connector_id,operation', CASES)
def test_query_preview_apply_preserves_distinct_ports(tmp_path, profile, language, connector_id, operation):
    project_workspace(tmp_path)
    source = f'''from sa_dsl import Project, {language}, Function, ServiceModule
project = Project("Example")
request_type = project.string_type("Request")
result_type = project.string_type("Result")
error_type = project.error_type("Failure")
storage = project.{profile}_connector("Storage")
service = project.service("Worker", language={language}(), module=ServiceModule("example.com/worker"))
flow = service.pipeline("Read storage")
# Preserve this user-owned explanation.
'''
    path = tmp_path / 'architecture.py'
    path.write_text(source)
    operations = [
        dict(kind='add_endpoint', receiver='storage', factory='endpoint', symbol='endpoint', name='Read',
             arguments=dict(function="Function('Read')", query_operation=repr(operation))),
        dict(kind='add_node', receiver='flow', factory='substream', symbol='entry', name='Request',
             arguments=dict(value_type='request_type')),
        dict(kind='add_node', receiver='flow', factory='query', symbol='query', name='Storage operation',
             arguments=dict(endpoint='endpoint', source='entry', value_type='result_type')),
        dict(kind='add_node', receiver='flow', factory='error', symbol='failure', name='Failure',
             arguments=dict(value_type='error_type')),
        dict(kind='connect_ports', source='query', target='failure', role='error'),
        dict(kind='connect_ports', source='query', target='entry', role='data'),
    ]

    async def run():
        server = StdioServerParameters(command=sys.executable, args=[
            '-m', 'sa_dsl.mcp_server', '--workspace', str(tmp_path)])
        async with asyncio.timeout(30):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    inspected = await _call(session, 'inspect_python_authoring', {'source_file': 'architecture.py'})
                    prepared = await _call(session, 'preview_python_changes', dict(
                        source_file='architecture.py', source_revision=inspected['sourceRevision'],
                        before_line=len(source.splitlines()) + 1, operations=operations))
                    assert prepared['status'] == 'success', str(prepared)
                    preview = prepared.get('preview', prepared)
                    assert preview['architectureDiff']['summary']['total'] > 0
                    assert path.read_text() == source
                    applied = await _call(session, 'apply_python_changes', dict(
                        preview_id=preview['previewId'], preview_revision=preview['previewRevision']))
                    assert applied['status'] == 'success', applied
                    assert path.read_text().startswith(source)
                    for tool in ('validate_project', 'export_project'):
                        result = await _call(session, tool, {'project_path': '.'})
                        assert result['status'] == 'success', result

    asyncio.run(run())
    namespace = {}
    # Execute only the test-owned model authored above.
    exec(compile(path.read_text(), str(path), 'exec'), namespace)
    api = to_api_document(namespace['project'].to_document())
    assert len(api['streams']) == 3  # No hidden completion node.
    assert {node['type'] for node in api['streams']} == {18, 19, 15}
    assert {node['valueType'] for node in api['streams']} == {'Request', 'Result', 'Failure'}
    assert api['endpoints'][0]['queryOperation'] == operation
    assert api['dataConnectors'][0]['type'] == connector_id
    entry = next(node for node in api['streams'] if node['type'] == 18)
    query = next(node for node in api['streams'] if node['type'] == 19)
    failure = next(node for node in api['streams'] if node['type'] == 15)
    assert query['idSource'] == entry['id']
    assert entry['idSource'] == query['id']
    assert failure['idSource'] == query['id']
    assert query['idEndpoint'] == api['endpoints'][0]['id']
