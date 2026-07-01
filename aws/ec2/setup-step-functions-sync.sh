#!/usr/bin/env bash
# One-time EC2 setup so Docker item-service can call Step Functions (IAM via metadata).
set -euo pipefail

echo "=== Lostify Step Functions sync setup ==="

# IMDSv2 (required on newer EC2 instances)
TOKEN=$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || true)
if [ -n "$TOKEN" ]; then
  INSTANCE_ID=$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/instance-id)
else
  INSTANCE_ID=$(curl -sf http://169.254.169.254/latest/meta-data/instance-id || true)
fi

if [ -z "${INSTANCE_ID:-}" ]; then
  echo "⚠️  Could not read instance ID from metadata."
  echo "   In EC2 console: Actions → Instance settings → Modify instance metadata options"
  echo "   Set Metadata response hop limit = 2"
else
  echo "Instance: $INSTANCE_ID"
  if command -v aws >/dev/null 2>&1; then
    echo "Setting metadata hop limit to 2 (required for Docker + IAM role)..."
    aws ec2 modify-instance-metadata-options \
      --instance-id "$INSTANCE_ID" \
      --http-put-response-hop-limit 2 \
      --http-endpoint enabled
    echo "✓ Hop limit updated"
  else
    echo "⚠️  aws CLI not found. Install with: sudo apt install -y awscli"
    echo "   Or in EC2 console set Metadata response hop limit = 2"
  fi
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
fi

if ! grep -q '^STEP_FUNCTIONS_STATE_MACHINE_ARN=' .env; then
  echo ""
  echo "Add to .env:"
  echo "STEP_FUNCTIONS_STATE_MACHINE_ARN=arn:aws:states:eu-central-1:589498924228:stateMachine:LostifyClaimRecoverySaga"
  echo "AWS_REGION=eu-central-1"
  exit 1
fi

if ! grep -q '^AWS_REGION=' .env; then
  echo "AWS_REGION=eu-central-1" >> .env
fi

echo "Restarting item-service and frontend..."
docker compose -f docker-compose.prod.yml up --build -d item-service frontend

echo ""
echo "=== Done ==="
echo "1. Ensure IAM role with states:StartExecution is attached to this EC2 instance"
echo "2. Submit/approve/reject a claim in the app"
echo "3. Saga panel should show AWS status: RUNNING → SUCCEEDED"
echo "4. Step Functions console (eu-central-1) should list new executions"
