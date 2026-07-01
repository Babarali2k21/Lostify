import { useCallback, useEffect, useState } from "react";
import { api, clearAuth, getUser, Item, ProcessedEvent, SagaStatus, setAuth, USER_API } from "./api";

type View = "login" | "dashboard";

export default function App() {
  const [view, setView] = useState<View>(getUser() ? "dashboard" : "login");
  const [user, setUser] = useState(getUser());
  const [items, setItems] = useState<Item[]>([]);
  const [events, setEvents] = useState<ProcessedEvent[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeSaga, setActiveSaga] = useState<SagaStatus | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [itemList, eventList] = await Promise.all([
        api.listItems(),
        api.listEvents(),
      ]);
      setItems(itemList);
      setEvents(eventList.slice(0, 15));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    }
  }, []);

  const syncSaga = useCallback(async (claimId: number) => {
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const saga = await api.getSagaStatus(claimId);
        setActiveSaga(saga);
        const eventList = await api.listEvents();
        setEvents(eventList.slice(0, 15));
        if (saga.awsExecutionStatus === "SUCCEEDED" || saga.awsExecutionStatus === "FAILED") {
          break;
        }
      } catch {
        /* saga may not be ready on first tick */
      }
      if (attempt < 4) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }
  }, []);

  useEffect(() => {
    if (view === "dashboard") refresh();
  }, [view, refresh]);

  const handleLogout = () => {
    clearAuth();
    setUser(null);
    setView("login");
  };

  if (view === "login") {
    return <LoginScreen onSuccess={(u, token) => { setAuth(token, u); setUser(u); setView("dashboard"); }} />;
  }

  const myId = user?.id;

  return (
    <div className="app">
      <header className="header">
        <div className="logo">Lost<span>ify</span></div>
        <div className="user-bar">
          <span>👤 {user?.username}</span>
          <button className="btn-ghost" onClick={refresh}>Refresh</button>
          <button className="btn-ghost" onClick={handleLogout}>Logout</button>
        </div>
      </header>

      {error && <div className="error" onClick={() => setError("")}>{error}</div>}
      {message && <div className="success-msg" onClick={() => setMessage("")}>{message}</div>}

      {activeSaga && (
        <SagaPanel saga={activeSaga} onClose={() => setActiveSaga(null)} />
      )}

      <div className="grid-2">
        <CreateItemForm
          loading={loading}
          onSubmit={async (title, description, item_type) => {
            setLoading(true);
            setError("");
            try {
              const item = await api.createItem(title, description, item_type);
              setMessage(`Item #${item.id} created${item.status === "MATCHED" ? " — match found!" : ""}`);
              await refresh();
            } catch (e) {
              setError(e instanceof Error ? e.message : "Failed");
            } finally {
              setLoading(false);
            }
          }}
        />

        <div className="card">
          <h2>Recent Events</h2>
          <div className="events-list">
            {events.length === 0 && <p style={{ color: "var(--muted)" }}>No events yet</p>}
            {events.map((e) => (
              <div key={e.eventId} className="event-row">
                <span className="event-type">{e.eventType}</span>
                <span>{new Date(e.processedAt).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2>All Items ({items.length})</h2>
        <div className="item-list">
          {items.length === 0 && <p style={{ color: "var(--muted)" }}>No items yet — post a lost or found item above.</p>}
          {items.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              myId={myId}
              loading={loading}
              onClaim={async () => {
                setLoading(true);
                setError("");
                try {
                  const claim = await api.submitClaim(item.id);
                  setMessage(`Claim #${claim.id} submitted — item reserved`);
                  await refresh();
                  await syncSaga(claim.id);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Claim failed");
                } finally {
                  setLoading(false);
                }
              }}
              onApprove={async (claimId) => {
                setLoading(true);
                setError("");
                try {
                  await api.approveClaim(claimId);
                  setMessage("Claim approved — item recovered!");
                  await refresh();
                  await syncSaga(claimId);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Approve failed");
                } finally {
                  setLoading(false);
                }
              }}
              onReject={async (claimId) => {
                setLoading(true);
                setError("");
                try {
                  await api.rejectClaim(claimId);
                  setMessage("Claim rejected — compensation applied");
                  await refresh();
                  await syncSaga(claimId);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Reject failed");
                } finally {
                  setLoading(false);
                }
              }}
              onViewSaga={async (claimId) => {
                setLoading(true);
                setError("");
                try {
                  await syncSaga(claimId);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Failed to load saga");
                } finally {
                  setLoading(false);
                }
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function LoginScreen({ onSuccess }: { onSuccess: (user: { id: number; username: string }, token: string) => void }) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      if (tab === "register") {
        await api.register(email, username, password);
      }
      const { access_token } = await api.login(username, password);
      const me = await fetch(`${USER_API}/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      }).then((r) => r.json());
      onSuccess({ id: me.id, username: me.username }, access_token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="card auth-card">
        <div className="logo" style={{ marginBottom: "1.5rem", textAlign: "center" }}>
          Lost<span>ify</span>
        </div>
        <div className="tabs">
          <button className={tab === "login" ? "active" : ""} onClick={() => setTab("login")}>Login</button>
          <button className={tab === "register" ? "active" : ""} onClick={() => setTab("register")}>Register</button>
        </div>
        {error && <div className="error">{error}</div>}
        {tab === "register" && (
          <div className="form-group">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@uni.edu" />
          </div>
        )}
        <div className="form-group">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <button className="btn-primary" style={{ width: "100%" }} disabled={loading} onClick={submit}>
          {loading ? "..." : tab === "login" ? "Login" : "Create account"}
        </button>
      </div>
    </div>
  );
}

function CreateItemForm({
  onSubmit,
  loading,
}: {
  onSubmit: (title: string, description: string, type: "LOST" | "FOUND") => void;
  loading: boolean;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [itemType, setItemType] = useState<"LOST" | "FOUND">("LOST");

  return (
    <div className="card">
      <h2>Post Item</h2>
      <div className="form-group">
        <label>Type</label>
        <select value={itemType} onChange={(e) => setItemType(e.target.value as "LOST" | "FOUND")}>
          <option value="LOST">Lost</option>
          <option value="FOUND">Found</option>
        </select>
      </div>
      <div className="form-group">
        <label>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Black iPhone 14" />
      </div>
      <div className="form-group">
        <label>Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Where and what..." />
      </div>
      <button
        className="btn-primary"
        disabled={loading || !title || !description}
        onClick={() => {
          onSubmit(title, description, itemType);
          setTitle("");
          setDescription("");
        }}
      >
        {loading ? "Posting..." : "Post item"}
      </button>
    </div>
  );
}

function SagaPanel({ saga, onClose }: { saga: SagaStatus; onClose: () => void }) {
  const stateClass =
    saga.sagaState === "COMPLETED"
      ? "saga-completed"
      : saga.sagaState === "COMPENSATED"
        ? "saga-compensated"
        : "saga-awaiting";

  return (
    <div className={`card saga-panel ${stateClass}`}>
      <div className="saga-header">
        <h2>Claim Recovery Saga</h2>
        <button className="btn-ghost saga-close" onClick={onClose}>Dismiss</button>
      </div>
      <div className="saga-meta">
        <span className={`badge saga-state-badge ${stateClass}`}>{saga.sagaState}</span>
        <span>Claim #{saga.claimId}</span>
        <span>Item #{saga.itemId} · {saga.itemStatus}</span>
        {saga.matchedItemId && <span>Matched #{saga.matchedItemId}</span>}
      </div>
      <div className="saga-steps">
        {saga.steps.map((step, i) => {
          const isLast = i === saga.steps.length - 1;
          const isPending = step === "AwaitingDecision";
          const done = !isPending && (saga.sagaState !== "AWAITING_DECISION" || !isLast);
          return (
            <div
              key={`${step}-${i}`}
              className={`saga-step ${done ? "done" : isPending ? "pending" : "active"}`}
            >
              <span className="saga-step-dot">{done ? "✓" : isPending ? "…" : "●"}</span>
              <span>{step}</span>
            </div>
          );
        })}
      </div>
      {saga.notifications.length > 0 && (
        <div className="saga-notifications">
          <strong>Notifications emitted</strong>
          <div className="saga-notif-tags">
            {saga.notifications.map((n) => (
              <span key={n} className="badge badge-matched">{n}</span>
            ))}
          </div>
        </div>
      )}
      <div className="saga-aws-sync">
        <strong>AWS Step Functions</strong>
        <div className="saga-aws-row">
          <span className={`badge aws-badge aws-${saga.awsExecutionStatus.toLowerCase()}`}>
            {saga.awsExecutionStatus}
          </span>
          {saga.awsSynced ? (
            <span className="aws-sync-ok">Synced with frontend action</span>
          ) : saga.awsExecutionStatus === "DISABLED" ? (
            <span className="aws-sync-muted">Not configured on server</span>
          ) : saga.awsExecutionStatus === "NOT_STARTED" ? (
            <span className="aws-sync-muted">No execution yet — check EC2 IAM setup</span>
          ) : (
            <span className="aws-sync-muted">Execution not linked</span>
          )}
        </div>
        {saga.awsExecutionArn && (
          <p className="aws-arn">{saga.awsExecutionArn.split(":").slice(-1)[0]}</p>
        )}
      </div>
    </div>
  );
}

function ItemCard({
  item,
  myId,
  loading,
  onClaim,
  onApprove,
  onReject,
  onViewSaga,
}: {
  item: Item;
  myId?: number;
  loading: boolean;
  onClaim: () => void;
  onApprove: (claimId: number) => void;
  onReject: (claimId: number) => void;
  onViewSaga: (claimId: number) => void;
}) {
  const [pendingClaimId, setPendingClaimId] = useState<number | null>(null);
  const isOwner = item.owner_user_id === myId;
  const canClaim = item.status === "MATCHED" && !isOwner;

  useEffect(() => {
    if (item.status === "RESERVED" || item.status === "RECOVERED") {
      api.listItemClaims(item.id).then((claims) => {
        if (isOwner) {
          const claim = claims.find((c) => c.status === "PENDING") ?? claims[0];
          setPendingClaimId(claim?.id ?? null);
        } else if (myId) {
          const mine = claims.find((c) => c.claimant_user_id === myId);
          setPendingClaimId(mine?.id ?? null);
        } else {
          setPendingClaimId(null);
        }
      }).catch(() => setPendingClaimId(null));
    } else {
      setPendingClaimId(null);
    }
  }, [item.id, item.status, isOwner, myId]);

  return (
    <div className="item-row">
      <div className="item-info">
        <h3>#{item.id} {item.title}</h3>
        <p>{item.description}</p>
        <div className="item-meta">
          <span className={`badge badge-${item.item_type.toLowerCase()}`}>{item.item_type}</span>
          <span className={`badge badge-${item.status.toLowerCase()}`}>{item.status}</span>
          {item.matched_item_id && (
            <span className="badge badge-matched">↔ #{item.matched_item_id}</span>
          )}
          <span className="badge badge-open">owner #{item.owner_user_id}</span>
        </div>
      </div>
      <div className="item-actions">
        {canClaim && (
          <button className="btn-primary" disabled={loading} onClick={onClaim}>
            Submit claim
          </button>
        )}
        {isOwner && item.status === "RESERVED" && pendingClaimId && (
          <>
            <button className="btn-success" disabled={loading} onClick={() => onApprove(pendingClaimId)}>
              Approve claim
            </button>
            <button className="btn-danger" disabled={loading} onClick={() => onReject(pendingClaimId)}>
              Reject claim
            </button>
          </>
        )}
        {(item.status === "RESERVED" || item.status === "RECOVERED") && pendingClaimId && (
          <button className="btn-ghost" disabled={loading} onClick={() => onViewSaga(pendingClaimId)}>
            View saga
          </button>
        )}
      </div>
    </div>
  );
}
