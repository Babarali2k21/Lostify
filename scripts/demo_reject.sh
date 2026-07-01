#!/usr/bin/env bash
# Phase 2 — Demo claim rejection flow (ClaimRejected + saga compensation)
set -euo pipefail

ITEM_URL="${ITEM_URL:-http://localhost:8001}"
CLAIM_URL="${CLAIM_URL:-http://localhost:8002}"
NOTIF_URL="${NOTIF_URL:-http://localhost:8003}"

echo "=== Lostify Reject Flow Demo (Phase 2) ==="

echo -e "\n[1] Register users (ignore if already exist)..."
curl -sf -X POST "$ITEM_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"carol@uni.edu","username":"carol","password":"secret123"}' || true
curl -sf -X POST "$ITEM_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"dave@uni.edu","username":"dave","password":"secret123"}' || true

TOKEN_CAROL=$(curl -sf -X POST "$ITEM_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"carol","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
TOKEN_DAVE=$(curl -sf -X POST "$ITEM_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"dave","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo -e "\n[2] Create LOST item (Carol)..."
curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_CAROL" \
  -H "Content-Type: application/json" \
  -d '{"title":"Blue backpack","description":"Lost blue backpack near cafeteria","item_type":"LOST"}' | python3 -m json.tool

echo -e "\n[3] Create FOUND item (Dave) → MatchFound..."
FOUND=$(curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_DAVE" \
  -H "Content-Type: application/json" \
  -d '{"title":"Found backpack","description":"Found blue backpack near university cafeteria","item_type":"FOUND"}')
echo "$FOUND" | python3 -m json.tool
FOUND_ID=$(echo "$FOUND" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo -e "\n[4] Submit claim (Carol) → item RESERVED..."
CLAIM=$(curl -sf -X POST "$CLAIM_URL/claims" \
  -H "Authorization: Bearer $TOKEN_CAROL" \
  -H "Content-Type: application/json" \
  -d "{\"item_id\":$FOUND_ID}")
echo "$CLAIM" | python3 -m json.tool
CLAIM_ID=$(echo "$CLAIM" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo -e "\n[5] Reject claim (Dave) → compensation RESERVED → MATCHED..."
curl -sf -X POST "$CLAIM_URL/claims/$CLAIM_ID/reject" \
  -H "Authorization: Bearer $TOKEN_DAVE" | python3 -m json.tool

echo -e "\n[6] Verify item back to MATCHED..."
curl -sf "$ITEM_URL/items/$FOUND_ID" | python3 -m json.tool

echo -e "\n[7] Latest processed events..."
curl -sf "$NOTIF_URL/events/processed" | python3 -m json.tool | head -20

echo -e "\n=== Reject demo complete! Look for ClaimRejected in notification logs. ==="
