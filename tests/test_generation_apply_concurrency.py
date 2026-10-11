from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
import yaml

from sa_dsl import generation_transaction as transaction
from sa_dsl.manifest import load_manifest
from tests.test_generation_transaction import Client, generated_archive, project_workspace


@pytest.mark.parametrize("same_preview,different_projects", [(True, False), (False, False), (False, True)])
def test_only_one_preview_may_apply_to_a_workspace(tmp_path, monkeypatch, same_preview, different_projects):
    if different_projects:
        (tmp_path / "generated").mkdir()
        manifests = []
        for name in ("authoring-one", "authoring-two"):
            root = tmp_path / name
            root.mkdir()
            current = project_workspace(root)
            document = yaml.safe_load(current.manifest_path.read_text(encoding="utf-8"))
            document["generation"]["outputDirectory"] = "../generated"
            current.manifest_path.write_text(yaml.safe_dump(document), encoding="utf-8")
            manifests.append(load_manifest(root))
        manifest, other_manifest = manifests
    else:
        manifest = other_manifest = project_workspace(tmp_path)

    def preview(authoring):
        result = transaction.preview_generation_transaction(
            authoring, client_factory=lambda _: Client(generated_archive()),
            boundary_root=tmp_path,
        )
        assert result["status"] == "success", result
        return result["preview"]

    first = preview(manifest)
    second = first if same_preview else preview(other_manifest)
    entered = Event()
    release = Event()
    calls = []
    original_merge = transaction._run_merge

    def controlled_merge(*args, **kwargs):
        if not kwargs["dry_run"]:
            calls.append(1)
            if len(calls) == 1:
                entered.set()
                assert release.wait(5), "test did not release first merge"
        return original_merge(*args, **kwargs)

    monkeypatch.setattr(transaction, "_run_merge", controlled_merge)

    def apply(authoring, preview):
        return transaction.apply_generation_transaction(
            authoring, preview_id=preview["previewId"],
            preview_revision=preview["previewRevision"], boundary_root=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(apply, manifest, first)
        try:
            assert entered.wait(5), "first apply never reached merge"
            refused = apply(other_manifest, second)
        finally:
            release.set()
        completed = future.result(timeout=5)
    assert completed["status"] == "success", completed
    assert refused["status"] == "failed", refused
    assert refused["diagnostics"][0]["code"] == "SA_GENERATION_APPLY_BUSY"
    assert len(calls) == 1
