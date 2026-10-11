import io
from pathlib import Path
from unittest.mock import patch
import zipfile

from sa_dsl.generation import GenerationResult
from sa_dsl.ide_generation import generate_and_merge
from tests.test_generation_transaction import generated_archive, MERGE_SCRIPT, project_workspace


def archive_writer(content):
    def generate(manifest, *, output, **_options):
        (manifest.workspace / output).write_bytes(content)
        return GenerationResult(status="success", project_name=manifest.name,
                                artifact=output, source_files=("architecture.py",))
    return generate


def test_generation_uses_existing_merge_contract(tmp_path: Path) -> None:
    manifest = project_workspace(tmp_path)
    destination = (tmp_path / "dist/generated-project").resolve()
    calls = []

    def fake_merge(_script, _archive, workspace, _report, *, dry_run, remove_stale):
        calls.append((workspace, dry_run, remove_stale))
        return {"status": "success"}

    with patch("sa_dsl.ide_generation.generate_project_archive", side_effect=archive_writer(generated_archive().content)), \
         patch("sa_dsl.ide_generation._run_merge", side_effect=fake_merge):
        result = generate_and_merge(manifest, output_dir="dist/generated-project")
    assert result["status"] == "success", result
    assert calls == [(destination, True, False), (destination, False, False)]


def test_generation_rejects_authoring_collision_before_merge(tmp_path: Path) -> None:
    manifest = project_workspace(tmp_path)
    before = (tmp_path / "architecture.py").read_bytes()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("example/architecture.py", "# must not replace the model\n")
        archive.writestr("example/scripts/merge.generated.sh", MERGE_SCRIPT)
    with patch("sa_dsl.ide_generation.generate_project_archive", side_effect=archive_writer(output.getvalue())), \
         patch("sa_dsl.ide_generation._run_merge") as merge:
        result = generate_and_merge(manifest, output_dir=".")
    assert result["status"] == "failed", result
    assert "conflicts with Python authoring" in result["message"]
    merge.assert_not_called()
    assert (tmp_path / "architecture.py").read_bytes() == before


def test_generation_runs_real_merge_script_in_chosen_directory(tmp_path: Path) -> None:
    manifest = project_workspace(tmp_path)
    destination = tmp_path / "dist/generated-project"
    destination.mkdir(parents=True)
    (destination / "user.txt").write_text("custom implementation\n", encoding="utf-8")
    with patch("sa_dsl.ide_generation.generate_project_archive", side_effect=archive_writer(generated_archive().content)):
        result = generate_and_merge(manifest, output_dir="dist/generated-project")
    assert result["status"] == "success", result
    assert (destination / "generated.txt").read_text() == "generated v2\n"
    assert (destination / "user.txt").read_text() == "custom implementation\n"
    assert result["merge"]["operation"] == "merge-apply"


def test_generation_rejects_higher_ancestor_without_request(tmp_path: Path) -> None:
    manifest = project_workspace(tmp_path)
    with patch("sa_dsl.ide_generation.generate_project_archive") as generate:
        result = generate_and_merge(manifest, output_dir="../..")
    assert result["status"] == "failed"
    generate.assert_not_called()
