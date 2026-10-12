"""Score → Tab: read a written score, rank candidate fingerings, keep a library.

Input tiers:
  1. MusicXML (.xml / .musicxml / .mxl) — exact; can be SAVED under a sequence
     name into the score library (``data/scores/``) and reloaded later.
  2. PDF / PNG / JPG via OMR (oemer) or Claude vision — best effort, ALWAYS
     passes through the review table so wrong accidentals can be fixed first.

Pitches from a score are absolute: the optimizer only decides WHERE on the
neck to play them (no octave re-voicing). Instead of one answer the page
proposes SEVERAL fingerings — Free best (+ its alternate), the five named
positions and three neck bands — ranked by feasibility under shared cost
weights (same engine as the Melodic Lines ranking). Click a row for its tab,
then save the winner back to the library as the sequence's best fingering.
"""

import os
import tempfile

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from scripts.utils import sidebar_practice_key, sidebar_metronome
from scripts import score_library
from scripts.fingering.config import FingeringConfig
from scripts.fingering.render import render_html, render_svg, format_report
from scripts.fingering.pitch import parse_pitch, midi_to_name
from scripts.fingering.positions import rank_absolute_fingerings
from scripts.fingering.score_import import (
    parse_score, chord_at, degree_for,
    pdf_to_png, omr_available, run_omr,
)
from scripts.fingering.vision_omr import read_score_with_claude, vision_available

st.set_page_config(layout="wide")
st.title("Score → Tab")
st.caption(
    "Upload a score (or reload a saved one); the engine proposes several "
    "Gypsy fingerings for the written pitches, ranked by feasibility. "
    "OMR output is never trusted blindly — review the notes before tabbing."
)

st.session_state.key, st.session_state.position = sidebar_practice_key()
tempo = sidebar_metronome()

pos_key = st.sidebar.selectbox(
    "Key for the position boxes", ["C", "G", "D", "A", "E", "B", "F#",
                                   "Db", "Ab", "Eb", "Bb", "F"], index=0,
    help="Named positions are anchored on this key's root; it also names "
         "where each ranked fingering lands.")


def _anthropic_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    try:
        key = key or st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:  # noqa: BLE001 — no secrets file
        pass
    return key


# --------------------------------------------------------------------------- #
# 1 · Source: a fresh upload, or a sequence saved in the library.
# --------------------------------------------------------------------------- #
st.subheader("1 · Score")
source = st.radio("Score source", ["Upload a file", "Score library"],
                  horizontal=True, label_visibility="collapsed")

raw, fname, source_id, seq_default = None, None, None, ""
if source == "Upload a file":
    upload = st.file_uploader(
        "Score file", type=["xml", "musicxml", "mxl", "pdf", "png", "jpg", "jpeg"])
    if upload is not None:
        raw, fname = upload.getvalue(), upload.name
        source_id = f"upload:{upload.name}"
        seq_default = upload.name.rsplit(".", 1)[0]
else:
    _index = score_library.load_index()
    if _index.empty:
        st.info("The library is empty — upload a MusicXML file and save it "
                "under a sequence name first.")
    else:
        pick = st.selectbox("Saved sequence", list(_index["Name"]))
        try:
            raw = score_library.load_score_bytes(pick)
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()
        fname = os.path.basename(score_library.score_path(pick))
        source_id = f"library:{pick}"
        seq_default = pick

suffix = fname.rsplit(".", 1)[-1].lower() if fname else None
is_image = suffix in ("pdf", "png", "jpg", "jpeg")

# A new source invalidates the previous recognition and ranking.
if source_id != st.session_state.get("score_source"):
    st.session_state.pop("score_parsed", None)
    st.session_state.pop("score_rank", None)
    st.session_state.score_source = source_id

if raw is None:
    st.info("Upload MusicXML for exact results (SoundSlice and MuseScore both "
            "export it), or a PDF/image to run OMR.")
    st.stop()

if is_image:
    if "score_parsed" not in st.session_state:
        c_v, c_o = st.columns(2)
        key = _anthropic_key()
        if c_v.button("Read with Claude vision (recommended for jazz fonts)",
                      type="primary", disabled=not (vision_available() and key)):
            with st.spinner("Claude is reading the score (~1-2 min)..."):
                with tempfile.TemporaryDirectory() as td:
                    src = os.path.join(td, fname)
                    with open(src, "wb") as f:
                        f.write(raw)
                    png = pdf_to_png(src, td) if suffix == "pdf" else src
                    st.session_state.score_parsed = read_score_with_claude(
                        png, td, api_key=key)
        if not key:
            c_v.caption("Needs ANTHROPIC_API_KEY in .streamlit/secrets.toml")
        if c_o.button("Run OMR (oemer — weak on jazz fonts)",
                      disabled=not omr_available()):
            with st.spinner("Reading the score (oemer, several minutes)..."):
                with tempfile.TemporaryDirectory() as td:
                    src = os.path.join(td, fname)
                    with open(src, "wb") as f:
                        f.write(raw)
                    png = pdf_to_png(src, td) if suffix == "pdf" else src
                    st.session_state.score_parsed = parse_score(run_omr(png, td))
    if "score_parsed" not in st.session_state:
        st.stop()
    parsed = st.session_state.score_parsed
    for u in parsed.get("uncertain", []):
        st.warning(f"Reader unsure at bar {u['measure']}: {u['reason']}")
else:
    try:
        parsed = parse_score(raw)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not parse the score: {e}")
        st.stop()

# ---- Name the sequence + save its MusicXML into the library ----------------
if not is_image:
    lc1, lc2 = st.columns((0.6, 0.4))
    seq_name = lc1.text_input(
        "Sequence name (for the library)", value=seq_default, key="score_seq_name")
    lc2.write("")  # vertical align the button with the input
    if lc2.button("Save MusicXML to library",
                  disabled=not seq_name.strip(),
                  help="Stores the file under data/scores/ so it can be "
                       "reloaded here; re-saving updates the file and keeps "
                       "any best fingering already chosen."):
        try:
            score_library.save_score(seq_name.strip(), raw, fname)
        except ValueError as e:
            st.error(str(e))
        else:
            st.success(f"Saved '{seq_name.strip()}' to the library.")
else:
    seq_name = ""
    st.caption("Image/PDF sources can be tabbed but not saved to the library — "
               "only MusicXML sequences are stored.")

# --------------------------------------------------------------------------- #
# 2 · Review table: fix wrong pitches/chords before trusting the tab.
# --------------------------------------------------------------------------- #
st.subheader("2 · Review the recognized notes")
chords = parsed["chords"]
rows = []
for i, n in enumerate(parsed["notes"]):
    rows.append({
        "note #": i,
        "bar": n.get("bar", 0),
        "start (beat)": n["start"],
        "pitch": midi_to_name(n["midi"]),
        "chord": chord_at(chords, n["start"]) or "",
        "after rest": n["phrase_start"],
    })
edited = st.data_editor(
    pd.DataFrame(rows), num_rows="dynamic", use_container_width=True,
    key=f"score_editor_{source_id}",
    column_config={
        "note #": st.column_config.NumberColumn(
            disabled=True, help="Matches the start/end-note slider below."),
        "start (beat)": st.column_config.NumberColumn(step=0.25),
    },
)

# ---- Optional slice: pick the note the line starts (and ends) on -----------
n_rows = len(edited)
if n_rows >= 2:
    slice_lo, slice_hi = st.slider(
        "Start / end note — tab only this slice of the score "
        "(`note #` in the table above)",
        0, n_rows - 1, (0, n_rows - 1),
        key=f"score_slice_{source_id}_{n_rows}",
    )
    _lo, _hi = edited.iloc[slice_lo], edited.iloc[slice_hi]
    st.caption(
        f"Line starts on note {slice_lo} — **{_lo['pitch']}** (bar {int(_lo['bar'])}) "
        f"and ends on note {slice_hi} — **{_hi['pitch']}** (bar {int(_hi['bar'])}) — "
        f"{slice_hi - slice_lo + 1} of {n_rows} notes."
    )
else:
    slice_lo, slice_hi = 0, max(0, n_rows - 1)

chord_txt = st.text_input(
    "Chords (auto-detected; edit as `beat:symbol, beat:symbol`)",
    value=", ".join(f"{c['start_beat']:g}:{c['symbol']}" for c in chords),
)

# --------------------------------------------------------------------------- #
# 3 · Rank fingerings: Free (+ alternate), the five positions, three neck
# bands — all scored under the SAME weights, most feasible first.
# --------------------------------------------------------------------------- #
if st.button("3 · Generate & rank fingerings", type="primary"):
    edited_chords = []
    for tok in chord_txt.split(","):
        tok = tok.strip()
        if not tok or ":" not in tok:
            continue
        b, sym = tok.split(":", 1)
        try:
            edited_chords.append({"start_beat": float(b), "symbol": sym.strip()})
        except ValueError:
            continue
    line = []
    for _, r in edited.iloc[slice_lo:slice_hi + 1].iterrows():
        try:
            midi = parse_pitch(str(r["pitch"]).strip())
        except ValueError as e:
            st.error(f"Bad pitch {r['pitch']!r}: {e}")
            st.stop()
        start = float(r["start (beat)"])
        sym = chord_at(edited_chords, start)
        line.append({
            "pitch": midi, "start": start,
            "phrase_start": bool(r["after rest"]),
            "degree": degree_for(midi, sym),
            "cell": f"bar {int(r['bar'])}" if r["bar"] else None,
        })
    if not line:
        st.error("No notes to finger — the review table is empty.")
        st.stop()
    line.sort(key=lambda n: n["start"])
    line[0]["phrase_start"] = True  # a sliced line still STARTS the phrase
    gaps = [b["start"] - a["start"] for a, b in zip(line, line[1:])]
    density = ("eighth" if gaps and sorted(gaps)[len(gaps) // 2] < 0.99
               else "quarter")
    ctx = {"key": pos_key, "chords": edited_chords,
           "beats_per_bar": parsed["beats_per_bar"], "density": density}
    with st.spinner("Ranking fingerings (Free, 5 positions, 3 neck bands)..."):
        fing_rows = rank_absolute_fingerings(
            line, ctx, pos_key,
            base=FingeringConfig(beats_per_bar=parsed["beats_per_bar"]))
    st.session_state.score_rank = {"rows": fing_rows, "density": density}

# ---- Results live in session_state so row clicks / saves survive reruns ----
_SHIFT_TEXT = {0: "as written", -12: "1 octave down", 12: "1 octave up",
               -24: "2 octaves down", 24: "2 octaves up"}

if st.session_state.get("score_rank"):
    fing_rows = st.session_state.score_rank["rows"]
    density = st.session_state.score_rank["density"]
    feasible = [r for r in fing_rows if r["result"] is not None]

    st.subheader("4 · Fingerings ranked by feasibility")
    st.write(f"density **{density}** · {len(feasible)} distinct playable "
             f"fingering(s) — click a row for its tab")
    if feasible and all(r["shift"] for r in feasible):
        st.info("The written register does not fit the guitar neck as "
                "written (highest playable note: string 1, fret 15 = G5) — "
                "every playable proposal below transposes the whole line by "
                "the octave shown in the Octave column.")
    if len(feasible) < 3:
        st.warning("Fewer than 3 distinct fingerings fit this line, even "
                   "with octave transposition — the register is tightly "
                   "constrained on the neck.")
    st.dataframe(
        pd.DataFrame([{
            "Fingering": r["label"],
            "Octave": (_SHIFT_TEXT.get(r["shift"], "—")
                       if r["shift"] is not None else "—"),
            "Cost": r["cost"],
            "Played at": r["where"],
            "Upstrokes": r["n_up"],
            "Also matches": ", ".join(r["also"]),
        } for r in fing_rows]),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="score_fing_table",
    )
    _sel = st.session_state.score_fing_table.selection["rows"]
    _row = fing_rows[_sel[0]] if _sel else (feasible[0] if feasible else None)
    if _row is None or _row["result"] is None:
        st.error("No playable fingering for this candidate"
                 + (f" — {_row['where']}" if _row is not None else "")
                 + ". Pick another row.")
        st.stop()

    result = _row["result"]
    for w in result.warnings:
        st.warning(w)
    _octave_txt = _SHIFT_TEXT.get(_row["shift"], "as written")
    st.write(f"**{_row['label']}**   ·   {_octave_txt}   ·   "
             f"cost {_row['cost']:.2f}   ·   {_row['where']}")
    if _row["shift"]:
        st.caption(f"This tab plays the line {_octave_txt} from the written "
                   f"pitch so it fits the neck; degrees and picking are "
                   f"unchanged.")
    components.html(render_html(result, tempo=int(tempo)),
                    height=380, scrolling=True)
    with st.expander("Full report (per-note table, flags, cost)"):
        st.code(format_report(result), language="text")

    dl1, dl2 = st.columns(2)
    dl1.download_button("Download tab as SVG", render_svg(result, int(tempo)),
                        file_name="score_tab.svg", mime="image/svg+xml")
    if not is_image and seq_name.strip():
        if dl2.button(f"Save this fingering as best for '{seq_name.strip()}'"):
            name = seq_name.strip()
            # The fingering belongs to the score — make sure the score is saved.
            if score_library.score_path(name) is None:
                score_library.save_score(name, raw, fname)
            _saved_label = _row["label"] + (
                f" ({_SHIFT_TEXT[_row['shift']]})" if _row["shift"] else "")
            score_library.save_best_fingering(
                name,
                svg=render_svg(result, int(tempo)),
                encoding=" ".join(f"{p.string}/{p.fret}{p.stroke}"
                                  for p in result.best.placed),
                label=_saved_label,
                cost=_row["cost"],
                where=_row["where"],
            )
            st.success(f"Best fingering for '{name}' saved to the library.")

# --------------------------------------------------------------------------- #
# Library browser: every saved sequence and its chosen best fingering.
# --------------------------------------------------------------------------- #
st.write("---")
st.write("## Score library")
_lib = score_library.load_index()
if _lib.empty:
    st.caption("Nothing saved yet.")
else:
    st.dataframe(
        _lib.drop(columns=["File", "Tab", "Tab file"]),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="score_lib_table",
    )
    _lsel = st.session_state.score_lib_table.selection["rows"]
    if _lsel:
        _lrow = _lib.iloc[_lsel[0]]
        _tab = score_library.tab_path(_lrow["Name"])
        if _tab is not None:
            st.write(f"Best fingering for **{_lrow['Name']}** "
                     f"({_lrow['Best fingering']} · cost {_lrow['Best cost']})")
            components.html(open(_tab).read(), height=380, scrolling=True)
        else:
            st.caption("No best fingering saved for this sequence yet — load "
                       "it above, rank, and save the winner.")
        if st.checkbox(f"Confirm deleting '{_lrow['Name']}' from the library",
                       key="score_lib_delete_confirm"):
            if st.button("Delete sequence", type="secondary"):
                score_library.delete_score(_lrow["Name"])
                st.rerun()
