import unittest

from sa_dsl import DslValidationError, Service


class ComponentIdentityTests(unittest.TestCase):
    def test_visual_identity_is_not_a_runtime_graph_key(self):
        service = Service("booking", "Booking", "Go", "example.com/booking")
        component = service.component("Reservations", key="original-identity")
        component.pipeline("reserve")
        component.name = "Renamed"
        metadata = service.to_document()["appearance"]["components"]
        self.assertEqual(metadata["pipelines"]["reserve"], "original-identity")
        self.assertEqual(metadata["groups"]["original-identity"]["name"], "Renamed")

    def test_empty_and_non_string_identities_are_rejected(self):
        for identity in ("", "  ", 1, False):
            with self.subTest(identity=identity), self.assertRaises(DslValidationError):
                Service("booking", "Booking", "Go", "example.com/booking").component("Booking", key=identity)
