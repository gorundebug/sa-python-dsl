import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from sa_dsl.ide import graph_snapshot, locate_source
from sa_dsl.ide_materialize import materialize_project
from sa_dsl.manifest import load_manifest


def test_materialize_updates_only_owned_files(tmp_path: Path) -> None:
    manifest = SimpleNamespace(name='sample', workspace=tmp_path)
    content = {'value': 'first'}

    def fake_import(_workspace, _source, output):
        generated = tmp_path / output
        generated.mkdir(parents=True)
        (generated / 'model.py').write_text(content['value'], encoding='utf-8')
        (generated / '.service-architect').mkdir()
        (generated / '.service-architect/project.yaml').write_text(
            'authoring:\n  entrypoint: main:project\n', encoding='utf-8')
        return SimpleNamespace(succeeded=True)

    exported = SimpleNamespace(succeeded=True, rendered_yaml='services: {}\n')
    with patch('sa_dsl.ide_materialize.execute_project', return_value=exported), \
         patch('sa_dsl.ide_materialize.import_yaml_project', side_effect=fake_import):
        first = materialize_project(manifest)
        assert first['status'] == 'success'
        destination = tmp_path / 'python-dsl' / 'model' / 'model.py'
        assert destination.read_text() == 'first'
        content['value'] = 'second'
        second = materialize_project(manifest)
        assert second['status'] == 'success'
        assert destination.read_text() == 'second'
        destination.write_text('my edit', encoding='utf-8')
        third = materialize_project(manifest)
        assert third['status'] == 'failed'
        assert destination.read_text() == 'my edit'


def test_materialize_refuses_unowned_directory(tmp_path: Path) -> None:
    target = tmp_path / 'python-dsl'
    target.mkdir()
    (target / 'user.py').write_text('keep me', encoding='utf-8')
    manifest = SimpleNamespace(name='sample', workspace=tmp_path)
    exported = SimpleNamespace(succeeded=True, rendered_yaml='services: {}\n')

    def fake_import(_workspace, _source, output):
        generated = tmp_path / output
        generated.mkdir(parents=True)
        (generated / 'model.py').write_text('model', encoding='utf-8')
        (generated / '.service-architect').mkdir()
        (generated / '.service-architect/project.yaml').write_text(
            'authoring:\n  entrypoint: main:project\n', encoding='utf-8')
        return SimpleNamespace(succeeded=True)

    with patch('sa_dsl.ide_materialize.execute_project', return_value=exported), \
         patch('sa_dsl.ide_materialize.import_yaml_project', side_effect=fake_import):
        result = materialize_project(manifest)
    assert result['status'] == 'failed'
    assert (target / 'user.py').read_text() == 'keep me'


def test_materialized_canonical_example_is_reexportable_and_equivalent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / 'examples/processorder'
    workspace = tmp_path / 'processorder'
    shutil.copytree(source, workspace, ignore=shutil.ignore_patterns('__pycache__'))
    before_main = (workspace / 'main.py').read_bytes()
    original = graph_snapshot(load_manifest(workspace))
    result = materialize_project(load_manifest(workspace))
    assert result['status'] == 'success', result
    materialized = graph_snapshot(load_manifest(workspace / 'python-dsl'))
    assert materialized['status'] == 'success', materialized
    assert yaml.safe_load(original['snapshot']['canonicalYaml']) == yaml.safe_load(
        materialized['snapshot']['canonicalYaml'])
    assert (workspace / 'main.py').read_bytes() == before_main
    first_service, service = next(iter(yaml.safe_load(original['snapshot']['canonicalYaml'])['services'].items()))
    first_stream = next(iter(next(iter(service['pipelines'].values()))))
    assert locate_source(workspace, kind='node', service=first_service, key=first_stream)['status'] == 'success'
