import copy
import json

import pytest
import yaml

from sa_dsl import ServiceArchitectClient
from sa_dsl.code_generation import to_api_document
from tests.test_code_generation import FakeResponse, zip_content


def document():
    return {
        "settings": {"name": "Example"},
        "types": {
            "value": {"name": "Order Value", "type": "string"},
            "key": {"name": "Order Key", "type": "string"},
            "values": {"name": "Order Values", "type": "array", "valueType": "value"},
            "by_key": {"name": "Orders By Key", "type": "map", "keyType": "key", "valueType": "values"},
            "batches": {"name": "Batches", "type": "array", "valueType": "by_key"},
        },
    }


def assert_references(payload):
    types = {item["name"]: item for item in payload["types"]}
    assert types["Order Values"]["valueType"] == "Order Value"
    assert types["Orders By Key"]["keyType"] == "Order Key"
    assert types["Orders By Key"]["valueType"] == "Order Values"
    assert types["Batches"]["valueType"] == "Orders By Key"


def test_composite_references_use_api_type_names_without_mutating_canonical_keys():
    canonical = document()
    original = copy.deepcopy(canonical)
    assert_references(to_api_document(canonical))
    assert canonical == original


@pytest.mark.parametrize("field", ["valueType", "keyType"])
def test_unknown_composite_reference_is_not_silently_replaced(field):
    canonical = document()
    canonical["types"]["by_key"][field] = "unknown_reference"
    types = {item["name"]: item for item in to_api_document(canonical)["types"]}
    assert types["Orders By Key"][field] == "unknown_reference"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_generation_requests_resolve_nested_composite_references(asynchronous):
    captured = []
    archive = zip_content()

    class CanonicalProject:
        def to_yaml(self):
            return yaml.safe_dump(document())

    def opener(request, **kwargs):
        if request.get_method() == "POST":
            captured.append(json.loads(request.data))
            if asynchronous:
                return FakeResponse({"job": {"id": "job", "status": "SUCCEEDED"}, "statusUrl": "/v1/generation-jobs/job"}, status=202)
            return FakeResponse(archive, headers={"Content-Type": "application/zip"})
        if request.full_url.endswith("/download"):
            return FakeResponse({"url": "https://objects.example/project.zip", "fileName": "project.zip"})
        assert request.full_url == "https://objects.example/project.zip"
        return FakeResponse(archive, headers={"Content-Type": "application/zip"})

    credentials = {"api_key": "test-key"} if asynchronous else {"id_token": "test-token"}
    result = ServiceArchitectClient(**credentials, opener=opener).generate_code(CanonicalProject())
    assert result.content == archive
    assert len(captured) == 1
    assert_references(captured[0])
