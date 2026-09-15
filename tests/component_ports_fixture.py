"""Real typed branching/join graphs used by the cross-language corpus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sa_dsl import Function, Golang, JoinStorageType, JoinType, Package, Project, ServiceModule
from sa_dsl.model import Stream


PortKind = Literal["split", "case", "join", "multi-join"]


@dataclass(frozen=True)
class PortFixture:
    project: Project
    swap_ports: Callable[[], None]


def port_fixture(kind: PortKind) -> PortFixture:
    project = Project("Ordered Components")
    service = project.service("Booking", language=Golang(), module=ServiceModule(path="example.com/booking"))
    amount = project.int_type("Amount", public_type=False)
    identifier = project.string_type("Identifier", public_type=False)
    connector = project.custom_connector("Requests")
    component = service.component("Business Processing")
    second_members: list[Stream] = []
    for name in ("Create", "Update"):
        pipeline = service.pipeline(name)

        def incoming(suffix: str) -> Stream:
            endpoint = connector.endpoint(name + suffix, function=Function("Make" + name + suffix.replace(" ", ""), Package("requests")))
            return pipeline.input(name + suffix, endpoint=endpoint, value_type=amount)

        def outgoing(source: Stream, suffix: str) -> None:
            endpoint = connector.endpoint(name + suffix, function=Function("Make" + name + suffix.replace(" ", ""), Package("requests")))
            pipeline.sink(name + suffix, endpoint=endpoint, value_type=amount, source=source)

        members: list[Stream]
        if kind in ("join", "multi-join"):
            keyed: list[Stream] = []
            for index in range(3 if kind == "multi-join" else 2):
                label = chr(ord("A") + index)
                keyed.append(pipeline.key_by(
                    name + " " + label + " Key", function=Function("Key" + label, Package("keys")),
                    key_type=identifier, value_type=amount, source=incoming(" " + label + " Request"),
                ))
            if kind == "join":
                combined = pipeline.join(name + " Combine", function=Function("Combine", Package("joins")),
                    value_type=amount, source=keyed[0], sources=keyed[1:], join_type=JoinType.INNER,
                    join_storage=JoinStorageType.HASH_MAP, ttl=60000, renew_ttl=True)
            else:
                combined = pipeline.multi_join(name + " Combine", function=Function("CombineMany", Package("joins")),
                    value_type=amount, source=keyed[0], sources=keyed[1:], join_storage=JoinStorageType.HASH_MAP, ttl=60000, renew_ttl=True)
            outgoing(combined, " Response")
            members = [*keyed, combined]
        else:
            request = incoming(" Request")
            if kind == "case":
                root = pipeline.case(name + " Route", function=Function("Route", Package("routing")), source=request)
                left = pipeline.when(name + " A When", value_type=amount, source=root)
                right = pipeline.when(name + " B When", value_type=amount, source=root)
                members = [root, left, right]
            else:
                root = pipeline.split(name + " Split", source=request)
                left = right = root
                members = [root]
            price = pipeline.map(name + " A Price", function=Function("Price", Package("processing")), value_type=amount, source=left)
            audit = pipeline.map(name + " B Audit", function=Function("Audit", Package("processing")), value_type=amount, source=right)
            outgoing(price, " A Response")
            outgoing(audit, " B Response")
            members.extend((price, audit))
        component.fragment(*members)
        if name == "Update":
            second_members = members

    def swap_ports() -> None:
        if kind in ("join", "multi-join"):
            combined = second_members[-1]
            if kind == "join":
                primary = combined.source
                if primary is None:
                    raise ValueError("Join fixture requires its primary source")
                combined.source, combined.sources = combined.sources[0], [primary]
            else:
                combined.sources = list(reversed(combined.sources))
        else:
            price, audit = second_members[-2:]
            price_function: object = price.properties["functionName"]
            audit_function: object = audit.properties["functionName"]
            if not isinstance(price_function, str) or not isinstance(audit_function, str):
                raise TypeError("Branch fixtures require explicit function names")
            price.properties["functionName"], audit.properties["functionName"] = audit_function, price_function

    return PortFixture(project, swap_ports)
