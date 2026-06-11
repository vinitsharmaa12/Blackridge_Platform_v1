"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MetricsRow } from "@/lib/api-types";

export function useLatest(symbol: string) {
  return useQuery({
    queryKey: ["latest", symbol],
    queryFn: () => api.getLatest(symbol),
    refetchInterval: 60_000,
  });
}

export function useMetricsSeries(symbol: string) {
  return useQuery({
    queryKey: ["metrics", symbol, "session"],
    queryFn: () => api.getMetrics(symbol),
    refetchInterval: 60_000,
  });
}

export function useSignals(symbol: string, endAt: string) {
  return useQuery({
    queryKey: ["signals", symbol, endAt],
    queryFn: () => api.getSignals(symbol, { at: endAt }),
    refetchInterval: 60_000,
  });
}

export function useChain(symbol: string, endAt: string) {
  return useQuery({
    queryKey: ["chain", symbol, endAt],
    queryFn: () => api.getChain(symbol, { at: endAt }),
    refetchInterval: 60_000,
  });
}

export function metricsAtTime(
  series: MetricsRow[] | undefined,
  time: string,
): MetricsRow | undefined {
  if (!series?.length) {
    return undefined;
  }
  return series.find((row) => row.time === time);
}
