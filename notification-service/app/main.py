import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import DATABASE_URL, REDIS_URL
from .consumer import start_consumer
from .database import Base, engine, get_db
from .models import ProcessedEvent

logger = logging.getLogger(__name__)

app = FastAPI(title="Lostify Notification Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    start_consumer()
    logger.info(
        "Notification Service started — consumer active (redis=%s db=%s)",
        REDIS_URL,
        DATABASE_URL,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}


@app.get("/events/processed")
def list_processed_events(db: Session = Depends(get_db)):
    events = db.query(ProcessedEvent).order_by(ProcessedEvent.processed_at.desc()).all()
    return [
        {
            "eventId": e.event_id,
            "eventType": e.event_type,
            "processedAt": e.processed_at.isoformat(),
        }
        for e in events
    ]
