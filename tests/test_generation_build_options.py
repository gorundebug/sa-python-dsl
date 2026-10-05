import json
import unittest
from urllib.parse import parse_qs, urlsplit

from sa_dsl import Project, ServiceArchitectClient, yaml_to_api_document
from sa_dsl.code_generation import generation_build_options
from test_code_generation import FakeResponse, zip_content


class GenerationBuildOptionsTest(unittest.TestCase):
    def test_both_auth_routes_send_options_without_modifying_model(self):
        for api_key in (None, "test-key"):
            for graph in ("typed", "dynamic"):
                for backend in ("epoll", "uring"):
                    with self.subTest(api_key=bool(api_key), graph=graph, backend=backend):
                        requests = []
                        payload = zip_content()

                        def opener(request, *, timeout):
                            requests.append(request)
                            if not api_key:
                                return FakeResponse(payload, headers={"Content-Type": "application/zip"})
                            if request.get_method() == "POST":
                                return FakeResponse({
                                    "job": {"status": "SUCCEEDED"},
                                    "statusUrl": "/v1/generation-jobs/test",
                                })
                            if request.full_url.endswith("/download"):
                                return FakeResponse({"url": "https://files.example/project.zip", "fileName": "project.zip"})
                            return FakeResponse(payload, headers={"Content-Type": "application/zip"})

                        project = Project("Options")
                        client = ServiceArchitectClient(api_key=api_key, id_token="token", opener=opener)
                        archive = client.generate_code(project, cpp_graph=graph, cpp_io_backend=backend)
                        self.assertEqual(archive.content, payload)
                        query = parse_qs(urlsplit(requests[0].full_url).query)
                        self.assertEqual(set(query), {"options"})
                        self.assertEqual(json.loads(query["options"][0]), {"packOptions": {
                            "cpp-userver-service": {"graph": graph},
                            "cpp-coro-service": {"graph": graph, "ioBackend": backend},
                        }})
                        self.assertEqual(json.loads(requests[0].data), yaml_to_api_document(project.to_yaml()))
                        for request in requests[1:]:
                            self.assertEqual(urlsplit(request.full_url).query, "")

    def test_defaults_and_invalid_options(self):
        self.assertEqual(generation_build_options(None, None), {})
        for graph, backend in (("other", None), (None, "poll"), (None, "URING")):
            with self.assertRaises(ValueError):
                generation_build_options(graph, backend)

    def test_external_pack_options_preserve_types_and_input(self):
        requests = []

        def opener(request, *, timeout):
            requests.append(request)
            return FakeResponse(zip_content(), headers={"Content-Type": "application/zip"})

        options = {"custom-ci": {"runner": "self-hosted", "capacity": 9007199254740993, "enabled": False}}
        client = ServiceArchitectClient(id_token="token", opener=opener)
        client.generate_code(Project("External"), pack_options=options)
        query = parse_qs(urlsplit(requests[0].full_url).query)
        self.assertEqual(json.loads(query["options"][0]), {"packOptions": options})
        self.assertEqual(set(options), {"custom-ci"})

    def test_conflicting_convenience_options_fail_before_request(self):
        client = ServiceArchitectClient(id_token="token")
        options = {"cpp-coro-service": {"graph": "dynamic"}}
        with self.assertRaisesRegex(ValueError, "conflicting graph"):
            client.generate_code(Project("Conflict"), cpp_graph="typed", pack_options=options)
        self.assertEqual(options, {"cpp-coro-service": {"graph": "dynamic"}})


if __name__ == "__main__":
    unittest.main()
