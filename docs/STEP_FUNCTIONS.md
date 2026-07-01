# Phase 4 — AWS Step Functions: Claim Recovery Saga

Visual orchestration of the Lostify saga using **AWS Step Functions** + **mock Lambda** tasks.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              AWS Step Functions: ClaimRecoverySaga              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  START                                                          │
│    │                                                            │
│    ▼                                                            │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐      │
│  │ CreateClaim │───►│ ReserveItem  │───►│ AwaitDecision │      │
│  │  (Lambda)   │    │   (Lambda)   │    │   (Choice)    │      │
│  └─────────────┘    └──────────────┘    └───────┬───────┘      │
│                                                  │              │
│                          ┌───────────────────────┴──────┐       │
│                          │                              │       │
│                    APPROVED                        REJECTED     │
│                          │                              │       │
│                          ▼                              ▼       │
│                   ┌─────────────┐              ┌─────────────┐  │
│                   │ RecoverItem │              │ ReleaseItem │  │
│                   │  (Lambda)   │              │  (Lambda)   │  │
│                   └──────┬──────┘              └──────┬──────┘  │
│                          │                            │         │
│                          ▼                            ▼         │
│                   ┌─────────────┐              ┌─────────────┐  │
│                   │SagaSucceeded│              │SagaCompens- │  │
│                   │  (Success)  │              │   ated      │  │
│                   └─────────────┘              └─────────────┘  │
│                                                                 │
│  Any Lambda error ──────────────────────────► SagaFailed (Fail)│
└─────────────────────────────────────────────────────────────────┘
```

This mirrors the local saga in `claim-recovery-service/app/saga.py`. Lambdas call Item Service REST endpoints for `reserve`, `release`, and `recover`; claim records live in Claim/Recovery Service.

---

## Files

| File | Purpose |
|------|---------|
| `aws/step-functions/claim-recovery-saga.asl.json` | State machine definition (ASL) |
| `aws/lambda/*/handler.py` | Mock Lambda handlers |
| `aws/examples/execution-input-approved.json` | Happy path input |
| `aws/examples/execution-input-rejected.json` | Compensation path input |
| `aws/package-lambdas.sh` | Package Lambdas into zip files |

---

## Step 1 — Package Lambda functions

```bash
cd ~/Projects/Lostify/aws
chmod +x package-lambdas.sh
./package-lambdas.sh
```

Creates 5 zip files in `aws/dist/`:
- `lostify-create-claim.zip`
- `lostify-reserve-item.zip`
- `lostify-recover-item.zip`
- `lostify-release-item.zip`
- `lostify-send-notification.zip`

---

## Step 2 — Create Lambda functions (AWS Console)

For **each** of the 5 functions:

1. Open [AWS Lambda Console](https://console.aws.amazon.com/lambda)
2. Click **Create function**
3. Choose **Author from scratch**
4. Settings:

| Setting | Value |
|---------|-------|
| Function name | `lostify-create-claim` (etc.) |
| Runtime | Python 3.12 |
| Architecture | arm64 or x86_64 |

5. Click **Create function**
6. Under **Code source**, click **Upload from** → **.zip file**
7. Upload the matching zip from `aws/dist/`
8. Set **Handler** to: `handler.handler`
9. Click **Deploy**

Repeat for all **5** function names:

| Function name | Zip file | Saga step |
|---------------|----------|-----------|
| `lostify-create-claim` | `lostify-create-claim.zip` | CreateClaim |
| `lostify-reserve-item` | `lostify-reserve-item.zip` | ReserveItem |
| `lostify-recover-item` | `lostify-recover-item.zip` | RecoverItem |
| `lostify-release-item` | `lostify-release-item.zip` | ReleaseItem (compensation) |
| `lostify-send-notification` | `lostify-send-notification.zip` | Notify* steps |

> **IAM:** Each Lambda needs basic execution role (`AWSLambdaBasicExecutionRole`). Step Functions needs permission to invoke them (added in Step 4).

---

## Step 3 — Create the State Machine (AWS Console)

1. Open [AWS Step Functions Console](https://console.aws.amazon.com/states)
2. Click **Create state machine**
3. Choose **Write your workflow in code**
4. Type: **Standard**
5. Copy the entire contents of:

   ```
   aws/step-functions/claim-recovery-saga.asl.json
   ```

6. Paste into the definition editor
7. Click **Next**
8. Name: `LostifyClaimRecoverySaga`
9. Create or select an execution role with **Lambda invoke** permissions
10. Click **Create state machine**

### Visual Graph View

After creation, open the state machine → **Graph view**. You should see:

```
CreateClaim → ReserveItem → NotifyClaimCreated → AwaitDecision
                                                    ├─ RecoverItem → NotifyClaimApproved → NotifyItemRecovered → Success
                                                    └─ ReleaseItem → NotifyClaimRejected → Compensated
```

This is your **Saga visualization** for the university presentation.

---

## Step 4 — IAM permissions

The Step Functions execution role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": [
        "arn:aws:lambda:REGION:ACCOUNT_ID:function:lostify-create-claim",
        "arn:aws:lambda:REGION:ACCOUNT_ID:function:lostify-reserve-item",
        "arn:aws:lambda:REGION:ACCOUNT_ID:function:lostify-recover-item",
        "arn:aws:lambda:REGION:ACCOUNT_ID:function:lostify-release-item"
      ]
    }
  ]
}
```

Replace `REGION` and `ACCOUNT_ID`. When creating via Console, the wizard can auto-generate this.

---

## Step 5 — Run executions

### Happy path (APPROVED → RECOVERED)

1. Open your state machine → **Start execution**
2. Paste input from `aws/examples/execution-input-approved.json`:

```json
{
  "itemId": 2,
  "claimantUserId": 1,
  "matchedItemId": 1,
  "decision": "APPROVED"
}
```

3. Click **Start execution**
4. Watch the **Graph** highlight each step green
5. Final state: **SagaSucceeded**

### Compensation path (REJECTED → MATCHED)

1. **Start execution** again
2. Paste input from `aws/examples/execution-input-rejected.json`:

```json
{
  "itemId": 2,
  "claimantUserId": 1,
  "matchedItemId": 1,
  "decision": "REJECTED"
}
```

3. Final state: **SagaCompensated**

---

## Step 6 — Verify Lambda logs

For each execution step, check CloudWatch Logs:

```
/aws/lambda/lostify-create-claim
/aws/lambda/lostify-reserve-item
...
```

Each log entry shows:
```
SAGA STEP | CreateClaim | payload={"itemId": 2, ...}
```

---

## Input schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `itemId` | number | yes | Found item being claimed |
| `claimantUserId` | number | yes | User submitting the claim |
| `matchedItemId` | number | yes | Paired lost item id |
| `decision` | string | yes | `"APPROVED"` or `"REJECTED"` |

---

## Mapping: Local ↔ AWS

| Local (FastAPI) | Step Functions state | Lambda |
|-----------------|---------------------|--------|
| `POST /claims` (:8002) | CreateClaim + ReserveItem | create-claim, reserve-item |
| `POST /claims/{id}/approve` (:8002) | RecoverItem | recover-item |
| `POST /claims/{id}/reject` (:8002) | ReleaseItem | release-item |
| `GET /claims/{id}/saga` (:8002) | Execution output | — |
| `POST /items/{id}/reserve\|release\|recover` (:8001) | ReserveItem / ReleaseItem / RecoverItem | reserve-item, release-item, recover-item |

In production, Lambdas call the Item Service REST API for item state transitions and the Claim/Recovery Service for claim records instead of returning mock data.

---

## Presentation tips

1. **Split screen:** Local demo (curl) on left, Step Functions Graph on right
2. **Run both paths:** Show APPROVED (green Success) vs REJECTED (compensation)
3. **Highlight Choice state:** Explain this is where the saga branches
4. **Mention:** Local uses choreography (events); AWS uses orchestration (Step Functions) — both implement the same saga pattern

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Lambda.ResourceNotFound` | Function names must exactly match ASL |
| `AccessDeniedException` | Add lambda:InvokeFunction to Step Functions role |
| Choice goes to SagaFailed | `decision` must be `"APPROVED"` or `"REJECTED"` (case-sensitive) |
| Handler error | Ensure handler is set to `handler.handler` |

---

## Next: Phase 5

Deploy the full Lostify stack to **EC2** with Docker Compose.
