import type { ChainRow } from "@/lib/api-types";
import { formatSnapshotTime } from "@/lib/format";

export function strikesNearAtm(
  rows: ChainRow[],
  atmStrike: number | null | undefined,
  window = 24,
): ChainRow[] {
  const sorted = [...rows].sort((a, b) => a.strike - b.strike);
  if (!sorted.length) {
    return [];
  }
  if (atmStrike == null) {
    return sorted.slice(0, window);
  }
  let mid = sorted.findIndex((r) => r.strike >= atmStrike);
  if (mid < 0) {
    mid = Math.floor(sorted.length / 2);
  }
  const half = Math.floor(window / 2);
  const start = Math.max(0, mid - half);
  return sorted.slice(start, start + window);
}

export function metricsTrendPoints(
  rows: Array<{
    time: string;
    pcr_oi?: number | null;
    sentiment_score?: number | null;
  }>,
) {
  return rows.map((row) => ({
    label: formatSnapshotTime(row.time),
    pcr_oi: row.pcr_oi ?? null,
    sentiment_score: row.sentiment_score ?? null,
  }));
}

export function oiHeatAlpha(value: number, max: number): number {
  if (value <= 0 || max <= 0) {
    return 0;
  }
  return 0.04 + Math.min(value / max, 1) * 0.2;
}
