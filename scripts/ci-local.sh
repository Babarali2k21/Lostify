#!/usr/bin/env bash
# Run the same checks as GitHub Actions CI locally
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Lostify Local CI ==="

echo -e "\n[1/2] Running tests..."
pip install -q -r tests/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/item-service:$(pwd)/notification-service" pytest tests/ -v --tb=short

echo -e "\n[2/2] Building Docker images..."
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml config --quiet

echo -e "\n=== CI passed ==="
