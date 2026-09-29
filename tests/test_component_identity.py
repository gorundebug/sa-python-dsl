import unittest

from sa_dsl import DslValidationError, Service


class ComponentIdentityTests(unittest.TestCase):
    def test_output_identity_follows_name_like_other_graph_entities(self):
        service = Service('booking', 'Booking', 'Go', 'example.com/booking')
        component = service.component('Reservations')
        service.pipeline('reserve')
        component.name = 'Renamed'
        metadata = service.to_document()['appearance']['components']
        self.assertNotIn('pipelines', metadata)
        self.assertEqual(metadata['groups']['renamed']['name'], 'Renamed')

    def test_key_is_not_part_of_component_factory(self):
        with self.assertRaises(TypeError):
            Service('booking', 'Booking', 'Go', 'example.com/booking').component('Booking', key='anything')

    def test_empty_name_is_rejected(self):
        with self.assertRaises(DslValidationError):
            Service('booking', 'Booking', 'Go', 'example.com/booking').component('')

    def test_display_names_use_the_same_identifier_rules_as_pipelines(self):
        for name, key in (('123', '_123'), ('Invalid!', 'invalid')):
            with self.subTest(name=name):
                service = Service('booking', 'Booking', 'Go', 'example.com/booking')
                component = service.component(name)
                self.assertEqual(component.name, name)
                self.assertEqual(component.key, key)
                self.assertEqual(component.key, service.pipeline(name).key)

    def test_normalized_component_keys_must_remain_unique(self):
        service = Service('booking', 'Booking', 'Go', 'example.com/booking')
        service.component('Invalid!')
        with self.assertRaises(DslValidationError):
            service.component('Invalid')
