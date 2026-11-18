"""Check local installable archives against current DSL and immutable IDE assets.

Does not install plugins, access credentials, publish, or claim remote Codex parity.
"""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
from zipfile import ZipFile
from sync_ide_assets import ASSET_DIGESTS, VERSION as DESIGNER_VERSION

ROOT = Path(__file__).resolve().parents[1]

def contents(path):
    with ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def sources():
    return {str(p.relative_to(ROOT / 'src')): p.read_bytes()
            for p in (ROOT / 'src/sa_dsl').rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}

def check_source(files, prefix, expected):
    for name, value in expected.items():
        assert files.get(prefix + name) == value, f'missing/stale bundled DSL file: {prefix}{name}'
    assert not any('__pycache__' in name or name.endswith('.pyc') for name in files), 'bundled bytecode'
    return len(expected)

def check_assets(files, prefix):
    for name, expected in ASSET_DIGESTS.items():
        assert digest(files[prefix + name]) == expected, f'stale Designer: {prefix}{name}'

def managed_cli_version(workspace=ROOT.parent):
    """Compare package loaders with checked-out sources, never a stale test pin."""
    vscode = json.loads((workspace / 'service-architect-vscode/package.json').read_text())['serviceArchitectCliVersion']
    java = (workspace / 'service-architect-jetbrains/src/main/java/com/gorundebug/servicearchitect/CliEnvironment.java').read_text()
    found = re.findall(r'static final String VERSION = "([^"]+)";', java)
    assert len(found) == 1, 'expected exactly one JetBrains managed CLI cache version'
    assert vscode == found[0], 'managed CLI cache versions differ between IDE sources'
    assert re.fullmatch(r'\d+\.\d+\.\d+', vscode), 'invalid managed CLI cache version'
    return vscode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('vsix', 'jetbrains', 'wheel', 'codex'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-codex-brokers', action='store_true', help='Fail when the pinned Codex runtime lacks broker classes')
    parser.add_argument('--runtime-dir', type=Path, help='Extract only verified source files for packaged CLI/MCP checks')
    args = parser.parse_args()
    expected = sources()
    cli_version = managed_cli_version()
    report = {'artifacts': {}, 'designerHashes': ASSET_DIGESTS, 'managedCliVersion': cli_version}
    for name in ('vsix', 'jetbrains', 'wheel', 'codex'):
        path = getattr(args, name)
        report['artifacts'][name] = {'path': str(path.resolve()), 'sha256': digest(path.read_bytes())}
    vsix = contents(args.vsix)
    report['vsixDslFiles'] = check_source(vsix, 'extension/resources/sa-python-dsl/src/', expected)
    check_assets(vsix, 'extension/media/')
    metadata = json.loads(vsix['extension/package.json'])
    assert metadata['serviceArchitectCliVersion'] == cli_version, 'stale VS Code managed CLI cache'
    assert cli_version.encode() in vsix['extension/bundle/extension.js'], 'stale bundled CLI loader'
    jars = contents(args.jetbrains)
    bundles = []
    for name, data in jars.items():
        if name.endswith('.jar'):
            files = contents(io.BytesIO(data))
            if 'cli/sa-python-dsl.zip' in files:
                bundles.append(files)
    assert len(bundles) == 1, 'expected exactly one embedded JetBrains CLI bundle'
    files = bundles[0]
    check_assets(files, 'ide/')
    assert cli_version.encode() in files['com/gorundebug/servicearchitect/CliEnvironment.class'], 'stale JetBrains managed CLI cache'
    jetbrains_cli = contents(io.BytesIO(files['cli/sa-python-dsl.zip']))
    report['jetbrainsDslFiles'] = check_source(jetbrains_cli, 'src/', expected)
    for name in ('pyproject.toml', 'README.md'):
        assert vsix['extension/resources/sa-python-dsl/' + name] == (ROOT / name).read_bytes()
        assert jetbrains_cli[name] == (ROOT / name).read_bytes()
    if args.runtime_dir:
        for kind, archive, prefix in [('vsix', vsix, 'extension/resources/sa-python-dsl/src/'), ('jetbrains', jetbrains_cli, 'src/')]:
            for name in expected:
                target = args.runtime_dir / kind / 'src' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive[prefix + name])
    report['wheelDslFiles'] = check_source(contents(args.wheel), '', expected)
    codex = contents(args.codex)
    for path in (ROOT / 'plugins/service-architect').rglob('*'):
        if path.is_file():
            name = 'service-architect/' + str(path.relative_to(ROOT / 'plugins/service-architect'))
            assert codex.get(name) == path.read_bytes(), f'stale Codex manifest/skill: {name}'
    manifest = json.loads(codex['service-architect/.mcp.json'])['mcpServers']['service-architect']
    pin = manifest['args'][1].rsplit('@', 1)[-1]
    old_model = subprocess.check_output(['git', 'show', pin + ':src/sa_dsl/model.py'], cwd=ROOT).decode()
    report['codex'] = {'runtimePin': pin, 'remoteDesigner': manifest['env']['SERVICE_ARCHITECT_DESIGNER_ASSET_BASE'],
       'missingPinnedConnectorClasses': [name for name in ('NATSConnector','JetStreamConnector','RabbitMQConnector','RedisStreamsConnector','PulsarConnector') if 'class '+name+'(' not in old_model and 'class '+name+':' not in old_model]}
    report['localIdeAndWheelParity'] = True
    report['codex']['expectedDesignerVersion'] = DESIGNER_VERSION
    report['codex']['designerVersionAligned'] = manifest['env']['SERVICE_ARCHITECT_DESIGNER_ASSET_BASE'].rstrip('/').endswith('/mcp-ui/' + DESIGNER_VERSION)
    # Manifest alignment is necessary, not proof that remote assets are deployed.
    report['codexBrokerParity'] = (not report['codex']['missingPinnedConnectorClasses']
                                  and report['codex']['designerVersionAligned'])
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if args.require_codex_brokers and not report['codexBrokerParity']:
        raise SystemExit("Codex broker acceptance blocked: runtime broker classes or Designer version are not aligned")

if __name__ == '__main__':
    main()
