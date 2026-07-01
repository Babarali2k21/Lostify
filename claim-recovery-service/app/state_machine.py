import logging

from fastapi import HTTPException

from .models import Claim, ClaimStatus

logger = logging.getLogger(__name__)


class ClaimStateMachine:
    """Claim lifecycle: PENDING → APPROVED | REJECTED"""

    VALID_TRANSITIONS = {
        ClaimStatus.PENDING: {ClaimStatus.APPROVED, ClaimStatus.REJECTED},
        ClaimStatus.APPROVED: set(),
        ClaimStatus.REJECTED: set(),
    }

    @classmethod
    def transition(cls, claim: Claim, new_status: ClaimStatus) -> None:
        allowed = cls.VALID_TRANSITIONS.get(claim.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid claim transition: {claim.status.value} → {new_status.value}",
            )
        old = claim.status
        claim.status = new_status
        logger.info("Claim %s state: %s → %s", claim.id, old.value, new_status.value)
