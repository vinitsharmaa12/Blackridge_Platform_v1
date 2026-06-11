import type { components } from "@/lib/types/api";

/** Re-export OpenAPI schema types — field names match the backend/DB. */
export type ChainRow = components["schemas"]["ChainRow"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type Insight = components["schemas"]["Insight"];
export type Instrument = components["schemas"]["Instrument"];
export type LatestMetricsResponse = components["schemas"]["LatestMetricsResponse"];
export type LatestSummary = components["schemas"]["LatestSummary"];
export type MetricsRow = components["schemas"]["MetricsRow"];
export type TopOiStrike = components["schemas"]["TopOiStrike"];
export type WatchlistEntry = components["schemas"]["WatchlistEntry"];
export type WatchlistAddRequest = components["schemas"]["WatchlistAddRequest"];

/** Not in OpenAPI (JSONResponse stub) — matches apps/api/models.py InsightJobResponse. */
export type InsightJobResponse = {
  job_id: string;
  status: string;
};

export type MetricsQuery = {
  from?: string;
  to?: string;
  fields?: string[];
};

export type ChainQuery = {
  at?: "latest" | string;
};

export type InsightsQuery = {
  limit?: number;
};

export type SignalCard = Omit<
  components["schemas"]["SignalCard"],
  "evidence"
> & {
  evidence?: Record<string, unknown>;
};

export type SignalsResponse = Omit<
  components["schemas"]["SignalsResponse"],
  "overall" | "signals"
> & {
  overall: SignalCard;
  signals: SignalCard[];
};

export type SignalsQuery = {
  at?: "latest" | string;
};
