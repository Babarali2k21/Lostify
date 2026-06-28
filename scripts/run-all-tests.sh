#!/usr/bin/env bash
# Phase 7 — Run complete test suite (unit + integration + latency)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "  Lostify Phase 7 — Full Test Suite"
echo "=========================================="

pip install -q -r tests/requirements.txt
export PYTHONPATH="$(pwd):$(pwd)/item-service:$(pwd)/notification-service"

echo -e "\n── Unit tests (no Docker required) ──"
pytest tests/test_events.py tests/test_duplicate_events.py tests/test_saga.py -v --tb=short

STACK_UP=false
if curl -sf http://localhost:8001/health >/dev/null 2>&1; then
  STACK_UP=true
  echo -e "\n── Integration + fault tolerance + latency (Docker running) ──"
  pytest tests/test_integration.py tests/test_fault_tolerance.py tests/test_event_latency.py -v --tb=short
else
  echo -e "\n── Skipping integration tests (Docker not running) ──"
  echo "   Start stack: docker compose up -d"
fi

echo -e "\n── Event latency report ──"
if [ "$STACK_UP" = true ]; then
  python3 scripts/measure-event-latency.py || true
else
  echo "   Skipped — Docker not running"
fi

echo -e "\n=========================================="
echo "  Test suite complete"
echo "=========================================="
