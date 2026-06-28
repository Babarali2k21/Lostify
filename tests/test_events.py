"""Phase 2 — Event model and serialization tests."""

import pytest

from shared.events import Event, EventType


class TestEventModel:
    def test_all_event_types_defined(self):
        expected = {
            "ItemCreated",
            "MatchFound",
            "ClaimCreated",
            "ClaimApproved",
            "ClaimRejected",
            "ItemRecovered",
        }
        actual = {t.value for t in EventType}
        assert actual == expected

    def test_event_to_dict_roundtrip(self):
        original = Event(
            event_type=EventType.MATCH_FOUND,
            payload={"lostItemId": 1, "foundItemId": 2, "title": "iPhone"},
            event_id="test-uuid-1234",
        )
        data = original.to_dict()
        restored = Event.from_dict(data)

        assert restored.event_id == "test-uuid-1234"
        assert restored.event_type == EventType.MATCH_FOUND
        assert restored.payload["lostItemId"] == 1
        assert restored.timestamp == original.timestamp

    def test_event_generates_unique_ids(self):
        e1 = Event(EventType.ITEM_CREATED, {"itemId": 1})
        e2 = Event(EventType.ITEM_CREATED, {"itemId": 2})
        assert e1.event_id != e2.event_id

    @pytest.mark.parametrize(
        "event_type,payload",
        [
            (EventType.ITEM_CREATED, {"itemId": 1, "itemType": "LOST", "title": "X", "ownerUserId": 1}),
            (EventType.MATCH_FOUND, {"lostItemId": 1, "foundItemId": 2, "title": "X"}),
            (EventType.CLAIM_CREATED, {"claimId": 1, "itemId": 2, "claimantUserId": 1}),
            (EventType.CLAIM_APPROVED, {"claimId": 1, "itemId": 2, "approvedBy": 2}),
            (EventType.CLAIM_REJECTED, {"claimId": 1, "itemId": 2, "rejectedBy": 2}),
            (EventType.ITEM_RECOVERED, {"itemId": 2, "claimId": 1, "recoveredBy": 1}),
        ],
    )
    def test_all_event_types_serialize(self, event_type, payload):
        event = Event(event_type=event_type, payload=payload)
        data = event.to_dict()
        assert data["eventType"] == event_type.value
        assert Event.from_dict(data).payload == payload
