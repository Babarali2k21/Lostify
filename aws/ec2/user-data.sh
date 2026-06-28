#!/usr/bin/env bash
# Cloud-init user-data script for EC2 launch (paste into "Advanced details → User data")
# Installs Docker, clones repo, and starts Lostify on first boot.
set -euo pipefail

exec > /var/log/lostify-setup.log 2>&1
echo "Lostify user-data starting at $(date)"

apt-get update -qq
apt-get install -y git

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
systemctl enable docker

# Clone repo — replace with your GitHub URL
LOSTIFY_REPO="${LOSTIFY_REPO:-https://github.com/YOUR_USERNAME/Lostify.git}"
LOSTIFY_DIR="/home/ubuntu/Lostify"

sudo -u ubuntu git clone "$LOSTIFY_REPO" "$LOSTIFY_DIR" || true
cd "$LOSTIFY_DIR"

cp .env.example .env
sed -i "s/change-me-to-a-long-random-string/lostify-ec2-$(openssl rand -hex 16)/" .env

docker compose -f docker-compose.prod.yml up --build -d

echo "Lostify user-data complete at $(date)"
