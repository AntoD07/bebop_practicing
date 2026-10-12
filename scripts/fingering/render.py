"""Human-facing output: the per-note table, an ASCII tab, the flag list, the
cost breakdown, and a SoundSlice-style SVG/HTML tab with cell and chord-tone
labels above the staff (and an optional Web-Audio play-along with a playhead).
"""

from __future__ import annotations

import html
from typing import List, Optional

from scripts.fingering.config import FingeringConfig
from scripts.fingering.costs import DOWN, UP, PULL, HAMMER, PlacedNote
from scripts.fingering.pitch import Note
from scripts.fingering.chords import chord_for_beat

# ASCII / glyph picking marks.
_GLYPH = {DOWN: "⊓", UP: "∨", PULL: "p", HAMMER: "h"}
_LEGATO = (PULL, HAMMER)


def _voicing_placed(result, voicing: str) -> List[PlacedNote]:
    """Select which note sequence to draw: phase-1 ``best`` (all-picked) or the
    applied phase-2 ``ornamented`` (slurred) version."""
    if voicing == "ornamented":
        if getattr(result, "ornamented", None) is None:
            raise ValueError("no ornamented voicing on this result "
                             "(enable config.ornament_engine_enabled)")
        return result.ornamented.placed
    return result.best.placed


def _glyph(stroke: str) -> str:
    return _GLYPH.get(stroke, stroke)


def _finger_str(p: PlacedNote) -> str:
    if p.finger == 0:
        return "0"
    return f"{p.finger}{'*' if p.is_stretch else ''}"


def _label(note: Note) -> str:
    return note.degree or note.role or ""


# --------------------------------------------------------------------------- #
# Text report
# --------------------------------------------------------------------------- #
def format_note_table(placed: List[PlacedNote]) -> str:
    hdr = f"{'#':>2}  {'beat':>4}  {'pitch':<5}  {'role/deg':<10}  {'str':>3}  {'fret':>4}  {'fin':>4}  {'stk':>3}  {'rest?':>5}"
    lines = [hdr, "-" * len(hdr)]
    for i, p in enumerate(placed):
        lines.append(
            f"{i:>2}  {p.beat:>4g}  {p.note.name:<5}  {_label(p.note):<10}  "
            f"{p.string:>3}  {p.fret:>4}  {_finger_str(p):>4}  {_glyph(p.stroke):>3}  "
            f"{'Y' if p.is_rest_stroke else 'N':>5}"
        )
    return "\n".join(lines)


def _bar_index(p, beats_per_bar: int) -> int:
    return int(p.note.onset // beats_per_bar)


def format_tab_ascii(placed: List[PlacedNote], beats_per_bar: int = 4) -> str:
    """6-line tab, string 1 (high E) on top, picking marks above, bar lines."""
    n = len(placed)
    w = 4  # column width
    # picking + label rows
    pick_row = " " * 4
    deg_row = " " * 4
    cols = {s: [] for s in range(1, 7)}
    for i, p in enumerate(placed):
        sep = "|" if (i > 0 and _bar_index(p, beats_per_bar)
                      > _bar_index(placed[i - 1], beats_per_bar)) else ""
        pad = w - len(sep)
        pick_row += sep + _glyph(p.stroke).center(pad)
        deg_row += sep + (_label(p.note)[:pad]).center(pad)
        for s in range(1, 7):
            if s == p.string:
                cell = f"({p.fret})" if p.note.is_grace else str(p.fret)
                cols[s].append((sep, cell.center(pad, "-")))
            else:
                cols[s].append((sep, "-" * pad))
    lines = [f"deg: {deg_row.rstrip()}", f"pick:{pick_row.rstrip()}"]
    string_names = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}
    for s in range(1, 7):  # top = string 1
        row = f"{string_names[s]}|--"
        for sep, cellstr in cols[s]:
            row += sep + cellstr
        lines.append(row)
    lines.append("  (⊓ = down/rest-stroke, ∨ = up, p = pull-off, h = hammer-on, "
                 "(n) = inserted grace)")
    return "\n".join(lines)


def _top_contributors(voicing, k: int = 3) -> List:
    return [(t, a) for t, a in voicing.contributions if a > 0][:k]


def format_report(result) -> str:
    cfg = result.config
    out: List[str] = []
    out.append("=" * 74)
    key = result.context.get("key", "?")
    out.append(f"FINGERING + PICKING  (key {key})   notes: {len(result.notes)}   "
               f"total cost: {result.best.total_cost}")
    out.append("=" * 74)

    for w in result.warnings:
        out.append(f"!! {w}")
    if result.warnings:
        out.append("")

    out.append("PHASE 1 (100% picked, orthodox Gypsy rest-strokes):")
    out.append(format_note_table(result.best.placed))
    out.append("")
    out.append(format_tab_ascii(result.best.placed, cfg.beats_per_bar))
    out.append("")

    out.append("FLAGS:")
    if result.best.flags:
        for f in result.best.flags:
            out.append(f"  - {f}")
    else:
        out.append("  (none — clean 2npS, all downbeats on D, no drops)")
    out.append("")

    n_up = sum(1 for p in result.best.placed if p.stroke == UP)
    n_desc = sum(
        1 for i in range(len(result.best.placed) - 1)
        if result.best.placed[i + 1].string > result.best.placed[i].string
    )
    out.append(f"Upstrokes: {n_up}   Descending crossings: {n_desc}   "
               f"(invariant: every U precedes a descending crossing)")
    out.append(f"Total cost: {result.best.total_cost}")
    top = _top_contributors(result.best)
    if top:
        out.append("Top cost contributors (debug by ear): " +
                   ", ".join(f"{t}={a:.2f}" for t, a in top))
    out.append("")

    if result.alternate is not None:
        out.append("-" * 74)
        out.append(f"ALTERNATE VOICING (within alt_margin={cfg.alt_margin}, "
                   f"cost {result.alternate.total_cost}):")
        out.append(format_note_table(result.alternate.placed))
        out.append("")

    if cfg.ornament_engine_enabled and getattr(result, "ornamented", None):
        o = result.ornamented
        out.append("-" * 74)
        out.append(f"PHASE 2 — ORNAMENTED VERSION — {len(o.events)} turn(s) "
                   f"applied, picks {o.picks_before} -> {o.picks_after}:")
        for fl in o.flags:
            out.append(f"  ! {fl}")
        if not o.events:
            out.append("  (no eligible site under the enabled families/budgets "
                       "— the slurred version equals the picked one)")
        out.append("")
        out.append(format_note_table(o.placed))
        out.append("")
        out.append(format_tab_ascii(o.placed, cfg.beats_per_bar))
        out.append("")
        if o.events:
            out.append("APPLIED ORNAMENTS:")
            for evd in o.events:
                added = ", ".join(f"{a['name']}[{_glyph(a['stroke'])}]"
                                  for a in evd["added_notes"]) or "none"
                out.append(
                    f"  * bar {evd['bar']} note {evd['at']} "
                    f"({evd['target_pitch']}): {evd['family']}  "
                    f"[{evd['stroke_before']} -> {evd['stroke_after']}, "
                    f"inserted: {added}"
                    + (", BREAKS 2npS" if evd["breaks_2nps"] else "")
                    + f", {evd['authentic']}]")
                out.append(f"      {evd['note']}")
        out.append("")

    out.append("=" * 74)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# SoundSlice-style SVG + HTML
# --------------------------------------------------------------------------- #
_STRING_Y = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}  # row order, string 1 on top
_STRING_NAME = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}

# The turn is the only applied ornament — one colour: boxes, arcs, band and
# label all share it, so the device reads at a glance.
_ORN_COLOR = {"turn": "#7b1fa2"}
_ORN_LABEL = {"turn": "turn"}


def _ornament_spans(placed: List[PlacedNote]):
    """Consecutive notes altered/inserted by one family -> (start, end, family)."""
    spans = []
    i = 0
    while i < len(placed):
        fam = placed[i].note.ornament
        if not fam:
            i += 1
            continue
        j = i
        while j + 1 < len(placed) and placed[j + 1].note.ornament == fam:
            j += 1
        spans.append((i, j, fam))
        i = j + 1
    return spans


def _cell_spans(notes: List[Note]):
    """Group consecutive notes sharing a cell name -> (start, end_inclusive, name)."""
    spans = []
    i = 0
    while i < len(notes):
        cell = notes[i].cell
        if cell is None:
            i += 1
            continue
        j = i
        while j + 1 < len(notes) and notes[j + 1].cell == cell:
            j += 1
        spans.append((i, j, cell))
        i = j + 1
    return spans


def _column_geometry(placed: List[PlacedNote], left: int, col: int = 62,
                     grace_col: int = 36):
    """Per-note column widths (grace notes are narrower) -> (starts, centres)."""
    widths = [grace_col if p.note.is_grace else col for p in placed]
    starts, centres, acc = [], [], left
    for w in widths:
        starts.append(acc)
        centres.append(acc + w // 2)
        acc += w
    return starts, centres, acc  # acc = right edge of the last column


def render_svg(result, tempo: int = 160, voicing: str = "best") -> str:
    placed = _voicing_placed(result, voicing)
    notes = [p.note for p in placed]
    cfg = result.config
    bpb = cfg.beats_per_bar

    left = 70
    top = 96          # room for chord + cell + degree lanes
    row_h = 26
    n = len(placed)
    starts, centres, right = _column_geometry(placed, left)
    width = right + 40
    staff_h = row_h * 5
    orn_spans = _ornament_spans(placed)
    height = top + staff_h + (124 if orn_spans else 90)

    def x(i):
        return centres[i]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="Menlo,Consolas,monospace" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fbfaf7"/>',
    ]

    # ---- chord lane -------------------------------------------------------
    last_chord = None
    for i in range(n):
        sym = chord_for_beat(result.context, placed[i].note.onset, bpb)
        if sym and sym != last_chord:
            parts.append(
                f'<text x="{x(i)}" y="22" fill="#1a3a8f" font-size="15" '
                f'font-weight="bold" text-anchor="middle">{html.escape(sym)}</text>')
            last_chord = sym

    # ---- cell-name brackets ----------------------------------------------
    for (a, b, name) in _cell_spans(notes):
        x0 = starts[a] + 6
        x1 = (starts[b + 1] if b + 1 < n else right) - 6
        y = 40
        parts.append(
            f'<path d="M{x0},{y+6} L{x0},{y} L{x1},{y} L{x1},{y+6}" '
            f'stroke="#b06a00" fill="none" stroke-width="1.4"/>')
        parts.append(
            f'<text x="{(x0+x1)/2}" y="{y-3}" fill="#b06a00" font-size="11" '
            f'text-anchor="middle">{html.escape(str(name))}</text>')

    # ---- degree / role labels + picking marks ----------------------------
    for i, p in enumerate(placed):
        lab = _label(p.note)
        if lab:
            parts.append(
                f'<text x="{x(i)}" y="64" fill="{"#999" if p.note.is_grace else "#3a7d3a"}" '
                f'font-size="{10 if p.note.is_grace else 12}" '
                f'text-anchor="middle">{html.escape(lab)}</text>')
        # picking glyph just above the staff; ornamented notes take their
        # family colour, legato marks otherwise grey (no attack)
        gcol = (_ORN_COLOR.get(p.note.ornament)
                or ("#c0392b" if p.stroke == UP
                    else "#8a7f6a" if p.stroke in _LEGATO else "#222"))
        parts.append(
            f'<text x="{x(i)}" y="{top-6}" font-size="{12 if p.note.is_grace else 15}" '
            f'text-anchor="middle" fill="{gcol}">{_glyph(p.stroke)}</text>')

    # ---- staff lines + string labels -------------------------------------
    for s in range(1, 7):
        yy = top + _STRING_Y[s] * row_h
        parts.append(
            f'<line x1="{left-10}" y1="{yy}" x2="{right}" y2="{yy}" '
            f'stroke="#cfc9bd" stroke-width="1"/>')
        parts.append(
            f'<text x="{left-24}" y="{yy+4}" font-size="12" fill="#888">'
            f'{_STRING_NAME[s]}</text>')

    # ---- bar lines (from real onsets) --------------------------------------
    bar_cols = [0] + [i for i in range(1, n)
                      if _bar_index(placed[i], bpb) > _bar_index(placed[i - 1], bpb)] + [n]
    for i in bar_cols:
        bx = starts[i] if i < n else right
        parts.append(
            f'<line x1="{bx}" y1="{top}" x2="{bx}" y2="{top+staff_h}" '
            f'stroke="#9a9384" stroke-width="1.5"/>')

    # ---- ornament highlight bands + labels (one colour per family) ---------
    # A span opening on a legato note extends one column left to include the
    # note it binds to (the pull source / slide start / hammered-from note).
    for (a, b, fam) in orn_spans:
        color = _ORN_COLOR.get(fam, "#555")
        a0 = a - 1 if (a > 0 and placed[a].stroke in _LEGATO) else a
        x0 = starts[a0] + 2
        x1 = (starts[b + 1] if b + 1 < n else right) - 2
        parts.append(
            f'<rect x="{x0}" y="{top-16}" width="{x1-x0}" height="{staff_h+28}" '
            f'rx="7" fill="{color}" fill-opacity="0.09" '
            f'stroke="{color}" stroke-opacity="0.55" stroke-width="1.2"/>')
        parts.append(
            f'<text x="{(x0+x1)/2}" y="{top+staff_h+34}" fill="{color}" '
            f'font-size="12" font-weight="bold" text-anchor="middle">'
            f'{html.escape(_ORN_LABEL.get(fam, fam))}</text>')

    # ---- slur arcs (legato notes bind to their predecessor) -----------------
    for i in range(1, n):
        p = placed[i]
        if p.stroke not in _LEGATO:
            continue
        color = _ORN_COLOR.get(p.note.ornament, "#8a7f6a")
        y0 = top + _STRING_Y[placed[i - 1].string] * row_h
        y1 = top + _STRING_Y[p.string] * row_h
        ytop = min(y0, y1) - 15
        letter = "H" if p.stroke == HAMMER else "P"
        parts.append(
            f'<path d="M{x(i-1)},{min(y0, y1)-12} '
            f'Q{(x(i-1)+x(i))/2},{ytop-8} {x(i)},{min(y0, y1)-12}" '
            f'stroke="{color}" fill="none" stroke-width="1.8"/>')
        parts.append(
            f'<text x="{(x(i-1)+x(i))/2}" y="{ytop-11}" fill="{color}" '
            f'font-size="11" font-weight="bold" text-anchor="middle">{letter}</text>')

    # ---- fret numbers on the string, boxed like SoundSlice ----------------
    for i, p in enumerate(placed):
        yy = top + _STRING_Y[p.string] * row_h
        grace = p.note.is_grace
        oc = _ORN_COLOR.get(p.note.ornament)
        fill = ("#f6f2ff" if grace
                else "#fdeaea" if (p.stroke == UP and not oc) else "#ffffff")
        border = oc or ("#777" if grace else "#333")
        w, h_box, fs = (18, 17, 11) if grace else (24, 22, 13)
        parts.append(
            f'<rect x="{x(i)-w//2}" y="{yy-h_box//2}" width="{w}" height="{h_box}" '
            f'rx="4" fill="{fill}" stroke="{border}" '
            f'stroke-width="{1.8 if oc else 1}"/>')
        bold = ' font-weight="bold"' if oc else ""
        parts.append(
            f'<text x="{x(i)}" y="{yy+4 if grace else yy+5}" font-size="{fs}" '
            f'text-anchor="middle" fill="{oc or "#111"}"{bold}>{p.fret}</text>')
        # small finger annotation under staff
        parts.append(
            f'<text x="{x(i)}" y="{top+staff_h+16}" font-size="10" '
            f'text-anchor="middle" fill="#777">{_finger_str(p)}</text>')

    # ---- playhead (animated by JS) ---------------------------------------
    parts.append(
        f'<line id="playhead" x1="{left}" y1="{top-2}" x2="{left}" '
        f'y2="{top+staff_h+2}" stroke="#c0392b" stroke-width="2" '
        f'opacity="0" />')

    # ---- legend -----------------------------------------------------------
    ly = top + staff_h + (58 if orn_spans else 44)
    parts.append(
        f'<text x="{left-24}" y="{ly}" font-size="11" fill="#666">'
        f'⊓ down/rest-stroke   ∨ up (parity)   H hammer-on   P pull-off   '
        f'fingers: 0=open 1-4 *=stretch</text>')
    if orn_spans:
        # colour key, only for the families actually on the page
        fams: List[str] = []
        for (_a, _b, fam) in orn_spans:
            if fam not in fams:
                fams.append(fam)
        lx = left - 24
        for fam in fams:
            color = _ORN_COLOR.get(fam, "#555")
            label = _ORN_LABEL.get(fam, fam)
            parts.append(
                f'<rect x="{lx}" y="{ly+8}" width="10" height="10" rx="2" '
                f'fill="{color}" fill-opacity="0.25" stroke="{color}" '
                f'stroke-width="1.4"/>')
            parts.append(
                f'<text x="{lx+15}" y="{ly+17}" font-size="11" '
                f'fill="{color}">{html.escape(label)}</text>')
            lx += 15 + 7 * len(label) + 22
    if voicing == "ornamented":
        o = result.ornamented
        parts.append(
            f'<text x="{left-24}" y="{ly+(34 if orn_spans else 16)}" '
            f'font-size="11" fill="#666">'
            f'ORNAMENTED version — {len(o.events)} turn(s) applied '
            f'(plain version kept separately; strip turns above ~180 bpm)</text>')
    else:
        parts.append(
            f'<text x="{left-24}" y="{ly+16}" font-size="11" fill="#666">'
            f'total cost {result.best.total_cost}'
            + (f"   |   {len(result.ornaments)} turn(s) in the ornamented version"
               if cfg.ornament_engine_enabled else "")
            + '</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def render_html(result, tempo: int = 160, voicing: str = "best") -> str:
    """SVG tab plus a Web-Audio 'play with moving playhead' button (SoundSlice feel).

    Scheduling is onset-based (not uniform), so inserted grace notes steal time
    from the preceding note and slurred notes sound softer (no pick attack).
    """
    svg = render_svg(result, tempo, voicing)
    placed = _voicing_placed(result, voicing)
    midis = [p.note.midi for p in placed]
    onsets = [p.note.onset for p in placed]
    base = onsets[0]
    starts = [round(o - base, 4) for o in onsets]
    durs = [round(max(0.08, starts[i + 1] - starts[i]), 4)
            for i in range(len(starts) - 1)] + [1.0]
    legato = [1 if p.stroke in _LEGATO else 0 for p in placed]
    left = 70
    _, centres, _right = _column_geometry(placed, left)
    beat_ms = int(60000 / max(1, tempo))
    import json as _json
    return f"""<!doctype html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#fbfaf7;font-family:Menlo,monospace">
<div style="padding:8px">
  <button id="play" style="font-size:14px;padding:6px 14px;border-radius:6px;
    border:1px solid #333;background:#fff;cursor:pointer">&#9654; Play</button>
  <label style="margin-left:12px;font-size:13px">tempo
    <input id="tempo" type="number" value="{tempo}" min="30" max="300"
      style="width:60px"></label>
</div>
<div id="tab">{svg}</div>
<script>
const MIDIS = {_json.dumps(midis)};
const STARTS = {_json.dumps(starts)};   // in beats, onset-based
const DURS = {_json.dumps(durs)};
const LEGATO = {_json.dumps(legato)};   // 1 = no pick attack (softer, bound)
const XS = {_json.dumps(centres)};
const BASE_BEAT_MS = {beat_ms};
let ctx = null;
function freq(m){{return 440*Math.pow(2,(m-69)/12);}}
document.getElementById('play').onclick = function(){{
  const tempo = parseInt(document.getElementById('tempo').value)||{tempo};
  const beat = 60000/tempo;
  ctx = ctx || new (window.AudioContext||window.webkitAudioContext)();
  const head = document.getElementById('playhead');
  const t0 = ctx.currentTime;
  MIDIS.forEach((m,i)=>{{
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type='triangle'; o.frequency.value=freq(m);
    const s = t0 + STARTS[i]*beat/1000;
    const d = DURS[i]*beat/1000;
    const peak = LEGATO[i] ? 0.16 : 0.25;         // slurred = softer attack
    const atk = LEGATO[i] ? 0.03 : 0.01;
    g.gain.setValueAtTime(0.0001,s);
    g.gain.exponentialRampToValueAtTime(peak,s+atk);
    g.gain.exponentialRampToValueAtTime(0.0001,s+d*0.95);
    o.connect(g); g.connect(ctx.destination); o.start(s); o.stop(s+d);
  }});
  head.setAttribute('opacity','1');
  MIDIS.forEach((m,i)=>{{
    setTimeout(()=>{{head.setAttribute('x1',XS[i]);head.setAttribute('x2',XS[i]);}}, STARTS[i]*beat);
  }});
  const end = (STARTS[STARTS.length-1]+DURS[DURS.length-1])*beat;
  setTimeout(()=>head.setAttribute('opacity','0'), end+150);
}};
</script>
</body></html>"""
