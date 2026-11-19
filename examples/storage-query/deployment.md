# Configuring the generated storage worker

These names are for this example's `Database` and `Objects` connectors. Renaming
connectors changes their generated environment prefixes. Shared clients belong to
service infrastructure makers; do not add clients or credentials to `main`.

## Runtime settings

| Setting | Purpose |
| --- | --- |
| `DATABASE_CONNECTION_STRING` | PostgreSQL URI; keep credentials in a Secret |
| `DATABASE_CONNECTIONS_COUNT` | PostgreSQL pool size |
| `DATABASE_CONNECT_TIMEOUT_MS` | Connection timeout; see the selected native connector's limitations |
| `DATABASE_OPERATION_TIMEOUT_MS` | Bound the whole Query invocation |
| `OBJECTS_ADDRESS` | S3 HTTP(S) endpoint; empty selects the AWS client's default endpoint |
| `OBJECTS_REGION` | Signing region |
| `OBJECTS_FORCE_PATH_STYLE` | Path-style addressing; unsupported by S3Userver |

The canonical model declares PostgreSQL pool/timeouts, so those fields have
runtime overrides. Do not infer that every optional model field automatically
gets an environment binding: inspect the generated configuration for your model.
DSN and S3 address have runtime bindings even when omitted from the model.

Go, TypeScript, Python, Rust and C++ Coro use native AWS credential providers.
For a local S3-compatible service, supply `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`; temporary credentials also require `AWS_SESSION_TOKEN`.
The SDK/provider decides how credentials are resolved and refreshed.

C++ userver instead requires `DATA_CONNECTORS_OBJECTS_ACCESS_KEY_ID` and
`DATA_CONNECTORS_OBJECTS_SECRET_ACCESS_KEY` in its default generated maker.
It requires an explicit `OBJECTS_ADDRESS` and virtual-host addressing:
`query-example.<endpoint-host>` must resolve and be accepted by the S3 server.
It does not advertise the AWS provider chain or session-token support. A custom
maker may provide a supported native authenticator. Do not enable path style to
work around DNS; this connector rejects it.

Transport TLS follows the native client and endpoint/connection configuration.
Use an HTTPS object endpoint and the selected PostgreSQL driver's supported TLS
settings for the intended deployment. There is no common Query switch to disable
certificate validation, and no cross-driver promise for arbitrary DSN options.
Native userver connection timeout also remains subject to its own cluster policy.

## Local Kubernetes through the existing Vault mechanism

From the generated project root, start the generated platform:

```sh
bash scripts/kubernetes.generated.sh infra-up
```

Create a private JSON file outside the repository containing string-valued
runtime settings. For Go/TypeScript/Python/Rust/Coro the shape is:

```json
{
  "DATABASE_CONNECTION_STRING": "postgresql://USER:PASSWORD@POSTGRES_HOST:5432/DATABASE",
  "OBJECTS_ADDRESS": "http://S3_HOST:9000",
  "OBJECTS_REGION": "us-east-1",
  "OBJECTS_FORCE_PATH_STYLE": "true",
  "AWS_ACCESS_KEY_ID": "ACCESS_KEY",
  "AWS_SECRET_ACCESS_KEY": "SECRET_KEY"
}
```

For userver, substitute its two credential names, use a virtual-host-compatible
address and set `OBJECTS_FORCE_PATH_STYLE` to `false`. These are placeholders;
this guide does not provision PostgreSQL, S3, credentials, schema or buckets.
Apply `python/schema.sql` and create `query-example` explicitly in a disposable
local environment before running the example.

Import the file using the generated helper and the namespace selected for your
local deployment:

```sh
python3 scripts/kubernetes-vault.generated.py put NAMESPACE storageworker-env \
  < /private/path/storageworker-secrets.json
make kubernetes-up
```

The existing Vault Secrets Operator projects the values into a Kubernetes Secret.
The generated local deployment wires `storageworker-env` through `secretEnvFrom`.
For direct Helm usage, provide the same setting explicitly in a private values
file (no secret values go in Helm values):

```yaml
secretEnvFrom:
  - storageworker-env
```

For an offline render, include the generated base values before your private
values file. The chart schema intentionally requires these base settings:

```sh
helm template storageworker storageworker/helm \
  -f storageworker/helm/values.generated.yaml \
  -f /private/path/storageworker-values.yaml
```

The workload imports its generated ConfigMap first and Secret second, so secret
values override defaults. The application reads environment at startup. Vault
rotation uses the existing operator rollout restart mechanism; Query adds no
Vault client or hot-reload loop. Repeat `put` with a complete desired JSON object
when rotating this Secret; do not assume the command merges individual keys.

This guide describes generated wiring, not production TLS, IAM or cluster
acceptance. Rust/C++ live storage acceptance remains tracked in the Query plan.
