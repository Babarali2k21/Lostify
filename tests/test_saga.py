"""Phase 3 — Saga pattern unit tests."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
ITEM_SERVICE = str(ROOT / "item-service")
CLAIM_SERVICE = str(ROOT / "claim-recovery-service")
NOTIF_SERVICE = str(ROOT / "notification-service")


def _clear_app_modules():
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]


def _load_item_modules():
    _clear_app_modules()
    for path in (CLAIM_SERVICE, NOTIF_SERVICE):
        while path in sys.path:
            sys.path.remove(path)
    if ITEM_SERVICE not in sys.path:
        sys.path.insert(0, ITEM_SERVICE)
    database = importlib.import_module("app.database")
    models = importlib.import_module("app.models")
    state_machine = importlib.import_module("app.state_machine")
    return database, models, state_machine


def _load_claim_modules():
    _clear_app_modules()
    for path in (ITEM_SERVICE, NOTIF_SERVICE):
        while path in sys.path:
            sys.path.remove(path)
    if CLAIM_SERVICE not in sys.path:
        sys.path.insert(0, CLAIM_SERVICE)
    database = importlib.import_module("app.database")
    models = importlib.import_module("app.models")
    saga = importlib.import_module("app.saga")
    return database, models, saga


@pytest.fixture
def item_db_session():
    database, models, _ = _load_item_modules()
    engine = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, models
    session.close()


@pytest.fixture
def claim_db_session():
    database, models, saga = _load_claim_modules()
    engine = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, models, saga
    session.close()


class TestItemStateMachine:
    def test_invalid_item_transition_blocked(self, item_db_session):
        _, models = item_db_session
        _, _, state_machine = _load_item_modules()
        Item = models.Item
        ItemType = models.ItemType
        ItemStatus = models.ItemStatus
        ItemStateMachine = state_machine.ItemStateMachine

        item = Item(
            title="Open",
            description="x",
            item_type=ItemType.LOST,
            status=ItemStatus.OPEN,
            owner_user_id=1,
        )
        with pytest.raises(HTTPException):
            ItemStateMachine.transition(item, ItemStatus.RECOVERED)


class TestClaimRecoverySaga:
    def _matched_item(self, item_id=2, owner=2, matched_id=1):
        return {
            "id": item_id,
            "status": "MATCHED",
            "owner_user_id": owner,
            "matched_item_id": matched_id,
            "title": "Found wallet",
            "description": "Brown wallet",
            "item_type": "FOUND",
        }

    def test_submit_claim_reserves_item(self, claim_db_session):
        db, models, saga = claim_db_session
        ClaimStatus = models.ClaimStatus
        ItemStatus = type("ItemStatus", (), {"RESERVED": "RESERVED"})()
        ClaimRecoverySaga = saga.ClaimRecoverySaga
        SagaStep = saga.SagaStep

        matched = self._matched_item()
        reserved = {**matched, "status": "RESERVED"}

        with patch.object(saga.item_client, "get_item", return_value=matched), patch.object(
            saga.item_client, "reserve_item", return_value=reserved
        ):
            result = ClaimRecoverySaga.submit_claim(db, item_id=2, claimant_user_id=1)

        assert result.outcome == "in_progress"
        assert SagaStep.CREATE_CLAIM in result.steps
        assert SagaStep.RESERVE_ITEM in result.steps
        assert result.claim.status == ClaimStatus.PENDING
        assert result.item["status"] == ItemStatus.RESERVED

    def test_approve_completes_saga(self, claim_db_session):
        db, models, saga = claim_db_session
        Claim = models.Claim
        ClaimStatus = models.ClaimStatus
        ClaimRecoverySaga = saga.ClaimRecoverySaga
        SagaStep = saga.SagaStep

        claim = Claim(item_id=2, claimant_user_id=1, status=ClaimStatus.PENDING)
        db.add(claim)
        db.commit()
        db.refresh(claim)

        matched = self._matched_item()
        recovered = {**matched, "status": "RECOVERED"}

        with patch.object(saga.item_client, "get_item", return_value=matched), patch.object(
            saga.item_client, "recover_item", return_value=recovered
        ):
            result = ClaimRecoverySaga.approve_claim(db, claim, approver_id=2)

        assert result.outcome == "completed"
        assert SagaStep.APPROVE_CLAIM in result.steps
        assert SagaStep.RECOVER_ITEM in result.steps
        assert result.claim.status == ClaimStatus.APPROVED
        assert result.item["status"] == "RECOVERED"

    def test_reject_compensates_saga(self, claim_db_session):
        db, models, saga = claim_db_session
        Claim = models.Claim
        ClaimStatus = models.ClaimStatus
        ClaimRecoverySaga = saga.ClaimRecoverySaga
        SagaStep = saga.SagaStep

        claim = Claim(item_id=2, claimant_user_id=1, status=ClaimStatus.PENDING)
        db.add(claim)
        db.commit()
        db.refresh(claim)

        reserved = {**self._matched_item(), "status": "RESERVED"}
        released = {**self._matched_item(), "status": "MATCHED"}

        with patch.object(saga.item_client, "get_item", return_value=reserved), patch.object(
            saga.item_client, "release_item", return_value=released
        ):
            result = ClaimRecoverySaga.reject_claim(db, claim, rejector_id=2)

        assert result.outcome == "compensated"
        assert SagaStep.REJECT_CLAIM in result.steps
        assert SagaStep.COMPENSATE_RELEASE in result.steps
        assert result.claim.status == ClaimStatus.REJECTED
        assert result.item["status"] == "MATCHED"

    def test_cannot_claim_open_item(self, claim_db_session):
        db, _, saga = claim_db_session
        ClaimRecoverySaga = saga.ClaimRecoverySaga

        with patch.object(
            saga.item_client,
            "get_item",
            return_value={**self._matched_item(item_id=1), "status": "OPEN"},
        ):
            with pytest.raises(HTTPException) as exc:
                ClaimRecoverySaga.submit_claim(db, item_id=1, claimant_user_id=2)
        assert exc.value.status_code == 400

    def test_saga_status_awaiting_decision(self, claim_db_session):
        db, models, saga = claim_db_session
        Claim = models.Claim
        ClaimStatus = models.ClaimStatus
        ClaimRecoverySaga = saga.ClaimRecoverySaga

        claim = Claim(item_id=2, claimant_user_id=1, status=ClaimStatus.PENDING)
        item = {**self._matched_item(), "status": "RESERVED"}
        status = ClaimRecoverySaga.get_status(claim, item)
        assert status["sagaState"] == "AWAITING_DECISION"
        assert status["itemStatus"] == "RESERVED"

    def test_saga_status_completed(self, claim_db_session):
        db, models, saga = claim_db_session
        Claim = models.Claim
        ClaimStatus = models.ClaimStatus
        ClaimRecoverySaga = saga.ClaimRecoverySaga

        claim = Claim(item_id=2, claimant_user_id=1, status=ClaimStatus.APPROVED)
        item = {**self._matched_item(), "status": "RECOVERED"}
        status = ClaimRecoverySaga.get_status(claim, item)
        assert status["sagaState"] == "COMPLETED"
        assert "ClaimApproved" in status["notifications"]
        assert "ItemRecovered" in status["notifications"]

    def test_saga_status_compensated(self, claim_db_session):
        db, models, saga = claim_db_session
        Claim = models.Claim
        ClaimStatus = models.ClaimStatus
        ClaimRecoverySaga = saga.ClaimRecoverySaga

        claim = Claim(item_id=2, claimant_user_id=1, status=ClaimStatus.REJECTED)
        item = {**self._matched_item(), "status": "MATCHED"}
        status = ClaimRecoverySaga.get_status(claim, item)
        assert status["sagaState"] == "COMPENSATED"
