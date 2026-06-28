"""Mock Lambda: SendNotification — mirrors Notification Service consuming events."""

from common import log_step

MESSAGES = {
    "ClaimCreated": "📝 Claim submitted for item",
    "ClaimApproved": "✅ Claim approved",
    "ClaimRejected": "❌ Claim rejected — compensation applied",
    "ItemRecovered": "🎉 Item recovered",
}


def handler(event, context):
    import uuid

    event_type = event["eventType"]
    payload = event.get("payload", {})
    log_step(f"SendNotification | {event_type}", {**event, "payload": payload})

    message = MESSAGES.get(event_type, f"Notification: {event_type}")
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "notified": True,
        "message": message,
        "payload": payload,
    }
