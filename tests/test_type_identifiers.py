import unittest

from sa_dsl import Project
from sa_dsl.model import Service
from sa_dsl.type_identifier_validation import validate_type_identifiers
from sa_dsl.validation import Validator


class TypeIdentifierTests(unittest.TestCase):
    def test_go_names_are_not_silently_camel_cased(self) -> None:
        for name in ("Price Compare Cache Request", "1Request", "type", "_"):
            with self.subTest(name=name):
                project = Project("Types")
                project.services["service"] = Service("service", "Service", "GoLang", "example.com/service")
                value = project.struct_type("Candidate")
                value.name = name
                validator = Validator(project)
                validate_type_identifiers(validator)
                diagnostic, = validator.values
                self.assertEqual(diagnostic.code, "SG_SEMANTIC_INVALID_IDENTIFIER")
                self.assertEqual(diagnostic.path, f"$.types.{value.key}.name")

    def test_legal_go_identifiers_and_unaliased_primitive_display_names(self) -> None:
        project = Project("Types")
        project.services["service"] = Service("service", "Service", "GoLang", "example.com/service")
        project.struct_type("PriceCompareCacheRequest")
        project.struct_type("UnicodeName").name = "Стоимость"
        project.string_type("Display Name", use_alias=False)
        validator = Validator(project)
        validate_type_identifiers(validator)
        self.assertEqual(validator.values, [])

    def test_other_language_does_not_inherit_go_keyword_restrictions(self) -> None:
        project = Project("Types")
        project.services["service"] = Service("service", "Service", "Python", "example.com/service")
        project.struct_type("defer")
        validator = Validator(project)
        validate_type_identifiers(validator)
        self.assertEqual(validator.values, [])


if __name__ == "__main__":
    unittest.main()
