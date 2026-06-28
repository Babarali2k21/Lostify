# Lostify Event Catalog (Phase 2)

All inter-service communication uses **Redis pub/sub** on channel `lostify:events`.

## Event Envelope

Every event follows this JSON structure:

```json
{
  "eventId": "uuid-v4",
  "eventType": "MatchFound",
  "payload": { },
  "timestamp": "2026-06-27T08:09:37.196234+00:00"
}
```

| Field       | Type   | Description                              |
|-------------|--------|------------------------------------------|
| `eventId`   | UUID   | Unique id — used for deduplication       |
| `eventType` | string | One of the types below                   |
| `payload`   | object | Event-specific data                      |
| `timestamp` | ISO8601| When the event was created               |

---

## Event Types

### 1. ItemCreated

**Publisher:** Item Service  
**Trigger:** `POST /items`

```json
{
  "eventType": "ItemCreated",
  "payload": {
    "itemId": 1,
    "itemType": "LOST",
    "title": "Black iPhone 14",
    "ownerUserId": 1
  }
}
```

---

### 2. MatchFound

**Publisher:** Item Service  
**Trigger:** Keyword match on item creation

```json
{
  "eventType": "MatchFound",
  "payload": {
    "lostItemId": 1,
    "foundItemId": 2,
    "title": "Found iPhone"
  }
}
```

---

### 3. ClaimCreated

**Publisher:** Item Service  
**Trigger:** `POST /claims` — item moves to RESERVED

```json
{
  "eventType": "ClaimCreated",
  "payload": {
    "claimId": 1,
    "itemId": 2,
    "claimantUserId": 1
  }
}
```

---

### 4. ClaimApproved

**Publisher:** Item Service  
**Trigger:** `POST /claims/{id}/approve`

```json
{
  "eventType": "ClaimApproved",
  "payload": {
    "claimId": 1,
    "itemId": 2,
    "approvedBy": 2
  }
}
```

---

### 5. ClaimRejected

**Publisher:** Item Service  
**Trigger:** `POST /claims/{id}/reject` — saga compensation

```json
{
  "eventType": "ClaimRejected",
  "payload": {
    "claimId": 1,
    "itemId": 2,
    "rejectedBy": 2
  }
}
```

---

### 6. ItemRecovered

**Publisher:** Item Service  
**Trigger:** Claim approved — item moves to RECOVERED

```json
{
  "eventType": "ItemRecovered",
  "payload": {
    "itemId": 2,
    "claimId": 1,
    "recoveredBy": 1
  }
}
```

---

## Deduplication

The **Notification Service** stores processed `eventId` values in its database.

```
Event received → eventId already in DB? → YES → log warning, skip
                                        → NO  → send notification, store eventId
```

This prevents duplicate notifications when:
- Redis redelivers a message
- A publisher retries with the same eventId
- Network glitches cause double delivery

---

## Demo Flow Event Sequence

```
ItemCreated (lost)
ItemCreated (found)
MatchFound
ClaimCreated
ClaimApproved
ItemRecovered
```

Your successful run produced exactly this sequence (6 events).
