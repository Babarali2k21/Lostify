import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from shared.events import Event, EventBus, EventType

from .auth import get_current_user_id
from .config import REDIS_URL
from .database import Base, engine, get_db
from .item_client import item_client
from .models import Claim
from .saga import ClaimRecoverySaga
from .saga_schemas import SagaStatusResponse
from .schemas import ClaimCreate, ClaimResponse
from .step_functions import get_aws_sync_status, trigger_claim_saga

logger = logging.getLogger(__name__)

app = FastAPI(title="Lostify Claim/Recovery Service", version="2.0.0")
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
    logger.info("Claim/Recovery Service started — database initialized")


@app.get("/health")
def health():
    return {"status": "ok", "service": "claim-recovery-service"}


@app.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def submit_claim(
    payload: ClaimCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    result = ClaimRecoverySaga.submit_claim(db, payload.item_id, user_id)

    publish(
        EventType.CLAIM_CREATED,
        {
            "claimId": result.claim.id,
            "itemId": result.item["id"],
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
        item_id=result.item["id"],
        claimant_user_id=user_id,
        matched_item_id=result.item.get("matched_item_id"),
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

    result = ClaimRecoverySaga.approve_claim(db, claim, user_id)

    publish(
        EventType.CLAIM_APPROVED,
        {"claimId": claim.id, "itemId": claim.item_id, "approvedBy": user_id},
    )
    publish(
        EventType.ITEM_RECOVERED,
        {
            "itemId": claim.item_id,
            "claimId": claim.id,
            "recoveredBy": claim.claimant_user_id,
        },
    )
    logger.info(
        "Saga completed: claimId=%s steps=%s outcome=%s",
        claim.id,
        [s.value for s in result.steps],
        result.outcome,
    )
    trigger_claim_saga(
        claim_id=claim.id,
        item_id=claim.item_id,
        claimant_user_id=claim.claimant_user_id,
        matched_item_id=result.item.get("matched_item_id"),
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

    result = ClaimRecoverySaga.reject_claim(db, claim, user_id)

    publish(
        EventType.CLAIM_REJECTED,
        {"claimId": claim.id, "itemId": claim.item_id, "rejectedBy": user_id},
    )
    logger.info(
        "Saga compensated: claimId=%s steps=%s outcome=%s",
        claim.id,
        [s.value for s in result.steps],
        result.outcome,
    )
    trigger_claim_saga(
        claim_id=claim.id,
        item_id=claim.item_id,
        claimant_user_id=claim.claimant_user_id,
        matched_item_id=result.item.get("matched_item_id"),
        decision="REJECTED",
    )
    return result.claim


@app.get("/items/{item_id}/claims", response_model=list[ClaimResponse])
def list_item_claims(item_id: int, db: Session = Depends(get_db)):
    item_client.get_item(item_id)
    return db.query(Claim).filter(Claim.item_id == item_id).order_by(Claim.id.desc()).all()


@app.get("/claims/{claim_id}/saga", response_model=SagaStatusResponse)
def get_saga_status(claim_id: int, db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    item = item_client.get_item(claim.item_id)
    status = ClaimRecoverySaga.get_status(claim, item)
    status.update(get_aws_sync_status(claim_id))
    return status


@app.get("/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim
