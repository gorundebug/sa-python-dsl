from pathlib import Path

import pytest

from sa_dsl.ide import locate_source


def write_project(root: Path, imports: str, connection: str) -> tuple[Path, str]:
    service = root / "model/services/ad_server"
    pipelines = service / "pipelines"
    pipelines.mkdir(parents=True)
    (pipelines / "delivery.py").write_text(
        'raise RuntimeError("Navigation must not execute this module")\n'
        'routes = {}\n'
        'for path, name in (("/rtb", "Reply to SSP RTB"), ("/ds", "Reply to Direct SSP")):\n'
        '    routes[path] = pipeline.when(name)\n', encoding="utf-8")
    (pipelines / "admission.py").write_text(
        'entry = pipeline.input("ssp API rtb")\n', encoding="utf-8")
    # Identical variable names in other modules must not determine the target.
    (pipelines / "unrelated.py").write_text(
        'entry = pipeline.input("Wrong target")\n'
        'routes = {}\n'
        'routes["/rtb"] = pipeline.when("Wrong source")\n', encoding="utf-8")
    source = service / "service.py"
    content = imports + "\n" + connection + "\n"
    source.write_text(content, encoding="utf-8")
    return source, content


def lookup(root: Path) -> dict:
    return locate_source(root, kind="link", service="adServer", key="",
                         source="replyToSSPRTB", target="sspAPIRtb")


@pytest.mark.parametrize(("imports", "connection"), [
    ('from .pipelines import delivery as d, admission as a', 'd.routes["/rtb"] >> a.entry'),
    ('from model.services.ad_server.pipelines import delivery as d, admission as a',
     'd.routes["/rtb"] >> a.entry'),
    ('import model.services.ad_server.pipelines.delivery as d\n'
     'import model.services.ad_server.pipelines.admission as a', 'd.routes["/rtb"] >> a.entry'),
    ('import model.services.ad_server.pipelines.delivery\n'
     'import model.services.ad_server.pipelines.admission as a',
     'model.services.ad_server.pipelines.delivery.routes["/rtb"] >> a.entry'),
    ('from .pipelines.delivery import routes as r\nfrom .pipelines.admission import entry as e',
     'r["/rtb"] >> e'),
    ('from .pipelines import delivery as d, admission as a', 'a.entry << d.routes["/rtb"]'),
    ('from .pipelines import delivery as d, admission as a',
     'd.routes["/rtb"].function_call(a.entry)'),
])
def test_imported_route_link_is_exact_and_read_only(tmp_path: Path, imports: str, connection: str) -> None:
    source, content = write_project(tmp_path, imports, connection)
    result = lookup(tmp_path)
    assert result == {"status": "success", "location": {
        "file": "model/services/ad_server/service.py", "line": len(imports.splitlines()) + 1,
        "column": 1}}
    assert source.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("extra", [
    'd = load_dynamic_module()',
    'del d',
    'from .pipelines import unrelated as d',
    'def worker(d):\n    pass',
    'def d():\n    pass',
])
def test_rebound_import_alias_is_not_guessed(tmp_path: Path, extra: str) -> None:
    write_project(tmp_path, 'from .pipelines import delivery as d, admission as a\n' + extra,
                  'd.routes["/rtb"] >> a.entry')
    assert lookup(tmp_path)["status"] == "not-found"


def test_dynamic_route_key_is_not_guessed(tmp_path: Path) -> None:
    write_project(tmp_path, 'from .pipelines import delivery as d, admission as a',
                  'd.routes[request_path()] >> a.entry')
    assert lookup(tmp_path)["status"] == "not-found"


def test_missing_import_does_not_use_another_modules_variables(tmp_path: Path) -> None:
    write_project(tmp_path, 'from .missing import delivery as d, admission as a',
                  'd.routes["/rtb"] >> a.entry')
    assert lookup(tmp_path)["status"] == "not-found"


def test_duplicate_connection_remains_ambiguous(tmp_path: Path) -> None:
    write_project(tmp_path, 'from .pipelines import delivery as d, admission as a',
                  'd.routes["/rtb"] >> a.entry\nd.routes["/rtb"] >> a.entry')
    assert lookup(tmp_path)["status"] == "ambiguous"
