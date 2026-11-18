# Generated Python Redis Streams example

This overlay implements the existing `../project.py` receive → normalize →
publish → correlated result graph. The generator test projects its service to
Python in memory; the canonical model remains unchanged.

Functions use the generated native source/sink contracts. Event.ID and Event.Value
are explicit Redis field/value records, not a JSON transport envelope. The source
registers its result callback before collect and XACKs only when the correlated
XADD result has Accepted=true. Done does not ACK. Unknown/failed outcomes leave
input pending. The sink callback preserves EventID and the returned EntryID;
its captured Event remains valid after EndRequest.

From servicegen:

```sh
SERVICEGEN_REDIS_STREAMS_PYTHON_IMPORT=1 \
SERVICEGEN_REDIS_STREAMS_PYTHON_CANONICAL=1 \
REDIS_STREAMS_TEST_URL=redis://127.0.0.1:16379 \
REDIS_STREAMS_TEST_PASSWORD=adapter-test \
go test ./internal/codegenerator \
  -run '^TestPythonRedisStreams(Generation|CanonicalExample)$' -count=1 -v
```

The tests export/validate the actual model, regenerate the complete service,
install only this user-owned overlay, and run the generated entrypoint with the
local Python SDK. Both result-order generation variants compile/import. The
native gate asserts generated environment bindings, three normalized outputs,
matching EventID/EntryID outcomes, zero source PEL entries, retained input records,
and SIGTERM shutdown with exit code zero. It cleans only unique fixture keys and
never restarts or reconfigures the shared Redis broker.

Use `SERVICEGEN_DSL_PYTHON` to override the DSL interpreter. By default the harness
uses `sa-python-dsl/.venv/bin/python` for model export and
`pyservicelib/.venv/bin/python` for SDK execution. `SERVICEGEN_REDIS_STREAMS_PYTHON_CANONICAL_ARTIFACTS`
can retain the generated archive contents; the overlay is applied separately.
