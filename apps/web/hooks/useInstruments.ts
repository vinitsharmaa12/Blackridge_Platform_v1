"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useInstruments() {
  return useQuery({
    queryKey: ["instruments"],
    queryFn: () => api.listInstruments(),
  });
}
