# Phase 3 — Saga Pattern: Claim & Recovery

Lostify uses a **choreography-based saga** coordinated by the **Claim/Recovery Service**. The saga calls Item Service via REST for item state transitions (`reserve`, `release`, `recover`) and publishes events consumed by the Notification Service.

---

## State Machines

### Item lifecycle (Item Service)

```
OPEN ──match──► MATCHED ──claim──► RESERVED ──approve──► RECOVERED
                                    │
                                    └──reject (compensate)──► MATCHED
```

### Claim lifecycle (Claim/Recovery Service)

```
PENDING ──approve──► APPROVED
    │
    └──reject──► REJECTED
```

---

## Saga Steps

| Step | Action | Item state | Claim state | Event emitted |
|------|--------|------------|-------------|---------------|
| 1 | `CreateClaim` | MATCHED | PENDING | — |
| 2 | `ReserveItem` (REST → Item Service) | RESERVED | PENDING | — |
| 3 | `NotifyClaimCreated` | RESERVED | PENDING | `ClaimCreated` |
| 4a | `ApproveClaim` | RESERVED | APPROVED | — |
| 5a | `RecoverItem` (REST → Item Service) | RECOVERED | APPROVED | — |
| 6a | `NotifyClaimApproved` | RECOVERED | APPROVED | `ClaimApproved` |
| 7a | `NotifyItemRecovered` | RECOVERED | APPROVED | `ItemRecovered` |
| 4b | `RejectClaim` | RESERVED | REJECTED | — |
| 5b | `CompensateRelease` (REST → Item Service) | MATCHED | REJECTED | — |
| 6b | `NotifyClaimRejected` | MATCHED | REJECTED | `ClaimRejected` |

---

## Happy Path (Approve)

```
SubmitClaim (Claim/Recovery Service)
  → CreateClaim
  → ReserveItem          (REST: MATCHED → RESERVED)
  → emit ClaimCreated

ApproveClaim
  → ApproveClaim         (PENDING → APPROVED)
  → RecoverItem          (REST: RESERVED → RECOVERED)
  → emit ClaimApproved + ItemRecovered
```

## Compensation Path (Reject)

```
SubmitClaim
  → CreateClaim
  → ReserveItem          (REST: MATCHED → RESERVED)

RejectClaim
  → RejectClaim          (PENDING → REJECTED)
  → CompensateRelease    (REST: RESERVED → MATCHED)   ← compensation
  → emit ClaimRejected
```

Compensation **undoes** the reserve step so the item can be claimed again.

---

## Implementation

| File | Role |
|------|------|
| `claim-recovery-service/app/saga.py` | `ClaimRecoverySaga` orchestrator |
| `claim-recovery-service/app/item_client.py` | REST client for Item Service |
| `claim-recovery-service/app/state_machine.py` | Claim transition rules |
| `claim-recovery-service/app/main.py` | REST endpoints delegate to saga |
| `item-service/app/state_machine.py` | Item transition rules |
| `item-service/app/main.py` | Item CRUD + `/items/{id}/reserve\|release\|recover` |

### API endpoints (Claim/Recovery Service :8002)

| Method | Path | Saga action |
|--------|------|-------------|
| POST | `/claims` | Start saga (CreateClaim + ReserveItem) |
| POST | `/claims/{id}/approve` | Happy path completion |
| POST | `/claims/{id}/reject` | Compensation path |
| GET | `/claims/{id}/saga` | Current saga status (demo) |

### Item Service workflow endpoints (:8001)

| Method | Path | Called by |
|--------|------|-----------|
| POST | `/items/{id}/reserve` | Claim/Recovery Service |
| POST | `/items/{id}/release` | Claim/Recovery Service (compensation) |
| POST | `/items/{id}/recover` | Claim/Recovery Service |

### Example saga status response

```json
{
  "sagaName": "ClaimRecoverySaga",
  "sagaState": "COMPLETED",
  "claimId": 1,
  "claimStatus": "APPROVED",
  "itemId": 2,
  "itemStatus": "RECOVERED",
  "matchedItemId": 1
}
```

`sagaState` values: `AWAITING_DECISION` | `COMPLETED` | `COMPENSATED`

---

## Phase 4 — AWS Step Functions

The saga is visualized in AWS Step Functions. See [`docs/STEP_FUNCTIONS.md`](STEP_FUNCTIONS.md).

```
Start → CreateClaim → ReserveItem → NotifyClaimCreated → Choice
                                                          ├─ APPROVED  → RecoverItem → NotifyClaimApproved → NotifyItemRecovered → Success
                                                          └─ REJECTED  → ReleaseItem → NotifyClaimRejected → Compensated
```
