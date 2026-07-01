#!/usr/bin/env bash
# Deploy Lostify on EC2 (run from repo root on the server)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "=== Lostify Deploy ==="

if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
  echo "⚠️  Edit .env and set JWT_SECRET_KEY before production use!"
fi

echo "Building and starting services..."
docker compose -f docker-compose.prod.yml up --build -d

echo "Waiting for services..."
sleep 8

PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_EC2_PUBLIC_IP")

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Health checks:"
curl -sf "http://localhost:8001/health" && echo "  item-service: ok" || echo "  item-service: FAILED"
curl -sf "http://localhost:8002/health" && echo "  claim-recovery-service: ok" || echo "  claim-recovery-service: FAILED"
curl -sf "http://localhost:8003/health" && echo "  notification-service: ok" || echo "  notification-service: FAILED"
echo ""
echo "Access from browser/curl:"
echo "  Item Service:           http://${PUBLIC_IP}:8001/health"
echo "  Claim/Recovery Service: http://${PUBLIC_IP}:8002/health"
echo "  Notification Service:   http://${PUBLIC_IP}:8003/health"
echo ""
echo "View logs: docker compose -f docker-compose.prod.yml logs -f"
