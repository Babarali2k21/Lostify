"""Mock Lambda: CreateClaim — creates a PENDING claim."""

import json
import uuid

from common import log_step


def handler(event, context):
    log_step("CreateClaim", event)

    item_id = event["itemId"]
    claimant_user_id = event["claimantUserId"]

    result = {
        "claimId": str(uuid.uuid4())[:8],
        "itemId": item_id,
        "claimantUserId": claimant_user_id,
        "claimStatus": "PENDING",
        "message": f"Claim created for item {item_id}",
    }

    return result
