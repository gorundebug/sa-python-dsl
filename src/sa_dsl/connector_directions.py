"""Offline builtin direction policy projected from authoritative language packs."""
from functools import lru_cache
import json
from importlib.resources import files

@lru_cache(maxsize=1)
def direction_capabilities() -> dict:
    return json.loads(files('sa_dsl').joinpath('connector_directions.generated.json').read_text(encoding='utf-8'))

def unsupported_direction(language: str, protocol: str, direction: str) -> str | None:
    for target in direction_capabilities()['languages']:
        if language not in (target['name'], target['backend'], str(target['id'])):
            continue
        feature = target['connectors'].get(protocol, {}).get(direction)
        if feature is not None and not feature['supported']:
            return feature.get('reason') or f'{protocol} {direction} is unsupported for {language}'
    return None
