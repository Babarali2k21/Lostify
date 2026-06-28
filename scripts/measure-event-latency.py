#!/usr/bin/env python3
"""Measure end-to-end event latency for Lostify demo/report."""

import os
import sys
import time
import uuid

import httpx

USER_URL = os.getenv("USER_URL", "http://localhost:8001")
ITEM_URL = os.getenv("ITEM_URL", "http://localhost:8002")
NOTIF_URL = os.getenv("NOTIF_URL", "http://localhost:8003")


def wait_for_event(client: httpx.Client, event_type: str, since: float, timeout: float = 5.0) -> float:
    deadline = since + timeout
    while time.perf_counter() < deadline:
        events = client.get(f"{NOTIF_URL}/events/processed").json()
        if any(e["eventType"] == event_type for e in events):
            return (time.perf_counter() - since) * 1000
        time.sleep(0.05)
    raise TimeoutError(f"{event_type} not seen within {timeout}s")


def main():
    uid = uuid.uuid4().hex[:8]
    password = "secret123"
    user_a, user_b = f"lat_a_{uid}", f"lat_b_{uid}"

    print("=== Lostify Event Latency Report ===\n")

    with httpx.Client(timeout=10.0) as client:
        for u in (user_a, user_b):
            client.post(
                f"{USER_URL}/register",
                json={"email": f"{u}@test.edu", "username": u, "password": password},
            )
        token_a = client.post(f"{USER_URL}/login", json={"username": user_a, "password": password}).json()["access_token"]
        token_b = client.post(f"{USER_URL}/login", json={"username": user_b, "password": password}).json()["access_token"]

        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"title": "Lost card", "description": "Lost id card near library", "item_type": "LOST"},
        )

        t0 = time.perf_counter()
        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"title": "Found card", "description": "Found id card near university library", "item_type": "FOUND"},
        )
        match_ms = wait_for_event(client, "MatchFound", t0)
        print(f"MatchFound latency:  {match_ms:7.1f} ms")

        found_id = client.get(f"{ITEM_URL}/items").json()[0]["id"]
        t1 = time.perf_counter()
        client.post(
            f"{ITEM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": found_id},
        )
        claim_ms = wait_for_event(client, "ClaimCreated", t1)
        print(f"ClaimCreated latency: {claim_ms:7.1f} ms")

        print(f"\nTotal async path (match + claim): {match_ms + claim_ms:.1f} ms")
        print("\nTypical local Docker: 50–500 ms per event")


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print("Services not running. Start with: docker compose up -d")
        sys.exit(1)
