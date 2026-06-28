#!/usr/bin/env bash
# Phase 3 — Full saga demo: happy path + compensation path with status checkpoints
set -euo pipefail

USER_URL="${USER_URL:-http://localhost:8001}"
ITEM_URL="${ITEM_URL:-http://localhost:8002}"

saga_status() {
  local claim_id=$1
  echo "--- Saga status (claim $claim_id) ---"
  curl -sf "$ITEM_URL/claims/$claim_id/saga" | python3 -m json.tool
}

echo "=========================================="
echo "  PHASE 3: Claim & Recovery Saga Demo"
echo "=========================================="

# ── Setup users ──────────────────────────────────────────
echo -e "\n▶ Registering saga demo users..."
curl -sf -X POST "$USER_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"saga-happy@uni.edu","username":"saga_happy","password":"secret123"}' || true
curl -sf -X POST "$USER_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"saga-comp@uni.edu","username":"saga_comp","password":"secret123"}' || true
curl -sf -X POST "$USER_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"owner-happy@uni.edu","username":"owner_happy","password":"secret123"}' || true
curl -sf -X POST "$USER_URL/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"owner-comp@uni.edu","username":"owner_comp","password":"secret123"}' || true

TOKEN_HAPPY=$(curl -sf -X POST "$USER_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"saga_happy","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
TOKEN_COMP=$(curl -sf -X POST "$USER_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"saga_comp","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
TOKEN_OWNER_H=$(curl -sf -X POST "$USER_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"owner_happy","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
TOKEN_OWNER_C=$(curl -sf -X POST "$USER_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"owner_comp","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# ══════════════════════════════════════════════════════════
echo -e "\n\n══ SAGA PATH A: Happy Path (Approve → RECOVERED) ══"
# ══════════════════════════════════════════════════════════

echo -e "\n▶ Step 1-2: Create matched pair..."
curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_HAPPY" \
  -H "Content-Type: application/json" \
  -d '{"title":"Lost keys","description":"Lost silver keys near gym","item_type":"LOST"}' > /dev/null

FOUND_H=$(curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_OWNER_H" \
  -H "Content-Type: application/json" \
  -d '{"title":"Found keys","description":"Found silver keys near university gym","item_type":"FOUND"}')
FOUND_H_ID=$(echo "$FOUND_H" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Matched found item id=$FOUND_H_ID"

echo -e "\n▶ Step 3: SubmitClaim → ReserveItem..."
CLAIM_H=$(curl -sf -X POST "$ITEM_URL/claims" \
  -H "Authorization: Bearer $TOKEN_HAPPY" \
  -H "Content-Type: application/json" \
  -d "{\"item_id\":$FOUND_H_ID}")
CLAIM_H_ID=$(echo "$CLAIM_H" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
saga_status "$CLAIM_H_ID"

echo -e "\n▶ Step 4: ApproveClaim → RecoverItem..."
curl -sf -X POST "$ITEM_URL/claims/$CLAIM_H_ID/approve" \
  -H "Authorization: Bearer $TOKEN_OWNER_H" | python3 -m json.tool
saga_status "$CLAIM_H_ID"

# ══════════════════════════════════════════════════════════
echo -e "\n\n══ SAGA PATH B: Compensation (Reject → MATCHED) ══"
# ══════════════════════════════════════════════════════════

echo -e "\n▶ Step 1-2: Create matched pair..."
curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_COMP" \
  -H "Content-Type: application/json" \
  -d '{"title":"Lost glasses","description":"Lost reading glasses in cafeteria","item_type":"LOST"}' > /dev/null

FOUND_C=$(curl -sf -X POST "$ITEM_URL/items" \
  -H "Authorization: Bearer $TOKEN_OWNER_C" \
  -H "Content-Type: application/json" \
  -d '{"title":"Found glasses","description":"Found reading glasses in university cafeteria","item_type":"FOUND"}')
FOUND_C_ID=$(echo "$FOUND_C" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo -e "\n▶ Step 3: SubmitClaim → ReserveItem..."
CLAIM_C=$(curl -sf -X POST "$ITEM_URL/claims" \
  -H "Authorization: Bearer $TOKEN_COMP" \
  -H "Content-Type: application/json" \
  -d "{\"item_id\":$FOUND_C_ID}")
CLAIM_C_ID=$(echo "$CLAIM_C" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
saga_status "$CLAIM_C_ID"

echo -e "\n▶ Step 4: RejectClaim → CompensateRelease..."
curl -sf -X POST "$ITEM_URL/claims/$CLAIM_C_ID/reject" \
  -H "Authorization: Bearer $TOKEN_OWNER_C" | python3 -m json.tool
saga_status "$CLAIM_C_ID"

echo -e "\n=========================================="
echo "  Phase 3 Saga Demo Complete"
echo "  Path A: sagaState = COMPLETED"
echo "  Path B: sagaState = COMPENSATED"
echo "=========================================="
