import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from shared.events import Event, EventBus, EventType

from .auth import (
    create_access_token,
    get_current_user,
    get_current_user_id,
    hash_password,
    verify_password,
)
from .config import REDIS_URL
from .database import Base, engine, get_db
from .matching import apply_match, find_match
from .models import Item, ItemType, User
from .schemas import (
    ItemCreate,
    ItemResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from .state_machine import compensate_release_item, recover_item, reserve_item_for_claim

logger = logging.getLogger(__name__)

app = FastAPI(title="Lostify Item Service", version="2.0.0")
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


@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registered: id=%s username=%s", user.id, user.username)
    return user


@app.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning("Failed login attempt for username=%s", payload.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token)


@app.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


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


@app.post("/items/{item_id}/reserve", response_model=ItemResponse)
def reserve_item(item_id: int, db: Session = Depends(get_db)):
    """Called by Claim/Recovery Service during the Saga."""
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    reserve_item_for_claim(db, item)
    db.refresh(item)
    return item


@app.post("/items/{item_id}/release", response_model=ItemResponse)
def release_item(item_id: int, db: Session = Depends(get_db)):
    """Saga compensation — release reserved item back to MATCHED."""
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    compensate_release_item(db, item)
    db.refresh(item)
    return item


@app.post("/items/{item_id}/recover", response_model=ItemResponse)
def recover_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    """Called by Claim/Recovery Service when a claim is approved."""
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    recover_item(db, item)
    db.refresh(item)
    return item
