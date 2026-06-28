#!/usr/bin/env python3
"""
Phase 2 — Duplicate event demo.

Publishes the same event twice with identical eventId.
The notification service should process it once and ignore the duplicate.

Usage (with docker compose running):
    pip install -r tests/requirements.txt   # once, if redis missing
    python3 scripts/test_duplicate_events.py
"""

import json
import os
import sys
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

try:
    from shared.events import Event, EventBus, EventType  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name == "redis":
        print("Missing 'redis' package. Run: pip install -r tests/requirements.txt")
    raise

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
NOTIF_URL = os.getenv("NOTIF_URL", "http://localhost:8003")


def count_processed(event_id: str) -> int:
    with urllib.request.urlopen(f"{NOTIF_URL}/events/processed") as resp:
        events = json.loads(resp.read())
    return sum(1 for e in events if e["eventId"] == event_id)


def main():
    bus = EventBus(REDIS_URL)
    event = Event(
        event_type=EventType.MATCH_FOUND,
        payload={"lostItemId": 99, "foundItemId": 100, "title": "Duplicate Test"},
        event_id="duplicate-demo-event-id",
    )

    print("=== Phase 2: Duplicate Event Test ===\n")
    print(f"Publishing event: eventId={event.event_id}")

    bus.publish(event)
    time.sleep(1)
    bus.publish(event)  # same eventId — should be ignored
    time.sleep(1)

    count = count_processed(event.event_id)
    print(f"\nProcessed count for eventId '{event.event_id}': {count}")

    if count == 1:
        print("✅ PASS — Duplicate event was correctly ignored")
    else:
        print(f"❌ FAIL — Expected 1 processed event, got {count}")
        sys.exit(1)

    print("\nCheck logs: docker compose logs notification-service | grep -i duplicate")


if __name__ == "__main__":
    main()
