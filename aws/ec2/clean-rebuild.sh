#!/usr/bin/env bash
# Full clean rebuild — run on EC2 inside ~/Lostify
set -euo pipefail

echo "=== Stopping and removing all Lostify containers ==="
docker compose -f docker-compose.prod.yml down --remove-orphans

echo "=== Building all services from scratch ==="
docker compose -f docker-compose.prod.yml build --no-cache

echo "=== Starting stack ==="
docker compose -f docker-compose.prod.yml up -d

echo "=== Waiting for services ==="
sleep 12

echo "=== Health checks (via nginx proxy) ==="
curl -sf http://localhost:3001/api/user/health | python3 -m json.tool
curl -sf http://localhost:3001/api/item/health | python3 -m json.tool
curl -sf http://localhost:3001/api/notif/health | python3 -m json.tool

echo ""
echo "=== Check JS has NO localhost ==="
if docker compose -f docker-compose.prod.yml exec frontend grep -rq "localhost" /usr/share/nginx/html/assets/ 2>/dev/null; then
  echo "❌ WARNING: localhost still in frontend JS!"
  docker compose -f docker-compose.prod.yml exec frontend grep -ro "localhost[^\"]*" /usr/share/nginx/html/assets/ | head -3
else
  echo "✓ Frontend uses relative /api/* paths only"
fi

IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_EC2_IP")
echo ""
echo "=== Done! Open in incognito: http://${IP}:3001 ==="
