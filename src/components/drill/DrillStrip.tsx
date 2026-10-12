"use client";

import * as React from "react";
import type { DrillItem } from "@/lib/drill/buildItems";
import { cn } from "@/lib/utils";

export function DrillStrip({ items, current, onJump, orientation }: { items: DrillItem[]; current: number; onJump: (i: number) => void; orientation: "horizontal" | "vertical" }) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    const el = ref.current?.querySelector<HTMLElement>(`[data-i="${current}"]`);
    el?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [current]);
  return (
    <div ref={ref} className={cn("scrollbar-thin", orientation === "horizontal" ? "flex gap-1.5 overflow-x-auto pb-1 touch-pan-x" : "max-h-72 space-y-1 overflow-y-auto")}>
      {items.map((it, i) => (
        <button
          key={it.id}
          data-i={i}
          onClick={() => onJump(i)}
          className={cn(
            "shrink-0 rounded-md border px-2 py-1 text-left text-[11px] leading-tight transition-colors",
            orientation === "horizontal" ? "max-w-[11rem]" : "w-full",
            i === current ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev hover:bg-bg-muted",
          )}
          title={`${it.end.name} → ${it.start.name}`}
        >
          <span className="font-semibold">#{i + 1}</span> <span className="text-fg-muted">·</span> {it.end.name} → {it.start.name}
          <span className="text-fg-muted">
            {" "}
            · {it.k}/{it.m} · {it.cost.toFixed(1)}
          </span>
        </button>
      ))}
    </div>
  );
}
