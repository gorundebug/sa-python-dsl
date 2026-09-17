import unittest

from component_fixture import component_project
from sa_dsl import Appearance
from sa_dsl.model import Project, Service, Stream
from sa_dsl.validation import Diagnostic
from sa_dsl.component_validation import MatchLimit, _MatchBudget, _Part, _equivalent


class ComponentSemanticsTests(unittest.TestCase):
    def model(self) -> tuple[Project, Service, list[tuple[Stream, Stream]]]:
        project, service, fragments = component_project()
        component = service.component("Pricing")
        for members in fragments:
            component.fragment(*members)
        return project, service, fragments

    def diagnostics(self, project: Project) -> list[Diagnostic]:
        return [item for item in project.validate() if item.code.startswith("SA_COMPONENT_")]

    def test_display_metadata_and_member_order_do_not_change_identity(self) -> None:
        project, service, fragments = self.model()
        for stream in fragments[1]:
            stream.name += " Renamed"
            stream.appearance = Appearance(x=100, y=-20)
            stream.properties["functionDescription"] = "A different explanation"
        service.components["pricing"].fragments[1] = (tuple(reversed(fragments[1])), Appearance())
        self.assertEqual(self.diagnostics(project), [])

    def test_function_identity_and_type_changes_are_rejected(self) -> None:
        for field, value in [
            ("functionName", "OtherFunction"), ("functionPackage", "other/package"),
            ("functionModule", "otherModule"), ("functionInitializerGroup", "otherGroup"),
            ("publicFunction", True), ("valueType", "otherType"),
        ]:
            with self.subTest(field=field):
                project, _, fragments = self.model()
                fragments[1][0].properties[field] = value
                errors = self.diagnostics(project)
                self.assertEqual([item.code for item in errors], ["SA_COMPONENT_FRAGMENT_MISMATCH"])
                self.assertTrue(errors[0].path.endswith(".fragments[1]"))

    def test_explicit_default_call_equals_inherited(self) -> None:
        project, _, fragments = self.model()
        fragments[1][0].function_call(fragments[1][1], async_=False)
        self.assertEqual(self.diagnostics(project), [])

    def test_internal_and_incoming_call_policy_belong_to_component(self) -> None:
        for incoming in (False, True):
            with self.subTest(incoming=incoming):
                project, _, fragments = self.model()
                load, price = fragments[1]
                (load.source if incoming else load).parallel_call(load if incoming else price)
                self.assertEqual(self.diagnostics(project)[0].code, "SA_COMPONENT_FRAGMENT_MISMATCH")

    def test_outgoing_call_policy_belongs_to_receiver(self) -> None:
        project, service, fragments = self.model()
        sink = service.pipelines["update"].streams["updateResponse"]
        fragments[1][1].parallel_call(sink)
        self.assertEqual(self.diagnostics(project), [])

    def test_disconnected_fragment_is_rejected(self) -> None:
        project, _, fragments = self.model()
        fragments[1][1].source = None
        self.assertEqual(self.diagnostics(project)[0].code, "SA_COMPONENT_INVALID_FRAGMENT")

    def test_split_consumer_order_is_not_a_component_contract(self) -> None:
        from sa_dsl import Function, Package
        from sa_dsl.component_validation import _ServiceGraph
        from sa_dsl.validation import Validator

        project, service, fragments = self.model()
        branches: list[tuple[Stream, Stream, Stream]] = []
        for load, price in fragments:
            load.type = "Split"
            load.function = None
            for key in list(load.properties):
                if key.startswith("function"):
                    del load.properties[key]
            other = load.pipeline.map(load.name + " Other", function=Function("Other", Package("pricing")), value_type=project.types["amount"], source=load)
            price.source = load
            branches.append((load, price, other))
        pipeline = branches[1][0].pipeline
        pipeline.streams = dict(reversed(list(pipeline.streams.items())))
        graph = _ServiceGraph(service, Validator(project).output_wire_type)
        self.assertTrue(_equivalent(graph.part(branches[0]), graph.part(branches[1]), _MatchBudget(500_000)))

    def test_direction_and_boundary_ports_are_not_ignored(self) -> None:
        project, _, fragments = self.model()
        load, price = fragments[1]
        price.source = load.source
        load.source = price
        self.assertEqual(self.diagnostics(project)[0].code, "SA_COMPONENT_FRAGMENT_MISMATCH")

    def test_mutated_overlapping_membership_is_diagnosed(self) -> None:
        project, service, fragments = self.model()
        service.components["pricing"].fragments[1] = (fragments[0], Appearance())
        self.assertEqual(self.diagnostics(project)[0].code, "SA_COMPONENT_INVALID_MEMBERSHIP")

    def test_matcher_does_not_accept_equal_degree_nonisomorphic_graphs(self) -> None:
        def graph(pairs: list[tuple[int, int]]) -> _Part:
            return _Part({node: "same" for node in range(6)},
                         {edge: ("edge",) for a, b in pairs for edge in [(a, b), (b, a)]})
        bipartite = graph([(a, b) for a in range(3) for b in range(3, 6)])
        prism = graph([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3), (1, 4), (2, 5)])
        self.assertFalse(_equivalent(bipartite, prism, _MatchBudget(500_000)))
        self.assertTrue(_equivalent(prism, prism, _MatchBudget(500_000)))
        with self.assertRaises(MatchLimit):
            _equivalent(prism, prism, _MatchBudget(0))


if __name__ == "__main__":
    unittest.main()
