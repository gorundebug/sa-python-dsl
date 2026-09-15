"""Build the shared Designer/Python/ServiceGen component contract fixtures.

Run from the DSL repository with PYTHONPATH=src:tests. Copy the resulting
JSON unchanged to the other two repositories; none needs the others at runtime.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import TypeAlias

import yaml

from component_fixture import component_project
from component_ports_fixture import PortKind, port_fixture


JSONValue: TypeAlias = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]


def json_value(value: object) -> JSONValue:
    """Narrow serialization-boundary input before manipulating the document."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Document keys must be strings")
            result[key] = json_value(item)
        return result
    raise TypeError(f"Unsupported document value: {type(value).__name__}")


def mapping(value: JSONValue) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise TypeError("Expected a document mapping")
    return value


@dataclass(frozen=True)
class Edit:
    path: tuple[str, ...]
    value: JSONValue


@dataclass(frozen=True)
class Scenario:
    name: str
    valid: bool
    edits: tuple[Edit, ...] = ()


SERVICE = ("services", "booking")
LOAD = (*SERVICE, "pipelines", "update", "updateLoad")
PRICE = (*SERVICE, "pipelines", "update", "updatePrice")
GROUP = (*SERVICE, "appearance", "components", "groups", "pricing")


def policy(source: str, target: str, semantics: str, *, async_: bool = False) -> Edit:
    return Edit((*SERVICE, "links"), {
        f"{source}_{target}": {
            "from": source, "to": target, "callSemantics": semantics,
            **({"async": async_} if semantics == "FunctionCall" else {}),
        },
    })


SCENARIOS = (
    Scenario("identical", True),
    Scenario("display-only", True, (
        Edit((*LOAD, "name"), "Renamed display node"),
        Edit((*LOAD, "functionDescription"), "Documentation is not execution identity"),
        Edit((*SERVICE, "appearance", "pipelines", "update", "updateLoad"), {"x": 500, "y": -20}),
    )),
    Scenario("member-order", True, (Edit((*GROUP, "fragments"), [
        {"streams": [["create", "createLoad"], ["create", "createPrice"]]},
        {"streams": [["update", "updatePrice"], ["update", "updateLoad"]]},
    ]),)),
    Scenario("explicit-default-call", True, (policy("updateLoad", "updatePrice", "FunctionCall"),)),
    Scenario("incoming-parallel", False, (policy("updateRequest", "updateLoad", "ParallelCall"),)),
    Scenario("incoming-async", False, (policy("updateRequest", "updateLoad", "FunctionCall", async_=True),)),
    Scenario("internal-parallel", False, (policy("updateLoad", "updatePrice", "ParallelCall"),)),
    Scenario("outgoing-parallel", True, (policy("updatePrice", "updateResponse", "ParallelCall"),)),
    Scenario("function-name", False, (Edit((*LOAD, "functionName"), "LoadAnotherCustomer"),)),
    Scenario("function-package", False, (Edit((*LOAD, "functionPackage"), "other"),)),
    Scenario("initializer-group", False, (Edit((*LOAD, "functionInitializerGroup"), "other"),)),
    Scenario("explicit-empty-module", True, (Edit((*LOAD, "functionModule"), ""),)),
    Scenario("explicit-private-function", True, (Edit((*LOAD, "publicFunction"), False),)),
    Scenario("different-output-type", False, (
        Edit(("types", "otherAmount"), {"name": "Other Amount", "type": "int", "publicType": False}),
        Edit((*PRICE, "valueType"), "otherAmount"),
    )),
    Scenario("disconnected", False, (Edit((*PRICE, "source"), "updateRequest"),)),
    Scenario("overlapping-fragments", False, (Edit((*GROUP, "fragments"), [
        {"streams": [["create", "createLoad"], ["create", "createPrice"]]},
        {"streams": [["create", "createLoad"], ["create", "createPrice"]]},
    ]),)),
)


def build() -> dict[str, JSONValue]:
    project, service, fragments = component_project()
    component = service.component("Pricing")
    for members in fragments:
        component.fragment(*members)
    base = mapping(json_value(project.to_document()))
    cases: list[JSONValue] = []
    for scenario in SCENARIOS:
        document = deepcopy(base)
        for edit in scenario.edits:
            target = document
            for key in edit.path[:-1]:
                target = mapping(target[key])
            target[edit.path[-1]] = deepcopy(edit.value)
        cases.append({"name": scenario.name, "valid": scenario.valid,
                      "yaml": yaml.safe_dump(document, sort_keys=False)})
    kinds: tuple[PortKind, ...] = ("split", "case", "join", "multi-join")
    for kind in kinds:
        fixture = port_fixture(kind)
        diagnostics = fixture.project.validate()
        if diagnostics:
            raise ValueError("Invalid positive port fixture: " + "; ".join(str(item) for item in diagnostics))
        cases.append({"name": kind + "-ordered-ports", "valid": True,
                      "yaml": fixture.project.to_yaml()})
        fixture.swap_ports()
        cases.append({"name": kind + "-swapped-ports", "valid": False,
                      "yaml": yaml.safe_dump(mapping(json_value(fixture.project.to_document())), sort_keys=False)})
    return {"version": 1, "cases": cases}


if __name__ == "__main__":
    output = Path(__file__).parent / "fixtures" / "component-semantics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
