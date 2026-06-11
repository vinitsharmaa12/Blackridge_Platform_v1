/** WebSocket URL helpers for live metrics (PRD 003b). */

export function metricsWsUrl(symbol: string, token: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  const parsed = new URL(base.replace(/\/$/, ""));
  parsed.protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
  parsed.pathname = `/ws/instruments/${encodeURIComponent(symbol.toUpperCase())}`;
  parsed.search = `token=${encodeURIComponent(token)}`;
  return parsed.toString();
}

export type MetricsWsMessage = {
  instrument_id: number;
  time: string;
  underlying?: number | null;
  sentiment_label?: string | null;
  initial?: boolean;
};
