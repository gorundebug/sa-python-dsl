import unittest

from sa_dsl import DslValidationError, Service


class ComponentIdentityTests(unittest.TestCase):
    def test_output_identity_follows_name_like_other_graph_entities(self):
        service = Service('booking', 'Booking', 'Go', 'example.com/booking')
        component = service.component('Reservations')
        component.pipeline('reserve')
        component.name = 'Renamed'
        metadata = service.to_document()['appearance']['components']
        self.assertEqual(metadata['pipelines']['reserve'], 'renamed')
        self.assertEqual(metadata['groups']['renamed']['name'], 'Renamed')

    def test_key_is_not_part_of_component_factory(self):
        with self.assertRaises(TypeError):
            Service('booking', 'Booking', 'Go', 'example.com/booking').component('Booking', key='anything')

    def test_invalid_names_are_rejected(self):
        for name in ('', '123', 'Invalid!'):
            with self.subTest(name=name), self.assertRaises(DslValidationError):
                Service('booking', 'Booking', 'Go', 'example.com/booking').component(name)
