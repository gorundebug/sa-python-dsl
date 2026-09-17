import unittest
from dataclasses import replace

from component_fixture import component_project


class ComponentSizeTests(unittest.TestCase):
    def test_large_fragments_validate_and_export_without_a_size_ceiling(self):
        project, service, pairs = component_project()
        component = service.component("Large Shared Business Operation")
        functions = [replace(pairs[0][0].function, name=f"SharedStage{index}") for index in range(300)]
        for first, last in pairs:
            continuations = [stream for stream in last.pipeline.streams.values() if stream.source is last]
            streams = []
            for index in range(300):
                stream = first.pipeline.map(
                    f"{first.name} Shared Stage {index}",
                    function=functions[index],
                    value_type=first.properties["valueType"],
                    source=streams[-1] if streams else last,
                )
                streams.append(stream)
            for continuation in continuations:
                continuation.source = streams[-1]
            component.fragment(*streams)

        self.assertEqual(project.validate(), [])
        exported = project.to_yaml()
        self.assertIn("Large Shared Business Operation", exported)
        for first, _ in pairs:
            self.assertIn(f"{first.name} Shared Stage 299", exported)


if __name__ == "__main__":
    unittest.main()
