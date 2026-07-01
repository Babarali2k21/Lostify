"""
Claim & Recovery Saga — orchestrates the distributed transaction
across Claim/Recovery Service and Item Service.

Compensation: RejectClaim → ReleaseItem (RESERVED → MATCHED).
"""

import logging
from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .item_client import item_client
from .models import Claim, ClaimStatus
from .state_machine import ClaimStateMachine

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
    item: dict
    steps: list[SagaStep]
    outcome: str  # "completed" | "compensated" | "in_progress"


class ClaimRecoverySaga:
    @staticmethod
    def submit_claim(db: Session, item_id: int, claimant_user_id: int) -> SagaResult:
        item = item_client.get_item(item_id)
        if item["status"] != "MATCHED":
            raise HTTPException(
                status_code=400,
                detail=f"Item must be MATCHED to submit claim (current: {item['status']})",
            )

        steps: list[SagaStep] = []
        claim = Claim(item_id=item_id, claimant_user_id=claimant_user_id)
        db.add(claim)
        db.commit()
        db.refresh(claim)
        steps.append(SagaStep.CREATE_CLAIM)
        logger.info("SAGA | CreateClaim | claimId=%s itemId=%s", claim.id, item_id)

        item = item_client.reserve_item(item_id)
        steps.append(SagaStep.RESERVE_ITEM)
        logger.info("SAGA | ReserveItem | itemId=%s status=%s", item_id, item["status"])

        return SagaResult(claim=claim, item=item, steps=steps, outcome="in_progress")

    @staticmethod
    def approve_claim(db: Session, claim: Claim, approver_id: int) -> SagaResult:
        item = item_client.get_item(claim.item_id)
        if item["owner_user_id"] != approver_id:
            raise HTTPException(status_code=403, detail="Only item owner can approve claims")
        if claim.status != ClaimStatus.PENDING:
            raise HTTPException(status_code=400, detail="Claim is not PENDING")

        steps: list[SagaStep] = []
        ClaimStateMachine.transition(claim, ClaimStatus.APPROVED)
        steps.append(SagaStep.APPROVE_CLAIM)
        logger.info("SAGA | ApproveClaim | claimId=%s", claim.id)

        item = item_client.recover_item(claim.item_id)
        steps.append(SagaStep.RECOVER_ITEM)
        logger.info("SAGA | RecoverItem | itemId=%s status=%s", claim.item_id, item["status"])

        db.commit()
        db.refresh(claim)
        return SagaResult(claim=claim, item=item, steps=steps, outcome="completed")

    @staticmethod
    def reject_claim(db: Session, claim: Claim, rejector_id: int) -> SagaResult:
        item = item_client.get_item(claim.item_id)
        if item["owner_user_id"] != rejector_id:
            raise HTTPException(status_code=403, detail="Only item owner can reject claims")
        if claim.status != ClaimStatus.PENDING:
            raise HTTPException(status_code=400, detail="Claim is not PENDING")

        steps: list[SagaStep] = []
        ClaimStateMachine.transition(claim, ClaimStatus.REJECTED)
        steps.append(SagaStep.REJECT_CLAIM)
        logger.info("SAGA | RejectClaim | claimId=%s", claim.id)

        item = item_client.release_item(claim.item_id)
        steps.append(SagaStep.COMPENSATE_RELEASE)
        logger.info(
            "SAGA | CompensateRelease | itemId=%s status=%s (RESERVED → MATCHED)",
            claim.item_id,
            item["status"],
        )

        db.commit()
        db.refresh(claim)
        return SagaResult(claim=claim, item=item, steps=steps, outcome="compensated")

    @staticmethod
    def get_status(claim: Claim, item: dict) -> dict:
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
            "itemId": item["id"],
            "itemStatus": item["status"],
            "matchedItemId": item.get("matched_item_id"),
            "notifications": _notifications_for(claim),
            "steps": _steps_for(claim),
        }


def _steps_for(claim: Claim) -> list[str]:
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


def _notifications_for(claim: Claim) -> list[str]:
    if claim.status == ClaimStatus.PENDING:
        return ["ClaimCreated"]
    if claim.status == ClaimStatus.APPROVED:
        return ["ClaimApproved", "ItemRecovered"]
    if claim.status == ClaimStatus.REJECTED:
        return ["ClaimRejected"]
    return []
