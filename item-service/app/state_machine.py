import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Claim, ClaimStatus, Item, ItemStatus

logger = logging.getLogger(__name__)


class ItemStateMachine:
    """Item lifecycle: OPEN → MATCHED → RESERVED → RECOVERED"""

    VALID_TRANSITIONS = {
        ItemStatus.OPEN: {ItemStatus.MATCHED},
        ItemStatus.MATCHED: {ItemStatus.RESERVED},
        ItemStatus.RESERVED: {ItemStatus.RECOVERED, ItemStatus.MATCHED},
        ItemStatus.RECOVERED: set(),
    }

    @classmethod
    def transition(cls, item: Item, new_status: ItemStatus) -> None:
        allowed = cls.VALID_TRANSITIONS.get(item.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition: {item.status.value} → {new_status.value}",
            )
        old = item.status
        item.status = new_status
        logger.info("Item %s state: %s → %s", item.id, old.value, new_status.value)


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


def reserve_item_for_claim(db: Session, item: Item) -> None:
    ItemStateMachine.transition(item, ItemStatus.RESERVED)
    if item.matched_item_id:
        matched = db.get(Item, item.matched_item_id)
        if matched:
            ItemStateMachine.transition(matched, ItemStatus.RESERVED)
    db.commit()


def recover_item(db: Session, item: Item) -> None:
    ItemStateMachine.transition(item, ItemStatus.RECOVERED)
    if item.matched_item_id:
        matched = db.get(Item, item.matched_item_id)
        if matched:
            ItemStateMachine.transition(matched, ItemStatus.RECOVERED)
    db.commit()


def compensate_release_item(db: Session, item: Item) -> None:
    """Saga compensation: RESERVED → MATCHED on claim rejection."""
    if item.status != ItemStatus.RESERVED:
        raise HTTPException(status_code=400, detail="Item is not RESERVED")
    ItemStateMachine.transition(item, ItemStatus.MATCHED)
    if item.matched_item_id:
        matched = db.get(Item, item.matched_item_id)
        if matched and matched.status == ItemStatus.RESERVED:
            ItemStateMachine.transition(matched, ItemStatus.MATCHED)
    db.commit()
    logger.info("Compensation applied: item %s released back to MATCHED", item.id)
