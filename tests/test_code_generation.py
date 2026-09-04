import base64
import io
import json
import unittest
import zipfile

from sa_dsl import (
    CodeGenerationError,
    Project,
    ServiceArchitectClient,
    yaml_to_api_document,
)


def zip_content() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("README.md", "generated")
    return output.getvalue()


class FakeResponse:
    def __init__(self, payload, *, status: int = 200, headers=None) -> None:
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self._content = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._content

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None


class CodeGenerationTest(unittest.TestCase):
    def test_authorized_generation_returns_zip_archive(self) -> None:
        expected = zip_content()
        captured = {}

        def open_request(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "headers": {
                        "Content-Disposition": 'attachment; filename="orders.zip"'
                    },
                    "body": base64.b64encode(expected).decode("ascii"),
                }
            )

        project = Project("Orders")
        client = ServiceArchitectClient(
            id_token="cognito-id-token",
            base_url="https://api.example.test/stage/",
            timeout=30,
            opener=open_request,
        )

        result = client.generate_code(project)

        self.assertEqual("orders.zip", result.filename)
        self.assertEqual(expected, result.content)
        self.assertEqual(30, captured["timeout"])
        self.assertEqual(
            "cognito-id-token",
            captured["request"].get_header("Authorization"),
        )
        self.assertEqual(
            "https://api.example.test/stage/service_architect/generateCode",
            captured["request"].full_url,
        )
        self.assertEqual(
            yaml_to_api_document(project.to_yaml()),
            json.loads(captured["request"].data),
        )

    def test_api_error_is_exposed(self) -> None:
        client = ServiceArchitectClient(
            id_token="token",
            opener=lambda request, timeout: FakeResponse(
                {"statusCode": 422, "body": '{"message":"invalid graph"}'}
            ),
        )

        with self.assertRaisesRegex(CodeGenerationError, "invalid graph") as raised:
            client.generate_code(Project("Invalid"))

        self.assertEqual(422, raised.exception.status_code)

    def test_api_key_generation_submits_polls_and_downloads_without_leaking_key(self) -> None:
        expected = zip_content()
        requests = []

        def open_request(request, *, timeout):
            requests.append(request)
            if request.full_url.endswith("/v1/generation-jobs"):
                return FakeResponse({
                    "job": {"id": "job-1", "status": "QUEUED"},
                    "statusUrl": "/v1/generation-jobs/job-1",
                    "pollAfterSeconds": 0,
                }, status=202)
            if request.full_url.endswith("/v1/generation-jobs/job-1"):
                return FakeResponse({"job": {"id": "job-1", "status": "SUCCEEDED"}})
            if request.full_url.endswith("/download"):
                return FakeResponse({
                    "url": "https://objects.example/orders.zip",
                    "fileName": "orders.zip",
                })
            if request.full_url == "https://objects.example/orders.zip":
                return FakeResponse(expected, headers={"Content-Type": "application/zip"})
            raise AssertionError(request.full_url)

        project = Project("Orders")
        client = ServiceArchitectClient(
            api_key="sa_live_key_secret",
            base_url="https://api.example.test/prod",
            opener=open_request,
            sleep=lambda _: None,
        )
        result = client.generate_code(project)

        self.assertEqual("orders.zip", result.filename)
        self.assertEqual(expected, result.content)
        self.assertEqual(
            ["POST", "GET", "GET", "GET"],
            [request.get_method() for request in requests],
        )
        self.assertEqual(
            "sa_live_key_secret",
            requests[0].get_header("X-service-architect-key"),
        )
        self.assertIsNone(requests[-1].get_header("X-service-architect-key"))

    def test_api_key_generation_exposes_terminal_job_failure(self) -> None:
        responses = iter([
            FakeResponse({
                "job": {"id": "job-1", "status": "QUEUED"},
                "statusUrl": "/v1/generation-jobs/job-1",
                "pollAfterSeconds": 0,
            }, status=202),
            FakeResponse({"job": {"id": "job-1", "status": "FAILED", "errorCode": "INVALID_ARCHITECTURE"}}),
        ])
        client = ServiceArchitectClient(
            api_key="sa_live_key_secret",
            base_url="https://api.example.test/prod",
            opener=lambda request, timeout: next(responses),
            sleep=lambda _: None,
        )
        with self.assertRaisesRegex(CodeGenerationError, "INVALID_ARCHITECTURE"):
            client.generate_code(Project("Invalid"))


if __name__ == "__main__":
    unittest.main()
