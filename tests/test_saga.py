"""Phase 3 — Saga pattern unit tests."""

import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
ITEM_SERVICE = str(ROOT / "item-service")
NOTIF_SERVICE = str(ROOT / "notification-service")

# Clear cached 'app' modules from other services (notification-service)
for name in list(sys.modules):
    if name == "app" or name.startswith("app."):
        del sys.modules[name]

for path in (NOTIF_SERVICE,):
    while path in sys.path:
        sys.path.remove(path)

sys.path.insert(0, ITEM_SERVICE)

database = importlib.import_module("app.database")
models = importlib.import_module("app.models")
saga = importlib.import_module("app.saga")
state_machine = importlib.import_module("app.state_machine")

Base = database.Base
Claim = models.Claim
ClaimStatus = models.ClaimStatus
Item = models.Item
ItemStatus = models.ItemStatus
ItemType = models.ItemType
ClaimRecoverySaga = saga.ClaimRecoverySaga
SagaStep = saga.SagaStep
ItemStateMachine = state_machine.ItemStateMachine


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_matched_pair(db):
    lost = Item(
        title="Lost wallet",
        description="Brown leather wallet",
        item_type=ItemType.LOST,
        status=ItemStatus.MATCHED,
        owner_user_id=1,
        matched_item_id=2,
    )
    found = Item(
        title="Found wallet",
        description="Brown wallet found",
        item_type=ItemType.FOUND,
        status=ItemStatus.MATCHED,
        owner_user_id=2,
        matched_item_id=1,
    )
    db.add_all([lost, found])
    db.commit()
    db.refresh(lost)
    db.refresh(found)
    found.matched_item_id = lost.id
    lost.matched_item_id = found.id
    db.commit()
    return lost, found


class TestClaimRecoverySaga:
    def test_submit_claim_reserves_item(self, db_session):
        lost, found = _seed_matched_pair(db_session)
        result = ClaimRecoverySaga.submit_claim(db_session, found, claimant_user_id=1)

        assert result.outcome == "in_progress"
        assert SagaStep.CREATE_CLAIM in result.steps
        assert SagaStep.RESERVE_ITEM in result.steps
        assert result.claim.status == ClaimStatus.PENDING
        assert result.item.status == ItemStatus.RESERVED
        assert db_session.get(Item, lost.id).status == ItemStatus.RESERVED

    def test_approve_completes_saga(self, db_session):
        _, found = _seed_matched_pair(db_session)
        submit = ClaimRecoverySaga.submit_claim(db_session, found, claimant_user_id=1)
        result = ClaimRecoverySaga.approve_claim(
            db_session, submit.claim, submit.item, approver_id=2
        )

        assert result.outcome == "completed"
        assert SagaStep.APPROVE_CLAIM in result.steps
        assert SagaStep.RECOVER_ITEM in result.steps
        assert result.claim.status == ClaimStatus.APPROVED
        assert result.item.status == ItemStatus.RECOVERED

    def test_reject_compensates_saga(self, db_session):
        lost, found = _seed_matched_pair(db_session)
        submit = ClaimRecoverySaga.submit_claim(db_session, found, claimant_user_id=1)
        result = ClaimRecoverySaga.reject_claim(
            db_session, submit.claim, submit.item, rejector_id=2
        )

        assert result.outcome == "compensated"
        assert SagaStep.REJECT_CLAIM in result.steps
        assert SagaStep.COMPENSATE_RELEASE in result.steps
        assert result.claim.status == ClaimStatus.REJECTED
        assert result.item.status == ItemStatus.MATCHED
        assert db_session.get(Item, lost.id).status == ItemStatus.MATCHED

    def test_cannot_claim_open_item(self, db_session):
        item = Item(
            title="Open item",
            description="Not matched yet",
            item_type=ItemType.LOST,
            status=ItemStatus.OPEN,
            owner_user_id=1,
        )
        db_session.add(item)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            ClaimRecoverySaga.submit_claim(db_session, item, claimant_user_id=2)
        assert exc.value.status_code == 400

    def test_invalid_item_transition_blocked(self, db_session):
        item = Item(
            title="Open",
            description="x",
            item_type=ItemType.LOST,
            status=ItemStatus.OPEN,
            owner_user_id=1,
        )
        with pytest.raises(HTTPException):
            ItemStateMachine.transition(item, ItemStatus.RECOVERED)

    def test_saga_status_awaiting_decision(self, db_session):
        _, found = _seed_matched_pair(db_session)
        submit = ClaimRecoverySaga.submit_claim(db_session, found, claimant_user_id=1)
        status = ClaimRecoverySaga.get_status(submit.claim, submit.item)
        assert status["sagaState"] == "AWAITING_DECISION"
        assert status["itemStatus"] == "RESERVED"

    def test_saga_status_completed(self, db_session):
        _, found = _seed_matched_pair(db_session)
        submit = ClaimRecoverySaga.submit_claim(db_session, found, claimant_user_id=1)
        ClaimRecoverySaga.approve_claim(db_session, submit.claim, submit.item, approver_id=2)
        status = ClaimRecoverySaga.get_status(submit.claim, submit.item)
        assert status["sagaState"] == "COMPLETED"
        assert "ClaimApproved" in status["notifications"]
        assert "ItemRecovered" in status["notifications"]

    def test_saga_status_compensated(self, db_session):
        _, found = _seed_matched_pair(db_session)
        submit = ClaimRecoverySaga.submit_claim(db_session, found, claimant_user_id=1)
        ClaimRecoverySaga.reject_claim(db_session, submit.claim, submit.item, rejector_id=2)
        status = ClaimRecoverySaga.get_status(submit.claim, submit.item)
        assert status["sagaState"] == "COMPENSATED"
