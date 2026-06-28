"""Mock Lambda: ReserveItem — MATCHED → RESERVED."""

from common import log_step


def handler(event, context):
    log_step("ReserveItem", event)

    return {
        "itemId": event["itemId"],
        "matchedItemId": event.get("matchedItemId"),
        "itemStatus": "RESERVED",
        "claimId": event["claimId"],
        "message": f"Item {event['itemId']} reserved for claim {event['claimId']}",
    }
