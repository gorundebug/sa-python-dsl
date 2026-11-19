import runpy
import unittest
from pathlib import Path
from sa_dsl.code_generation import to_api_document

class StorageQueryExampleTests(unittest.TestCase):
    def test_all_targets_export_independent_operations_and_timeouts(self):
        source = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'examples/storage-query/project.py'))
        for target in source['TARGETS']:
            with self.subTest(target=target):
                project = source['build_project'](target)
                self.assertEqual([], project.validate())
                document = to_api_document(project.to_document())
                returning = next(e for e in document['endpoints'] if e['name'] == 'Returning')
                self.assertEqual('Rows', returning['queryOperation'])
                self.assertEqual({'Rows', 'Execute', 'GetObject', 'HeadObject', 'ListObjects', 'PutObject', 'DeleteObject'},
                                 {endpoint['queryOperation'] for endpoint in document['endpoints']})
                for kind in (18, 19, 15):
                    self.assertEqual(8, sum(stream['type'] == kind for stream in document['streams']))
                postgres = next(c for c in document['dataConnectors'] if c['name'] == 'Database')
                if target == 'cpp-userver':
                    self.assertNotIn('connectTimeoutMs', postgres)
                else:
                    self.assertEqual(1000, postgres['connectTimeoutMs'])
                self.assertEqual(2000, postgres['operationTimeoutMs'])
                self.assertNotIn('connectionString', postgres)

    def test_userver_fetch_size_matches_native_uint32(self):
        from types import SimpleNamespace
        from sa_dsl.query_validation import validate_query_bindings
        endpoint = SimpleNamespace(connector=SimpleNamespace(type='PostgreSQLUserver'),
                                   properties={'queryOperation': 'Rows', 'fetchSize': 4294967296})
        stream = SimpleNamespace(type='Query', endpoint=endpoint,
                                 service=SimpleNamespace(programming_language='CppUserver'),
                                 properties={'valueType': 'result'})
        self.assertIn('uint32', str(validate_query_bindings(stream)))
        endpoint.properties['fetchSize'] = 4294967295
        self.assertEqual([], validate_query_bindings(stream))
