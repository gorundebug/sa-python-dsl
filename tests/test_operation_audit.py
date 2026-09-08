import tempfile
import time
import unittest
from pathlib import Path

from sa_dsl.operation_audit import read_audit, record_operation


class OperationAuditTest(unittest.TestCase):
    def test_audit_records_metadata_without_payload_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-audit-") as temporary:
            workspace = Path(temporary)
            secret = "sa_live_never_log_this"
            payload = {
                "status": "failed",
                "project": {"name": "Example"},
                "preview": {"previewId": "preview-id", "canonicalRevision": "sha256:abc"},
                "diagnostics": [{"code": "SA_TEST", "message": secret}],
                "source": secret,
            }

            record_operation(workspace, "preview-generation", payload, time.monotonic())
            result = read_audit(workspace)

            self.assertEqual(1, len(result["events"]))
            event = result["events"][0]
            self.assertEqual(["SA_TEST"], event["diagnosticCodes"])
            self.assertEqual("preview-id", event["references"]["previewId"])
            self.assertNotIn(secret, str(result))
            self.assertEqual(0o600, (workspace / ".service-architect/audit.jsonl").stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
