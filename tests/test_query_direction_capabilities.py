"""Query direction is declared by the packs and projected for offline agents."""
import pytest

from sa_dsl.connector_directions import direction_capabilities, unsupported_direction
from tests.test_query_authoring import PROFILES, fixture


@pytest.mark.parametrize('profile,language,_id', PROFILES)
def test_storage_direction_policy_matches_typed_model(profile, language, _id):
    project, connector, _, query = fixture(profile, language)
    target = query.service.programming_language
    assert unsupported_direction(target, connector.type, 'query') is None
    assert unsupported_direction(target, connector.type, 'source')
    assert unsupported_direction(target, connector.type, 'sink')
    assert project.validate() == []
    query.type = 'Sink'
    assert any(error.details.get('direction') == 'sink' for error in project.validate())


def test_each_projected_connector_declares_query_without_inventing_sink_support():
    storage_count = 0
    for language in direction_capabilities()['languages']:
        for name, features in language['connectors'].items():
            storage = name.startswith(('PostgreSQL', 'S3'))
            assert features['query']['supported'] is storage
            if storage:
                storage_count += 1
                assert features['source']['supported'] is False
                assert features['sink']['supported'] is False
    assert storage_count == 12
