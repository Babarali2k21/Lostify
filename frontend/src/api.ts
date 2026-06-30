// Relative paths — proxied by nginx (Docker) or Vite dev server (local)
export const USER_API = "/api/user";
export const ITEM_API = "/api/item";
export const NOTIF_API = "/api/notif";

const TOKEN_KEY = "lostify_token";
const USER_KEY = "lostify_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user: { id: number; username: string }) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser(): { id: number; username: string } | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request<T>(
  url: string,
  options: RequestInit = {},
  auth = false
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || `Request failed (${res.status})`);
  }
  return data as T;
}

export interface Item {
  id: number;
  title: string;
  description: string;
  item_type: "LOST" | "FOUND";
  status: "OPEN" | "MATCHED" | "RESERVED" | "RECOVERED";
  owner_user_id: number;
  matched_item_id: number | null;
}

export interface ProcessedEvent {
  eventId: string;
  eventType: string;
  processedAt: string;
}

export interface SagaStatus {
  sagaName: string;
  sagaState: "AWAITING_DECISION" | "COMPLETED" | "COMPENSATED";
  claimId: number;
  claimStatus: string;
  itemId: number;
  itemStatus: string;
  matchedItemId: number | null;
  notifications: string[];
}

export const api = {
  register: (email: string, username: string, password: string) =>
    request<{ id: number; username: string }>(`${USER_API}/register`, {
      method: "POST",
      body: JSON.stringify({ email, username, password }),
    }),

  login: (username: string, password: string) =>
    request<{ access_token: string }>(`${USER_API}/login`, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  me: () =>
    request<{ id: number; username: string; email: string }>(`${USER_API}/me`, {}, true),

  listItems: () => request<Item[]>(`${ITEM_API}/items`),

  createItem: (title: string, description: string, item_type: "LOST" | "FOUND") =>
    request<Item>(
      `${ITEM_API}/items`,
      {
        method: "POST",
        body: JSON.stringify({ title, description, item_type }),
      },
      true
    ),

  submitClaim: (item_id: number) =>
    request<{ id: number; status: string }>(
      `${ITEM_API}/claims`,
      { method: "POST", body: JSON.stringify({ item_id }) },
      true
    ),

  approveClaim: (claimId: number) =>
    request<{ id: number; status: string }>(
      `${ITEM_API}/claims/${claimId}/approve`,
      { method: "POST" },
      true
    ),

  rejectClaim: (claimId: number) =>
    request<{ id: number; status: string }>(
      `${ITEM_API}/claims/${claimId}/reject`,
      { method: "POST" },
      true
    ),

  listEvents: () => request<ProcessedEvent[]>(`${NOTIF_API}/events/processed`),

  listItemClaims: (itemId: number) =>
    request<{ id: number; status: string; claimant_user_id: number }[]>(
      `${ITEM_API}/items/${itemId}/claims`
    ),

  getSagaStatus: (claimId: number) =>
    request<SagaStatus>(`${ITEM_API}/claims/${claimId}/saga`, {}, true),
};
