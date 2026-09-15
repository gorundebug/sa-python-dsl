import copy
import unittest
from sa_dsl.generation_document import generation_document


def source():
    return {"services": [{"id": 1, "appearance": {"components": {"version": 2, "groups": {
        "pricing": {"name": "Pricing", "fragments": [{"streams": [["create", "load"]]}, {"streams": [["update", "load"]]}]}
    }}}}], "streams": [
        {"id": 1, "idService": 1, "name": "Input", "pipeline": "create"},
        {"id": 2, "idService": 1, "name": "Load", "pipeline": "create", "idSource": 1},
        {"id": 3, "idService": 1, "name": "Load", "pipeline": "update"},
    ], "links": [{"from": 1, "to": 2, "callSemantics": 2}]}


class GenerationDocumentTest(unittest.TestCase):
    def test_concrete_labels_without_topology_changes(self):
        doc = source()
        before = copy.deepcopy(doc)
        result = generation_document(doc)
        self.assertEqual(before, doc)
        self.assertEqual([None, "Pricing", "Pricing"], [stream.get("component") for stream in result["streams"]])
        self.assertEqual(doc["links"], result["links"])
        self.assertEqual(doc["streams"], [{k:v for k,v in stream.items() if k != "component"} for stream in result["streams"]])
        self.assertNotIn("appearance", result["services"][0])
        self.assertNotIn("component_instance", str(result))

    def test_unknown_member_rejected(self):
        doc = source()
        doc["streams"].pop()
        with self.assertRaisesRegex(ValueError, "Unknown component stream"):
            generation_document(doc)

    def test_empty_groups_clear_stale_labels(self):
        doc = source()
        doc["services"][0]["appearance"]["components"]["groups"] = {}
        doc["streams"][0]["component"] = "Old"
        self.assertTrue(all("component" not in stream for stream in generation_document(doc)["streams"]))
        self.assertEqual("Old", doc["streams"][0]["component"])

    def test_other_service_not_attributed(self):
        doc = source()
        doc["services"].append({"id": 2, "name": "Other"})
        doc["streams"].append({"id":4,"idService":2,"name":"Load","pipeline":"create"})
        self.assertNotIn("component", generation_document(doc)["streams"][-1])
