"use client";

import * as React from "react";
import { create } from "zustand";
import { cn } from "@/lib/utils";

export function Badge({ className, tone = "default", ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: "default" | "ok" | "warn" | "danger" | "accent" }) {
  const tones = {
    default: "bg-bg-muted text-fg-muted",
    ok: "bg-ok/15 text-ok",
    warn: "bg-warn/15 text-warn",
    danger: "bg-danger/15 text-danger",
    accent: "bg-accent-soft text-accent",
  };
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone], className)} {...props} />;
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border bg-bg-elev p-4", className)} {...props} />;
}

export function Info({ className, tone = "info", children }: { className?: string; tone?: "info" | "warn" | "danger" | "ok"; children: React.ReactNode }) {
  const tones = { info: "border-accent/30 bg-accent-soft/60", warn: "border-warn/40 bg-warn/10", danger: "border-danger/40 bg-danger/10", ok: "border-ok/40 bg-ok/10" };
  return <div className={cn("rounded-md border px-3 py-2 text-sm", tones[tone], className)}>{children}</div>;
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("inline-block h-4 w-4 animate-spin rounded-full border-2 border-fg-muted border-t-transparent", className)} aria-label="loading" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-bg-muted", className)} />;
}

// ---- toasts ----------------------------------------------------------------
type Toast = { id: number; text: string; tone: "default" | "ok" | "danger" };
const useToasts = create<{ list: Toast[]; push: (t: Omit<Toast, "id">) => void; remove: (id: number) => void }>((set) => ({
  list: [],
  push: (t) => {
    const id = Date.now() + Math.random();
    set((s) => ({ list: [...s.list.slice(-3), { ...t, id }] }));
    setTimeout(() => set((s) => ({ list: s.list.filter((x) => x.id !== id) })), 3500);
  },
  remove: (id) => set((s) => ({ list: s.list.filter((x) => x.id !== id) })),
}));

export function toast(text: string, tone: Toast["tone"] = "default") {
  useToasts.getState().push({ text, tone });
}

export function Toaster() {
  const list = useToasts((s) => s.list);
  const remove = useToasts((s) => s.remove);
  return (
    <div className="pointer-events-none fixed inset-x-0 top-[calc(var(--header-h)+8px)] z-[60] flex flex-col items-center gap-2 px-4">
      {list.map((t) => (
        <button
          key={t.id}
          onClick={() => remove(t.id)}
          className={cn("pointer-events-auto rounded-md border px-3 py-2 text-sm shadow-md", t.tone === "ok" ? "bg-ok text-white" : t.tone === "danger" ? "bg-danger text-white" : "bg-bg-elev")}
        >
          {t.text}
        </button>
      ))}
    </div>
  );
}
