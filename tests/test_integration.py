"""Phase 7 — Integration tests (require Docker Compose stack)."""

import httpx
import pytest

from conftest import ITEM_URL, NOTIF_URL, USER_URL, requires_services


@requires_services
@pytest.mark.integration
class TestIntegrationHappyPath:
    def test_full_demo_flow(self, client, two_users):
        token_a = two_users["a"]["token"]
        token_b = two_users["b"]["token"]

        lost = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": "Lost laptop",
                "description": "Lost silver laptop near campus library",
                "item_type": "LOST",
            },
        )
        assert lost.status_code == 201
        assert lost.json()["status"] == "OPEN"

        found = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "title": "Found laptop",
                "description": "Found silver laptop near university library",
                "item_type": "FOUND",
            },
        )
        assert found.status_code == 201
        found_body = found.json()
        assert found_body["status"] == "MATCHED"
        found_id = found_body["id"]

        claim = client.post(
            f"{ITEM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": found_id},
        )
        assert claim.status_code == 201
        claim_id = claim.json()["id"]

        saga = client.get(f"{ITEM_URL}/claims/{claim_id}/saga")
        if saga.status_code == 404:
            pytest.skip("Saga endpoint not deployed — rebuild: docker compose up --build -d item-service")
        assert saga.status_code == 200
        assert saga.json()["sagaState"] == "AWAITING_DECISION"
        assert saga.json()["itemStatus"] == "RESERVED"

        approved = client.post(
            f"{ITEM_URL}/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"

        final_saga = client.get(f"{ITEM_URL}/claims/{claim_id}/saga")
        if final_saga.status_code == 200:
            body = final_saga.json()
            assert body["sagaState"] == "COMPLETED"
            assert body["itemStatus"] == "RECOVERED"

        events = client.get(f"{NOTIF_URL}/events/processed").json()
        event_types = {e["eventType"] for e in events}
        for expected in ("MatchFound", "ClaimCreated", "ClaimApproved", "ItemRecovered"):
            assert expected in event_types


@requires_services
@pytest.mark.integration
class TestIntegrationRejectPath:
    def test_reject_compensates_item(self, client, two_users):
        token_a = two_users["a"]["token"]
        token_b = two_users["b"]["token"]

        client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "title": "Lost umbrella",
                "description": "Lost red umbrella near cafeteria",
                "item_type": "LOST",
            },
        )
        found = client.post(
            f"{ITEM_URL}/items",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "title": "Found umbrella",
                "description": "Found red umbrella near university cafeteria",
                "item_type": "FOUND",
            },
        ).json()
        found_id = found["id"]

        claim = client.post(
            f"{ITEM_URL}/claims",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"item_id": found_id},
        ).json()
        claim_id = claim["id"]

        rejected = client.post(
            f"{ITEM_URL}/claims/{claim_id}/reject",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"

        saga_resp = client.get(f"{ITEM_URL}/claims/{claim_id}/saga")
        if saga_resp.status_code == 200:
            saga = saga_resp.json()
            assert saga["sagaState"] == "COMPENSATED"
            assert saga["itemStatus"] == "MATCHED"

        item = client.get(f"{ITEM_URL}/items/{found_id}").json()
        assert item["status"] == "MATCHED"
