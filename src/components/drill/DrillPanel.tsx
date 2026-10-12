"use client";

import * as React from "react";
import { ChevronDown, ChevronUp, Pause, Play, Repeat, RotateCcw, SkipBack, SkipForward, Volume2, VolumeX, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/misc";
import { TabPlayer } from "@/components/tab/TabPlayer";
import { fingeringFor, selectRemainingSeconds, useDrill } from "@/lib/drill/store";
import { useSession } from "@/lib/store/session";
import { cn } from "@/lib/utils";
import { DrillStrip } from "./DrillStrip";

function useRemainingSeconds() {
  const [sec, setSec] = React.useState(() => selectRemainingSeconds(useDrill.getState()));
  React.useEffect(() => {
    const compute = () => setSec(selectRemainingSeconds(useDrill.getState()));
    const id = setInterval(compute, 200);
    const unsub = useDrill.subscribe(compute);
    return () => {
      clearInterval(id);
      unsub();
    };
  }, []);
  return sec;
}

function mmss(s: number) {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function DrillPanel({ onStart, summary, className }: { onStart?: () => void; summary?: React.ReactNode; className?: string }) {
  const d = useDrill();
  const sec = useRemainingSeconds();
  const clickOn = useSession((s) => s.clickOn);
  const setClickOn = useSession((s) => s.setClickOn);
  const [expanded, setExpanded] = React.useState(false);
  const item = d.items[d.currentIndex];
  const fingering = item ? fingeringFor(item.id) : undefined;
  const per = d.config?.secondsPerItem ?? 0;
  const pct = per ? Math.max(0, Math.min(100, (100 * (per - sec)) / per)) : 0;
  const active = d.status !== "idle";

  const controls = (
    <div className="flex items-center justify-center gap-2">
      <Button size="icon" variant="outline" aria-label="Previous" onClick={d.prev} disabled={!active}>
        <SkipBack size={18} />
      </Button>
      <Button
        size="iconLg"
        aria-label={d.status === "running" ? "Pause" : "Play"}
        onClick={() => (d.status === "running" ? d.pause() : d.status === "paused" ? d.resume() : d.status === "finished" ? d.jumpTo(0) : onStart?.())}
      >
        {d.status === "running" ? <Pause size={24} /> : <Play size={24} />}
      </Button>
      <Button size="icon" variant="outline" aria-label="Next" onClick={d.next} disabled={!active}>
        <SkipForward size={18} />
      </Button>
      <Button size="icon" variant="ghost" aria-label="Restart item" onClick={d.restartItem} disabled={!active} title="Restart item (R)">
        <RotateCcw size={16} />
      </Button>
      <Button size="icon" variant={d.config?.loopSession ? "soft" : "ghost"} aria-label="Loop session" onClick={() => d.setConfig({ loopSession: !d.config?.loopSession })} disabled={!active} title="Loop the session (L)">
        <Repeat size={16} />
      </Button>
      <Button size="icon" variant={clickOn ? "ghost" : "soft"} aria-label="Toggle click" onClick={() => setClickOn(!clickOn)} title="Mute/unmute the click (M)">
        {clickOn ? <Volume2 size={16} /> : <VolumeX size={16} />}
      </Button>
    </div>
  );

  const header = item ? (
    <div className="min-w-0">
      <div className="truncate text-sm font-semibold">
        {item.end.name} <span className="text-fg-muted">→</span> {item.start.name}
      </div>
      <div className="text-xs text-fg-muted">
        #{d.currentIndex + 1}/{d.items.length} · fingering {item.k}/{item.m} · cost {item.cost.toFixed(2)}
        {fingering ? ` · ${fingering.where}` : ""}
      </div>
    </div>
  ) : (
    <div className="text-sm text-fg-muted">{summary ?? "No exercise yet."}</div>
  );

  const full = (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        {header}
        <div className="flex items-center gap-1">
          <Badge tone={d.status === "running" ? "ok" : d.status === "paused" ? "warn" : "default"}>{d.status}</Badge>
          {active && (
            <Button size="icon" variant="ghost" className="h-8 w-8" aria-label="End session" onClick={d.reset} title="End the session">
              <X size={16} />
            </Button>
          )}
        </div>
      </div>
      {active && (
        <div>
          <div className="flex items-end justify-between">
            <div className="font-mono text-4xl font-bold tabular-nums">{mmss(sec)}</div>
            <div className="text-xs text-fg-muted">{per}s per item</div>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-bg-muted">
            <div className="h-full bg-accent transition-[width] duration-200" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
      {controls}
      {active && d.config?.showTab && fingering && (
        <TabPlayer placed={fingering.placed} chords={fingering.chords} beatsPerBar={fingering.beats_per_bar} totalCost={fingering.cost} patternId={item.id} controls={false} followTransport options={{ showLegend: false }} />
      )}
      {active && d.config?.showTab && !fingering && <p className="text-xs text-fg-muted">Loading this fingering&apos;s tab…</p>}
      {active && (
        <Button size="sm" variant="ghost" onClick={() => d.setConfig({ showTab: !d.config?.showTab })}>
          {d.config?.showTab ? "Hide the tab (T)" : "Show the tab (T)"}
        </Button>
      )}
      {d.items.length > 0 && (
        <div className="hidden lg:block">
          <DrillStrip items={d.items} current={d.currentIndex} onJump={d.jumpTo} orientation="vertical" />
        </div>
      )}
      {!active && onStart && (
        <Button size="lg" className="w-full" onClick={onStart}>
          <Play size={18} /> Start exercise
        </Button>
      )}
      {d.status === "finished" && <p className="text-sm text-ok">Completed all combinations — easiest to hardest.</p>}
      <p className="hidden text-[11px] text-fg-muted lg:block">Space play/pause · ←/→ prev/next · R restart · L loop · M click · T tab</p>
    </div>
  );

  // phone: a bottom sheet over the page (mini bar / expanded); desktop: inline
  return (
    <div className={cn("lg:static", className)}>
      <div className="hidden lg:block">{full}</div>
      <div className={cn("fixed inset-x-0 bottom-[calc(var(--bottom-nav-h)+env(safe-area-inset-bottom))] z-20 border-t bg-bg shadow-[0_-4px_16px_rgba(0,0,0,0.12)] lg:hidden", !active && "hidden")}>
        {expanded ? (
          <div className="scrollbar-thin max-h-[85dvh] overflow-y-auto p-3">
            <button className="mb-2 flex w-full items-center justify-center text-fg-muted" onClick={() => setExpanded(false)} aria-label="Collapse">
              <ChevronDown size={18} />
            </button>
            {full}
            {d.items.length > 0 && (
              <div className="mt-2">
                <DrillStrip items={d.items} current={d.currentIndex} onJump={d.jumpTo} orientation="horizontal" />
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-[72px] items-center gap-2 px-3">
            <button className="min-w-0 flex-1 text-left" onClick={() => setExpanded(true)} aria-label="Expand">
              <div className="flex items-center gap-2">
                <ChevronUp size={16} className="shrink-0 text-fg-muted" />
                <div className="min-w-0">
                  <div className="truncate text-xs font-semibold">
                    {item ? `${item.end.name} → ${item.start.name}` : "Exercise"}
                  </div>
                  <div className="text-[11px] text-fg-muted">
                    #{d.currentIndex + 1}/{d.items.length} · {item ? `${item.k}/${item.m}` : ""}
                  </div>
                </div>
              </div>
            </button>
            <div className="font-mono text-2xl font-bold tabular-nums">{mmss(sec)}</div>
            <Button size="icon" aria-label={d.status === "running" ? "Pause" : "Play"} onClick={() => (d.status === "running" ? d.pause() : d.status === "paused" ? d.resume() : d.jumpTo(0))}>
              {d.status === "running" ? <Pause size={18} /> : <Play size={18} />}
            </Button>
            <Button size="icon" variant="outline" aria-label="Next" onClick={d.next}>
              <SkipForward size={18} />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
