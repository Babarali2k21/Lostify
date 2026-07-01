# Lostify — Lost & Found Microservices MVP

Event-driven microservices system for university demo.

## Architecture

Three microservices plus a React frontend. User authentication is **embedded in Item Service** as application-level auth (register/login/JWT) — not a separate microservice, per course guidance.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Frontend (nginx :3001)                           │
│   /api/item/*  →  item-service:8001                                      │
│   /api/claim/* →  claim-recovery-service:8002                            │
│   /api/notif/* →  notification-service:8003                              │
└──────────────────────────────────────────────────────────────────────────┘
         │                    │                         │
         ▼                    ▼                         ▼
┌─────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
│  Item Service   │  │ Claim/Recovery Svc   │  │ Notification Service│
│     :8001       │◄─│       :8002          │  │        :8003        │
│                 │  │  REST: reserve/      │  │  Redis subscriber   │
│ • auth (JWT)    │  │  release/recover     │  │  + deduplication    │
│ • items/match   │  │ • claims + saga      │  └──────────▲──────────┘
│ • item states   │  │ • Step Functions     │             │
└────────┬────────┘  └──────────┬───────────┘             │
         │ publish              │ publish                  │ subscribe
         └──────────────────────┴──────────────────────────┘
                                    │
                              ┌─────▼─────┐
                              │   Redis   │
                              │   :6379   │
                              └───────────┘
```

> **Note:** Per course guidance, user registration and login live inside Item Service as application-level authentication — not as a fourth microservice.

## Quick Start

```bash
cd ~/Projects/Lostify
docker compose up --build
```

Wait until all services are healthy, then open **http://localhost:3001** for the web UI.

Or run the demo flow via curl below (direct service ports).

## Demo Flow (curl)

### 1. Register two users (Item Service :8001)

```bash
# User A (lost item owner)
curl -s -X POST http://localhost:8001/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@uni.edu","username":"alice","password":"secret123"}'

# User B (found item owner)
curl -s -X POST http://localhost:8001/register \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@uni.edu","username":"bob","password":"secret123"}'
```

### 2. Login and save JWT tokens (Item Service :8001)

```bash
export TOKEN_ALICE=$(curl -s -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

export TOKEN_BOB=$(curl -s -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"secret123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Alice token: $TOKEN_ALICE"
echo "Bob token: $TOKEN_BOB"
```

### 3. Create lost item (Alice) — Item Service :8001

```bash
curl -s -X POST http://localhost:8001/items \
  -H "Authorization: Bearer $TOKEN_ALICE" \
  -H "Content-Type: application/json" \
  -d '{"title":"Black iPhone 14","description":"Lost black iPhone 14 near library","item_type":"LOST"}'
```

### 4. Create found item (Bob) → triggers MatchFound event — Item Service :8001

```bash
curl -s -X POST http://localhost:8001/items \
  -H "Authorization: Bearer $TOKEN_BOB" \
  -H "Content-Type: application/json" \
  -d '{"title":"Found iPhone","description":"Found black iPhone 14 near university library","item_type":"FOUND"}'
```

Check notification-service logs for `MatchFound` notification.

### 5. Submit claim (Alice claims the found item) — Claim/Recovery Service :8002

```bash
# Use the FOUND item id from step 4 (usually id=2)
curl -s -X POST http://localhost:8002/claims \
  -H "Authorization: Bearer $TOKEN_ALICE" \
  -H "Content-Type: application/json" \
  -d '{"item_id":2}'
```

### 6. Approve claim (Bob, item owner) — Claim/Recovery Service :8002

```bash
curl -s -X POST http://localhost:8002/claims/1/approve \
  -H "Authorization: Bearer $TOKEN_BOB"
```

Check notification-service logs for `ClaimApproved` and `ItemRecovered`.

### 7. View processed events (duplicate prevention) — Notification Service :8003

```bash
curl -s http://localhost:8003/events/processed
```

## Health Checks

```bash
curl http://localhost:8001/health   # item-service
curl http://localhost:8002/health   # claim-recovery-service
curl http://localhost:8003/health   # notification-service
```

Via frontend proxy:

```bash
curl http://localhost:3001/api/item/health
curl http://localhost:3001/api/claim/health
curl http://localhost:3001/api/notif/health
```

## Services

| Service                  | Port | Database | Responsibility |
|--------------------------|------|----------|----------------|
| **frontend**             | 3001 | —        | React UI + API proxy |
| **item-service**         | 8001 | SQLite   | Auth, items, matching, item state transitions |
| **claim-recovery-service** | 8002 | SQLite | Claims, saga, compensation, Step Functions sync |
| **notification-service** | 8003 | SQLite   | Event consumer + deduplication |
| Redis (event bus)        | 6379 | —        | Pub/sub channel `lostify:events` |

## API paths (frontend proxy)

| Path prefix    | Backend service           |
|----------------|---------------------------|
| `/api/item/*`  | item-service:8001         |
| `/api/claim/*` | claim-recovery-service:8002 |
| `/api/notif/*` | notification-service:8003 |

## Project Structure

```
Lostify/
├── docker-compose.yml
├── frontend/                    # React UI + nginx proxy (port 3001)
├── shared/events/               # Redis event bus + event models
├── item-service/                # Auth, items, matching, item states
├── claim-recovery-service/      # Claims, saga, compensation, Step Functions
└── notification-service/        # Event consumer + deduplication
```

## Phase 2 — Event System

See full event catalog: [`docs/EVENTS.md`](docs/EVENTS.md)

### Run unit tests

```bash
pip install -r tests/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/item-service:$(pwd)/claim-recovery-service:$(pwd)/notification-service" pytest tests/ -v
```

### Test duplicate event handling (live)

```bash
python3 scripts/test_duplicate_events.py
# Expected: ✅ PASS — Duplicate event was correctly ignored
```

### Demo claim rejection (ClaimRejected + compensation)

```bash
./scripts/demo_reject.sh
```

## Phase 3 — Saga Pattern

See full saga docs: [`docs/SAGA.md`](docs/SAGA.md)

Claim/Recovery Service orchestrates the saga and calls Item Service via REST (`/items/{id}/reserve`, `/release`, `/recover`).

### Run saga unit tests

```bash
PYTHONPATH="$(pwd):$(pwd)/item-service:$(pwd)/claim-recovery-service:$(pwd)/notification-service" pytest tests/ -v
```

### Demo both saga paths (approve + reject)

Rebuild claim-recovery-service after code changes, then:

```bash
docker compose up --build -d claim-recovery-service
chmod +x scripts/demo_saga.sh
./scripts/demo_saga.sh
```

### Check saga status at any point

```bash
curl http://localhost:8002/claims/1/saga | python3 -m json.tool
```

## Phase 4 — AWS Step Functions

See full deployment guide: [`docs/STEP_FUNCTIONS.md`](docs/STEP_FUNCTIONS.md)

### Quick start

```bash
# 1. Package mock Lambdas
cd aws && chmod +x package-lambdas.sh && ./package-lambdas.sh

# 2. Upload zips to AWS Lambda (Console) — 5 functions
# 3. Create state machine from aws/step-functions/claim-recovery-saga.asl.json
# 4. Run execution with aws/examples/execution-input-approved.json
```

State machine flow:
```
CreateClaim → ReserveItem → Choice
                               ├─ APPROVED  → RecoverItem  → Success
                               └─ REJECTED  → ReleaseItem  → Compensated
```

## Phase 5 — EC2 Deployment

See full guide: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

### Quick deploy

```bash
# On EC2 (after SSH)
git clone <your-repo> && cd Lostify
cp .env.example .env
./aws/ec2/deploy.sh

# Or from your Mac
./aws/ec2/remote-deploy.sh ubuntu@YOUR_EC2_IP ~/.ssh/key.pem
```

Verify: `curl http://YOUR_EC2_IP:8001/health`

## Phase 6 — CI/CD

See full guide: [`docs/CICD.md`](docs/CICD.md)

### GitHub Actions workflows

| Workflow | Trigger | Action |
|----------|---------|--------|
| `ci.yml` | Push / PR | pytest + Docker build |
| `deploy.yml` | Push to main / manual | Test → deploy EC2 → health check |

### Setup secrets (GitHub → Settings → Secrets)

- `EC2_HOST` — public IP
- `EC2_USER` — `ubuntu`
- `EC2_SSH_KEY` — contents of `.pem` file

### Run CI locally

```bash
./scripts/ci-local.sh
```

## Phase 7 — Testing & Evaluation

See full guide: [`docs/TESTING.md`](docs/TESTING.md)

### Run complete test suite

```bash
docker compose up -d
./scripts/run-all-tests.sh
```

### Generate evaluation report

```bash
./scripts/evaluation-report.sh
```

### Measure event latency

```bash
python3 scripts/measure-event-latency.py
```

**29 tests total:** 21 unit + 8 integration/fault/latency

---

## Project complete

All 7 phases delivered. See [`docs/TESTING.md`](docs/TESTING.md) for demo checklist.
