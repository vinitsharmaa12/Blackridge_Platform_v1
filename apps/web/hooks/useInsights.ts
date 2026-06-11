"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useInsights(symbol: string) {
  return useQuery({
    queryKey: ["insights", symbol],
    queryFn: () => api.getInsights(symbol, { limit: 20 }),
    refetchInterval: 60_000,
  });
}

export function useGenerateInsight(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateInsight(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["insights", symbol] });
    },
  });
}
