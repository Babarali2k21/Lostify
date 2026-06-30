"""
Claim & Recovery Saga — orchestrates the distributed transaction
for submitting, approving, or rejecting a claim.

Pattern: Choreography (each step emits events; no central coordinator).
Compensation: RejectClaim → ReleaseItem (RESERVED → MATCHED).
"""

import logging
from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Claim, ClaimStatus, Item, ItemStatus
from .state_machine import (
    ClaimStateMachine,
    compensate_release_item,
    recover_item,
    reserve_item_for_claim,
)

logger = logging.getLogger(__name__)


class SagaStep(str, Enum):
    CREATE_CLAIM = "CreateClaim"
    RESERVE_ITEM = "ReserveItem"
    NOTIFY_CLAIM_CREATED = "NotifyClaimCreated"
    APPROVE_CLAIM = "ApproveClaim"
    RECOVER_ITEM = "RecoverItem"
    NOTIFY_CLAIM_APPROVED = "NotifyClaimApproved"
    NOTIFY_ITEM_RECOVERED = "NotifyItemRecovered"
    REJECT_CLAIM = "RejectClaim"
    COMPENSATE_RELEASE = "CompensateRelease"
    NOTIFY_CLAIM_REJECTED = "NotifyClaimRejected"


@dataclass
class SagaResult:
    claim: Claim
    item: Item
    steps: list[SagaStep]
    outcome: str  # "completed" | "compensated"


class ClaimRecoverySaga:
    """
    Saga state machines:

        Claim: PENDING → APPROVED | REJECTED
        Item:  OPEN → MATCHED → RESERVED → RECOVERED
                              ↘ (compensate) → MATCHED
    """

    @staticmethod
    def submit_claim(db: Session, item: Item, claimant_user_id: int) -> SagaResult:
        """Step 1–2: CreateClaim → ReserveItem"""
        if item.status != ItemStatus.MATCHED:
            raise HTTPException(
                status_code=400,
                detail=f"Item must be MATCHED to submit claim (current: {item.status.value})",
            )

        steps: list[SagaStep] = []

        claim = Claim(item_id=item.id, claimant_user_id=claimant_user_id)
        db.add(claim)
        db.commit()
        db.refresh(claim)
        steps.append(SagaStep.CREATE_CLAIM)
        logger.info("SAGA | CreateClaim | claimId=%s itemId=%s", claim.id, item.id)

        reserve_item_for_claim(db, item)
        db.refresh(item)
        steps.append(SagaStep.RESERVE_ITEM)
        logger.info("SAGA | ReserveItem | itemId=%s status=%s", item.id, item.status.value)

        return SagaResult(claim=claim, item=item, steps=steps, outcome="in_progress")

    @staticmethod
    def approve_claim(db: Session, claim: Claim, item: Item, approver_id: int) -> SagaResult:
        """Step 3–4: ApproveClaim → RecoverItem (happy path)"""
        if item.owner_user_id != approver_id:
            raise HTTPException(status_code=403, detail="Only item owner can approve claims")
        if claim.status != ClaimStatus.PENDING:
            raise HTTPException(status_code=400, detail="Claim is not PENDING")

        steps: list[SagaStep] = []

        ClaimStateMachine.transition(claim, ClaimStatus.APPROVED)
        steps.append(SagaStep.APPROVE_CLAIM)
        logger.info("SAGA | ApproveClaim | claimId=%s", claim.id)

        recover_item(db, item)
        db.refresh(item)
        steps.append(SagaStep.RECOVER_ITEM)
        logger.info("SAGA | RecoverItem | itemId=%s status=%s", item.id, item.status.value)

        db.commit()
        db.refresh(claim)
        return SagaResult(claim=claim, item=item, steps=steps, outcome="completed")

    @staticmethod
    def reject_claim(db: Session, claim: Claim, item: Item, rejector_id: int) -> SagaResult:
        """Step 3–4: RejectClaim → CompensateRelease (compensation path)"""
        if item.owner_user_id != rejector_id:
            raise HTTPException(status_code=403, detail="Only item owner can reject claims")
        if claim.status != ClaimStatus.PENDING:
            raise HTTPException(status_code=400, detail="Claim is not PENDING")

        steps: list[SagaStep] = []

        ClaimStateMachine.transition(claim, ClaimStatus.REJECTED)
        steps.append(SagaStep.REJECT_CLAIM)
        logger.info("SAGA | RejectClaim | claimId=%s", claim.id)

        compensate_release_item(db, item)
        db.refresh(item)
        steps.append(SagaStep.COMPENSATE_RELEASE)
        logger.info(
            "SAGA | CompensateRelease | itemId=%s status=%s (RESERVED → MATCHED)",
            item.id,
            item.status.value,
        )

        db.commit()
        db.refresh(claim)
        return SagaResult(claim=claim, item=item, steps=steps, outcome="compensated")

    @staticmethod
    def get_status(claim: Claim, item: Item) -> dict:
        """Return current saga state for demo/API visibility."""
        if claim.status == ClaimStatus.PENDING:
            saga_state = "AWAITING_DECISION"
        elif claim.status == ClaimStatus.APPROVED:
            saga_state = "COMPLETED"
        else:
            saga_state = "COMPENSATED"

        return {
            "sagaName": "ClaimRecoverySaga",
            "sagaState": saga_state,
            "claimId": claim.id,
            "claimStatus": claim.status.value,
            "itemId": item.id,
            "itemStatus": item.status.value,
            "matchedItemId": item.matched_item_id,
            "notifications": _notifications_for(claim, item),
            "steps": _steps_for(claim),
        }


def _steps_for(claim: Claim) -> list[str]:
    """Saga steps completed or in progress for this claim."""
    base = ["CreateClaim", "ReserveItem", "NotifyClaimCreated"]
    if claim.status == ClaimStatus.PENDING:
        return base + ["AwaitingDecision"]
    if claim.status == ClaimStatus.APPROVED:
        return base + [
            "ApproveClaim",
            "RecoverItem",
            "NotifyClaimApproved",
            "NotifyItemRecovered",
        ]
    if claim.status == ClaimStatus.REJECTED:
        return base + ["RejectClaim", "CompensateRelease", "NotifyClaimRejected"]
    return base


def _notifications_for(claim: Claim, item: Item) -> list[str]:
    """Events emitted to Notification Service during this saga."""
    if claim.status == ClaimStatus.PENDING:
        return ["ClaimCreated"]
    if claim.status == ClaimStatus.APPROVED:
        return ["ClaimApproved", "ItemRecovered"]
    if claim.status == ClaimStatus.REJECTED:
        return ["ClaimRejected"]
    return []
