from dataclasses import dataclass


@dataclass(slots=True)
class Event:
    ID: str
    Value: str
