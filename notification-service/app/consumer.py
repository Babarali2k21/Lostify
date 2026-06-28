import json
import logging
import threading

from sqlalchemy.orm import Session

from shared.events import Event, EventBus

from .config import REDIS_URL
from .database import SessionLocal
from .models import ProcessedEvent

logger = logging.getLogger(__name__)

NOTIFICATION_MESSAGES = {
    "ItemCreated": "📦 New item posted: {title} ({itemType})",
    "MatchFound": "🔗 Match found! Lost #{lostItemId} ↔ Found #{foundItemId}",
    "ClaimCreated": "📝 Claim #{claimId} submitted for item #{itemId}",
    "ClaimApproved": "✅ Claim #{claimId} approved for item #{itemId}",
    "ClaimRejected": "❌ Claim #{claimId} rejected for item #{itemId}",
    "ItemRecovered": "🎉 Item #{itemId} recovered via claim #{claimId}",
}


def _format_message(event: Event) -> str:
    template = NOTIFICATION_MESSAGES.get(
        event.event_type.value,
        f"Event {event.event_type.value}: {event.payload}",
    )
    try:
        return template.format(**event.payload)
    except KeyError:
        return f"{event.event_type.value}: {event.payload}"


def is_duplicate(db: Session, event_id: str) -> bool:
    return db.get(ProcessedEvent, event_id) is not None


def mark_processed(db: Session, event: Event) -> None:
    db.add(
        ProcessedEvent(
            event_id=event.event_id,
            event_type=event.event_type.value,
        )
    )
    db.commit()


def handle_event(event: Event) -> None:
    db = SessionLocal()
    try:
        if is_duplicate(db, event.event_id):
            logger.warning(
                "Duplicate event ignored: eventId=%s type=%s",
                event.event_id,
                event.event_type.value,
            )
            return

        message = _format_message(event)
        logger.info("NOTIFICATION | %s | eventId=%s", message, event.event_id)
        print(f"\n{'='*60}\nNOTIFICATION: {message}\n{'='*60}\n", flush=True)

        mark_processed(db, event)
    finally:
        db.close()


def start_consumer() -> threading.Thread:
    """Start Redis event consumer in a background thread."""

    def run():
        bus = EventBus(REDIS_URL)
        pubsub = bus.subscribe()
        logger.info("Notification consumer listening for events...")

        for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                event = Event.from_dict(data)
                handle_event(event)
            except Exception as exc:
                logger.exception("Failed to process event: %s", exc)

    thread = threading.Thread(target=run, daemon=True, name="event-consumer")
    thread.start()
    return thread
