# Lostify — Lost and Found Web Application

**Zain Afzal\***, **Babar Ali†**, **Muhammad Hamza Azeem‡**  
Team 04  
**July 1, 2026**

*Serverless Cloud Application Automation*  
Prof. Sashko Ristov

\* zain.afzal@student.uibk.ac.at  
† babar.ali@student.uibk.ac.at  
‡ hamza.azeem@student.uibk.ac.at

**Repository:** https://github.com/Babarali2k21/Lostify  
**Live demo:** http://44.220.148.111:3001

---

## Abstract

Lostify is a microservice-based lost-and-found platform where users report lost or found items, receive automatic match notifications, and complete recovery through a claim workflow. The system is built around **three business microservices** — Item Service, Claim/Recovery Service, and Notification Service — plus a React frontend. User registration and login are implemented as **application-level authentication inside Item Service** (JWT), not as a separate microservice, following course guidance on service boundaries.

The prototype uses **Python FastAPI** backends, **SQLite** databases (one per service), **REST APIs**, **Redis pub/sub** for asynchronous events, **Docker** containers, **AWS EC2** for cloud deployment, **GitHub Actions** for CI/CD, and **AWS Step Functions** for Saga visualization and optional workflow sync. The Claim/Recovery Service orchestrates a **Saga pattern** with compensation when claims are rejected.

The project demonstrates microservice decomposition, distributed transaction coordination, event-driven notifications, API composition, container deployment, automated delivery pipelines, and evaluation through **31 automated tests** covering unit, integration, latency, fault tolerance, and lead-time metrics.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Solution](#2-solution)
3. [Core Techniques and Implementation Decisions](#3-core-techniques-and-implementation-decisions)
4. [AWS Deployment and Automation](#4-aws-deployment-and-automation)
5. [Evaluation](#5-evaluation)
6. [Discussion](#6-discussion)
7. [Conclusion and Future Work](#7-conclusion-and-future-work)

---

## 1. Introduction

People lose personal items in universities, public buildings, offices, libraries, and events every day. Recovery often depends on manual communication: calling an office, visiting a physical lost-and-found desk, or hoping someone posts about the found item. This process is slow, unstructured, and hard to track.

Lostify addresses this with a digital lost-and-found platform. Users report lost or found items; the system searches for matches and guides recovery through claims, approvals, and notifications. The platform demonstrates:

- Microservice architecture
- Distributed transactions and Saga coordination
- Queries across microservices (API composition)
- Event-driven communication
- Cloud deployment on AWS
- CI/CD automation
- Structured evaluation

### Service boundary decision (professor feedback)

During the course, we were advised that **User Service should not be a separate microservice**. Authentication is a **cross-cutting concern** that supports the domain but is not an independent business capability. Therefore:

| Component | Role |
|-----------|------|
| **Item Service** | Business microservice — items, matching, item states, **register/login/JWT** |
| **Claim/Recovery Service** | Business microservice — claims, Saga, compensation, Step Functions sync |
| **Notification Service** | Business microservice — event consumer, deduplication, notification log |

This matches the three-service architecture required for evaluation while keeping security (JWT) available to all protected endpoints.

---

## 2. Solution

### 2.1 Use case overview

Lostify supports the typical lost-and-found workflow:

1. A user who **lost** an item creates a lost-item report.
2. A finder creates a **found** item report.
3. The **Item Service** runs keyword-based matching on title and description.
4. If a match is found, item status becomes **MATCHED** and a **MatchFound** event is published.
5. The **Notification Service** consumes the event and records the notification.
6. The matched user submits a **claim** via the Claim/Recovery Service.
7. The Saga **reserves** the item (MATCHED → RESERVED) while the finder reviews.
8. **Approved** → item becomes RECOVERED; **Rejected** → compensation releases item back to MATCHED.

**Design scenarios implemented:**

| Scenario | Outcome |
|----------|---------|
| Match found | MATCHED + MatchFound notification |
| Claim approved | APPROVED claim, RECOVERED item, ClaimApproved + ItemRecovered events |
| Claim rejected | REJECTED claim, item released to MATCHED (compensation), ClaimRejected event |
| No match | Item stays OPEN until a compatible report appears |

> **Note:** Claim cancellation before approval is described in the original design but is **not implemented** in the MVP prototype. Rejection by the finder covers the main compensation path.

### 2.2 Complete flow

```
┌─────────────┐     register/login/items      ┌──────────────┐
│   Frontend  │ ────────────────────────────► │ Item Service │
│  React:3001 │                               │    :8001     │
└──────┬──────┘                               └──────┬───────┘
       │ claims/approve/reject                        │ publish
       ▼                                              ▼
┌──────────────────┐    REST reserve/release/   ┌─────────┐
│ Claim/Recovery   │ ◄── recover ──────────────► │  Redis  │
│ Service :8002    │                             │ pub/sub │
└────────┬─────────┘                             └────┬────┘
         │ publish                                    │ subscribe
         └────────────────────────────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  Notification    │
                          │  Service :8003   │
                          └──────────────────┘
```

**Happy-path event sequence (verified in integration tests):**

```
ItemCreated (lost) → ItemCreated (found) → MatchFound → ClaimCreated
  → ClaimApproved → ItemRecovered
```

### 2.3 Project objectives and requirements

| Requirement | Implementation | Objective |
|-------------|----------------|-----------|
| Item reports | Item Service: CRUD, matching, states OPEN/MATCHED/RESERVED/RECOVERED | Business-capability decomposition |
| Authentication | JWT register/login in Item Service (not a 4th microservice) | Cross-cutting auth without wrong service split |
| Claim & recovery | Claim/Recovery Service: claims, Saga, compensation | Distributed workflow coordination |
| Notifications | Notification Service: Redis consumer + eventId deduplication | Event-driven async communication |
| Separate databases | SQLite per service (`item.db`, `claim.db`, `notification.db`) | Data ownership, loose coupling |
| Cross-service workflow | ClaimRecoverySaga + AWS Step Functions mirror | Saga pattern with compensation |
| Dashboard queries | Frontend API composition across three services | Cross-service queries |
| Cloud deployment | Docker on AWS EC2, Redis internal, Step Functions in eu-central-1 | Container + cloud deployment |
| Automation | GitHub Actions: test → build → deploy | CI/CD lead time ~3–5 min |
| Evaluation | 31 pytest tests + demo scripts + latency measurement | Reproducible evidence |

### 2.4 Project implementation

| Layer | Technology | Notes |
|-------|------------|-------|
| Frontend | React 18 + Vite + nginx | Port 3001; proxies `/api/item/*`, `/api/claim/*`, `/api/notif/*` |
| Backend | Python 3.12 + FastAPI | Three independent services |
| Databases | SQLite (per service) | PostgreSQL via RDS documented as upgrade path |
| Event bus | Redis 7 pub/sub | Channel `lostify:events` |
| Containers | Docker + Docker Compose | `docker-compose.yml` (local), `docker-compose.prod.yml` (EC2) |
| Cloud | AWS EC2 (Ubuntu 24.04, t3.small) | Public demo at `44.220.148.111` |
| Workflow | AWS Step Functions + 5 Lambda functions | Region `eu-central-1`; optional auto-trigger from Claim/Recovery Service |
| CI/CD | GitHub Actions | `ci.yml` + `deploy.yml` with `environment: production` |

**Repository structure:**

```
Lostify/
├── frontend/                 # React UI + nginx reverse proxy
├── item-service/             # Auth, items, matching, workflow endpoints
├── claim-recovery-service/   # Claims, saga, Step Functions integration
├── notification-service/     # Event consumer + deduplication
├── shared/events/            # Event models + Redis EventBus
├── aws/                      # Step Functions ASL, Lambdas, EC2 scripts
├── tests/                    # 31 automated tests
├── scripts/                  # Demo + evaluation scripts
└── .github/workflows/        # CI/CD pipelines
```

### 2.5 Main implementation innovation

The key idea is combining **automatic matching** with a **controlled recovery Saga**:

1. **Separation of concerns:** Matching stays in Item Service; claim states and compensation live in Claim/Recovery Service.
2. **Hybrid Saga model:** Local orchestration in `claim-recovery-service/app/saga.py` drives the real demo; AWS Step Functions provides a **visual orchestration graph** and execution history for presentation.
3. **Event-driven notifications:** Item and Claim/Recovery services publish events; Notification Service never receives direct “create notification” calls from business logic.
4. **Compensation:** Rejecting a claim triggers `POST /items/{id}/release` on Item Service, undoing the reserve step.

### 2.6 Implementation challenges

#### 2.6.1 Development challenges

- **Service split:** Deciding to merge auth into Item Service while keeping three clear business boundaries.
- **Event contracts:** Stable envelope (`eventId`, `eventType`, `payload`, `timestamp`) across all publishers.
- **Saga coordination:** Claim/Recovery Service must call Item Service REST endpoints atomically per step, with clear failure handling.
- **Matching quality:** Keyword overlap works for demo data but can false-positive on vague descriptions.

#### 2.6.2 Evaluation challenges

- Async paths (Redis → Notification Service) require measuring **end-to-end latency**, not just HTTP response time.
- Results differ between local Docker and EC2 due to network and instance size.
- Integration tests need a healthy full stack (`docker compose up --build -d`).

#### 2.6.3 Team work challenges

- Agreement on REST contracts between Item Service (`/items/{id}/reserve|release|recover`) and Claim/Recovery Service.
- Shared event schema in `shared/events/` used by all services.

#### 2.6.4 Other challenges

- **AWS IAM on EC2:** Docker containers need IMDSv2 hop limit = 2 for Step Functions boto3 calls (`aws/ec2/setup-step-functions-sync.sh`).
- **CI/CD secrets:** GitHub `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY` for automated deploy.
- **Git history hygiene:** Co-authored commit trailers removed to keep contributor list accurate.

---

## 3. Core Techniques and Implementation Decisions

### 3.1 Microservice architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Frontend (nginx :3001)                                │
│   /api/item/*  →  item-service:8001                                    │
│   /api/claim/* →  claim-recovery-service:8002                            │
│   /api/notif/* →  notification-service:8003                              │
└──────────────────────────────────────────────────────────────────────────┘
         │                    │                         │
         ▼                    ▼                         ▼
┌─────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
│  Item Service   │  │ Claim/Recovery Svc   │  │ Notification Service│
│     :8001       │◄─│       :8002          │  │        :8003        │
│ • auth (JWT)    │  │ • claims + saga      │  │ • Redis subscriber  │
│ • items/match   │  │ • Step Functions     │  │ • deduplication     │
│ • item states   │  │ • compensation       │  └──────────▲──────────┘
└────────┬────────┘  └──────────┬───────────┘             │
         │ publish              │ publish                  │ subscribe
         └──────────────────────┴──────────────────────────┘
                                    │
                              ┌─────▼─────┐
                              │   Redis   │
                              │   :6379   │
                              └───────────┘
```

| Service | Port | Database | Responsibility |
|---------|------|----------|----------------|
| item-service | 8001 | SQLite | Register, login, JWT, items, matching, state machine |
| claim-recovery-service | 8002 | SQLite | Claims, Saga, REST calls to Item Service, Step Functions |
| notification-service | 8003 | SQLite | Consume events, dedupe by `eventId`, notification log |
| frontend | 3001 | — | React SPA + API gateway |
| redis | 6379 (internal on EC2) | — | Pub/sub channel `lostify:events` |

### 3.2 Transactions and coordination (Saga)

**Item state machine (Item Service):**

```
OPEN ──match──► MATCHED ──claim──► RESERVED ──approve──► RECOVERED
                                    │
                                    └──reject (compensate)──► MATCHED
```

**Claim state machine (Claim/Recovery Service):**

```
PENDING ──approve──► APPROVED
    │
    └──reject──► REJECTED
```

**Saga steps:**

| Step | Action | Item state | Claim state | Event |
|------|--------|------------|-------------|-------|
| 1 | CreateClaim | MATCHED | PENDING | — |
| 2 | ReserveItem (REST) | RESERVED | PENDING | — |
| 3 | NotifyClaimCreated | RESERVED | PENDING | ClaimCreated |
| 4a | ApproveClaim | RESERVED | APPROVED | — |
| 5a | RecoverItem (REST) | RECOVERED | APPROVED | ClaimApproved, ItemRecovered |
| 4b | RejectClaim | RESERVED | REJECTED | — |
| 5b | CompensateRelease (REST) | MATCHED | REJECTED | ClaimRejected |

**AWS Step Functions mirror** (`aws/step-functions/claim-recovery-saga.asl.json`):

```
CreateClaim → ReserveItem → NotifyClaimCreated → Choice
    ├─ APPROVED  → RecoverItem → NotifyClaimApproved → NotifyItemRecovered → SagaSucceeded
    └─ REJECTED  → ReleaseItem → NotifyClaimRejected → SagaCompensated
```

Five mock Lambda functions package the same logical steps for the AWS Console graph view. When `STEP_FUNCTIONS_STATE_MACHINE_ARN` is set on EC2, Claim/Recovery Service can auto-start executions and the frontend Saga panel shows AWS sync status.

### 3.3 Queries across microservices

The React dashboard uses **API composition**:

| Data | Source | Endpoint |
|------|--------|----------|
| Items | Item Service | `GET /items` |
| Processed events / notifications | Notification Service | `GET /events/processed` |
| Saga status | Claim/Recovery Service | `GET /claims/{id}/saga` |

The frontend combines these in parallel (`Promise.all`). If one service is unavailable, the UI shows an error for that section without crashing the whole page.

**Pull synchronization:** Dashboard refresh fetches current state on demand.  
**Push synchronization:** MatchFound and claim events update Notification Service asynchronously via Redis without the user polling.

### 3.4 Communication and event handling

**REST** is used for synchronous operations (create item, submit claim, approve/reject).  
**Redis pub/sub** is used for asynchronous notifications.

**Event catalog (implemented):**

| Event | Publisher | Trigger |
|-------|-----------|---------|
| ItemCreated | Item Service | `POST /items` |
| MatchFound | Item Service | Keyword match on item creation |
| ClaimCreated | Claim/Recovery Service | `POST /claims` |
| ClaimApproved | Claim/Recovery Service | `POST /claims/{id}/approve` |
| ClaimRejected | Claim/Recovery Service | `POST /claims/{id}/reject` |
| ItemRecovered | Claim/Recovery Service | After approve + recover |

**Event envelope:**

```json
{
  "eventId": "uuid-v4",
  "eventType": "MatchFound",
  "payload": { "lostItemId": 1, "foundItemId": 2, "title": "Found iPhone" },
  "timestamp": "2026-07-01T16:00:00+00:00"
}
```

**Deduplication:** Notification Service stores processed `eventId` values. Duplicate delivery (Redis retry, network glitch) is ignored — verified by unit and fault-tolerance tests.

### 3.5 Scalability and deployment concepts

- **Container isolation:** Each service has its own Dockerfile and can be rebuilt independently.
- **Database per service:** No shared tables; schema changes are local to each service.
- **Internal Redis on EC2:** Port 6379 not exposed in `docker-compose.prod.yml`.
- **Optional horizontal scaling:** Item and Notification services could be replicated behind a load balancer; Claim/Recovery Saga steps are stateful per claim.
- **Managed workflow:** Step Functions provides execution history and visual debugging.

### 3.6 Portability and interoperability

| Portable | AWS-specific |
|----------|--------------|
| HTTP/REST, JSON | Step Functions state machine |
| Docker, Docker Compose | EC2 instance + security groups |
| SQLite (dev) / PostgreSQL (upgrade) | Lambda function ARNs in ASL |
| Redis pub/sub | IAM roles for EC2 → Step Functions |

Event format abstraction in `shared/events/` allows swapping Redis for another broker if the envelope stays stable.

---

## 4. AWS Deployment and Automation

### 4.1 EC2 deployment

| Setting | Value |
|---------|-------|
| Instance | Ubuntu 24.04 LTS, t3.small |
| Public IP | 44.220.148.111 |
| Frontend URL | http://44.220.148.111:3001 |
| Security group | 22 (SSH), 3001, 8001–8003 |
| Compose file | `docker-compose.prod.yml` |
| Deploy script | `aws/ec2/deploy.sh` |

**Health verification:**

```bash
curl http://44.220.148.111:3001/api/item/health
curl http://44.220.148.111:3001/api/claim/health
curl http://44.220.148.111:3001/api/notif/health
```

**Estimated monthly cost (demo):** ~$17 (t3.small + 20 GB EBS). Stop instance when not demoing.

### 4.2 AWS Step Functions and Lambda

| Asset | Location |
|-------|----------|
| State machine definition | `aws/step-functions/claim-recovery-saga.asl.json` |
| Lambda handlers | `aws/lambda/{create_claim,reserve_item,recover_item,release_item,send_notification}/` |
| Package script | `aws/package-lambdas.sh` → `aws/dist/*.zip` |
| Example inputs | `aws/examples/execution-input-approved.json`, `execution-input-rejected.json` |
| Region | `eu-central-1` |

**Setup steps (AWS Console):**

1. Package and upload 5 Lambda zip files (Python 3.12, handler `handler.handler`).
2. Create state machine `LostifyClaimRecoverySaga` from ASL JSON.
3. Grant Step Functions role `lambda:InvokeFunction`.
4. On EC2: set `STEP_FUNCTIONS_STATE_MACHINE_ARN` in `.env`, run `aws/ec2/setup-step-functions-sync.sh`.

The frontend **Saga panel** displays local saga state and optional `awsExecutionStatus` when Step Functions is enabled.

### 4.3 CI/CD pipeline (GitHub Actions)

**Repository:** https://github.com/Babarali2k21/Lostify

| Workflow | Trigger | Jobs |
|----------|---------|------|
| `ci.yml` | Push / PR to `main` | Unit tests → Integration tests (Docker) → Docker build |
| `deploy.yml` | Push to `main` / manual | Pre-deploy tests → rsync to EC2 → `docker compose up --build` → health check |

**GitHub secrets:** `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`

**Deploy job** uses `environment: production` so the repository Deployments sidebar reflects the latest status.

**Lead time (commit → production):**

| Stage | Duration |
|-------|----------|
| Unit tests | ~30 s |
| Integration + Docker build | ~2–3 min |
| EC2 deploy + health check | ~1–2 min |
| **Total** | **~3–5 min** |

### 4.4 Demo scripts (evaluation evidence)

| Script | Purpose |
|--------|---------|
| `scripts/demo.sh` | Full happy-path curl demo |
| `scripts/demo_reject.sh` | Compensation path |
| `scripts/demo_saga.sh` | Saga status API |
| `scripts/test_duplicate_events.py` | Live deduplication proof |
| `scripts/run-all-tests.sh` | Complete test suite |
| `scripts/evaluation-report.sh` | Printable evaluation summary |
| `scripts/measure-event-latency.py` | Async latency metrics |

---

## 5. Evaluation

This section completes the evaluation that was marked TODO in the earlier report draft. All tests and scripts live in the repository and can be reproduced by the evaluator.

### 5.1 Evaluation methodology

We evaluated Lostify across five dimensions aligned with the course objectives:

1. **Functional correctness** — unit and integration tests
2. **Distributed workflow** — Saga approve and reject paths
3. **Event-driven behavior** — latency and deduplication
4. **Fault tolerance** — invalid states, auth errors, duplicate events
5. **Automation lead time** — GitHub Actions pipeline duration

### 5.2 Automated test suite

**Total: 31 tests** (22 unit + 9 integration/fault/latency)

| Category | File | Tests | Docker required |
|----------|------|-------|-----------------|
| Event model | `test_events.py` | 4 | No |
| Deduplication | `test_duplicate_events.py` | 4 | No |
| Saga logic | `test_saga.py` | 8 | No |
| Step Functions client | `test_step_functions.py` | 6 | No |
| E2E happy + reject | `test_integration.py` | 2 | Yes |
| Fault tolerance | `test_fault_tolerance.py` | 5 | Yes (3), No (2) |
| Event latency | `test_event_latency.py` | 2 | Yes |

**Run locally:**

```bash
cd ~/Projects/Lostify
docker compose down --remove-orphans
docker compose up --build -d
./scripts/run-all-tests.sh
```

**CI:** GitHub Actions runs the same suites on every push to `main`. Latest pipeline status: green on `main` (commit `4e79dc1`).

### 5.3 Functional evaluation results

| Test scenario | Expected | Verified by |
|---------------|----------|-------------|
| Register + login | JWT returned | `test_full_demo_flow` |
| Create lost + found items | Items stored | `test_full_demo_flow` |
| Keyword matching | MATCHED status + MatchFound | `test_full_demo_flow` |
| Submit claim | RESERVED item, PENDING claim | `test_submit_claim_reserves_item` |
| Approve claim | RECOVERED item, COMPLETED saga | `test_approve_completes_saga` |
| Reject claim | MATCHED item (compensated), COMPENSATED saga | `test_reject_compensates_saga`, `test_reject_compensates_item` |
| Claim on OPEN item | HTTP 400 | `test_cannot_claim_open_item` |
| Double approve | HTTP 400 | `test_cannot_approve_twice` |
| Wrong user approves | HTTP 403 | `test_wrong_user_cannot_approve` |
| Invalid item transition | HTTP 400 | `test_invalid_item_transition_blocked` |

### 5.4 Fault tolerance evaluation

| Scenario | Mechanism | Test |
|----------|-----------|------|
| Duplicate Redis delivery | `eventId` stored in Notification DB | `test_duplicate_event_not_processed_twice` |
| Duplicate publish | Second event ignored | `test_duplicate_publish_single_processed_count` |
| Saga compensation | `POST /items/{id}/release` on reject | `test_reject_compensates_item` |
| Authorization | JWT validated on protected routes | `test_wrong_user_cannot_approve` |

Live deduplication demo:

```bash
python3 scripts/test_duplicate_events.py
# Expected: ✅ PASS — Duplicate event was correctly ignored
```

### 5.5 Performance and latency evaluation

**Synchronous API:** Item and claim endpoints respond in tens of milliseconds on local Docker.

**Asynchronous event path** (publish → Redis → Notification Service):

```bash
python3 scripts/measure-event-latency.py
```

Typical local results:

| Metric | Typical range |
|--------|---------------|
| MatchFound latency | 50–500 ms |
| ClaimCreated latency | 50–500 ms |
| Automated test threshold | < 5000 ms (CI-safe) |

EC2 latency is higher due to network hop but remains within the test threshold when the stack is healthy.

### 5.6 CI/CD lead time evaluation

Measured from GitHub Actions workflow runs:

| Workflow run | Commit | Result | Duration |
|--------------|--------|--------|----------|
| CI #11 | Frontend USER_API fix | Success | ~1m 38s |
| Deploy #12 | Test harness hardening | Success | ~1m 0s |
| Deploy #13 | Production environment reporting | Success | ~56s |

**Observation:** Automated deploy from `git push` to healthy EC2 completes in under 5 minutes, satisfying the automation evaluation criterion.

### 5.7 Manual demo checklist (live evaluation)

Use during the presentation with the professor:

- [ ] Open http://44.220.148.111:3001 — register two users, create lost + found items
- [ ] Confirm match notification in events panel
- [ ] Submit claim → show RESERVED / saga AWAITING_DECISION
- [ ] Approve → RECOVERED + events ClaimApproved, ItemRecovered
- [ ] Repeat with reject → COMPENSATED saga, item back to MATCHED
- [ ] AWS Console: Step Functions graph — run APPROVED and REJECTED executions
- [ ] GitHub Actions: show green CI and Deploy workflows
- [ ] Run `./scripts/evaluation-report.sh` for timestamped summary

### 5.8 Evaluation summary

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Microservice decomposition (3 services) | ✅ | Architecture + running EC2 stack |
| No User microservice | ✅ | Auth in Item Service; professor feedback addressed |
| Saga with compensation | ✅ | `test_reject_compensates_*`, demo scripts |
| Event-driven notifications | ✅ | 6 event types, integration flow |
| Deduplication | ✅ | Unit + fault tests + live script |
| AWS EC2 deployment | ✅ | Live URL + deploy workflow |
| AWS Step Functions | ✅ | ASL + Lambdas + optional EC2 sync |
| CI/CD automation | ✅ | GitHub Actions, ~3–5 min lead time |
| Automated test coverage | ✅ | 31 tests |

---

## 6. Discussion

### 6.1 Threats to validity

- **Small dataset:** Tests use controlled item descriptions; real-world data may reduce matching accuracy.
- **Environment differences:** Local Docker vs EC2 network affects latency numbers.
- **Simplified matching:** Keyword overlap is demonstrable but not production-grade.
- **Partial failure coverage:** Not every distributed failure mode (network partition, partial Redis outage) is tested.

### 6.2 Project limitations

- No claim **cancellation** endpoint (reject path covers compensation).
- No strong identity verification beyond JWT username/password.
- SQLite instead of PostgreSQL in the MVP (RDS path documented).
- Console-log notifications instead of email (SES documented as future work).
- Step Functions Lambdas are **mock** handlers for visualization; local Saga drives the live demo.

### 6.3 Self reflection

| Student | Main contribution | Reflection |
|---------|-------------------|------------|
| **Zain Afzal** | Notification Service, Redis event handling, deduplication, integration testing | Learned that notifications need `eventId` deduplication. Would define event contracts earlier next time. |
| **Babar Ali** | Claim/Recovery Service, Saga, Step Functions, EC2 + CI/CD deployment | Learned that Saga needs explicit failure paths and compensation. Would design the state machine diagram before coding. |
| **Muhammad Hamza Azeem** | Item Service, matching, item states, auth merge, workflow tests | Learned that keeping matching inside Item Service simplified the prototype. Would only split matching if data volume demands it. |

---

## 7. Conclusion and Future Work

Lostify demonstrates a working lost-and-found platform using **three business microservices**, event-driven notifications, Saga-based claim recovery with compensation, Docker deployment on **AWS EC2**, and **GitHub Actions** CI/CD. Authentication is correctly placed in Item Service rather than as a separate microservice.

**Key technical achievements:**

- Choreographed Saga in Claim/Recovery Service with REST coordination to Item Service
- Redis pub/sub event bus with deduplication in Notification Service
- AWS Step Functions visualization of the same workflow
- 31 automated tests and reproducible demo scripts
- Production deploy in ~3–5 minutes via CI/CD

**Future work:**

- PostgreSQL on RDS, email via SES, image storage on S3
- Claim cancellation endpoint
- Better matching (structured fields, fuzzy text, manual review queue)
- Replace mock Lambdas with handlers that call live EC2 service URLs
- Kubernetes or ECS for multi-instance scaling
- Restrict EC2 security group to university IP for production hardening

---

## Appendix A — Quick reference

### Service ports (local and EC2)

| Service | Port |
|---------|------|
| Frontend | 3001 |
| Item Service | 8001 |
| Claim/Recovery Service | 8002 |
| Notification Service | 8003 |
| Redis | 6379 (local only; internal on EC2) |

### Key API endpoints

| Method | Path | Service |
|--------|------|---------|
| POST | `/register`, `/login` | Item :8001 |
| POST | `/items` | Item :8001 |
| POST | `/items/{id}/reserve\|release\|recover` | Item :8001 |
| POST | `/claims` | Claim/Recovery :8002 |
| POST | `/claims/{id}/approve\|reject` | Claim/Recovery :8002 |
| GET | `/claims/{id}/saga` | Claim/Recovery :8002 |
| GET | `/events/processed` | Notification :8003 |

### Documentation index

| Document | Content |
|----------|---------|
| `README.md` | Quick start, all phases |
| `docs/EVENTS.md` | Event catalog |
| `docs/SAGA.md` | Saga steps and APIs |
| `docs/STEP_FUNCTIONS.md` | AWS setup guide |
| `docs/DEPLOYMENT.md` | EC2 deployment |
| `docs/CICD.md` | GitHub Actions |
| `docs/TESTING.md` | Test strategy |

---

*Report generated to reflect the implemented prototype as of July 1, 2026. Repository: https://github.com/Babarali2k21/Lostify*
