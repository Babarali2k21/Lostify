"""Unit tests for Step Functions auto-trigger helper."""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
ITEM_SERVICE = str(ROOT / "item-service")
sys.path.insert(0, ITEM_SERVICE)

step_functions = importlib.import_module("app.step_functions")


class TestStepFunctionsTrigger:
    def setup_method(self):
        step_functions.STATE_MACHINE_ARN = ""
        step_functions._client = None

    def test_disabled_when_arn_missing(self):
        assert step_functions.is_enabled() is False
        assert (
            step_functions.trigger_claim_saga(
                claim_id=1,
                item_id=2,
                claimant_user_id=3,
                matched_item_id=4,
                decision="APPROVED",
            )
            is None
        )

    @patch.dict("os.environ", {"STEP_FUNCTIONS_STATE_MACHINE_ARN": "arn:aws:states:eu-central-1:1:stateMachine:Test"})
    def test_starts_execution_with_payload(self):
        step_functions.STATE_MACHINE_ARN = "arn:aws:states:eu-central-1:1:stateMachine:Test"
        mock_client = MagicMock()
        mock_client.start_execution.return_value = {
            "executionArn": "arn:aws:states:eu-central-1:1:execution:Test:claim-1-approved-1"
        }
        step_functions._client = mock_client

        arn = step_functions.trigger_claim_saga(
            claim_id=1,
            item_id=2,
            claimant_user_id=3,
            matched_item_id=4,
            decision="APPROVED",
        )

        assert arn is not None
        mock_client.start_execution.assert_called_once()
        call = mock_client.start_execution.call_args.kwargs
        assert call["stateMachineArn"] == "arn:aws:states:eu-central-1:1:stateMachine:Test"
        payload = json.loads(call["input"])
        assert payload["claimId"] == 1
        assert payload["decision"] == "APPROVED"

    def test_pending_decision_supported(self):
        step_functions.STATE_MACHINE_ARN = "arn:aws:states:eu-central-1:1:stateMachine:Test"
        mock_client = MagicMock()
        mock_client.start_execution.return_value = {"executionArn": "arn:exec"}
        step_functions._client = mock_client

        step_functions.trigger_claim_saga(
            claim_id=5,
            item_id=6,
            claimant_user_id=7,
            matched_item_id=8,
            decision="PENDING",
        )

        payload = json.loads(mock_client.start_execution.call_args.kwargs["input"])
        assert payload["decision"] == "PENDING"
