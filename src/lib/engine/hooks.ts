"use client";

import { useQuery } from "@tanstack/react-query";
import { engineGet } from "./client";
import type { HealthJSON, PositionsJSON } from "./types";

export function useEngineHealth() {
  return useQuery({ queryKey: ["engine", "health"], queryFn: () => engineGet<HealthJSON>("health"), staleTime: 5 * 60_000, retry: 1 });
}

export function usePositions(key: string) {
  return useQuery({ queryKey: ["engine", "positions", key], queryFn: () => engineGet<PositionsJSON>("positions", { key }), staleTime: Infinity });
}

export function useConstants() {
  const q = usePositions("C");
  return { ...q, constants: q.data?.constants ?? null };
}
