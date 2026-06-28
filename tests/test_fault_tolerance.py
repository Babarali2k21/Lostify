"""Phase 7 — Fault tolerance tests."""

import importlib
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conftest import ITEM_URL, NOTIF_URL, REDIS_URL, USER_URL, requires_services
from shared.events import Event, EventBus, EventType

NOTIF_SERVICE = str(ROOT / "notification-service")
ITEM_SERVICE = str(ROOT / "item-service")


def _load_notification_consumer():
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    for path in (ITEM_SERVICE,):
        while path in sys.path:
            sys.path.remove(path)
    if NOTIF_SERVICE not in sys.path:
        sys.path.insert(0, NOTIF_SERVICE)
    return importlib.import_module("app.consumer"), importlib.import_module("app.database")


def _redis_available() -> bool:
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        return True
    except Exception:
        return False


class TestFaultToleranceUnit:
    def test_duplicate_event_not_processed_twice(self):
        consumer, database = _load_notification_consumer()
        engine = create_engine("sqlite:///:memory:")
        database.Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        event_id = f"fault-tolerance-{uuid.uuid4().hex}"
        event = Event(
            EventType.MATCH_FOUND,
            {"lostItemId": 1, "foundItemId": 2, "title": "Test"},
            event_id=event_id,
        )

        with patch.object(consumer, "SessionLocal", return_value=db):
            consumer.handle_event(event)
            consumer.handle_event(event)

        assert consumer.is_duplicate(db, event_id) is True
        db.close()

    def test_duplicate_publish_single_processed_count(self):
        if not _redis_available():
            pytest.skip("Redis not available")

        with httpx.Client(timeout=5.0) as client:
            if client.get(f"{NOTIF_URL}/health").status_code != 200:
                pytest.skip("Notification service not running")

        bus = EventBus(REDIS_URL)
        event_id = f"dup-fault-{uuid.uuid4().hex}"
        event = Event(
            EventType.CLAIM_CREATED,
            {"claimId": 99, "itemId": 1, "claimantUserId": 1},
            event_id=event_id,
        )
        bus.publish(event)
        time.sleep(0.5)
        bus.publish(event)
        time.sleep(1.0)

        with httpx.Client(timeout=5.0) as client:
            events = client.get(f"{NOTIF_URL}/events/processed").json()
            count = sum(1 for e in events if e["eventId"] == event_id)
            assert count == 1


@requires_services
@pytest.mark.integration
class TestFaultToleranceIntegration:
    def test_cannot_claim_open_item(self, client, two_users):
        token_a = two_users["a"]["token"]
        item = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": "Unmatched item",
                "description": "No match yet",
                "item_type": "LOST",
            },
        ).json()

        claim = client.post(
            f"{ITEM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": item["id"]},
        )
        assert claim.status_code == 400

    def test_cannot_approve_twice(self, client, two_users):
        token_a = two_users["a"]["token"]
        token_b = two_users["b"]["token"]

        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": "Lost watch",
                "description": "Lost watch near gym",
                "item_type": "LOST",
            },
        )
        found = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "title": "Found watch",
                "description": "Found watch near university gym",
                "item_type": "FOUND",
            },
        ).json()

        claim_id = client.post(
            f"{ITEM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": found["id"]},
        ).json()["id"]

        first = client.post(
            f"{ITEM_URL}/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert first.status_code == 200

        second = client.post(
            f"{ITEM_URL}/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert second.status_code == 400

    def test_wrong_user_cannot_approve(self, client, two_users):
        token_a = two_users["a"]["token"]
        token_b = two_users["b"]["token"]

        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": "Lost book",
                "description": "Lost book near hall",
                "item_type": "LOST",
            },
        )
        found = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "title": "Found book",
                "description": "Found book near university hall",
                "item_type": "FOUND",
            },
        ).json()

        claim_id = client.post(
            f"{ITEM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": found["id"]},
        ).json()["id"]

        forbidden = client.post(
            f"{ITEM_URL}/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert forbidden.status_code == 403
