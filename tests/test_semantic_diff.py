import unittest

import yaml

from sa_dsl.semantic_diff import document_revision, preview_architecture_diff


class SemanticDiffTest(unittest.TestCase):
    def test_revision_is_independent_of_mapping_order(self) -> None:
        self.assertEqual(
            document_revision({"services": {"a": {"name": "A"}}, "settings": {"name": "P"}}),
            document_revision({"settings": {"name": "P"}, "services": {"a": {"name": "A"}}}),
        )

    def test_preview_reports_graph_entities_without_duplicate_parent_change(self) -> None:
        baseline = {
            "settings": {"name": "Example"},
            "types": {"event": {"name": "Event", "type": "struct"}},
            "services": {
                "orders": {
                    "name": "Orders",
                    "streams": {
                        "source": {"name": "Source", "type": "Input"},
                        "map": {"name": "Map", "type": "Map"},
                    },
                    "links": {"source_map": {"from": "source", "to": "map"}},
                }
            },
        }
        candidate = {
            "settings": {"name": "Example"},
            "types": {"event": {"name": "Event v2", "type": "struct"}},
            "services": {
                "orders": {
                    "name": "Orders",
                    "streams": {
                        "source": {"name": "Source", "type": "Input"},
                        "sink": {"name": "Sink", "type": "Sink"},
                    },
                    "links": {"source_sink": {"from": "source", "to": "sink"}},
                }
            },
        }

        preview = preview_architecture_diff(
            yaml.safe_dump(baseline), yaml.safe_dump(candidate)
        )

        self.assertEqual(
            {("changed", "type", "event"), ("removed", "stream", "map"),
             ("added", "stream", "sink"), ("removed", "link", "source_map"),
             ("added", "link", "source_sink")},
            {(item["change"], item["kind"], item["identity"]) for item in preview["changes"]},
        )
        self.assertNotIn("service", {item["kind"] for item in preview["changes"]})
        self.assertEqual(5, preview["summary"]["total"])
        self.assertNotEqual(preview["baselineRevision"], preview["candidateRevision"])


if __name__ == "__main__":
    unittest.main()
