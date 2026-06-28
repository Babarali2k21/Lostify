import logging
import re

from sqlalchemy.orm import Session

from .models import Item, ItemStatus, ItemType

logger = logging.getLogger(__name__)


def _keywords(text: str) -> set[str]:
    """Extract meaningful keywords for simple matching."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    stopwords = {"the", "a", "an", "and", "or", "is", "was", "my", "in", "on", "at"}
    return {w for w in words if len(w) > 2 and w not in stopwords}


def find_match(db: Session, new_item: Item) -> Item | None:
    """
    Simple keyword overlap matching:
    - LOST item looks for OPEN FOUND items
    - FOUND item looks for OPEN LOST items
    """
    if new_item.item_type == ItemType.LOST:
        candidates = (
            db.query(Item)
            .filter(
                Item.item_type == ItemType.FOUND,
                Item.status == ItemStatus.OPEN,
            )
            .all()
        )
    else:
        candidates = (
            db.query(Item)
            .filter(
                Item.item_type == ItemType.LOST,
                Item.status == ItemStatus.OPEN,
            )
            .all()
        )

    new_kw = _keywords(f"{new_item.title} {new_item.description}")
    if not new_kw:
        return None

    best: Item | None = None
    best_score = 0

    for candidate in candidates:
        cand_kw = _keywords(f"{candidate.title} {candidate.description}")
        overlap = len(new_kw & cand_kw)
        if overlap > best_score:
            best_score = overlap
            best = candidate

    if best and best_score >= 1:
        logger.info(
            "Match candidate found: new_item=%s matched_item=%s score=%s",
            new_item.id,
            best.id,
            best_score,
        )
        return best

    return None


def apply_match(db: Session, item_a: Item, item_b: Item) -> None:
    """Mark both items as MATCHED and link them."""
    item_a.status = ItemStatus.MATCHED
    item_b.status = ItemStatus.MATCHED
    item_a.matched_item_id = item_b.id
    item_b.matched_item_id = item_a.id
    db.commit()
    logger.info("Items matched: %s <-> %s", item_a.id, item_b.id)
