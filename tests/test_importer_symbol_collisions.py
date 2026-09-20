import unittest

import yaml

from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files


class ImporterSymbolCollisionTests(unittest.TestCase):
    def test_streams_do_not_shadow_types_or_normalized_stream_names(self):
        document = {
            'settings': {'name': 'Roundtrip'},
            'services': {'worker': {
                'name': 'Worker', 'programmingLanguage': 'GoLang',
                'modulePath': 'example.com/worker', 'golangVersion': '1.25.4',
                'defaultCallSemantics': 'FunctionCall',
                'pipelines': {'work': {
                    'entry': {'name': 'Entry', 'type': 'SubStream',
                              'source': 'result_stream', 'valueType': 'result'},
                    'result': {'name': 'Business: result', 'type': 'Map',
                               'source': 'entry', 'valueType': 'result', 'functionName': 'Convert'},
                    'resultStream': {'name': 'Business: intermediate', 'type': 'Map',
                                     'source': 'result', 'valueType': 'result', 'functionName': 'Prepare'},
                    'result_stream': {'name': 'Business: return', 'type': 'Map',
                                      'source': 'resultStream', 'valueType': 'result', 'functionName': 'Finish'},
                }},
                'links': {'resultStream_result_stream': {'from': 'resultStream', 'to': 'result_stream',
                                                   'callSemantics': 'FunctionCall', 'async': False}},
            }},
            'types': {
                'result': {'name': 'Result', 'type': 'string', 'useAlias': False},
                'resultStream': {'name': 'ResultStream', 'type': 'string', 'useAlias': False},
            },
        }
        # Function defaults are emitted by the typed API even when omitted in YAML.
        for stream in document['services']['worker']['pipelines']['work'].values():
            if 'functionName' in stream:
                for field in ('functionPackage', 'functionDescription', 'functionInitializerGroup'):
                    stream.setdefault(field, '')
        for default_semantics, asynchronous in (
            ('FunctionCall', None), ('FunctionCall', False), ('FunctionCall', True),
            ('ParallelCall', False),
        ):
            with self.subTest(default_semantics=default_semantics, asynchronous=asynchronous):
                worker = document['services']['worker']
                worker['defaultCallSemantics'] = default_semantics
                link = worker['links']['resultStream_result_stream']
                link.pop('async', None)
                if asynchronous is not None:
                    link['async'] = asynchronous
                generated = yaml_to_python_files(document, 'collision_roundtrip')
                restored = yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint))
                service = restored['services']['worker']
                self.assertEqual(document['services']['worker']['pipelines'], service['pipelines'])
                if default_semantics == 'FunctionCall' and not asynchronous:
                    self.assertFalse(service.get('links'))
                else:
                    self.assertEqual(worker['links'], service['links'])
                self.assertEqual(document['types'], restored['types'])
