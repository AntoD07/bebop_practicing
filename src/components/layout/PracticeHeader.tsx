"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Settings2, Play, Square, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NumberStepper, Select, Switch, Field, Slider } from "@/components/ui/field";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { audioEngine } from "@/lib/audio/engine";
import { useBeat, useEngineState } from "@/lib/audio/useAudio";
import { POSITIONS, POSITION_SHORT, PRACTICE_KEYS } from "@/lib/music/constants";
import { usePracticeDay } from "@/lib/store/practiceDay";
import { pickSessionSettings, useSession } from "@/lib/store/session";
import { startSettingsSync } from "@/lib/store/sync";
import { cn } from "@/lib/utils";
import { usePageSettingsContext } from "./PageSettings";

function useEngineBindings() {
  const tempo = useSession((s) => s.tempo);
  const meter = useSession((s) => s.meter);
  const clickOn = useSession((s) => s.clickOn);
  const metronome = useSession((s) => s.metronome);
  const volumes = useSession((s) => s.volumes);
  useEffect(() => audioEngine.setTempo(tempo), [tempo]);
  useEffect(() => audioEngine.setMeter(meter), [meter]);
  useEffect(() => audioEngine.setClickOn(clickOn && metronome === "native"), [clickOn, metronome]);
  useEffect(() => audioEngine.setVolumes(volumes), [volumes]);
  useEffect(() => startSettingsSync(useSession, "session", pickSessionSettings), []);
}

const narrowQuery = "(max-width: 639px)";
function subscribeNarrow(cb: () => void) {
  const mq = window.matchMedia(narrowQuery);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
/** Phone-width flag that hydrates safely (server + first client render = false). */
function useNarrow() {
  return useSyncExternalStore(subscribeNarrow, () => window.matchMedia(narrowQuery).matches, () => false);
}

function BeatDots() {
  const beat = useBeat();
  const meter = useSession((s) => s.meter);
  const { running } = useEngineState();
  return (
    <div className="flex items-center gap-1" aria-hidden>
      {Array.from({ length: meter }, (_, i) => (
        <span
          key={i}
          className={cn("h-2 w-2 rounded-full border transition-colors", running && beat && beat.beat === i + 1 ? (i === 0 ? "bg-accent border-accent" : "bg-fg border-fg") : "bg-transparent")}
        />
      ))}
    </div>
  );
}

export function PracticeHeader() {
  useEngineBindings();
  const { setKey, setPosition } = usePracticeDay();
  const key = useSession((s) => s.key);
  const position = useSession((s) => s.position);
  const tempo = useSession((s) => s.tempo);
  const setTempo = useSession((s) => s.setTempo);
  const meter = useSession((s) => s.meter);
  const setMeter = useSession((s) => s.setMeter);
  const clickOn = useSession((s) => s.clickOn);
  const setClickOn = useSession((s) => s.setClickOn);
  const metronome = useSession((s) => s.metronome);
  const setMetronome = useSession((s) => s.setMetronome);
  const showIframe = useSession((s) => s.showIframe);
  const setShowIframe = useSession((s) => s.setShowIframe);
  const volumes = useSession((s) => s.volumes);
  const setVolumes = useSession((s) => s.setVolumes);
  const countInBars = useSession((s) => s.countInBars);
  const setCountInBars = useSession((s) => s.setCountInBars);
  const theme = useSession((s) => s.theme);
  const setTheme = useSession((s) => s.setTheme);
  const { running } = useEngineState();
  const page = usePageSettingsContext();
  const narrow = useNarrow();

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);

  return (
    <header className="sticky top-0 z-30 h-[var(--header-h)] border-b bg-bg/95 backdrop-blur supports-[backdrop-filter]:bg-bg/80" style={{ paddingTop: "env(safe-area-inset-top)" }}>
      <div className="mx-auto flex h-full max-w-6xl items-center gap-2 px-3 sm:px-4">
        <div className="flex items-center gap-1.5">
          <Select aria-label="Today's key" value={key} onChange={(e) => setKey(e.target.value)} className="h-9 w-[4.6rem] font-semibold">
            {PRACTICE_KEYS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </Select>
          <Select aria-label="Today's position" value={position} onChange={(e) => setPosition(Number(e.target.value))} className="h-9 w-[7.2rem] sm:w-[14rem]">
            {POSITIONS.map((p, i) => (
              <option key={p} value={i + 1}>
                {i + 1} · {narrow ? POSITION_SHORT[p] : p}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <NumberStepper ariaLabel="Tempo" value={tempo} onChange={setTempo} min={30} max={300} className="h-9 hidden sm:inline-flex" />
          <button
            type="button"
            className="inline-flex h-9 items-center whitespace-nowrap rounded-md border bg-bg-elev px-2 text-xs tabular-nums sm:hidden"
            onClick={() => page.setOpen(true)}
            aria-label="Tempo (open settings)"
          >
            {tempo} bpm
          </button>
          <BeatDots />
          <Button
            size="icon"
            variant={running ? "default" : "outline"}
            className="h-9 w-9"
            aria-label={running ? "Stop metronome" : "Start metronome"}
            onClick={() => (running ? audioEngine.stop() : audioEngine.start({ countInBars: 0 }))}
          >
            {running ? <Square size={16} /> : <Play size={16} />}
          </Button>
          <Sheet open={page.open} onOpenChange={page.setOpen}>
            <SheetTrigger asChild>
              <Button size="icon" variant="ghost" className="h-9 w-9" aria-label="Practice settings">
                <Settings2 size={18} />
              </Button>
            </SheetTrigger>
            <SheetContent title="Practice settings" description="Shared between all pages and devices">
              <div className="space-y-5">
                <Field label="Tempo (bpm) — also the tabs' play-along tempo">
                  <div className="flex items-center gap-3">
                    <NumberStepper ariaLabel="Tempo" value={tempo} onChange={setTempo} min={30} max={300} />
                    <Slider min={30} max={300} value={tempo} onChange={(e) => setTempo(Number(e.target.value))} className="flex-1" />
                  </div>
                </Field>
                <Field label="Metronome">
                  <div className="flex flex-wrap items-center gap-3">
                    <Select value={meter} onChange={(e) => setMeter(Number(e.target.value) as 2 | 4)} className="w-28">
                      <option value={2}>2 beats</option>
                      <option value={4}>4 beats</option>
                    </Select>
                    <Switch checked={clickOn} onCheckedChange={setClickOn} label={clickOn ? "Click on" : "Click muted"} />
                    <NumberStepper ariaLabel="Count-in bars" value={countInBars} onChange={setCountInBars} min={0} max={4} />
                    <span className="text-xs text-fg-muted">count-in bars</span>
                  </div>
                </Field>
                <Field label="Metronome source">
                  <div className="flex items-center gap-3">
                    <Select
                      value={metronome}
                      onChange={(e) => {
                        const m = e.target.value as "native" | "iframe";
                        setMetronome(m);
                        if (m === "iframe") setShowIframe(true);
                      }}
                      className="w-44"
                    >
                      <option value="native">Native (Web Audio)</option>
                      <option value="iframe">guitarapp.com panel</option>
                    </Select>
                    <Switch checked={showIframe} onCheckedChange={setShowIframe} label="Show panel" />
                  </div>
                </Field>
                <Field label="Volumes">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Volume2 size={16} className="text-fg-muted" />
                      <Slider min={0} max={1} step={0.05} value={volumes.click} onChange={(e) => setVolumes({ click: Number(e.target.value) })} valueLabel="click" className="flex-1" />
                    </div>
                    <div className="flex items-center gap-2">
                      {volumes.tab > 0 ? <Volume2 size={16} className="text-fg-muted" /> : <VolumeX size={16} className="text-fg-muted" />}
                      <Slider min={0} max={1} step={0.05} value={volumes.tab} onChange={(e) => setVolumes({ tab: Number(e.target.value) })} valueLabel="tab" className="flex-1" />
                    </div>
                  </div>
                </Field>
                <Field label="Theme">
                  <Select value={theme} onChange={(e) => setTheme(e.target.value as "system" | "light" | "dark")} className="w-36">
                    <option value="system">System</option>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                  </Select>
                </Field>
                {page.content && (
                  <div className="border-t pt-4">
                    <h3 className="mb-3 text-sm font-semibold">This page</h3>
                    {page.content}
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
