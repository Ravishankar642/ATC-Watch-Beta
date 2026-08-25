import type { AtcAhead, AtcCoverage, Me, MyFlight, Traffic, UserSettings } from "../types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    throw new ApiAuthError();
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export class ApiAuthError extends Error {
  constructor() {
    super("Not authenticated");
  }
}

export const api = {
  me: () => request<Me | null>("/api/auth/me"),
  loginUrl: () => `${BASE}/api/auth/login`,
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  myFlight: () => request<MyFlight>("/api/flight/me"),
  atcAhead: () => request<AtcAhead>("/api/atc/ahead"),
  atcCoverage: () => request<AtcCoverage>("/api/atc/coverage"),
  traffic: (radiusNm?: number, altDiffFt?: number) => {
    const params = new URLSearchParams();
    if (radiusNm) params.set("radius_nm", String(radiusNm));
    if (altDiffFt) params.set("altitude_diff_ft", String(altDiffFt));
    const qs = params.toString();
    return request<Traffic>(`/api/traffic${qs ? `?${qs}` : ""}`);
  },

  getSettings: () => request<UserSettings>("/api/settings"),
  updateSettings: (patch: Partial<UserSettings>) =>
    request<UserSettings>("/api/settings", { method: "PUT", body: JSON.stringify(patch) }),

  vapidPublicKey: () => request<{ publicKey: string }>("/api/push/vapid-public-key"),
  subscribePush: (subscription: PushSubscriptionJSON) =>
    request<void>("/api/push/subscribe", {
      method: "POST",
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        keys: subscription.keys,
        user_agent: navigator.userAgent,
      }),
    }),
  unsubscribePush: (endpoint: string) =>
    request<void>(`/api/push/unsubscribe?endpoint=${encodeURIComponent(endpoint)}`, { method: "POST" }),
  sendTestPush: () => request<void>("/api/push/test", { method: "POST" }),

  health: () => request<Record<string, unknown>>("/api/health"),
  debugState: () => request<Record<string, unknown>>("/api/debug/state"),
};
