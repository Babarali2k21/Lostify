#!/usr/bin/env bash
# Verify Lostify deployment — run on EC2 or against public IP
set -euo pipefail

HOST="${1:-localhost}"
PORT="${FRONTEND_PORT:-3001}"
BASE="http://${HOST}:${PORT}"

echo "=== Lostify Health Check (${BASE}) ==="

check_proxy() {
  local name=$1 path=$2
  if curl -sf "${BASE}${path}/health" > /dev/null; then
    echo "✅ ${name} (${path})"
  else
    echo "❌ ${name} (${path})"
    return 1
  fi
}

check_proxy "user-service" "/api/user"
check_proxy "item-service" "/api/item"
check_proxy "notification-service" "/api/notif"

echo ""
echo "All services healthy via frontend proxy."
