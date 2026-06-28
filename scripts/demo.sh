#!/usr/bin/env bash
# Lostify end-to-end demo script
set -euo pipefail

USER_URL="${USER_URL:-http://localhost:8001}"
ITEM_URL="${ITEM_URL:-http://localhost:8002}"
NOTIF_URL="${NOTIF_URL:-http://localhost:8003}"

echo "=== Lostify Demo Flow ==="

echo -e "\n[1] Health checks..."
curl -sf "$USER_URL/health" | python3 -m json.tool
curl -sf "$ITEM_URL/health" | python3 -m json.tool
curl -sf "$NOTIF_URL/health" | python3 -m json.tool

echo -e "\n[2] Register users..."
curl -sf -X POST "$USER_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@uni.edu","username":"alice","password":"secret123"}' || true
curl -sf -X POST "$USER_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@uni.edu","username":"bob","password":"secret123"}' || true

echo -e "\n[3] Login..."
TOKEN_ALICE=$(curl -sf -X POST "$USER_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
TOKEN_BOB=$(curl -sf -X POST "$USER_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Alice token obtained"
echo "Bob token obtained"

echo -e "\n[4] Create LOST item (Alice)..."
LOST=$(curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_ALICE" \
  -H "Content-Type: application/json" \
  -d '{"title":"Black iPhone 14","description":"Lost black iPhone 14 near library","item_type":"LOST"}')
echo "$LOST" | python3 -m json.tool

echo -e "\n[5] Create FOUND item (Bob) → should trigger MatchFound..."
FOUND=$(curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_BOB" \
  -H "Content-Type: application/json" \
  -d '{"title":"Found iPhone","description":"Found black iPhone 14 near university library","item_type":"FOUND"}')
echo "$FOUND" | python3 -m json.tool
FOUND_ID=$(echo "$FOUND" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo -e "\n[6] Submit claim (Alice)..."
CLAIM=$(curl -sf -X POST "$ITEM_URL/claims" \
  -H "Authorization: Bearer $TOKEN_ALICE" \
  -H "Content-Type: application/json" \
  -d "{\"item_id\":$FOUND_ID}")
echo "$CLAIM" | python3 -m json.tool
CLAIM_ID=$(echo "$CLAIM" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo -e "\n[7] Approve claim (Bob) → ItemRecovered..."
curl -sf -X POST "$ITEM_URL/claims/$CLAIM_ID/approve" \
  -H "Authorization: Bearer $TOKEN_BOB" | python3 -m json.tool

echo -e "\n[8] Processed events (notification-service)..."
curl -sf "$NOTIF_URL/events/processed" | python3 -m json.tool

echo -e "\n=== Demo complete! Check 'docker compose logs notification-service' for notifications. ==="
