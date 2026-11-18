from dataclasses import dataclass


@dataclass(slots=True)
class PublicationOutcome:
    EventID: str
    MessageID: str
    Accepted: bool
    Reason: str
