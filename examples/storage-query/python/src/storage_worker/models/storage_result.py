"""Application data and explicit successful completion use the same output."""
from dataclasses import dataclass

@dataclass(slots=True)
class StorageResult:
    request_id: str
    kind: str
    value: bytes = b""
