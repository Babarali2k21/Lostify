import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    ITEM_CREATED = "ItemCreated"
    MATCH_FOUND = "MatchFound"
    CLAIM_CREATED = "ClaimCreated"
    CLAIM_APPROVED = "ClaimApproved"
    CLAIM_REJECTED = "ClaimRejected"
    ITEM_RECOVERED = "ItemRecovered"


class Event:
    def __init__(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        event_id: str | None = None,
    ):
        self.event_id = event_id or str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        event = cls(
            event_type=EventType(data["eventType"]),
            payload=data["payload"],
            event_id=data["eventId"],
        )
        event.timestamp = data.get("timestamp", event.timestamp)
        return event
