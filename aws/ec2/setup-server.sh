#!/usr/bin/env bash
# EC2 bootstrap — install Docker & Docker Compose on Ubuntu 22.04/24.04
# Run as root or with sudo: sudo bash setup-server.sh
set -euo pipefail

echo "=== Lostify EC2 Server Setup ==="

if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  apt-get update -qq
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo "Docker installed."
else
  echo "Docker already installed."
fi

# Allow ubuntu user to run docker without sudo
if id ubuntu &>/dev/null; then
  usermod -aG docker ubuntu
  echo "Added 'ubuntu' user to docker group."
fi

docker --version
docker compose version

echo ""
echo "=== Setup complete ==="
echo "Next: clone Lostify repo and run deploy.sh"
