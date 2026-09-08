import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from sa_dsl.designer import DesignerSnapshotServer, designer_document, make_snapshot
from sa_dsl.mcp_workspace import WorkspaceBoundary, WorkspaceBoundaryError


class WorkspaceBoundaryTest(unittest.TestCase):
    def test_resolves_only_paths_under_registered_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            boundary = WorkspaceBoundary(root)
            self.assertEqual(root.resolve(), boundary.resolve("."))
            self.assertEqual((root / "project").resolve(), boundary.resolve("project"))
            with self.assertRaises(WorkspaceBoundaryError):
                boundary.resolve("../outside")
            with self.assertRaises(WorkspaceBoundaryError):
                boundary.resolve(root)
            with self.assertRaises(WorkspaceBoundaryError):
                boundary.resolve("project\\outside")

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            (root / "escape").symlink_to(outside, target_is_directory=True)
            boundary = WorkspaceBoundary(root)
            with self.assertRaises(WorkspaceBoundaryError):
                boundary.resolve("escape/project")


class DesignerViewTest(unittest.TestCase):
    def test_snapshot_revision_is_deterministic_and_content_sensitive(self) -> None:
        first = make_snapshot("Example", "name: Example\n")
        same = make_snapshot("Example", "name: Example\n")
        changed = make_snapshot("Example", "name: Changed\n")
        self.assertEqual(first["revision"], same["revision"])
        self.assertNotEqual(first["revision"], changed["revision"])
        self.assertEqual("read-only", first["mode"])

    def test_ui_document_loads_only_versioned_remote_assets(self) -> None:
        document = designer_document("https://gorundebug.com/mcp-ui/0.1.1")
        self.assertIn("https://gorundebug.com/mcp-ui/0.1.1/designer.js", document)
        self.assertIn("https://gorundebug.com/mcp-ui/0.1.1/designer.css", document)
        self.assertNotIn("canonicalYaml", document)

    def test_loopback_snapshot_url_is_unguessable_and_not_cached(self) -> None:
        server = DesignerSnapshotServer(ttl_seconds=60)
        try:
            snapshot = make_snapshot("Example", "name: Example\n")
            url = server.publish(snapshot)
            self.assertTrue(url.startswith("http://127.0.0.1:"), url)
            self.assertNotIn("Example", url)
            with urllib.request.urlopen(url, timeout=2) as response:
                body = response.read().decode("utf-8")
                self.assertEqual("no-store", response.headers["Cache-Control"])
                self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
                self.assertIn("service-architect-snapshot", body)
                self.assertIn("name: Example", body)
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(f"{server.origin}/designer/unknown", timeout=2)
            self.assertEqual(404, raised.exception.code)
            raised.exception.close()
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()
