import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from shared.events import Event, EventBus, EventType

from .auth import get_current_user_id
from .config import REDIS_URL
from .database import Base, engine, get_db
from .matching import apply_match, find_match
from .models import Claim, Item, ItemType
from .schemas import ClaimCreate, ClaimResponse, ItemCreate, ItemResponse
from .saga import ClaimRecoverySaga
from .saga_schemas import SagaStatusResponse
from .step_functions import get_aws_sync_status, trigger_claim_saga

logger = logging.getLogger(__name__)

app = FastAPI(title="Lostify Item Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
event_bus = EventBus(REDIS_URL)


def publish(event_type: EventType, payload: dict) -> None:
    event_bus.publish(Event(event_type=event_type, payload=payload))


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Item Service started — database initialized")


@app.get("/health")
def health():
    return {"status": "ok", "service": "item-service"}


@app.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = Item(
        title=payload.title,
        description=payload.description,
        item_type=payload.item_type,
        owner_user_id=user_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info("Item created: id=%s type=%s title=%s", item.id, item.item_type, item.title)

    publish(
        EventType.ITEM_CREATED,
        {
            "itemId": item.id,
            "itemType": item.item_type.value,
            "title": item.title,
            "ownerUserId": user_id,
        },
    )

    match = find_match(db, item)
    if match:
        apply_match(db, item, match)
        db.refresh(item)
        publish(
            EventType.MATCH_FOUND,
            {
                "lostItemId": item.id if item.item_type == ItemType.LOST else match.id,
                "foundItemId": item.id if item.item_type == ItemType.FOUND else match.id,
                "title": item.title,
            },
        )

    return item


@app.get("/items", response_model=list[ItemResponse])
def list_items(db: Session = Depends(get_db)):
    return db.query(Item).order_by(Item.id.desc()).all()


@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def submit_claim(
    payload: ClaimCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = db.get(Item, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    result = ClaimRecoverySaga.submit_claim(db, item, user_id)

    publish(
        EventType.CLAIM_CREATED,
        {
            "claimId": result.claim.id,
            "itemId": result.item.id,
            "claimantUserId": user_id,
        },
    )
    logger.info(
        "Saga started: claimId=%s steps=%s",
        result.claim.id,
        [s.value for s in result.steps],
    )
    trigger_claim_saga(
        claim_id=result.claim.id,
        item_id=result.item.id,
        claimant_user_id=user_id,
        matched_item_id=result.item.matched_item_id,
        decision="PENDING",
    )
    return result.claim


@app.post("/claims/{claim_id}/approve", response_model=ClaimResponse)
def approve_claim(
    claim_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    item = db.get(Item, claim.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    result = ClaimRecoverySaga.approve_claim(db, claim, item, user_id)

    publish(
        EventType.CLAIM_APPROVED,
        {"claimId": claim.id, "itemId": item.id, "approvedBy": user_id},
    )
    publish(
        EventType.ITEM_RECOVERED,
        {"itemId": item.id, "claimId": claim.id, "recoveredBy": claim.claimant_user_id},
    )
    logger.info(
        "Saga completed: claimId=%s steps=%s outcome=%s",
        claim.id,
        [s.value for s in result.steps],
        result.outcome,
    )
    trigger_claim_saga(
        claim_id=claim.id,
        item_id=item.id,
        claimant_user_id=claim.claimant_user_id,
        matched_item_id=item.matched_item_id,
        decision="APPROVED",
    )
    return result.claim


@app.post("/claims/{claim_id}/reject", response_model=ClaimResponse)
def reject_claim(
    claim_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    item = db.get(Item, claim.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    result = ClaimRecoverySaga.reject_claim(db, claim, item, user_id)

    publish(
        EventType.CLAIM_REJECTED,
        {"claimId": claim.id, "itemId": item.id, "rejectedBy": user_id},
    )
    logger.info(
        "Saga compensated: claimId=%s steps=%s outcome=%s",
        claim.id,
        [s.value for s in result.steps],
        result.outcome,
    )
    trigger_claim_saga(
        claim_id=claim.id,
        item_id=item.id,
        claimant_user_id=claim.claimant_user_id,
        matched_item_id=item.matched_item_id,
        decision="REJECTED",
    )
    return result.claim


@app.get("/items/{item_id}/claims", response_model=list[ClaimResponse])
def list_item_claims(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return db.query(Claim).filter(Claim.item_id == item_id).order_by(Claim.id.desc()).all()


@app.get("/claims/{claim_id}/saga", response_model=SagaStatusResponse)
def get_saga_status(claim_id: int, db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    item = db.get(Item, claim.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    status = ClaimRecoverySaga.get_status(claim, item)
    status.update(get_aws_sync_status(claim_id))
    return status


@app.get("/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim
