import unittest

from sa_dsl import Appearance, Component, DslValidationError, Service


class ComponentModelTests(unittest.TestCase):
    def service(self, name="booking"):
        return Service(name, name, "Go", "example.com/" + name)

    def test_entity_and_optional_properties(self):
        service = self.service()
        component = service.component("Booking", key="stable", appearance=Appearance(x=12))
        self.assertIsInstance(component, Component)
        pipeline = component.pipeline("reserve")
        self.assertIs(pipeline.component, component)
        component.name = "Reservations"
        metadata = service.to_document()["appearance"]["components"]
        self.assertEqual(metadata, {"version": 1, "groups": {
            "stable": {"name": "Reservations", "position": {"x": 12}}},
            "pipelines": {"reserve": "stable"}})

    def test_no_components_keeps_legacy_document(self):
        self.assertNotIn("components", self.service().to_document()["appearance"])

    def test_foreign_component_rejected_at_creation_and_serialization(self):
        service = self.service()
        foreign = self.service("inventory").component("Inventory")
        with self.assertRaises(DslValidationError):
            service.pipeline("reserve", component=foreign)
        pipeline = service.pipeline("reserve")
        pipeline.component = foreign
        with self.assertRaises(DslValidationError):
            service.to_document()

    def test_unregistered_component_rejected(self):
        service = self.service()
        component = Component("detached", "Detached", service)
        with self.assertRaises(DslValidationError):
            service.pipeline("reserve", component=component)


if __name__ == "__main__":
    unittest.main()
