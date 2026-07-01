"""AWS Step Functions integration — auto-trigger and frontend sync status."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import redis

logger = logging.getLogger(__name__)

STATE_MACHINE_ARN = os.getenv("STEP_FUNCTIONS_STATE_MACHINE_ARN", "").strip()
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1").strip()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client = None
_redis = None


def _get_client():
    global _client
    if _client is None:
        import boto3

        _client = boto3.client("stepfunctions", region_name=AWS_REGION)
    return _client


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


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
        logger.warning(
            "Step Functions disabled — set STEP_FUNCTIONS_STATE_MACHINE_ARN in .env"
        )
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
        _store_execution(claim_id, arn, decision)
        logger.info(
            "Step Functions started | claimId=%s decision=%s arn=%s",
            claim_id,
            decision,
            arn,
        )
        return arn
    except Exception as exc:
        logger.error(
            "Step Functions start failed | claimId=%s decision=%s error=%s",
            claim_id,
            decision,
            exc,
        )
        logger.error(
            "If 'Unable to locate credentials': attach IAM role to EC2 and set "
            "metadata hop limit to 2 (run aws/ec2/setup-step-functions-sync.sh)"
        )
        return None


def get_aws_sync_status(claim_id: int) -> dict[str, Any]:
    """Return AWS execution sync info for the saga API / frontend panel."""
    if not is_enabled():
        return {
            "awsSynced": False,
            "awsExecutionArn": None,
            "awsExecutionStatus": "DISABLED",
        }

    arn = _get_redis().get(f"sfn:claim:{claim_id}:latest")
    if not arn:
        return {
            "awsSynced": False,
            "awsExecutionArn": None,
            "awsExecutionStatus": "NOT_STARTED",
        }

    try:
        desc = _get_client().describe_execution(executionArn=arn)
        status = desc["status"]
        return {
            "awsSynced": status in ("RUNNING", "SUCCEEDED"),
            "awsExecutionArn": arn,
            "awsExecutionStatus": status,
        }
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if error_code == "AccessDeniedException":
            # Execution was started; describe needs extra IAM permission
            return {
                "awsSynced": True,
                "awsExecutionArn": arn,
                "awsExecutionStatus": "STARTED",
            }
        logger.warning("describe_execution failed for %s: %s", arn, exc)
        return {
            "awsSynced": False,
            "awsExecutionArn": arn,
            "awsExecutionStatus": "UNKNOWN",
        }


def _store_execution(claim_id: int, arn: str, decision: str) -> None:
    r = _get_redis()
    r.set(f"sfn:claim:{claim_id}:latest", arn, ex=86400)
    r.set(f"sfn:claim:{claim_id}:{decision.lower()}", arn, ex=86400)


def _safe_execution_name(base: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in base)[:70]
    return f"{safe}-{int(time.time())}"
