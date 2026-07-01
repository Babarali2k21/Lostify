# Phase 5 — AWS EC2 Deployment

Deploy Lostify to a single **Ubuntu EC2** instance using Docker Compose.

---

## Architecture on EC2

```
                    Internet
                        │
                        ▼
              ┌─────────────────┐
              │  Security Group │
              │  :3001,:8001–8003
              └────────┬────────┘
                        │
              ┌─────────▼─────────┐
              │   Ubuntu EC2        │
              │  Docker Compose     │
              │                     │
              │  frontend      :3001 │
              │  item-service  :8001│  (auth + items)
              │  claim-recovery:8002│  (claims + saga)
              │  notification  :8003│
              │  redis (internal)   │
              └─────────────────────┘
```

Redis is **not** exposed publicly in `docker-compose.prod.yml`.

---

## Prerequisites

- AWS account
- SSH key pair (.pem file)
- Lostify repo (GitHub or local copy)

---

## Step 1 — Launch EC2 Instance

1. Open [EC2 Console](https://console.aws.amazon.com/ec2) → **Launch instance**

2. Configure:

| Setting | Recommended value |
|---------|-------------------|
| Name | `lostify-demo` |
| AMI | Ubuntu Server 24.04 LTS |
| Instance type | `t3.small` (2 vCPU, 2 GB — enough for demo) |
| Key pair | Create or select existing `.pem` |
| Storage | 20 GB gp3 |

3. **Network settings** → Create security group:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | My IP | SSH access |
| Custom TCP | 3001 | 0.0.0.0/0 | Frontend (UI + API proxy) |
| Custom TCP | 8001 | 0.0.0.0/0 | Item Service (auth + items) |
| Custom TCP | 8002 | 0.0.0.0/0 | Claim/Recovery Service |
| Custom TCP | 8003 | 0.0.0.0/0 | Notification Service |

> For university demo, `0.0.0.0/0` is fine. For real production, restrict to your IP or use a load balancer.

4. **Do NOT** open port 6379 (Redis stays internal).

5. Launch instance and note the **Public IPv4 address**.

---

## Step 2 — Connect via SSH

```bash
chmod 400 ~/Downloads/lostify-key.pem
ssh -i ~/Downloads/lostify-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

---

## Step 3 — Install Docker

On the EC2 instance:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker
docker --version
docker compose version
```

Or use the project script:

```bash
# After cloning repo (Step 4)
sudo bash aws/ec2/setup-server.sh
```

---

## Step 4 — Deploy Lostify

### Option A — Clone from GitHub

```bash
git clone https://github.com/YOUR_USERNAME/Lostify.git
cd Lostify
cp .env.example .env
nano .env   # set JWT_SECRET_KEY to a random string
chmod +x aws/ec2/*.sh
./aws/ec2/deploy.sh
```

### Option B — Deploy from your Mac (rsync)

From your local machine (in the Lostify repo):

```bash
chmod +x aws/ec2/remote-deploy.sh
./aws/ec2/remote-deploy.sh ubuntu@YOUR_EC2_PUBLIC_IP ~/Downloads/lostify-key.pem
```

This syncs files and runs `deploy.sh` on the server.

---

## Step 5 — Verify deployment

On EC2 (via frontend proxy):

```bash
./aws/ec2/health-check.sh localhost
```

Direct service ports from your laptop:

```bash
curl http://YOUR_EC2_PUBLIC_IP:8001/health
curl http://YOUR_EC2_PUBLIC_IP:8002/health
curl http://YOUR_EC2_PUBLIC_IP:8003/health
```

Expected:
```json
{"status":"ok","service":"item-service"}
{"status":"ok","service":"claim-recovery-service"}
{"status":"ok","service":"notification-service"}
```

---

## Step 6 — Run demo against EC2

Replace `localhost` with your EC2 public IP:

```bash
export EC2_IP=YOUR_EC2_PUBLIC_IP

# Register (Item Service :8001)
curl -X POST http://$EC2_IP:8001/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@uni.edu","username":"alice","password":"secret123"}'

# Login (Item Service :8001)
export TOKEN=$(curl -s -X POST http://$EC2_IP:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create item (Item Service :8001)
curl -X POST http://$EC2_IP:8001/items \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Lost keys","description":"Lost keys near library","item_type":"LOST"}'
```

Or adapt `scripts/demo.sh`:

```bash
ITEM_URL=http://$EC2_IP:8001 CLAIM_URL=http://$EC2_IP:8002 NOTIF_URL=http://$EC2_IP:8003 ./scripts/demo.sh
```

---

## Useful commands on EC2

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop
docker compose -f docker-compose.prod.yml down

# Rebuild after code changes
docker compose -f docker-compose.prod.yml up --build -d
```

---

## Step 3 (Optional) — Upgrade to managed AWS services

### RDS PostgreSQL (replace SQLite)

1. Create RDS PostgreSQL instance (db.t3.micro for demo)
2. Security group: allow inbound 5432 from EC2 security group
3. Update `.env`:

```bash
DATABASE_URL=postgresql://lostify:YOUR_PASSWORD@your-rds.xxxx.region.rds.amazonaws.com:5432/lostify
```

4. Update each service's `docker-compose.prod.yml` environment block with the same URL.

> Requires adding `psycopg2-binary` to service requirements — SQLite works fine for the university MVP.

### S3 (item photos — future)

Store item images in S3 instead of local disk. Add `boto3` and an upload endpoint in Item Service.

### SES (email notifications — future)

Replace console-log notifications with real email via Amazon SES in the Notification Service.

For the MVP demo, **SQLite + console notifications on EC2 is sufficient**.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection timed out | Check security group ports 3001 and 8001–8003 |
| Permission denied (docker) | Run `sudo usermod -aG docker ubuntu` and re-login |
| Build fails (out of memory) | Use `t3.small` or add 2GB swap |
| Services not starting | Check logs: `docker compose -f docker-compose.prod.yml logs` |
| JWT errors between services | Ensure same `JWT_SECRET_KEY` in `.env` for item-service and claim-recovery-service |

---

## Cost estimate (demo)

| Resource | Approx. monthly cost |
|----------|---------------------|
| t3.small EC2 | ~$15 |
| 20 GB EBS | ~$2 |
| Data transfer | minimal for demo |
| **Total** | **~$17/month** |

Stop the instance when not demoing to save costs.

---

## Files reference

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production compose (Redis not public) |
| `.env.example` | Environment template |
| `aws/ec2/setup-server.sh` | Install Docker on Ubuntu |
| `aws/ec2/deploy.sh` | Build & start on EC2 |
| `aws/ec2/health-check.sh` | Verify all services via frontend proxy |
| `aws/ec2/remote-deploy.sh` | Deploy from local Mac via SSH |
| `aws/ec2/user-data.sh` | Optional EC2 launch script |

---

## Next: Phase 6

Add **CI/CD** with GitHub Actions to automate test → build → deploy to EC2.
