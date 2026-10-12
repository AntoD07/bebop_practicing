"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { todayLocal } from "@/lib/utils";
import { useSession } from "./session";

type Day = { date: string; key: string; position: number; updatedAt: string };

async function fetchDay(date: string): Promise<Day> {
  const r = await fetch(`/api/practice-day?date=${date}`);
  if (!r.ok) throw new Error(`practice-day ${r.status}`);
  return r.json();
}

async function putDay(body: { date: string; key?: string; position?: number }): Promise<Day> {
  const r = await fetch("/api/practice-day", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`practice-day ${r.status}`);
  return r.json();
}

/** Today's key/position: the SERVER draws them once per day; the store caches
 * them; changing either persists the override so every device agrees. */
export function usePracticeDay() {
  const date = todayLocal();
  const qc = useQueryClient();
  const setDay = useSession((s) => s.setDay);
  const q = useQuery({ queryKey: ["practice-day", date], queryFn: () => fetchDay(date), staleTime: 60_000, refetchOnWindowFocus: true });
  useEffect(() => {
    if (q.data) setDay(q.data.date, q.data.key, q.data.position);
  }, [q.data, setDay]);
  const mut = useMutation({
    mutationFn: putDay,
    onMutate: async (body) => {
      const prev = qc.getQueryData<Day>(["practice-day", date]);
      if (prev) {
        const next = { ...prev, ...(body.key ? { key: body.key } : {}), ...(body.position ? { position: body.position } : {}) };
        qc.setQueryData(["practice-day", date], next);
        setDay(next.date, next.key, next.position);
      }
      return { prev };
    },
    onError: (_e, _b, ctx) => {
      if (ctx?.prev) {
        qc.setQueryData(["practice-day", date], ctx.prev);
        setDay(ctx.prev.date, ctx.prev.key, ctx.prev.position);
      }
    },
    onSuccess: (data) => {
      qc.setQueryData(["practice-day", date], data);
      setDay(data.date, data.key, data.position);
    },
  });
  return {
    date,
    loading: q.isLoading,
    error: q.error,
    setKey: (key: string) => mut.mutate({ date, key }),
    setPosition: (position: number) => mut.mutate({ date, position }),
  };
}
