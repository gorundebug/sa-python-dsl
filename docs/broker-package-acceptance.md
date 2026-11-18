# Local broker package acceptance — 2026-11-18

User decision (2026-11-18): native plugin interaction checks are user-owned.
No further IDE installation/Refresh tests are required of the agent; the agent
verifies full/embedded Designer and matching assets delivered in plugin packages.
Historical native-host observations below are retained, not future gates.

Current local artifacts below supersede earlier B08 package logs. These are not
releases or proof of interactive installation in an already-running IDE.

## Latest Designer source update

The subsequent unified connector-validation refactor builds candidate
`0.1.19-brokers.2`; 486 Designer tests and canonical Chromium snapshot checks pass.
Both IDE source directories contain the exact new JS/CSS, verified by
`sync_ide_assets.py --check`. JS SHA256:
`6fb9300d732c34c95974f520c6e90c773761df805afff73cdd2f9581f1b2b224`.
CSS is unchanged. Build: `/private/tmp/sa-designer-brokers-format-20261118/`;
UI results: `/private/tmp/sa-broker-format-ui-20261118/results.json`.
Current VSIX and JetBrains archives were subsequently repackaged with .2 using
normal bundle/vsce and Gradle buildPlugin commands, omitting plugin tests.
`/private/tmp/sa-broker-packages-candidate2-20261118.json` verifies all 60 DSL files,
cache 0.1.24 and exact new assets. VSIX SHA256:
`a5a587f83791d381097ccb8c9e36d9bf22cace53d0c281d9e3c313df7a9853e4`;
JetBrains SHA256:
`dab6dd01775840c5fe9c8d976fb6c6f10bbe8340e0bcaa4f129308aa69b07df6`.
Build logs: `/private/tmp/sa-{vscode,jetbrains}-package-only-fixed-20261118.log`.
Earlier .1 hashes/results below remain historical evidence, not current identities.
No further native IDE/plugin interaction checks are in agent scope.

## Earlier built artifacts and verification

- VS Code `dist/service-architect-vscode-0.1.21.vsix` in the sibling repository:
  normal make docker-build passed; `/private/tmp/sa-brokers-direction-vscode-package-fixed.log`.
- JetBrains `dist/service-architect-jetbrains-0.1.28.zip` in the sibling repository:
  normal make docker-build, Gradle tests and buildPlugin passed;
  `/private/tmp/sa-brokers-direction-jetbrains-package-fixed.log`.
- DSL `dist/sa_python_dsl-0.1.0-py3-none-any.whl` and Codex
  `dist/service-architect-codex-0.1.27.zip`: make package passed;
  `/private/tmp/sa-brokers-direction-dsl-package-fixed.log`.

`/private/tmp/sa-direction-packages-final.json` records artifact SHA256 hashes,
all 60 DSL source/resource files matching in both IDE archives and the wheel,
managed CLI cache 0.1.24 and candidate Designer 0.1.19-brokers.1 assets.
JS SHA256: `812d4f4b9cb46b375f8ba2e22b7adf3e8ae329a18310e7e6ac214cd40ac3b20f`.
CSS SHA256: `8177430f824bad516fb497d9a3a6b6443b91d35280d2e608d5b89b780157f35c`.
The version is a local candidate, not a published immutable asset replacement.

The package checker derives the cache version from both source loaders and rejects
disagreement, stale archive loaders and missing resources. Controlled cache tests
preserve external/project CLI overrides. The old archive correctly failed before
rebuilding (`/private/tmp/sa-broker-packages-pre-direction-rebuild.log`).

Direct-wheel import exposed a real resource-loading defect (filesystem Path cannot
read a ZIP member); the loader now uses importlib.resources. The corrected wheel
passes 45 Rabbit authoring tests including sink-only acceptance and source/mixed
rejection: `/private/tmp/sa-direction-wheel-authoring-fixed.log`.

Actual stdio MCP through the wheel and both extracted IDE runtimes passes:

- `/private/tmp/sa-direction-wheel-mcp-final.log` (also Designer catalog/assets).
- `/private/tmp/sa-direction-vsix-mcp-final.log`.
- `/private/tmp/sa-direction-jetbrains-mcp-final.log`.

Capability revision:
`sha256:403f5215c935a10b74f97d6240b0e927a8c4c22084b0c2447dad42a590a94cd3`.
There are 24 connector/target entries across six runtimes; this is NOT 24
full-duplex profiles. TypeScript/RabbitMQ SOURCE is explicitly unsupported,
SINK remains eligible. These checks use the actual cached local generator export,
not a separately maintained runtime allowlist or a claim of public deployment.

## Embedded browser acceptance

Candidate assets matching both IDE archives pass actual Chromium loading through
an IDE-style snapshot host. Four canonical graphs cover NATS Core/JetStream,
RabbitMQ, Redis Streams and Pulsar: expected node counts, ten source/sink search,
selection and focus actions, no browser errors. Graph and asset hashes plus
screenshots: `/private/tmp/sa-broker-candidate-ui-20261118/`.
Harness `/private/tmp/sa-broker-candidate-ui.mjs`, successful log
`/private/tmp/sa-broker-candidate-ui-fixed-20261118.log`.
Initial harness failed because its HTML omitted UTF-8; matching the real IDE
charset fixed that without changing application assets. This is browser-host
acceptance, not installation inside native IDEs or editable full Designer forms.

Full Designer editing forms separately pass all five transports, explicit creation
flags, field retention and official-client selections. TypeScript Rabbit source
restriction and retained sink support are available through the standard property
label tooltip; the shared panel previously did not render description metadata.
Evidence: `/private/tmp/sa-broker-forms-browser-hints-20261118.log` and screenshots
in the matching directory. Rebuilding embedded assets after this full-Designer-only
change produces byte-identical JS/CSS, preserving the package identities above.
Native IDE installation/refresh is user-owned and is not an agent acceptance gate.

## Actual VS Code extension host

VSIX installation into an isolated extensions directory succeeds. The official
VS Code extension-test runner activates that installed artifact, executes its real
openGraph command for a copied RabbitMQ Python project, confirms the webview tab,
and observes the webview ready handshake execute ide-snapshot successfully.
The CLI is explicitly the extracted, previously verified VSIX runtime; no mock
vscode module or plugin rewrite. This does not exercise first-run CLI installation.

Evidence: `/private/tmp/sa-broker-vscode-native-20261118/host-result.json`,
`host-test-fixed.log` (exit 0), `cli-events.jsonl`, `install.log`.
The initial test omitted the CLI setting; corrected fixture sets it only in the
disposable workspace. Native-window automation could not observe the target
window. Manual Refresh and JetBrains native installation are now user-owned;
actual graph rendering is covered by the separate candidate Chromium acceptance.

## Codex release blocker and remaining checks

`make mcp-conformance` still passes its exact pinned runtime handshake (21 tools,
8 resources): `/private/tmp/sa-b08-codex-pinned-mcp.log`. That older gate checks
tool availability, not broker support. Pin
`09f45bdd8e4e5e39d4051cac4391167acbb01d86` lacks NATSConnector,
JetStreamConnector, RabbitMQConnector, RedisStreamsConnector and PulsarConnector.
The manifest also selects remote Designer `https://gorundebug.com/mcp-ui/0.1.10`,
not the 0.1.19-brokers.1 assets checked in the IDE packages.

The release path requires publishing a reviewed broker-capable DSL revision,
updating the immutable Codex pin, and separately deploying/selecting a reviewed
remote Designer build, followed by exact pinned-runtime broker/MCP acceptance.
No unpublished local commit, mutable branch or local-path substitute was inserted
into the release manifest. This immutable-runtime/remote-asset alignment remains
an external B08 prerequisite. Native plugin UI checks are user-owned; local
Designer/source acceptance is already documented above. The coordinated release
steps are in [the handoff](../../servicegen/docs/message-brokers-release.md).

## Reproduce artifact inspection

From this repository, after sibling IDE `make docker-build` and `make package`:

```sh
make package-check PACKAGE_CHECK_ARGS='--vsix ../service-architect-vscode/dist/service-architect-vscode-0.1.21.vsix --jetbrains ../service-architect-jetbrains/dist/service-architect-jetbrains-0.1.28.zip --wheel dist/sa_python_dsl-0.1.0-py3-none-any.whl --codex dist/service-architect-codex-0.1.27.zip --runtime-dir /private/tmp/sa-direction-packaged-runtimes --output /private/tmp/sa-direction-packages-final.json'
```

The report explicitly separates `localIdeAndWheelParity` from
`codexBrokerParity`; a faithful archive does not imply a broker-capable pin.
Add `--require-codex-brokers` to make the missing pinned broker support fail the
gate explicitly (currently expected to fail).
No shared Nexus mutation, credentials access, release, push or version bump of
published plugins/Python distribution is part of these targets.
