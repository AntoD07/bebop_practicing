// Identical to the legacy render_html play-along: triangle notes, 10 ms attack,
// exponential decay to 0.95 × duration; click = 30 ms sine blip.
export function midiToFreq(m: number) {
  return 440 * Math.pow(2, (m - 69) / 12);
}

export function scheduleClick(ctx: AudioContext, out: AudioNode, time: number, accent: boolean) {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = "sine";
  o.frequency.value = accent ? 1000 : 800;
  g.gain.setValueAtTime(0.0001, time);
  g.gain.exponentialRampToValueAtTime(accent ? 1.0 : 0.7, time + 0.002);
  g.gain.exponentialRampToValueAtTime(0.0001, time + 0.03);
  o.connect(g);
  g.connect(out);
  o.start(time);
  o.stop(time + 0.04);
}

export function scheduleNote(ctx: AudioContext, out: AudioNode, time: number, midi: number, durSec: number, legato = false) {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = "triangle";
  o.frequency.value = midiToFreq(midi);
  const peak = legato ? 0.16 : 0.25;
  const atk = legato ? 0.03 : 0.01;
  const d = Math.max(0.05, durSec);
  g.gain.setValueAtTime(0.0001, time);
  g.gain.exponentialRampToValueAtTime(peak, time + atk);
  g.gain.exponentialRampToValueAtTime(0.0001, time + d * 0.95);
  o.connect(g);
  g.connect(out);
  o.start(time);
  o.stop(time + d);
}

export function scheduleBlip(ctx: AudioContext, out: AudioNode, time: number, freq: number, dur = 0.06, gain = 0.5) {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = "square";
  o.frequency.value = freq;
  g.gain.setValueAtTime(0.0001, time);
  g.gain.exponentialRampToValueAtTime(gain, time + 0.004);
  g.gain.exponentialRampToValueAtTime(0.0001, time + dur);
  o.connect(g);
  g.connect(out);
  o.start(time);
  o.stop(time + dur + 0.01);
}
