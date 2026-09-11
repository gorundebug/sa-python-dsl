import unittest

from sa_dsl.visual_components import normalize_components, without_visual_components


def metadata():
    return {"version": 1, "groups": {"booking": {"name": "Booking", "position": {"x": 10}}},
            "pipelines": {"validate": "booking", "reserve": "booking"}}


class VisualComponentsTest(unittest.TestCase):
    def test_membership_and_optional_coordinates(self):
        self.assertEqual(metadata(), normalize_components(metadata(), ["validate", "reserve"]))

    def test_legacy(self):
        self.assertEqual({"version": 1, "groups": {}, "pipelines": {}}, normalize_components(None, []))

    def test_invalid_references_and_version(self):
        with self.assertRaisesRegex(ValueError, "pipeline"):
            normalize_components(metadata(), ["validate"])
        value = metadata()
        value["pipelines"]["reserve"] = "missing"
        with self.assertRaisesRegex(ValueError, "component"):
            normalize_components(value, ["validate", "reserve"])
        with self.assertRaisesRegex(ValueError, "version"):
            normalize_components({**metadata(), "version": 2}, [])

    def test_invalid_positions_and_view_state(self):
        value = metadata()
        value["groups"]["booking"]["position"]["x"] = float("inf")
        with self.assertRaisesRegex(ValueError, "finite"):
            normalize_components(value, [])
        value = metadata()
        value["groups"]["booking"]["collapsed"] = True
        with self.assertRaisesRegex(ValueError, "not supported"):
            normalize_components(value, [])

    def test_generation_preserves_source(self):
        for array in [True, False]:
            service = {"appearance": {"color": "#123456", "components": metadata()}, "pipelines": {"validate": {}}}
            document = {"services": [service] if array else {"booking": service}}
            clean = without_visual_components(document)
            result = clean["services"][0] if array else clean["services"]["booking"]
            self.assertEqual({"color": "#123456"}, result["appearance"])
            self.assertEqual(service["pipelines"], result["pipelines"])
            self.assertEqual(metadata(), service["appearance"]["components"])
