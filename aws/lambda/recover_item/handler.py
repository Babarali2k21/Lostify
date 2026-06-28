"""Mock Lambda: RecoverItem — RESERVED → RECOVERED (happy path)."""

from common import log_step


def handler(event, context):
    log_step("RecoverItem", event)

    return {
        "claimId": event["claimId"],
        "claimStatus": "APPROVED",
        "itemId": event["itemId"],
        "itemStatus": "RECOVERED",
        "sagaOutcome": "COMPLETED",
        "message": f"Item {event['itemId']} recovered via claim {event['claimId']}",
    }
