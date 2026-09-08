import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from sa_dsl.code_generation import GeneratedProjectArchive
from sa_dsl.generation_transaction import (
    apply_generation_transaction,
    preview_generation_transaction,
)
from sa_dsl.manifest import load_manifest


MERGE_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
dry=0
report=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry=1; shift ;;
    --remove-stale) shift ;;
    --report-json) report="$2"; shift 2 ;;
    *) archive="$1"; shift ;;
  esac
done
if [[ "$dry" -eq 0 ]]; then
  printf 'generated v2\n' > "$SERVICEGEN_PROJECT_DIR_OVERRIDE/generated.txt"
fi
python3 - "$report" "$dry" <<'PY'
import json, sys
from pathlib import Path
dry = sys.argv[2] == "1"
Path(sys.argv[1]).write_text(json.dumps({
    "schemaVersion": "1.0",
    "operation": "merge-preview" if dry else "merge-apply",
    "status": "success",
    "summary": {"added": 0, "generatedUpdated": 1, "preserved": 1},
    "files": [
        {"action": "UPD", "path": "generated.txt"},
        {"action": "SKP", "path": "user.txt"},
    ],
}))
PY
'''


def generated_archive(*, unsafe: bool = False) -> GeneratedProjectArchive:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../escape.txt" if unsafe else "example/generated.txt", "generated v2\n")
        archive.writestr("example/user.txt", "regenerated\n")
        archive.writestr("example/scripts/merge.generated.sh", MERGE_SCRIPT)
    return GeneratedProjectArchive("example.zip", output.getvalue())


class Client:
    def __init__(self, archive: GeneratedProjectArchive) -> None:
        self.archive = archive

    def generate_code(self, project):
        self.yaml = project.to_yaml()
        return self.archive


def project_workspace(root: Path):
    (root / "architecture.py").write_text(
        "from sa_dsl import Project\nproject = Project('Example')\n",
        encoding="utf-8",
    )
    manifest = root / ".service-architect/project.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": {"name": "Example"},
                "authoring": {"mode": "python", "entrypoint": "architecture:project"},
                "canonical": {"output": ".service-architect/build/architecture.yaml"},
                "generation": {"targets": ["go"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "generated.txt").write_text("generated v1\n", encoding="utf-8")
    (root / "user.txt").write_text("custom user code\n", encoding="utf-8")
    (root / ".env").write_text("SERVICE_ARCHITECT_API_KEY=test\n", encoding="utf-8")
    return load_manifest(root)


class GenerationTransactionTest(unittest.TestCase):
    def test_preview_and_apply_exact_archive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-transaction-") as temporary:
            workspace = Path(temporary)
            manifest = project_workspace(workspace)
            preview = preview_generation_transaction(
                manifest,
                client_factory=lambda _: Client(generated_archive()),
                now=lambda: 1000,
            )

            self.assertEqual("success", preview["status"])
            self.assertEqual("generated v1\n", (workspace / "generated.txt").read_text())
            self.assertEqual("custom user code\n", (workspace / "user.txt").read_text())
            token = preview["preview"]
            applied = apply_generation_transaction(
                manifest,
                preview_id=token["previewId"],
                preview_revision=token["previewRevision"],
                now=lambda: 1001,
            )

            self.assertEqual("success", applied["status"])
            self.assertEqual("generated v2\n", (workspace / "generated.txt").read_text())
            self.assertEqual("custom user code\n", (workspace / "user.txt").read_text())
            replay = apply_generation_transaction(
                manifest,
                preview_id=token["previewId"],
                preview_revision=token["previewRevision"],
                now=lambda: 1002,
            )
            self.assertEqual("SA_PREVIEW_ALREADY_APPLIED", replay["diagnostics"][0]["code"])

    def test_apply_rejects_changed_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-transaction-") as temporary:
            workspace = Path(temporary)
            manifest = project_workspace(workspace)
            preview = preview_generation_transaction(
                manifest,
                client_factory=lambda _: Client(generated_archive()),
                now=lambda: 1000,
            )["preview"]
            (workspace / "user.txt").write_text("changed after preview\n", encoding="utf-8")

            result = apply_generation_transaction(
                manifest,
                preview_id=preview["previewId"],
                preview_revision=preview["previewRevision"],
                now=lambda: 1001,
            )

            self.assertEqual("failed", result["status"])
            self.assertEqual("SA_STALE_WORKSPACE", result["diagnostics"][0]["code"])
            self.assertEqual("generated v1\n", (workspace / "generated.txt").read_text())

    def test_preview_rejects_archive_traversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-transaction-") as temporary:
            manifest = project_workspace(Path(temporary))
            result = preview_generation_transaction(
                manifest,
                client_factory=lambda _: Client(generated_archive(unsafe=True)),
                now=lambda: 1000,
            )

            self.assertEqual("failed", result["status"])
            self.assertEqual("SA_ARCHIVE_INVALID_PATH", result["diagnostics"][0]["code"])


if __name__ == "__main__":
    unittest.main()
