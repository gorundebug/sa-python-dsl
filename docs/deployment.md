# Optional deployment settings

Deployment metadata controls generated packaging, not runtime graph semantics.
Existing projects without it keep their defaults. Kubernetes workload type stays
in the existing `Kubernetes(workload_type=...)` service setting.

```python
from sa_dsl import (
    Deployment, Golang, KubernetesDeployment, Project, SecretKeyRef, ServiceModule,
)

project = Project("Example", deployment=Deployment(
    kubernetes=KubernetesDeployment(termination_grace_period_seconds=120),
))
worker = project.service(
    "Worker", language=Golang(), module=ServiceModule("example.com/worker"),
    deployment=Deployment(kubernetes=KubernetesDeployment(
        deployment_strategy={"type": "Recreate"},
        secret_env={"API_TOKEN": SecretKeyRef("existing-token", "token")},
    )),
)
```

Python export writes project defaults to `settings.deployment.kubernetes` and
service overrides to `services.<key>.deployment.kubernetes` in canonical YAML.
JSON code-generation requests preserve the same metadata separately from SDK
runtime records. YAML import produces typed deployment constructors too.

Omission inherits. Arrays replace. Nonempty nested mappings merge; an explicitly
empty mapping clears an inherited mapping. Empty arrays and permitted zero/false
values are retained. `None` means omitted in Python, not a YAML null override.
Environment-specific user-owned Helm values remain the final layer.

Nested service overrides are partial too. For example,
`SecretKeyRef(optional=False)` inherits the Secret name and key from project
defaults. The exported service YAML contains only `optional: false`, not a
materialized copy of those defaults. Required effective fields are checked on
each service after inheritance when exporting the project; a standalone partial
policy can be constructed without inventing missing fields.

Nested record annotations and local shape validation derive from the same closed
deployment definitions in `servicelib/api/serviceapi.yaml`. To refresh them during
SDK development (no runtime repository access is needed):

```sh
python scripts/sync_deployment_contract.py ../servicelib/api/serviceapi.yaml
python scripts/sync_deployment_contract.py ../servicelib/api/serviceapi.yaml --check
```

This validates the supported transport subset, not every Kubernetes cross-field
rule or cluster admission policy. Unknown nested fields and malformed scalar types
are rejected without copying their submitted values into diagnostics.

`SecretKeyRef` references a Secret already provisioned in the workload namespace;
it does not create credentials or grant access. Additional containers receive only
the environment, mounts and permissions explicitly configured for them. Platform
object details are validated by the generated chart/Kubernetes; exporting YAML
does not prove image readiness or application correctness.
