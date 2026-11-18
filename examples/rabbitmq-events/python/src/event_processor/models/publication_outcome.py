from dataclasses import dataclass

@dataclass(slots=True)
class PublicationOutcome:
    EventID: str
    Accepted: bool
    Reason: str
