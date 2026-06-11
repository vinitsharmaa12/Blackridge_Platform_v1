import type { MetricsRow } from "@/lib/api-types";

export type TimeViewMode = "session" | "current";

export type TimeRangeSelection = {
  mode: TimeViewMode;
  from: string;
  to: string;
};

export type SessionBounds = {
  from: string;
  to: string;
};

export const EMPTY_TIME_RANGE: TimeRangeSelection = {
  mode: "session",
  from: "",
  to: "",
};

export function deriveSessionBounds(
  series: MetricsRow[] | undefined,
): SessionBounds | null {
  if (!series?.length) {
    return null;
  }
  return {
    from: series[0].time,
    to: series[series.length - 1].time,
  };
}

export function clampRange(
  from: string,
  to: string,
  bounds: SessionBounds | null,
): SessionBounds {
  if (!bounds) {
    return { from: from || "", to: to || "" };
  }
  let clampedFrom = from || bounds.from;
  let clampedTo = to || bounds.to;

  if (clampedFrom < bounds.from) {
    clampedFrom = bounds.from;
  }
  if (clampedFrom > bounds.to) {
    clampedFrom = bounds.to;
  }
  if (clampedTo > bounds.to) {
    clampedTo = bounds.to;
  }
  if (clampedTo < bounds.from) {
    clampedTo = bounds.from;
  }
  if (clampedFrom > clampedTo) {
    clampedTo = clampedFrom;
  }

  return { from: clampedFrom, to: clampedTo };
}

export function filterMetricsByRange(
  series: MetricsRow[] | undefined,
  from: string,
  to: string,
): MetricsRow[] {
  if (!series?.length || !from || !to) {
    return series ?? [];
  }
  return series.filter((row) => row.time >= from && row.time <= to);
}

export function resolveEndAt(
  selection: TimeRangeSelection,
  bounds: SessionBounds | null,
): string {
  if (selection.mode === "current") {
    return "latest";
  }
  if (!bounds) {
    return selection.to || "latest";
  }
  if (!selection.to || selection.to === bounds.to) {
    return "latest";
  }
  return selection.to;
}

export function defaultTimeRange(bounds: SessionBounds | null): TimeRangeSelection {
  if (!bounds) {
    return EMPTY_TIME_RANGE;
  }
  return {
    mode: "session",
    from: bounds.from,
    to: bounds.to,
  };
}

export function snapshotTimesFromSeries(series: MetricsRow[] | undefined): string[] {
  if (!series?.length) {
    return [];
  }
  return [...series].map((row) => row.time).reverse();
}

export function endOptionsForStart(
  snapshotTimes: string[],
  start: string,
): string[] {
  if (!start) {
    return snapshotTimes;
  }
  return snapshotTimes.filter((time) => time >= start);
}
