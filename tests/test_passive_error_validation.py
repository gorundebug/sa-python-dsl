import unittest

from sa_dsl import Function, Project
from sa_dsl.model import Service
from sa_dsl.validation import RANGE, Validator


class PassiveErrorValidationTests(unittest.TestCase):
    def test_error_rejects_function_object_and_serialized_metadata(self):
        for metadata_only in (False, True):
            with self.subTest(metadata_only=metadata_only):
                project = Project('Error Contract')
                service = Service('worker', 'Worker', 'GoLang', 'example.com/worker')
                project.services[service.key] = service
                pipeline = service.pipeline('Work')
                failure = pipeline.error('Failure', value_type=project.error_type('FailureValue'))
                if metadata_only:
                    failure.properties['functionName'] = 'CaptureFailure'
                else:
                    failure.function = Function('CaptureFailure')
                validator = Validator(project)
                validator.validate_streams()
                errors = [d for d in validator.values
                          if d.code == RANGE and d.path.endswith('.functionName')]
                self.assertEqual(1, len(errors))
                self.assertIn('following Map', errors[0].message)

    def test_passive_error_does_not_report_function_diagnostic(self):
        project = Project('Error Contract')
        service = Service('worker', 'Worker', 'GoLang', 'example.com/worker')
        project.services[service.key] = service
        service.pipeline('Work').error('Failure', value_type=project.error_type('FailureValue'))
        validator = Validator(project)
        validator.validate_streams()
        self.assertFalse(any(d.path.endswith('.functionName') for d in validator.values))
