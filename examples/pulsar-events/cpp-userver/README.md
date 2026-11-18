# Pulsar userver canonical example

The typed Python model is `../project.py`. The runner changes only the selected
runtime to C++ userver in memory, validates and exports it, generates a fresh
project and overlays these user-owned native types and functions.

The source decodes Event, registers its result callback before emitting, and ACKs
only a correlated Accepted publication with a native MessageId. The map preserves
ID and trims/uppercases Value. The sink publishes asynchronously through its
standard endpoint, preserving key/properties. No additional broker client runs
inside business functions. Done completes the request without an implicit ACK.

Run from `servicegen` with the official C++ 4.2.0 installation:

```sh
PULSAR_NATIVE_PREFIX=/path/to/official/install/usr scripts/test-userver-pulsar.sh
```

The harness compiles the actual graph and a separate official native test peer.
It uses a unique namespace on the existing broker, checks three normalized outputs,
correlated native IDs, empty pending/backlog and clean SIGTERM. It removes only its
own resources; the shared broker is never restarted. Artifacts include exported
model/archive, service log and acceptance.results.json. Runtime images are a
separate gate, using `image_acceptance.py`; source/binaries are not mounted into
the service container in that gate.

Verified locally against official Pulsar C++ 4.2.0 and the existing Pulsar 4.1.2
broker: full generated compile/link, three records, native ID correlation,
explicit ACK/empty pending and SIGTERM exit 0. Evidence is retained at
`/private/tmp/sa-pulsar-userver-canonical-1/acceptance.log` and
`pulsarevents/acceptance.results.json`. ARM64 runtime-image execution also passes
with the image's own command/configuration/libraries, no application mounts,
three outputs, matching IDs, explicit ACK and SIGTERM exit 0. Evidence:
`pulsarevents/image-acceptance.arm64.results.json`. AMD64 image acceptance also
passes under emulation, with an independent ARM64 peer: three outputs/IDs, explicit
ACK and SIGTERM exit 0 (112 ms). Its evidence is
`pulsarevents/image-acceptance.amd64.results.json`.
The generator supplies the required userver --config/--config_vars through CMD.

To verify an already-built AMD64 image with the independent native ARM64 peer:

```sh
PULSAR_RUNTIME_IMAGE=sa-pulsar-userver-canonical:amd64 \
PULSAR_RUNTIME_PLATFORM=linux/amd64 PULSAR_PEER_PLATFORM=linux/arm64 \
PULSAR_NATIVE_PREFIX=/path/to/official/arm64/install/usr \
python3 image_acceptance.py /path/to/generated/pulsarevents
```

This keeps the service architecture check separate from the test-peer architecture;
the peer is a real official client, not an emulated broker response.
