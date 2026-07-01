"""Phase 7 — Event latency measurement."""

import time
import uuid

import httpx
import pytest

from conftest import CLAIM_URL, ITEM_URL, NOTIF_URL, requires_services

MAX_LATENCY_MS = 5000  # 5 seconds — generous for local Docker


@requires_services
@pytest.mark.integration
@pytest.mark.latency
class TestEventLatency:
    def test_match_found_latency(self, client, two_users):
        """Measure time from FOUND item creation to MatchFound event processed."""
        token_a = two_users["a"]["token"]
        token_b = two_users["b"]["token"]

        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": "Lost phone",
                "description": "Lost black phone near library",
                "item_type": "LOST",
            },
        )

        before = time.perf_counter()
        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "title": "Found phone",
                "description": "Found black phone near university library",
                "item_type": "FOUND",
            },
        )

        latency_ms = _wait_for_event(client, "MatchFound", before)
        print(f"\nMatchFound latency: {latency_ms:.1f} ms")
        assert latency_ms < MAX_LATENCY_MS

    def test_claim_created_latency(self, client, two_users):
        token_a = two_users["a"]["token"]
        token_b = two_users["b"]["token"]

        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": f"Lost bag {uuid.uuid4().hex[:6]}",
                "description": "Lost bag near parking",
                "item_type": "LOST",
            },
        )
        found_id = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "title": "Found bag",
                "description": "Found bag near university parking",
                "item_type": "FOUND",
            },
        ).json()["id"]

        before = time.perf_counter()
        client.post(
            f"{CLAIM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": found_id},
        )

        latency_ms = _wait_for_event(client, "ClaimCreated", before)
        print(f"\nClaimCreated latency: {latency_ms:.1f} ms")
        assert latency_ms < MAX_LATENCY_MS


def _wait_for_event(client: httpx.Client, event_type: str, since: float) -> float:
    deadline = since + (MAX_LATENCY_MS / 1000)
    while time.perf_counter() < deadline:
        events = client.get(f"{NOTIF_URL}/events/processed").json()
        matching = [e for e in events if e["eventType"] == event_type]
        if matching:
            elapsed_ms = (time.perf_counter() - since) * 1000
            return elapsed_ms
        time.sleep(0.05)
    pytest.fail(f"Event {event_type} not processed within {MAX_LATENCY_MS}ms")
