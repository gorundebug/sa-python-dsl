"""Input shared by the seven callable storage examples."""
from dataclasses import dataclass

@dataclass(slots=True)
class StorageRequest:
    request_id: str
    key: str
    value: bytes = b""
