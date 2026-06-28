#!/usr/bin/env bash
# Deploy Lostify to EC2 from your local machine via SSH
# Usage: ./aws/ec2/remote-deploy.sh ubuntu@YOUR_EC2_PUBLIC_IP
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 user@host [ssh_key_path]"
  echo "Example: $0 ubuntu@54.123.45.67 ~/.ssh/lostify.pem"
  exit 1
fi

REMOTE="$1"
SSH_KEY="${2:-}"
SSH_OPTS=()
[ -n "$SSH_KEY" ] && SSH_OPTS=(-i "$SSH_KEY")

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=== Remote deploy to ${REMOTE} ==="

# Sync project files (exclude dev artifacts)
rsync -avz "${SSH_OPTS[@]}" \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.db' \
  --exclude 'aws/dist' \
  "$REPO_ROOT/" "${REMOTE}:~/Lostify/"

echo "Running deploy on remote..."
ssh "${SSH_OPTS[@]}" "$REMOTE" "cd ~/Lostify && chmod +x aws/ec2/*.sh && bash aws/ec2/deploy.sh"

echo ""
echo "Running health check..."
ssh "${SSH_OPTS[@]}" "$REMOTE" "bash ~/Lostify/aws/ec2/health-check.sh localhost"

HOST="${REMOTE#*@}"
echo ""
echo "Try from your machine:"
echo "  curl http://${HOST}:8001/health"
