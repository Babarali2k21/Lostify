#!/usr/bin/env bash
# Verify Lostify deployment — run on EC2 or against public IP
set -euo pipefail

HOST="${1:-localhost}"
BASE="http://${HOST}"

echo "=== Lostify Health Check (${HOST}) ==="

check() {
  local name=$1 port=$2
  if curl -sf "${BASE}:${port}/health" > /dev/null; then
    echo "✅ ${name} (:${port})"
  else
    echo "❌ ${name} (:${port})"
    return 1
  fi
}

check "user-service" 8001
check "item-service" 8002
check "notification-service" 8003

echo ""
echo "All services healthy."
