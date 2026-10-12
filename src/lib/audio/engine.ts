// The ONE AudioContext of the app (module singleton): native metronome and tab
// play-along share it, so the click never stops when a page or a drill item
// changes. "Tale of two clocks": a Worker timer wakes the scheduler every
// 25 ms, which schedules every beat/note whose time falls within the next
// 100 ms on the AudioContext clock. Tempo changes apply at the next beat.
import { scheduleBlip, scheduleClick, scheduleNote } from "./voices";
import type { BeatEvent, CueKind, EngineEvents, Pattern } from "./types";

const LOOKAHEAD = 0.1; // seconds
const TICK_MS = 25;

type Listener<K extends keyof EngineEvents> = (e: EngineEvents[K]) => void;

type ActivePattern = {
  pattern: Pattern;
  loop: boolean;
  startBeat: number; // absolute beat index of the pattern's first bar
  loopBeats: number; // whole click bars
  nextNote: number; // index into notes for the current loop
  loopIndex: number;
  ended: boolean;
};

class AudioEngine {
  ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private clickGain: GainNode | null = null;
  private tabGain: GainNode | null = null;
  private cueGain: GainNode | null = null;
  private worker: Worker | null = null;
  private fallbackTimer: ReturnType<typeof setInterval> | null = null;

  tempo = 85;
  meter: 2 | 4 = 2;
  clickOn = true;
  running = false;
  private nextBeatTime = 0;
  private nextBeatIndex = 0;
  private countInBeats = 0;
  private active: ActivePattern | null = null;
  private pending: { pattern: Pattern | null; loop: boolean } | null = null;
  private listeners = new Map<keyof EngineEvents, Set<(e: never) => void>>();
  private dispatchQueue: { time: number; fire: () => void }[] = [];
  private dispatchTimer: ReturnType<typeof setInterval> | null = null;

  // ---- context ------------------------------------------------------------
  async unlock(): Promise<AudioContext | null> {
    if (typeof window === "undefined") return null;
    if (!this.ctx) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AC) return null;
      this.ctx = new AC({ latencyHint: "interactive" });
      this.master = this.ctx.createGain();
      this.master.connect(this.ctx.destination);
      this.clickGain = this.ctx.createGain();
      this.clickGain.gain.value = 0.8;
      this.clickGain.connect(this.master);
      this.tabGain = this.ctx.createGain();
      this.tabGain.gain.value = 0.9;
      this.tabGain.connect(this.master);
      this.cueGain = this.ctx.createGain();
      this.cueGain.gain.value = 0.6;
      this.cueGain.connect(this.master);
    }
    if (this.ctx.state === "suspended") {
      try {
        await this.ctx.resume();
      } catch {
        /* needs a gesture */
      }
    }
    return this.ctx;
  }

  get ready() {
    return !!this.ctx && this.ctx.state === "running";
  }

  now() {
    return this.ctx?.currentTime ?? 0;
  }

  // ---- settings -----------------------------------------------------------
  setTempo(bpm: number) {
    this.tempo = Math.min(300, Math.max(30, Math.round(bpm)));
    this.emitState();
  }
  setMeter(m: 2 | 4) {
    this.meter = m;
    this.emitState();
  }
  setClickOn(on: boolean) {
    this.clickOn = on;
    this.emitState();
  }
  setVolumes(v: { click?: number; tab?: number }) {
    if (this.clickGain && v.click !== undefined) this.clickGain.gain.value = v.click;
    if (this.tabGain && v.tab !== undefined) this.tabGain.gain.value = v.tab;
  }

  beatSeconds() {
    return 60 / this.tempo;
  }

  // ---- transport ----------------------------------------------------------
  /** Start the click (and the transport). Count-in bars are clicked before a
   * pending pattern starts. */
  async start(opts: { countInBars?: number } = {}) {
    const ctx = await this.unlock();
    if (!ctx) return;
    if (this.running) return;
    this.running = true;
    this.nextBeatTime = ctx.currentTime + 0.05;
    this.nextBeatIndex = 0;
    this.countInBeats = (opts.countInBars ?? 0) * this.meter;
    if (this.active) {
      this.active.startBeat = this.countInBeats;
      this.active.nextNote = 0;
      this.active.loopIndex = 0;
      this.active.ended = false;
    }
    this.startTimer();
    this.emitState();
  }

  stop() {
    this.running = false;
    this.stopTimer();
    this.dispatchQueue = [];
    this.emitState();
  }

  async toggle(opts: { countInBars?: number } = {}) {
    if (this.running) this.stop();
    else await this.start(opts);
  }

  /** The absolute beat index of the next bar boundary (>= the next beat). */
  nextBarBeat(): number {
    const b = this.nextBeatIndex;
    return Math.ceil(b / this.meter) * this.meter;
  }

  /** Set (or clear) the play-along pattern. With the transport running the
   * pattern starts at the next bar; otherwise it waits for start(). */
  setPattern(pattern: Pattern | null, opts: { loop?: boolean; atNextBar?: boolean } = {}) {
    const loop = opts.loop ?? true;
    if (!pattern) {
      this.active = null;
      this.pending = null;
      this.emitState();
      return;
    }
    const loopBeats = Math.max(this.meter, Math.ceil(pattern.beats / this.meter) * this.meter);
    const startBeat = this.running ? (opts.atNextBar === false ? this.nextBeatIndex : this.nextBarBeat()) : 0;
    this.active = { pattern, loop, startBeat, loopBeats, nextNote: 0, loopIndex: 0, ended: false };
    this.emitState();
  }

  get patternId() {
    return this.active?.pattern.id ?? null;
  }

  /** One-shot playback from now, independent of the transport (used by the
   * tab preview "Play" button when the click is off). */
  async playOnce(pattern: Pattern): Promise<void> {
    const ctx = await this.unlock();
    if (!ctx || !this.tabGain) return;
    const t0 = ctx.currentTime + 0.05;
    const bs = this.beatSeconds();
    pattern.notes.forEach((n, i) => {
      const t = t0 + n.start * bs;
      scheduleNote(ctx, this.tabGain!, t, n.midi, n.dur * bs, n.legato);
      this.queueDispatch(t, () => this.emit("note", { patternId: pattern.id, index: i, time: t, midi: n.midi, loopIndex: 0 }));
    });
    const end = t0 + pattern.beats * bs;
    this.queueDispatch(t0, () => this.emit("patternStart", { patternId: pattern.id, time: t0, loopIndex: 0 }));
    this.queueDispatch(end, () => this.emit("patternEnd", { patternId: pattern.id, time: end, loopIndex: 0 }));
    this.ensureDispatcher();
  }

  async cue(kind: CueKind, at?: number) {
    const ctx = await this.unlock();
    if (!ctx || !this.cueGain) return;
    const t = at ?? ctx.currentTime + 0.01;
    const g = this.cueGain;
    switch (kind) {
      case "three":
      case "two":
      case "one":
      case "tick":
        scheduleBlip(ctx, g, t, 1320, 0.05, 0.35);
        break;
      case "next":
        scheduleBlip(ctx, g, t, 880, 0.07, 0.4);
        scheduleBlip(ctx, g, t + 0.09, 1320, 0.09, 0.4);
        break;
      case "done":
        scheduleBlip(ctx, g, t, 880, 0.08, 0.4);
        scheduleBlip(ctx, g, t + 0.12, 1100, 0.08, 0.4);
        scheduleBlip(ctx, g, t + 0.24, 1320, 0.16, 0.4);
        break;
    }
  }

  // ---- events -------------------------------------------------------------
  subscribe<K extends keyof EngineEvents>(ev: K, fn: Listener<K>): () => void {
    let set = this.listeners.get(ev);
    if (!set) {
      set = new Set();
      this.listeners.set(ev, set);
    }
    set.add(fn as (e: never) => void);
    return () => {
      set!.delete(fn as (e: never) => void);
    };
  }

  private emit<K extends keyof EngineEvents>(ev: K, e: EngineEvents[K]) {
    const set = this.listeners.get(ev) as Set<Listener<K>> | undefined;
    if (!set) return;
    for (const fn of Array.from(set)) {
      try {
        fn(e);
      } catch (err) {
        console.error(err);
      }
    }
  }

  private emitState() {
    this.emit("state", { running: this.running, tempo: this.tempo, meter: this.meter, clickOn: this.clickOn, pattern: this.patternId });
  }

  // ---- scheduling ---------------------------------------------------------
  private startTimer() {
    this.stopTimer();
    try {
      this.worker = new Worker(new URL("./timer.worker.ts", import.meta.url));
      this.worker.onmessage = () => this.tick();
      this.worker.postMessage({ cmd: "start", interval: TICK_MS });
    } catch {
      this.worker = null;
      this.fallbackTimer = setInterval(() => this.tick(), TICK_MS);
    }
    this.ensureDispatcher();
  }

  private stopTimer() {
    if (this.worker) {
      this.worker.postMessage({ cmd: "stop" });
      this.worker.terminate();
      this.worker = null;
    }
    if (this.fallbackTimer) {
      clearInterval(this.fallbackTimer);
      this.fallbackTimer = null;
    }
  }

  private tick() {
    const ctx = this.ctx;
    if (!ctx || !this.running) return;
    while (this.nextBeatTime < ctx.currentTime + LOOKAHEAD) {
      this.scheduleBeat(this.nextBeatIndex, this.nextBeatTime);
      this.nextBeatTime += this.beatSeconds();
      this.nextBeatIndex += 1;
    }
  }

  private scheduleBeat(absBeat: number, time: number) {
    const ctx = this.ctx!;
    const beatInBar = absBeat % this.meter;
    const countIn = absBeat < this.countInBeats;
    if (this.clickOn && this.clickGain) scheduleClick(ctx, this.clickGain, time, beatInBar === 0);
    const ev: BeatEvent = { bar: Math.floor(absBeat / this.meter), beat: beatInBar + 1, time, countIn, absBeat };
    this.queueDispatch(time, () => this.emit("beat", ev));

    const a = this.active;
    if (!a || a.ended || !this.tabGain) return;
    const bs = this.beatSeconds();
    // notes of the pattern whose onset lies in [absBeat, absBeat + 1)
    for (;;) {
      const rel = absBeat - a.startBeat - a.loopIndex * a.loopBeats; // beats into the current loop
      if (rel < 0) return;
      const notes = a.pattern.notes;
      if (a.nextNote === 0 && rel === 0) {
        const li = a.loopIndex;
        this.queueDispatch(time, () => this.emit("patternStart", { patternId: a.pattern.id, time, loopIndex: li }));
      }
      while (a.nextNote < notes.length && notes[a.nextNote].start < rel + 1) {
        const n = notes[a.nextNote];
        const idx = a.nextNote;
        const t = time + (n.start - rel) * bs;
        scheduleNote(ctx, this.tabGain, t, n.midi, n.dur * bs, n.legato);
        const li = a.loopIndex;
        this.queueDispatch(t, () => this.emit("note", { patternId: a.pattern.id, index: idx, time: t, midi: n.midi, loopIndex: li }));
        a.nextNote += 1;
      }
      if (rel + 1 >= a.loopBeats) {
        const endT = time + (a.loopBeats - rel) * bs;
        const li = a.loopIndex;
        this.queueDispatch(endT, () => this.emit("patternEnd", { patternId: a.pattern.id, time: endT, loopIndex: li }));
        if (!a.loop) {
          a.ended = true;
          return;
        }
        a.loopIndex += 1;
        a.nextNote = 0;
        // the next loop may also have notes in this same beat window (rel wraps to 0 next beat)
        if (absBeat - a.startBeat - a.loopIndex * a.loopBeats < 0) return;
        continue;
      }
      return;
    }
  }

  private queueDispatch(time: number, fire: () => void) {
    this.dispatchQueue.push({ time, fire });
    this.dispatchQueue.sort((x, y) => x.time - y.time);
  }

  private ensureDispatcher() {
    if (this.dispatchTimer) return;
    this.dispatchTimer = setInterval(() => {
      const ctx = this.ctx;
      if (!ctx) return;
      const now = ctx.currentTime;
      while (this.dispatchQueue.length && this.dispatchQueue[0].time <= now + 0.005) {
        const e = this.dispatchQueue.shift()!;
        e.fire();
      }
      if (!this.running && !this.dispatchQueue.length) {
        clearInterval(this.dispatchTimer!);
        this.dispatchTimer = null;
      }
    }, 16);
  }
}

const g = globalThis as unknown as { __bebopAudio?: AudioEngine };
export const audioEngine: AudioEngine = g.__bebopAudio ?? (g.__bebopAudio = new AudioEngine());
