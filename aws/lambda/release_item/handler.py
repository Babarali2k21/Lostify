"""Mock Lambda: ReleaseItem — compensation RESERVED → MATCHED."""

from common import log_step


def handler(event, context):
    log_step("ReleaseItem (Compensation)", event)

    return {
        "claimId": event["claimId"],
        "claimStatus": "REJECTED",
        "itemId": event["itemId"],
        "itemStatus": "MATCHED",
        "sagaOutcome": "COMPENSATED",
        "message": f"Compensation applied: item {event['itemId']} released back to MATCHED",
    }
