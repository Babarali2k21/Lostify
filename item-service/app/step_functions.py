"""Fire-and-forget AWS Step Functions executions for claim saga visualization."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

STATE_MACHINE_ARN = os.getenv("STEP_FUNCTIONS_STATE_MACHINE_ARN", "").strip()
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1").strip()

_client = None


def _get_client():
    global _client
    if _client is None:
        import boto3

        _client = boto3.client("stepfunctions", region_name=AWS_REGION)
    return _client


def is_enabled() -> bool:
    return bool(STATE_MACHINE_ARN)


def trigger_claim_saga(
    *,
    claim_id: int,
    item_id: int,
    claimant_user_id: int,
    matched_item_id: int | None,
    decision: str,
) -> str | None:
    """
    Start a Step Functions execution mirroring the frontend claim action.

    decision: PENDING (submit), APPROVED, or REJECTED
    Returns execution ARN on success, None if disabled or on failure.
    """
    if not is_enabled():
        logger.debug("Step Functions disabled — set STEP_FUNCTIONS_STATE_MACHINE_ARN to enable")
        return None

    payload: dict[str, Any] = {
        "claimId": claim_id,
        "itemId": item_id,
        "claimantUserId": claimant_user_id,
        "matchedItemId": matched_item_id or item_id,
        "decision": decision,
    }

    execution_name = f"claim-{claim_id}-{decision.lower()}"

    try:
        response = _get_client().start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=_safe_execution_name(execution_name),
            input=json.dumps(payload),
        )
        arn = response["executionArn"]
        logger.info(
            "Step Functions started | claimId=%s decision=%s arn=%s",
            claim_id,
            decision,
            arn,
        )
        return arn
    except Exception:
        logger.exception(
            "Step Functions start failed | claimId=%s decision=%s",
            claim_id,
            decision,
        )
        return None


def _safe_execution_name(base: str) -> str:
    """Execution names must be unique; append suffix if name was recently used."""
    import time

    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in base)[:70]
    return f"{safe}-{int(time.time())}"
