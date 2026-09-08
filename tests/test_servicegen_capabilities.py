import json
import tempfile
import unittest
from pathlib import Path

from sa_dsl.servicegen_capabilities import (
    CACHE_RELATIVE_PATH,
    CapabilityError,
    compatibility_diagnostics,
    fetch_capabilities,
    load_cached_capabilities,
    save_capabilities,
)


def matrix(*, schema: str = "1.0", backends: tuple[str, ...] = ("golang", "python")):
    return {
        "schemaVersion": schema,
        "servicegenVersion": "0.2.100",
        "apiRevision": "v0.2.100",
        "revision": "sha256:abc",
        "languages": [
            {
                "id": index,
                "name": backend,
                "backend": backend,
                "streams": [],
                "callSemantics": [],
                "connectors": {},
            }
            for index, backend in enumerate(backends, start=1)
        ],
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


class ServiceGenCapabilitiesTest(unittest.TestCase):
    def test_fetch_is_public_and_cache_round_trips_without_secrets(self) -> None:
        captured = {}

        def open_request(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response(matrix())

        document = fetch_capabilities(
            "https://api.example.test/prod", opener=open_request
        )
        self.assertEqual("https://api.example.test/prod/v1/capabilities", captured["request"].full_url)
        self.assertIsNone(captured["request"].get_header("Authorization"))
        self.assertIsNone(captured["request"].get_header("X-service-architect-key"))

        with tempfile.TemporaryDirectory(prefix="sa-capabilities-") as temporary:
            workspace = Path(temporary)
            output = save_capabilities(workspace, document)
            self.assertEqual((workspace / CACHE_RELATIVE_PATH).resolve(), output)
            self.assertEqual(document, load_cached_capabilities(workspace))

    def test_rejects_incompatible_schema(self) -> None:
        with self.assertRaisesRegex(CapabilityError, "unsupported capability schema"):
            fetch_capabilities(
                "https://api.example.test", opener=lambda request, timeout: Response(matrix(schema="2.0"))
            )

    def test_reports_manifest_target_missing_from_generator(self) -> None:
        diagnostics = compatibility_diagnostics(matrix(backends=("golang",)), ("go", "python"))
        self.assertEqual("SA_CAPABILITY_TARGET_UNAVAILABLE", diagnostics[0]["code"])
        self.assertEqual("$.generation.targets[1]", diagnostics[0]["path"])


if __name__ == "__main__":
    unittest.main()
