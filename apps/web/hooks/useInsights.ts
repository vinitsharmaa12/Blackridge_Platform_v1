"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";

const FAST_POLL_MS = 3_000;
const NORMAL_POLL_MS = 60_000;
const FAST_POLL_DURATION_MS = 120_000;

export function useInsights(symbol: string, options?: { fastPoll?: boolean }) {
  const fastPoll = options?.fastPoll ?? false;
  return useQuery({
    queryKey: ["insights", symbol],
    queryFn: () => api.getInsights(symbol, { limit: 20 }),
    refetchInterval: fastPoll ? FAST_POLL_MS : NORMAL_POLL_MS,
  });
}

export function useInsightJob(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: ["insight-job", symbol],
    queryFn: () => api.getInsightJob(symbol),
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "done" || status === "failed") {
        return false;
      }
      return FAST_POLL_MS;
    },
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) {
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function useGenerateInsight(symbol: string) {
  const queryClient = useQueryClient();
  const [fastPollActive, setFastPollActive] = useState(false);
  const fastPollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.generateInsight(symbol),
    onSuccess: () => {
      if (fastPollTimerRef.current != null) {
        clearTimeout(fastPollTimerRef.current);
      }
      setFastPollActive(true);
      fastPollTimerRef.current = setTimeout(() => {
        setFastPollActive(false);
        fastPollTimerRef.current = null;
      }, FAST_POLL_DURATION_MS);
      void queryClient.invalidateQueries({ queryKey: ["insights", symbol] });
      void queryClient.invalidateQueries({ queryKey: ["insight-job", symbol] });
    },
  });

  return { ...mutation, fastPollActive };
}
