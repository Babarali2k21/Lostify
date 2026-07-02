# Phase 7 — Testing & Evaluation

Complete test strategy for the Lostify university project.

---

## Test pyramid

```
                    ┌─────────────────┐
                    │  Integration    │  8 tests — full Docker stack
                    │  + Latency      │
                    ├─────────────────┤
                    │ Fault tolerance │  4 tests — rejection, dedup, auth
                    ├─────────────────┤
                    │   Unit tests    │  21 tests — events, saga, dedup
                    └─────────────────┘
```

**Total: 29 tests**

---

## Test categories

| Category | Files | Requires Docker |
|----------|-------|-----------------|
| Unit | `test_events.py`, `test_duplicate_events.py`, `test_saga.py` | No |
| Integration | `test_integration.py` | Yes |
| Fault tolerance | `test_fault_tolerance.py` | Partial (3 need Docker) |
| Event latency | `test_event_latency.py` | Yes |

---

## Run all tests

```bash
# Full suite (auto-detects Docker)
chmod +x scripts/run-all-tests.sh
./scripts/run-all-tests.sh

# Unit only
PYTHONPATH="$(pwd):$(pwd)/item-service:$(pwd)/claim-recovery-service:$(pwd)/notification-service" \
  pytest tests/test_events.py tests/test_duplicate_events.py tests/test_saga.py -v

# Integration only (Docker must be running)
docker compose up -d
pytest tests/test_integration.py tests/test_fault_tolerance.py tests/test_event_latency.py -v -m integration
```

---

## Fault tolerance scenarios

| Scenario | Test | Expected |
|----------|------|----------|
| Claim rejection | `test_reject_compensates_item` | Item returns to MATCHED |
| Event duplication | `test_duplicate_publish_single_processed_count` | Only 1 notification |
| Claim on OPEN item | `test_cannot_claim_open_item` | HTTP 400 |
| Double approve | `test_cannot_approve_twice` | HTTP 400 |
| Wrong user approves | `test_wrong_user_cannot_approve` | HTTP 403 |
| Invalid state transition | `test_invalid_item_transition_blocked` | HTTP 400 |

---

## Event latency measurement

```bash
python3 scripts/measure-event-latency.py
```

Example output:
```
MatchFound latency:    142.3 ms
ClaimCreated latency:   89.7 ms
Total async path:      232.0 ms
```

Typical local Docker: **50–500 ms** per event.

Automated threshold in tests: **5000 ms** (generous for CI).

---

## Evaluation report

Generate a summary for your report/presentation:

```bash
chmod +x scripts/evaluation-report.sh
./scripts/evaluation-report.sh
```

---

## CI/CD integration

GitHub Actions runs:

1. **Unit tests** — every push/PR
2. **Docker build** — validates images
3. **Integration tests** — with `docker compose up` in CI

See [CICD.md](CICD.md) for pipeline details.

---

## Lead time metrics

| Stage | Duration |
|-------|----------|
| Unit tests | ~30 s |
| Docker build | ~2 min |
| Integration tests | ~1 min |
| EC2 deploy | ~1–2 min |
| **Total commit → production** | **~3–5 min** |

---

## Demo checklist for evaluation

- [ ] `./scripts/demo.sh` — happy path
- [ ] `./scripts/demo_reject.sh` — compensation
- [ ] `./scripts/demo_saga.sh` — saga status API
- [ ] `python3 scripts/test_duplicate_events.py` — deduplication
- [ ] AWS Step Functions graph — both APPROVED/REJECTED paths
- [ ] `./scripts/evaluation-report.sh` — metrics summary

---

## Project completion summary

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | Local microservices MVP | Done |
| 2 | Event system + deduplication | Done |
| 3 | Saga pattern + compensation | Done |
| 4 | AWS Step Functions visualization | Done |
| 5 | EC2 deployment | Done |
| 6 | CI/CD pipeline | Done |
| 7 | Testing & evaluation | Done |