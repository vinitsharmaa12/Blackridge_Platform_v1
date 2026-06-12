import { createClient } from "@/lib/supabase/client";
import type {
  ChainQuery,
  ChainRow,
  HealthResponse,
  Insight,
  InsightJobResponse,
  InsightJobStatusResponse,
  InsightsQuery,
  Instrument,
  LatestMetricsResponse,
  MetricsQuery,
  MetricsRow,
  SessionSnapshotsQuery,
  SessionSnapshotsResponse,
  SignalsQuery,
  SignalsResponse,
  WatchlistEntry,
} from "@/lib/api-types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function apiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  return base.replace(/\/$/, "");
}

async function getAccessToken(): Promise<string> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (session?.access_token) {
    return session.access_token;
  }

  const {
    data: { session: refreshed },
    error,
  } = await supabase.auth.refreshSession();

  if (error || !refreshed?.access_token) {
    throw new ApiError(401, "Not authenticated");
  }

  return refreshed.access_token;
}

type FetchOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
};

function buildQuery(
  params: Record<string, string | string[] | number | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        search.append(key, item);
      }
    } else {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function apiFetch<T>(
  path: string,
  { method = "GET", body, auth = true }: FetchOptions = {},
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    headers.Authorization = `Bearer ${await getAccessToken()}`;
  }

  const res = await fetch(`${apiBaseUrl()}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && !retried) {
    const supabase = createClient();
    const { data, error } = await supabase.auth.refreshSession();
    if (!error && data.session?.access_token) {
      return apiFetch<T>(path, { method, body, auth }, true);
    }
    throw new ApiError(401, "Session expired — sign in again");
  }

  if (!res.ok) {
    let detail: unknown = null;
    const contentType = res.headers.get("content-type") ?? "";
    try {
      detail = contentType.includes("application/json")
        ? await res.json()
        : await res.text();
    } catch {
      detail = null;
    }
    const message =
      typeof detail === "object" &&
      detail !== null &&
      "detail" in detail &&
      typeof (detail as { detail: unknown }).detail === "string"
        ? (detail as { detail: string }).detail
        : res.statusText || `Request failed (${res.status})`;
    throw new ApiError(res.status, message, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

function enc(symbol: string): string {
  return encodeURIComponent(symbol.toUpperCase());
}

export const api = {
  health: (): Promise<HealthResponse> => apiFetch("/health", { auth: false }),

  listInstruments: (): Promise<Instrument[]> => apiFetch("/instruments"),

  getLatest: (symbol: string): Promise<LatestMetricsResponse> =>
    apiFetch(`/instruments/${enc(symbol)}/latest`),

  getSessionSnapshots: (
    symbol: string,
    query: SessionSnapshotsQuery = {},
  ): Promise<SessionSnapshotsResponse> =>
    apiFetch(
      `/instruments/${enc(symbol)}/session-snapshots${buildQuery({
        date: query.date,
      })}`,
    ),

  getSignals: (
    symbol: string,
    query: SignalsQuery = {},
  ): Promise<SignalsResponse> =>
    apiFetch(
      `/instruments/${enc(symbol)}/signals${buildQuery({
        at: query.at ?? "latest",
      })}`,
    ),

  getMetrics: (symbol: string, query: MetricsQuery = {}): Promise<MetricsRow[]> =>
    apiFetch(
      `/instruments/${enc(symbol)}/metrics${buildQuery({
        from: query.from,
        to: query.to,
        fields: query.fields,
      })}`,
    ),

  getChain: (symbol: string, query: ChainQuery = {}): Promise<ChainRow[]> =>
    apiFetch(
      `/instruments/${enc(symbol)}/chain${buildQuery({
        at: query.at ?? "latest",
      })}`,
    ),

  getInsights: (
    symbol: string,
    query: InsightsQuery = {},
  ): Promise<Insight[]> =>
    apiFetch(
      `/instruments/${enc(symbol)}/insights${buildQuery({
        limit: query.limit,
      })}`,
    ),

  generateInsight: (symbol: string): Promise<InsightJobResponse> =>
    apiFetch(`/instruments/${enc(symbol)}/insights:generate`, { method: "POST" }),

  getInsightJob: (symbol: string): Promise<InsightJobStatusResponse> =>
    apiFetch(`/instruments/${enc(symbol)}/insights/job`),

  getWatchlist: (): Promise<WatchlistEntry[]> => apiFetch("/me/watchlist"),

  addToWatchlist: (symbol: string): Promise<{ symbol: string }> =>
    apiFetch("/me/watchlist", {
      method: "POST",
      body: { symbol: symbol.toUpperCase() },
    }),

  removeFromWatchlist: (symbol: string): Promise<void> =>
    apiFetch(`/me/watchlist/${enc(symbol)}`, { method: "DELETE" }),
};
