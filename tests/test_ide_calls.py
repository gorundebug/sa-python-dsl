from pathlib import Path

import pytest

from sa_dsl.ide_calls import analysis_request


def test_refresh_analyzes_all_go_substreams_and_preserves_other_services_on_error(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    import yaml
    from sa_dsl import ide_calls
    from sa_dsl.designer import make_snapshot

    document = model()
    document['services']['second'] = model()['services']['orders']
    document['services']['broken'] = model()['services']['orders']
    document['services']['rust'] = model('Rust')['services']['orders']
    document['services']['empty'] = {'programmingLanguage': 'GoLang', 'pipelines': {}}
    rendered = yaml.safe_dump(document)
    manifest = SimpleNamespace(name='test', workspace=tmp_path,
                               generation=SimpleNamespace(output_directory='.'))
    monkeypatch.setattr(ide_calls, 'execute_project', lambda *a: SimpleNamespace(succeeded=True, rendered_yaml=rendered))
    builds = []
    monkeypatch.setattr(ide_calls, '_analyzer', lambda: (builds.append(True) or (Path('/analyzer'), {})))
    analyzed = []
    def run(*args, **kwargs):
        key = Path(json.loads(kwargs['input'])['serviceDirectory']).name
        analyzed.append(key)
        return SimpleNamespace(returncode=1 if key == 'broken' else 0, stderr='type error',
                               stdout=json.dumps({'links': [{'source': 'work', 'target': 'call', 'chain': []}], 'unresolved': []}))
    monkeypatch.setattr(ide_calls.subprocess, 'run', run)
    result = ide_calls.substream_calls(manifest, revision=make_snapshot('test', rendered)['revision'])
    assert result['status'] == 'success'
    assert {link['service'] for link in result['links']} == {'orders', 'second'}
    assert result['errors'] == [{'service': 'broken', 'message': 'type error'}]
    assert set(analyzed) == {'orders', 'second', 'broken'}
    assert len(builds) == 1


def model(language="GoLang"):
    return {"services": {"orders": {"programmingLanguage": language, "pipelines": {"main": {
        "work": {"type": "Process", "functionName": "ResolveOrder", "functionPackage": "orders"},
        "call": {"type": "SubStream", "name": "Lookup inventory"},
    }}}}}


def test_model_is_the_identity_source(tmp_path):
    request = analysis_request(model(), tmp_path, "orders")
    assert request["substreams"] == [{"key": "call", "symbols": ["LookupInventory", "Call"]}]
    assert request["business"][0]["key"] == "work"
    assert request["business"][0]["directory"] == str(tmp_path / "orders/internal/functions/orders")
    assert request["patterns"] == ["./orders/..."]


def test_rejects_unsupported_languages_and_escaped_packages(tmp_path):
    with pytest.raises(ValueError, match="Go services only"):
        analysis_request(model("Rust"), tmp_path, "orders")
    document = model()
    document["services"]["orders"]["pipelines"]["main"]["work"]["functionPackage"] = "../../../../outside"
    with pytest.raises(ValueError, match="escapes"):
        analysis_request(document, tmp_path, "orders")


def test_shared_module_is_separate_from_service_owner(tmp_path):
    (tmp_path / "shared_go").mkdir()
    (tmp_path / "shared_go/go.mod").write_text("module example.test/shared")
    document = model()
    document["services"]["orders"]["pipelines"]["main"]["work"]["functionModule"] = "shared"
    request = analysis_request(document, tmp_path, "orders")
    assert Path(request["business"][0]["directory"]) == tmp_path / "shared_go/pkg/functions/orders"


def test_default_go_template_acronyms_are_resolved_without_losing_original_names(tmp_path):
    document = model()
    pipeline = document['services']['orders']['pipelines']['main']
    pipeline['publishDSPBillingNotice'] = {'type': 'SubStream', 'name': 'Publish DSP billing notice'}
    pipeline['work']['functionName'] = 'PublishDSPNotice'
    request = analysis_request(document, tmp_path, 'orders')
    target = next(item for item in request['substreams'] if item['key'] == 'publishDSPBillingNotice')
    assert target['symbols'] == ['PublishDSPBillingNotice', 'PublishDspBillingNotice']
    assert 'PublishDSPNotice' in request['business'][0]['symbols']
    assert 'PublishDspNotice' in request['business'][0]['symbols']
