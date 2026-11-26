import unittest

import yaml

from sa_dsl import (
    Deployment, DslValidationError, Golang, KubernetesDeployment, Project,
    SecretKeyRef, ServiceModule, python_files_to_yaml, yaml_to_python_files,
)
from sa_dsl.code_generation import to_api_document


class DeploymentTest(unittest.TestCase):
    def test_partial_secret_override_roundtrips_without_materializing_inheritance(self):
        project = self.project()
        project.service("Partial", language=Golang(), module=ServiceModule("example.com/partial"),
            deployment=Deployment(kubernetes=KubernetesDeployment(secret_env={"TOKEN": SecretKeyRef(optional=False)})))
        document = project.to_document()
        self.assertEqual({"optional": False}, document["services"]["partial"]["deployment"]["kubernetes"]["secretEnv"]["TOKEN"])
        generated = yaml_to_python_files(document, "partial_deployment")
        self.assertEqual(document, yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint)))

    def test_incomplete_effective_secret_reference_is_rejected(self):
        project = Project("Incomplete")
        project.service("Worker", language=Golang(), module=ServiceModule("example.com/worker"),
            deployment=Deployment(kubernetes=KubernetesDeployment(secret_env={"TOKEN": SecretKeyRef(optional=False)})))
        with self.assertRaisesRegex(DslValidationError, "required field"):
            project.to_document()

    def test_nested_contract_is_closed_and_errors_do_not_echo_values(self):
        for settings in (
            {"security_context": {"unknown": "PRIVATE_VALUE"}},
            {"extra_env": [{"name": "TOKEN", "valueFrom": {"secretKeyRef": {"unknown": "PRIVATE_VALUE"}}}]},
            {"resources": {"requests": {"cpu": True}}},
            {"probes": {"readiness": {"spec": {"httpGet": {"port": False}}}}},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError) as caught:
                KubernetesDeployment(**settings).to_document()
            self.assertNotIn("PRIVATE_VALUE", str(caught.exception))

    def project(self):
        project = Project("Deployment Example", deployment=Deployment(
            kubernetes=KubernetesDeployment(replica_count=3,
                termination_grace_period_seconds=120,
                secret_env={"TOKEN": SecretKeyRef("existing-secret", "token", False)})))
        project.service("Worker", language=Golang(),
            module=ServiceModule("example.com/worker"), deployment=Deployment(
                kubernetes=KubernetesDeployment(termination_grace_period_seconds=0,
                    command=[], resources={})))
        return project

    def test_round_trip_and_flat_api_preserve_explicit_values(self):
        project = self.project()
        document = project.to_document()
        generated = yaml_to_python_files(document, "deployment_example")
        restored = yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint))
        self.assertEqual(document, restored)
        sources = "\n".join(generated.files.values())
        self.assertIn("KubernetesDeployment(", sources)
        self.assertIn("SecretKeyRef(", sources)
        flat = to_api_document(document)
        self.assertEqual(flat["settings"]["deployment"], document["settings"]["deployment"])
        self.assertEqual(flat["services"][0]["deployment"], document["services"]["worker"]["deployment"])

    def test_old_documents_do_not_acquire_deployment(self):
        project = Project("Old")
        self.assertNotIn("deployment", project.to_document()["settings"])

    def test_collections_are_copied(self):
        env = [{"name": "MODE", "value": "test"}]
        settings = KubernetesDeployment(extra_env=env)
        document = settings.to_document()
        document["extraEnv"][0]["value"] = "changed"
        self.assertEqual("test", env[0]["value"])

    def test_invalid_values_do_not_echo_secrets(self):
        for value in (True, -1, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                KubernetesDeployment(replica_count=value).to_document()
        cyclic = {}
        cyclic["self"] = cyclic
        with self.assertRaises(ValueError):
            KubernetesDeployment(resources=cyclic).to_document()
        with self.assertRaises(ValueError):
            KubernetesDeployment(secret_env={"TOKEN": {"value": "secret"}}).to_document()
        with self.assertRaises(DslValidationError):
            Project("Invalid", deployment={}).to_document()

    def test_import_rejects_unsupported_and_null_settings(self):
        for settings in ({"kubernetes": {"unknown": "secret"}},
                         {"kubernetes": {"command": None}}, {"other": {}}):
            with self.subTest(settings=settings), self.assertRaises(ValueError) as caught:
                yaml_to_python_files({"settings": {"name": "Invalid", "deployment": settings}}, "invalid")
            self.assertNotIn("secret", str(caught.exception))
