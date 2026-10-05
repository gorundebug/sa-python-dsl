from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sa_dsl.ide_generation import generate_and_merge
from tests.test_generation_transaction import generated_archive


def test_generation_uses_existing_merge_contract(tmp_path: Path) -> None:
    manifest = SimpleNamespace(name='sample', workspace=tmp_path)
    destination = (tmp_path / 'dist/generated-project').resolve()
    calls = []

    def fake_generate(_manifest, *, output, **_options):
        (tmp_path / output).write_bytes(b'zip')
        return SimpleNamespace(succeeded=True)

    def fake_merge(_script, _archive, workspace, _report, *, dry_run, remove_stale):
        calls.append((workspace, dry_run, remove_stale))
        return {'status': 'success'}

    with patch('sa_dsl.ide_generation.generate_project_archive', side_effect=fake_generate), \
         patch('sa_dsl.ide_generation._extract_merge_script', return_value=Path('merge.generated.sh')), \
         patch('sa_dsl.ide_generation._run_merge', side_effect=fake_merge):
        result = generate_and_merge(manifest, output_dir='dist/generated-project')
    assert result['status'] == 'success'
    assert calls == [(destination, True, False), (destination, False, False)]


def test_generation_never_merges_into_authoring_root(tmp_path: Path) -> None:
    manifest = SimpleNamespace(name='sample', workspace=tmp_path)
    assert generate_and_merge(manifest, output_dir='.')['status'] == 'failed'


def test_generation_runs_real_merge_script_in_chosen_directory(tmp_path: Path) -> None:
    manifest = SimpleNamespace(name='sample', workspace=tmp_path)
    archive = generated_archive()

    def fake_generate(_manifest, *, output, **_options):
        (tmp_path / output).write_bytes(archive.content)
        return SimpleNamespace(succeeded=True)

    with patch('sa_dsl.ide_generation.generate_project_archive', side_effect=fake_generate):
        result = generate_and_merge(manifest, output_dir='dist/generated-project')
    assert result['status'] == 'success', result
    assert (tmp_path / 'dist/generated-project/generated.txt').read_text() == 'generated v2\n'
    assert result['merge']['operation'] == 'merge-apply'
