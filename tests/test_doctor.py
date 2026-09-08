import tempfile
import unittest
from pathlib import Path

import yaml

from sa_dsl.doctor import diagnose_project
from sa_dsl.servicegen_capabilities import save_capabilities


class DoctorTest(unittest.TestCase):
    def test_doctor_is_passive_and_never_exposes_credentials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-doctor-") as temporary:
            workspace = Path(temporary)
            marker = workspace / "executed.marker"
            (workspace / "architecture.py").write_text(
                "from pathlib import Path\nPath('executed.marker').write_text('yes')\n",
                encoding="utf-8",
            )
            manifest = workspace / ".service-architect/project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(yaml.safe_dump({
                "version": 1,
                "project": {"name": "Doctor"},
                "authoring": {"mode": "python", "entrypoint": "architecture:project"},
                "canonical": {"output": ".service-architect/build/architecture.yaml"},
                "generation": {"targets": ["go"]},
            }, sort_keys=False), encoding="utf-8")
            secret = "sa_live_private_value"
            (workspace / ".env").write_text(
                f"SERVICE_ARCHITECT_API_KEY={secret}\n", encoding="utf-8"
            )

            result = diagnose_project(workspace)

            self.assertEqual("success", result["status"])
            self.assertGreaterEqual(result["summary"]["warnings"], 1)
            self.assertNotIn(secret, str(result))
            self.assertFalse(marker.exists())

    def test_invalid_manifest_fails_with_stable_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-doctor-") as temporary:
            result = diagnose_project(Path(temporary))
            self.assertEqual("failed", result["status"])
            self.assertEqual("manifest", result["checks"][-1]["id"])

    def test_capability_cache_reports_backend_compatibility(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-doctor-") as temporary:
            workspace = Path(temporary)
            manifest = workspace / ".service-architect/project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(yaml.safe_dump({
                "version": 1,
                "project": {"name": "Doctor"},
                "authoring": {"mode": "python", "entrypoint": "architecture:project"},
                "canonical": {"output": ".service-architect/build/architecture.yaml"},
                "generation": {"targets": ["go", "python"]},
            }, sort_keys=False), encoding="utf-8")
            save_capabilities(workspace, {
                "schemaVersion": "1.0",
                "servicegenVersion": "0.2.100",
                "apiRevision": "v0.2.100",
                "revision": "sha256:test",
                "languages": [{"id": 1, "name": "GoLang", "backend": "golang"}],
            })

            result = diagnose_project(workspace)

            capability = next(check for check in result["checks"] if check["id"] == "capabilities")
            self.assertEqual("error", capability["status"])
            self.assertIn("python", capability["message"])


if __name__ == "__main__":
    unittest.main()
