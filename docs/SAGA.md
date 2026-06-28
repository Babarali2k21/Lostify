# Phase 3 — Saga Pattern: Claim & Recovery

Lostify uses a **choreography-based saga** to coordinate the claim and recovery flow across the Item Service and Notification Service (via events).

---

## State Machines

### Item lifecycle

```
OPEN ──match──► MATCHED ──claim──► RESERVED ──approve──► RECOVERED
                                    │
                                    └──reject (compensate)──► MATCHED
```

### Claim lifecycle

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
| 2 | `ReserveItem` | RESERVED | PENDING | — |
| 3 | `NotifyClaimCreated` | RESERVED | PENDING | `ClaimCreated` |
| 4a | `ApproveClaim` | RESERVED | APPROVED | — |
| 5a | `RecoverItem` | RECOVERED | APPROVED | — |
| 6a | `NotifyClaimApproved` | RECOVERED | APPROVED | `ClaimApproved` |
| 7a | `NotifyItemRecovered` | RECOVERED | APPROVED | `ItemRecovered` |
| 4b | `RejectClaim` | RESERVED | REJECTED | — |
| 5b | `CompensateRelease` | MATCHED | REJECTED | — |
| 6b | `NotifyClaimRejected` | MATCHED | REJECTED | `ClaimRejected` |

---

## Happy Path (Approve)

```
SubmitClaim
  → CreateClaim
  → ReserveItem          (MATCHED → RESERVED)
  → emit ClaimCreated

ApproveClaim
  → ApproveClaim         (PENDING → APPROVED)
  → RecoverItem          (RESERVED → RECOVERED)
  → emit ClaimApproved + ItemRecovered
```

## Compensation Path (Reject)

```
SubmitClaim
  → CreateClaim
  → ReserveItem          (MATCHED → RESERVED)

RejectClaim
  → RejectClaim          (PENDING → REJECTED)
  → CompensateRelease    (RESERVED → MATCHED)   ← compensation
  → emit ClaimRejected
```

Compensation **undoes** the reserve step so the item can be claimed again.

---

## Implementation

| File | Role |
|------|------|
| `item-service/app/saga.py` | `ClaimRecoverySaga` orchestrator |
| `item-service/app/state_machine.py` | Valid transition rules |
| `item-service/app/main.py` | REST endpoints delegate to saga |

### API endpoints

| Method | Path | Saga action |
|--------|------|-------------|
| POST | `/claims` | Start saga (CreateClaim + ReserveItem) |
| POST | `/claims/{id}/approve` | Happy path completion |
| POST | `/claims/{id}/reject` | Compensation path |
| GET | `/claims/{id}/saga` | Current saga status (demo) |

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

The saga is visualized in AWS Step Functions. See [`docs/STEP_FUNCTIONS.md`](../STEP_FUNCTIONS.md).

```
Start → CreateClaim → ReserveItem → NotifyClaimCreated → Choice
                                                          ├─ APPROVED  → RecoverItem → NotifyClaimApproved → NotifyItemRecovered → Success
                                                          └─ REJECTED  → ReleaseItem → NotifyClaimRejected → Compensated
```
