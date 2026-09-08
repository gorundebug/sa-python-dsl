import json
import tempfile
import unittest
from pathlib import Path

from sa_dsl.servicegen_validation import (
    CACHE_RELATIVE_PATH,
    ValidationContractError,
    attach_remediation,
    diagnostic_descriptor,
    fetch_validation_contract,
    load_validation_contract,
    save_validation_contract,
)


def contract(*, schema="1.0", capability_revision="sha256:cap"):
    return {
        "schemaVersion": schema,
        "servicegenVersion": "0.2.100",
        "diagnosticSchemaVersion": "1.0",
        "capabilityRevision": capability_revision,
        "revision": "sha256:rules",
        "diagnostics": [{
            "code": "SG_SEMANTIC_TYPE_MISMATCH",
            "stage": "semantic",
            "scopes": ["stream"],
            "condition": "Connected types differ.",
            "meaning": "The edge is invalid.",
            "remediation": "Align the wire types.",
            "userCorrectable": True,
            "evaluation": "servicegen",
        }],
    }


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class ServiceGenValidationContractTest(unittest.TestCase):
    def test_public_fetch_cache_and_lookup_do_not_send_credentials(self):
        captured = {}

        def opener(request, *, timeout):
            captured["request"] = request
            return Response(contract())

        document = fetch_validation_contract(
            "https://api.example.test/prod", opener=opener
        )
        self.assertEqual(
            "https://api.example.test/prod/v1/validation-contract",
            captured["request"].full_url,
        )
        self.assertIsNone(captured["request"].get_header("Authorization"))
        self.assertIsNone(
            captured["request"].get_header("X-service-architect-key")
        )
        with tempfile.TemporaryDirectory(prefix="sa-validation-") as temporary:
            workspace = Path(temporary)
            output = save_validation_contract(workspace, document)
            self.assertEqual((workspace / CACHE_RELATIVE_PATH).resolve(), output)
            cached = load_validation_contract(workspace)
            self.assertEqual(
                "Align the wire types.",
                diagnostic_descriptor(cached, "SG_SEMANTIC_TYPE_MISMATCH")["remediation"],
            )

    def test_rejects_unknown_schema_and_non_servicegen_evaluator(self):
        with self.assertRaisesRegex(ValidationContractError, "unsupported"):
            fetch_validation_contract(
                "https://api.example.test",
                opener=lambda request, timeout: Response(contract(schema="2.0")),
            )
        invalid = contract()
        invalid["diagnostics"][0]["evaluation"] = "python"
        with self.assertRaisesRegex(ValidationContractError, "evaluated by servicegen"):
            fetch_validation_contract(
                "https://api.example.test",
                opener=lambda request, timeout: Response(invalid),
            )

    def test_validation_payload_is_enriched_from_exact_cached_revision(self):
        with tempfile.TemporaryDirectory(prefix="sa-validation-") as temporary:
            workspace = Path(temporary)
            save_validation_contract(workspace, contract())
            payload = attach_remediation({
                "diagnostics": [{
                    "code": "SG_SEMANTIC_TYPE_MISMATCH",
                    "message": "mismatch",
                }]
            }, workspace)
            diagnostic = payload["diagnostics"][0]
            self.assertEqual(
                "servicegen://validation/rules/SG_SEMANTIC_TYPE_MISMATCH",
                diagnostic["validationRuleUri"],
            )
            self.assertEqual("sha256:rules", diagnostic["validationRule"]["contractRevision"])
            self.assertEqual("Align the wire types.", diagnostic["validationRule"]["remediation"])


if __name__ == "__main__":
    unittest.main()
