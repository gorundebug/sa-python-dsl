"""Query is a separate request/result stream, with no completion port."""
import pytest
import yaml
from sa_dsl import Project, Golang, TypeScript, Python, Rust, CppUserver, CppCoro, Function, ServiceModule
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.code_generation import to_api_document

PROFILES = [
    ('postgresql_bun', Golang, 12),
    ('postgresql_kysely', TypeScript, 13),
    ('postgresql_sqlalchemy', Python, 14),
    ('postgresql_sqlx', Rust, 15),
    ('postgresql_userver', CppUserver, 16),
    ('postgresql_libpq', CppCoro, 17),
    ('s3_aws', Golang, 18), ('s3_aws', Python, 18),
    ('s3_aws', TypeScript, 18), ('s3_aws', Rust, 18),
    ('s3_aws', CppCoro, 18), ('s3_userver', CppUserver, 19),
]


def fixture(profile='postgresql_bun', language=Golang):
    project = Project('Storage queries')
    connector = getattr(project, profile + '_connector')('Storage')
    endpoint = connector.endpoint('Read data', function=Function('ReadData'),
                                  query_operation='GetObject' if profile.startswith('s3') else 'Rows')
    service = project.service('Worker', language=language(), module=ServiceModule('example.com/worker'))
    flow = service.pipeline('Load')
    text = project.string_type('Text')
    entry = flow.substream('Load request', value_type=text)
    query = flow.query('Query data', endpoint=endpoint, source=entry, value_type=text)
    query >> entry
    return project, connector, endpoint, query


@pytest.mark.parametrize('profile,language,connector_id', PROFILES)
def test_query_round_trip(profile, language, connector_id):
    project, _, _, _ = fixture(profile, language)
    assert not project.validate(), project.validate()
    document = project.to_document()
    imported = yaml_to_python_files(document, 'query_roundtrip')
    assert yaml.safe_load(python_files_to_yaml(imported.files, imported.entrypoint)) == document
    api = to_api_document(document)
    assert api['dataConnectors'][0]['type'] == connector_id
    queries = [stream for stream in api['streams'] if stream['type'] == 19]
    assert len(queries) == 1
    assert len(api['streams']) == 2  # request entry + Query; no completion node


@pytest.mark.parametrize('profile,operation', [
    ('postgresql_bun', 'Rows'), ('postgresql_bun', 'Execute'),
    *[('s3_aws', op) for op in ('GetObject', 'HeadObject', 'ListObjects', 'PutObject', 'DeleteObject')],
])
def test_operation_belongs_to_endpoint(profile, operation):
    project, _, endpoint, _ = fixture(profile)
    endpoint.properties['queryOperation'] = operation
    assert not project.validate(), project.validate()
    assert to_api_document(project.to_document())['endpoints'][0]['queryOperation'] == operation


@pytest.mark.parametrize('field,value', [('queryOperation', 'Unknown'), ('queryOperation', []), ('queryOperation', 'PutObject'),
                                         ('fetchSize', 0), ('fetchSize', True), ('fetchSize', 1.5)])
def test_invalid_postgres_operation_settings(field, value):
    project, _, endpoint, _ = fixture()
    endpoint.properties[field] = value
    assert project.validate()


def test_connector_library_limits_language():
    project, _, _, query = fixture()
    query.service.programming_language = 'TypeScript'
    assert any('PostgreSQLBun does not support TypeScript' in str(error) for error in project.validate())


def test_query_cannot_silently_become_sink():
    project, _, _, query = fixture()
    query.type = 'Sink'
    assert any('require Query' in str(error) for error in project.validate())


def test_query_requires_storage_endpoint_and_result_type():
    project, _, _, query = fixture()
    query.properties.pop('valueType')
    assert any('explicit result type' in str(error) for error in project.validate())
    query.endpoint = project.custom_connector('Custom').endpoint('Other', function=Function('Other'))
    assert any('Query requires a PostgreSQL or S3' in str(error) for error in project.validate())


@pytest.mark.parametrize('field,value', [('connectionsCount', 0), ('connectionsCount', True), ('connectTimeoutMs', -1), ('operationTimeoutMs', 2147483648)])
def test_postgres_pool_configuration_validation(field, value):
    project, connector, _, _ = fixture()
    connector.properties[field] = value
    assert any(field in str(error) for error in project.validate())


def test_postgres_timeout_configuration_round_trip():
    project, connector, _, _ = fixture()
    connector.properties.update(connectTimeoutMs=5000, operationTimeoutMs=30000)
    imported = yaml_to_python_files(project.to_document(), 'query_timeouts')
    assert yaml.safe_load(python_files_to_yaml(imported.files, imported.entrypoint)) == project.to_document()

@pytest.mark.parametrize('timeout', [0, 1000])
def test_userver_rejects_unsupported_connect_timeout(timeout):
    project, connector, _, _ = fixture('postgresql_userver', CppUserver)
    connector.properties['connectTimeoutMs'] = timeout
    assert any('must be omitted' in str(error) for error in project.validate())
    with pytest.raises(TypeError, match='connect_timeout_ms'):
        project.postgresql_userver_connector('Other', connect_timeout_ms=timeout)


def test_sqlx_requires_positive_connect_timeout():
    project, connector, _, _ = fixture('postgresql_sqlx', Rust)
    connector.properties['connectTimeoutMs'] = 0
    assert any('connectTimeoutMs' in str(error) for error in project.validate())

@pytest.mark.parametrize('style', [True, 'true', 1])
def test_userver_rejects_unsupported_path_style(style):
    project, connector, _, _ = fixture('s3_userver', CppUserver)
    connector.properties['forcePathStyle'] = style
    assert any('forcePathStyle' in str(error) for error in project.validate())


def test_aws_path_style_remains_supported():
    project, connector, _, _ = fixture('s3_aws', Golang)
    connector.properties['forcePathStyle'] = True
    assert not project.validate()
