"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, NumberStepper, Select } from "@/components/ui/field";
import { Badge, Card, Info, Skeleton, Spinner, toast } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { FingeringCard } from "@/components/tab/FingeringCard";
import { TabPlayer } from "@/components/tab/TabPlayer";
import { usePageSettings } from "@/components/layout/PageSettings";
import { enginePost } from "@/lib/engine/client";
import { useEngineHealth } from "@/lib/engine/hooks";
import type { FingeringJSON, RankAbsoluteJSON, ScoreParseJSON } from "@/lib/engine/types";
import { PRACTICE_KEYS } from "@/lib/music/constants";
import { useScore } from "@/lib/store/score";
import { useSession } from "@/lib/store/session";
import { fmtCost } from "@/lib/utils";

type Row = { bar: number; start: number; pitch: string; chord: string; afterRest: boolean };
type SavedScore = { name: string; savedAt: string; filename: string; bestFingering: { label: string; cost: number | null; where: string | null; encoding?: string | null; fingering?: FingeringJSON | null } | null };

const IMAGE_EXT = new Set(["pdf", "png", "jpg", "jpeg"]);

function toBase64(buf: ArrayBuffer): string {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

async function renderPdfPage(data: ArrayBuffer, scale = 2): Promise<string> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  const doc = await pdfjs.getDocument({ data }).promise;
  const page = await doc.getPage(1);
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const ctx = canvas.getContext("2d")!;
  await page.render({ canvasContext: ctx, viewport, canvas }).promise;
  return canvas.toDataURL("image/png").split(",")[1];
}

async function imageToPng(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    await new Promise<void>((res, rej) => {
      img.onload = () => res();
      img.onerror = () => rej(new Error("could not decode the image"));
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.getContext("2d")!.drawImage(img, 0, 0);
    return canvas.toDataURL("image/png").split(",")[1];
  } finally {
    URL.revokeObjectURL(url);
  }
}

function PageOptions() {
  const s = useScore();
  const todayKey = useSession((x) => x.key);
  return (
    <Field label="Key for the position boxes" hint="Named positions are anchored on this key's root; it also names where each ranked fingering lands.">
      <Select value={s.posKey ?? ""} onChange={(e) => s.set({ posKey: e.target.value || null })}>
        <option value="">Today&apos;s key ({todayKey})</option>
        {PRACTICE_KEYS.map((k) => (
          <option key={k} value={k}>
            {k}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function ScorePage() {
  const s = useScore();
  const todayKey = useSession((x) => x.key);
  const posKey = s.posKey ?? todayKey;
  const health = useEngineHealth();
  const qc = useQueryClient();
  usePageSettings(<PageOptions />, []);

  const [source, setSource] = React.useState<"upload" | "library">("upload");
  const [file, setFile] = React.useState<{ name: string; bytes: ArrayBuffer } | null>(null);
  const [libName, setLibName] = React.useState<string>("");
  const [parsed, setParsed] = React.useState<ScoreParseJSON | null>(null);
  const [rows, setRows] = React.useState<Row[]>([]);
  const [chordText, setChordText] = React.useState("");
  const [slice, setSlice] = React.useState<[number, number]>([0, 0]);
  const [seqName, setSeqName] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [rank, setRank] = React.useState<RankAbsoluteJSON | null>(null);
  const [selLabel, setSelLabel] = React.useState<string | null>(null);

  const ext = file?.name.split(".").pop()?.toLowerCase() ?? "";
  const isImage = IMAGE_EXT.has(ext);
  const library = useQuery({ queryKey: ["scores"], queryFn: async () => (await (await fetch("/api/scores")).json()) as { scores: SavedScore[] } });

  function adopt(p: ScoreParseJSON, name: string) {
    setParsed(p);
    setRows(p.notes.map((n) => ({ bar: n.bar, start: n.start, pitch: n.name, chord: n.chord, afterRest: n.phrase_start })));
    setChordText(p.chords.map((c) => `${c.start_beat}:${c.symbol}`).join(", "));
    setSlice([0, Math.max(0, p.notes.length - 1)]);
    setRank(null);
    setSeqName(name);
  }

  async function onFile(f: File) {
    const bytes = await f.arrayBuffer();
    setFile({ name: f.name, bytes });
    setParsed(null);
    setRank(null);
    const e = f.name.split(".").pop()?.toLowerCase() ?? "";
    if (!IMAGE_EXT.has(e)) {
      setBusy("Parsing MusicXML…");
      try {
        const p = await enginePost<ScoreParseJSON>("score/parse-musicxml", { filename: f.name, data_b64: toBase64(bytes) });
        adopt(p, f.name.replace(/\.[^.]+$/, ""));
      } catch (err) {
        toast((err as Error).message, "danger");
      } finally {
        setBusy(null);
      }
    }
  }

  async function readVision() {
    if (!file) return;
    setBusy("Claude is reading the score (~1–2 min)…");
    try {
      const png = ext === "pdf" ? await renderPdfPage(file.bytes) : await imageToPng(new File([file.bytes], file.name));
      const p = await enginePost<ScoreParseJSON>("score/read-vision", { images: [png] });
      adopt(p, file.name.replace(/\.[^.]+$/, ""));
      p.uncertain.forEach((u) => toast(`Reader unsure at bar ${u.measure}: ${u.reason}`, "danger"));
    } catch (err) {
      toast((err as Error).message, "danger");
    } finally {
      setBusy(null);
    }
  }

  async function loadFromLibrary(name: string) {
    setLibName(name);
    if (!name) return;
    setBusy("Loading…");
    try {
      const r = await fetch(`/api/scores/${encodeURIComponent(name)}`);
      const j = (await r.json()) as { score: SavedScore & { musicxml: string } };
      const bytes = new TextEncoder().encode(j.score.musicxml).buffer as ArrayBuffer;
      setFile({ name: j.score.filename, bytes });
      const p = await enginePost<ScoreParseJSON>("score/parse-musicxml", { filename: j.score.filename, data_b64: toBase64(bytes) });
      adopt(p, name);
    } catch (err) {
      toast((err as Error).message, "danger");
    } finally {
      setBusy(null);
    }
  }

  const saveScore = useMutation({
    mutationFn: async () => {
      if (!file || isImage) throw new Error("only MusicXML can be saved");
      const r = await fetch("/api/scores", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: seqName.trim(), filename: file.name, musicxml: new TextDecoder().decode(file.bytes) }) });
      if (!r.ok) throw new Error(`save ${r.status}`);
    },
    onSuccess: () => {
      toast(`Saved '${seqName.trim()}' to the library`, "ok");
      qc.invalidateQueries({ queryKey: ["scores"] });
    },
    onError: (e) => toast((e as Error).message, "danger"),
  });

  async function generate() {
    if (!parsed) return;
    const chords = chordText
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.includes(":"))
      .map((t) => {
        const [b, sym] = t.split(/:(.*)/s);
        return { start_beat: Number(b), symbol: sym.trim() };
      })
      .filter((c) => Number.isFinite(c.start_beat) && c.symbol);
    const [lo, hi] = slice;
    const line = rows.slice(lo, hi + 1).map((r) => ({ pitch: r.pitch.trim(), start: Number(r.start), phrase_start: r.afterRest, cell: r.bar ? `bar ${r.bar}` : null }));
    if (!line.length) {
      toast("No notes to finger", "danger");
      return;
    }
    setBusy("Ranking fingerings (Free, 5 positions, 3 neck bands)…");
    try {
      const out = await enginePost<RankAbsoluteJSON>("fingering/rank-absolute", { key: posKey, line, chords, beats_per_bar: parsed.beats_per_bar });
      setRank(out);
      setSelLabel(null);
    } catch (err) {
      toast((err as Error).message, "danger");
    } finally {
      setBusy(null);
    }
  }

  const feasible = rank?.rows.filter((r) => r.fingering) ?? [];
  const selRow = rank?.rows.find((r) => r.label === selLabel && r.fingering) ?? feasible[0] ?? null;

  async function saveBest() {
    if (!selRow?.fingering || !seqName.trim() || !file || isImage) return;
    const name = seqName.trim();
    if (!library.data?.scores.some((x) => x.name === name)) await saveScore.mutateAsync();
    const r = await fetch(`/api/scores/${encodeURIComponent(name)}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ best_fingering: { label: selRow.label + (selRow.shift ? ` (${selRow.shift_text})` : ""), cost: selRow.cost, where: selRow.where, encoding: selRow.fingering.encoding, fingering: selRow.fingering } }) });
    if (r.ok) {
      toast(`Best fingering for '${name}' saved`, "ok");
      qc.invalidateQueries({ queryKey: ["scores"] });
    } else toast("Could not save the best fingering", "danger");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Score → Tab</h1>
        <p className="text-xs text-fg-muted">Upload a score (or reload a saved one); the engine proposes several Gypsy fingerings for the written pitches, ranked by feasibility. Vision output is never trusted blindly — review the notes before tabbing.</p>
      </div>

      <Card className="space-y-3">
        <h2 className="text-base font-semibold">1 · Score</h2>
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={source === "upload"} onChange={() => setSource("upload")} /> Upload a file
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={source === "library"} onChange={() => setSource("library")} /> Score library
          </label>
        </div>
        {source === "upload" ? (
          <input type="file" accept=".xml,.musicxml,.mxl,.pdf,.png,.jpg,.jpeg" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} className="block text-sm" />
        ) : (
          <Select value={libName} onChange={(e) => loadFromLibrary(e.target.value)} className="max-w-sm">
            <option value="">Pick a saved sequence…</option>
            {(library.data?.scores ?? []).map((x) => (
              <option key={x.name} value={x.name}>
                {x.name}
              </option>
            ))}
          </Select>
        )}
        {file && isImage && !parsed && (
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={readVision} disabled={!!busy || !health.data?.vision}>
              Read with Claude vision (recommended for jazz fonts)
            </Button>
            {!health.data?.vision && <span className="text-xs text-fg-muted">Needs ANTHROPIC_API_KEY on the Python API.</span>}
          </div>
        )}
        {busy && (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> {busy}
          </p>
        )}
        {!file && !busy && <Info>Upload MusicXML for exact results (SoundSlice and MuseScore both export it), or a PDF/image for the vision reader.</Info>}
        {parsed && !isImage && (
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Sequence name (for the library)" className="min-w-56 flex-1">
              <Input value={seqName} onChange={(e) => setSeqName(e.target.value)} />
            </Field>
            <Button variant="outline" onClick={() => saveScore.mutate()} disabled={!seqName.trim() || saveScore.isPending}>
              Save MusicXML to library
            </Button>
          </div>
        )}
        {parsed && isImage && <p className="text-xs text-fg-muted">Image/PDF sources can be tabbed but not saved to the library — only MusicXML sequences are stored.</p>}
      </Card>

      {parsed && (
        <Card className="space-y-3">
          <h2 className="text-base font-semibold">2 · Review the recognized notes</h2>
          <p className="text-xs text-fg-muted">
            {rows.length} notes · {parsed.beats_per_bar}/4 · density {parsed.density}. Fix wrong pitches/chords before trusting the tab.
          </p>
          <NoteEditor rows={rows} onChange={setRows} />
          {rows.length >= 2 && (
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Start note #">
                <NumberStepper ariaLabel="Start note" value={slice[0]} onChange={(v) => setSlice([Math.min(v, slice[1]), slice[1]])} min={0} max={rows.length - 1} />
              </Field>
              <Field label="End note #">
                <NumberStepper ariaLabel="End note" value={slice[1]} onChange={(v) => setSlice([slice[0], Math.max(v, slice[0])])} min={0} max={rows.length - 1} />
              </Field>
              <p className="text-xs text-fg-muted">
                Line starts on note {slice[0]} — <strong>{rows[slice[0]]?.pitch}</strong> (bar {rows[slice[0]]?.bar}) and ends on note {slice[1]} — <strong>{rows[slice[1]]?.pitch}</strong> (bar {rows[slice[1]]?.bar}) — {slice[1] - slice[0] + 1} of {rows.length} notes.
              </p>
            </div>
          )}
          <Field label="Chords (auto-detected; edit as `beat:symbol, beat:symbol`)">
            <Input value={chordText} onChange={(e) => setChordText(e.target.value)} className="font-mono" />
          </Field>
          <Button onClick={generate} disabled={!!busy}>
            3 · Generate &amp; rank fingerings
          </Button>
        </Card>
      )}

      {rank && (
        <Card className="space-y-3">
          <h2 className="text-base font-semibold">4 · Fingerings ranked by feasibility</h2>
          <p className="text-xs text-fg-muted">
            density <strong>{rank.density}</strong> · {rank.n_feasible} distinct playable fingering(s) — click a row for its tab
          </p>
          {rank.all_shifted && <Info>The written register does not fit the neck as written (highest playable note: string 1, fret 15 = G5) — every playable proposal transposes the whole line by the octave shown.</Info>}
          {rank.n_feasible < 3 && <Info tone="warn">Fewer than 3 distinct fingerings fit this line, even with octave transposition — the register is tightly constrained on the neck.</Info>}
          <Table>
            <thead>
              <tr>
                <Th>Fingering</Th>
                <Th>Octave</Th>
                <Th className="text-right">Cost</Th>
                <Th>Played at</Th>
                <Th className="text-right">↑</Th>
                <Th>Also matches</Th>
              </tr>
            </thead>
            <tbody>
              {rank.rows.map((r) => (
                <Tr key={r.label} selected={selRow?.label === r.label} onClick={() => r.fingering && setSelLabel(r.label)} className={r.fingering ? "" : "opacity-50"}>
                  <Td>{r.label}</Td>
                  <Td>{r.shift_text}</Td>
                  <Td className="text-right tabular-nums">{fmtCost(r.cost)}</Td>
                  <Td className="max-w-[16rem] truncate">{r.where}</Td>
                  <Td className="text-right">{r.n_up ?? "—"}</Td>
                  <Td className="max-w-[12rem] truncate text-fg-muted">{r.also.join(", ")}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
          {selRow?.fingering && (
            <>
              <p className="text-sm">
                <strong>{selRow.label}</strong> · {selRow.shift_text} · cost {fmtCost(selRow.cost)} · {selRow.where}
              </p>
              {selRow.shift ? <p className="text-xs text-fg-muted">This tab plays the line {selRow.shift_text} from the written pitch so it fits the neck; degrees and picking are unchanged.</p> : null}
              <FingeringCard fingering={selRow.fingering} filename="score_tab.svg">
                {!isImage && seqName.trim() && (
                  <Button size="sm" onClick={saveBest}>
                    Save as best for &apos;{seqName.trim()}&apos;
                  </Button>
                )}
              </FingeringCard>
            </>
          )}
        </Card>
      )}

      <ScoreLibrary scores={library.data?.scores ?? []} loading={library.isLoading} onLoad={(n) => { setSource("library"); loadFromLibrary(n); }} />
    </div>
  );
}

function NoteEditor({ rows, onChange }: { rows: Row[]; onChange: (r: Row[]) => void }) {
  const upd = (i: number, patch: Partial<Row>) => onChange(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <div className="max-h-[22rem] overflow-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <Th>#</Th>
            <Th>bar</Th>
            <Th>start (beat)</Th>
            <Th>pitch</Th>
            <Th>chord</Th>
            <Th>after rest</Th>
            <Th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <Td>{i}</Td>
              <Td>
                <input type="number" className="w-14 rounded border bg-bg px-1" value={r.bar} onChange={(e) => upd(i, { bar: Number(e.target.value) })} />
              </Td>
              <Td>
                <input type="number" step={0.25} className="w-20 rounded border bg-bg px-1" value={r.start} onChange={(e) => upd(i, { start: Number(e.target.value) })} />
              </Td>
              <Td>
                <input className="w-16 rounded border bg-bg px-1 font-mono" value={r.pitch} onChange={(e) => upd(i, { pitch: e.target.value })} />
              </Td>
              <Td>
                <input className="w-24 rounded border bg-bg px-1" value={r.chord} onChange={(e) => upd(i, { chord: e.target.value })} />
              </Td>
              <Td>
                <Checkbox checked={r.afterRest} onChange={(e) => upd(i, { afterRest: e.target.checked })} className="min-h-0" />
              </Td>
              <Td>
                <button className="text-fg-muted hover:text-danger" onClick={() => onChange(rows.filter((_, k) => k !== i))} aria-label="delete note">
                  ×
                </button>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t p-2">
        <Button size="sm" variant="ghost" onClick={() => onChange([...rows, { bar: rows.at(-1)?.bar ?? 1, start: (rows.at(-1)?.start ?? -1) + 1, pitch: "C4", chord: rows.at(-1)?.chord ?? "", afterRest: false }])}>
          + add note
        </Button>
      </div>
    </div>
  );
}

function ScoreLibrary({ scores, loading, onLoad }: { scores: SavedScore[]; loading: boolean; onLoad: (name: string) => void }) {
  const qc = useQueryClient();
  const [open, setOpen] = React.useState<string | null>(null);
  const sel = scores.find((s) => s.name === open) ?? null;
  async function remove(name: string) {
    if (!confirm(`Delete '${name}' from the library?`)) return;
    await fetch(`/api/scores/${encodeURIComponent(name)}`, { method: "DELETE" });
    qc.invalidateQueries({ queryKey: ["scores"] });
    setOpen(null);
  }
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Score library</h2>
      {loading && <Skeleton className="h-16" />}
      {!loading && !scores.length && <p className="text-sm text-fg-muted">Nothing saved yet.</p>}
      {scores.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Name</Th>
              <Th>Saved</Th>
              <Th>Best fingering</Th>
              <Th className="text-right">Cost</Th>
              <Th>Played at</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {scores.map((x) => (
              <Tr key={x.name} selected={sel?.name === x.name} onClick={() => setOpen(sel?.name === x.name ? null : x.name)}>
                <Td className="font-medium">{x.name}</Td>
                <Td className="whitespace-nowrap">{x.savedAt.slice(0, 10)}</Td>
                <Td>{x.bestFingering?.label ?? <span className="text-fg-muted">—</span>}</Td>
                <Td className="text-right tabular-nums">{fmtCost(x.bestFingering?.cost)}</Td>
                <Td className="max-w-[14rem] truncate">{x.bestFingering?.where ?? ""}</Td>
                <Td onClick={(e) => e.stopPropagation()}>
                  <Button size="sm" variant="ghost" onClick={() => onLoad(x.name)}>
                    load
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(x.name)}>
                    delete
                  </Button>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
      {sel && (
        <Card>
          {sel.bestFingering?.fingering ? (
            <>
              <p className="mb-2 text-sm">
                Best fingering for <strong>{sel.name}</strong> <Badge className="ml-1">{sel.bestFingering.label}</Badge> cost {fmtCost(sel.bestFingering.cost)}
              </p>
              <TabPlayer placed={sel.bestFingering.fingering.placed} chords={sel.bestFingering.fingering.chords} beatsPerBar={sel.bestFingering.fingering.beats_per_bar} totalCost={sel.bestFingering.fingering.cost} patternId={`score:${sel.name}`} />
            </>
          ) : (
            <p className="text-sm text-fg-muted">No best fingering saved for this sequence yet — load it, rank, and save the winner.</p>
          )}
        </Card>
      )}
    </section>
  );
}
