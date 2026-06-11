"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: () => api.getWatchlist(),
  });
}

export function useAddWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) => api.addToWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
}

export function useRemoveWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) => api.removeFromWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
}
