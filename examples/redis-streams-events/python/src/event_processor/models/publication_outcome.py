from dataclasses import dataclass


@dataclass(slots=True)
class PublicationOutcome:
    EventID: str
    EntryID: str
    Accepted: bool
    Reason: str
