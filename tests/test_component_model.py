import unittest
from sa_dsl import Appearance, Component, DslValidationError
from component_fixture import component_project


class ComponentModelTests(unittest.TestCase):
    def test_entity_concrete_fragments_and_optional_coordinates(self):
        project, service, fragments = component_project()
        component = service.component('Pricing')
        self.assertIsInstance(component, Component)
        for streams in fragments:
            component.fragment(*streams, appearance=Appearance(x=12))
        component.name = 'Reservations'
        metadata = service.to_document()['appearance']['components']
        self.assertEqual(metadata['version'], 2)
        self.assertNotIn('pipelines', metadata)
        self.assertEqual(metadata['groups']['reservations']['fragments'], [
            {'streams': [['create', 'createLoad'], ['create', 'createPrice']], 'position': {'x': 12}},
            {'streams': [['update', 'updateLoad'], ['update', 'updatePrice']], 'position': {'x': 12}},
        ])
        self.assertEqual(project.validate(), [])

    def test_no_components_preserves_document(self):
        _, service, _ = component_project()
        self.assertNotIn('components', service.to_document()['appearance'])

    def test_foreign_stream_rejected_at_creation_and_serialization(self):
        _, service, fragments = component_project()
        _, foreign, foreign_fragments = component_project()
        component = service.component('Pricing')
        with self.assertRaises(DslValidationError):
            component.fragment(*foreign_fragments[0])
        component.fragment(*fragments[0])
        fragments[0][0].service = foreign
        with self.assertRaises(DslValidationError):
            service.to_document()

    def test_detached_definition_cannot_register_members(self):
        _, service, fragments = component_project()
        component = Component('detached', 'Detached', service)
        with self.assertRaises(DslValidationError):
            component.fragment(*fragments[0])

    def test_overlap_and_nesting_are_rejected_atomically(self):
        _, service, fragments = component_project()
        first = service.component('Pricing')
        second = service.component('Nested')
        first.fragment(*fragments[0])
        with self.assertRaises(DslValidationError):
            first.fragment(*fragments[0])
        with self.assertRaises(DslValidationError):
            second.fragment(fragments[0][0])
        with self.assertRaises(DslValidationError):
            second.fragment(fragments[1][0], fragments[1][0])
        self.assertEqual(second.fragments, [])

    def test_removed_stream_is_rejected(self):
        _, service, fragments = component_project()
        component = service.component('Pricing')
        component.fragment(*fragments[0])
        stream = fragments[0][0]
        del stream.pipeline.streams[stream.key]
        with self.assertRaises(DslValidationError):
            service.to_document()

    def test_old_pipeline_group_api_is_not_silently_accepted(self):
        _, service, _ = component_project()
        component = service.component('Pricing')
        with self.assertRaises(TypeError):
            service.pipeline('Other', component=component)
        self.assertFalse(hasattr(component, 'pipeline'))


if __name__ == '__main__':
    unittest.main()
