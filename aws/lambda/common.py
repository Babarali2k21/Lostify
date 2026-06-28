"""Shared helpers for Lostify mock Lambda functions."""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
    }


def log_step(step: str, payload: dict) -> None:
    logger.info("SAGA STEP | %s | payload=%s", step, json.dumps(payload))
