"""Score → Tab: read a written score and convert it to Gypsy-jazz fingering.

Input tiers:
  1. MusicXML (.xml / .musicxml / .mxl) — exact.
  2. PDF / PNG / JPG via OMR (oemer) — best effort, ALWAYS passes through the
     review table below so wrong accidentals can be fixed before tabbing.

Pitches from a score are absolute: the optimizer only decides WHERE on the
neck to play them (no octave re-voicing). Chord symbols from the score label
each note's degree on top of the tab.
"""

import os
import tempfile

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from scripts.utils import get_or_update_practice_details
from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering
from scripts.fingering.render import render_html, render_svg, format_report
from scripts.fingering.pitch import parse_pitch, midi_to_name
from scripts.fingering.positions import (
    POSITIONS, classify_position, position_config_for_key,
)
from scripts.fingering.score_import import (
    parse_score, line_from_score, chord_at, degree_for,
    pdf_to_png, omr_available, run_omr,
)
from scripts.fingering.vision_omr import read_score_with_claude, vision_available

st.set_page_config(layout="wide")
st.title("Score → Tab")
st.caption(
    "Upload a score; the engine finds the Gypsy fingering + picking for the "
    "written pitches. OMR output is never trusted blindly — review the notes "
    "below before generating the tab."
)

st.session_state.key, st.session_state.position = get_or_update_practice_details()
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.key}]")

_POS_OPTIONS = ["Free (best on the neck)"] + POSITIONS
score_position = st.sidebar.selectbox(
    "Fingering position", _POS_OPTIONS, index=0,
    help="A score's pitches are fixed — a named position constrains the box; "
         "if the written register doesn't fit it, you'll be told honestly.")
pos_key = st.sidebar.selectbox(
    "Key for the position box", ["C", "G", "D", "A", "E", "B", "F#",
                                 "Db", "Ab", "Eb", "Bb", "F"], index=0)
tempo = st.sidebar.number_input("Play-along tempo (bpm)", 30, 300, 160)

upload = st.file_uploader(
    "Score file", type=["xml", "musicxml", "mxl", "pdf", "png", "jpg", "jpeg"])

def _anthropic_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    try:
        key = key or st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:  # noqa: BLE001 — no secrets file
        pass
    return key


if upload is not None:
    raw = upload.getvalue()
    suffix = upload.name.rsplit(".", 1)[-1].lower()
    is_image = suffix in ("pdf", "png", "jpg", "jpeg")

    if is_image:
        # Fresh upload invalidates any previous recognition.
        if st.session_state.get("score_source") != upload.name:
            st.session_state.pop("score_parsed", None)
        if "score_parsed" not in st.session_state:
            c_v, c_o = st.columns(2)
            key = _anthropic_key()
            if c_v.button("Read with Claude vision (recommended for jazz fonts)",
                          type="primary", disabled=not (vision_available() and key)):
                with st.spinner("Claude is reading the score (~1-2 min)..."):
                    with tempfile.TemporaryDirectory() as td:
                        src = os.path.join(td, upload.name)
                        with open(src, "wb") as f:
                            f.write(raw)
                        png = pdf_to_png(src, td) if suffix == "pdf" else src
                        st.session_state.score_parsed = read_score_with_claude(
                            png, td, api_key=key)
                st.session_state.score_source = upload.name
            if not key:
                c_v.caption("Needs ANTHROPIC_API_KEY in .streamlit/secrets.toml")
            if c_o.button("Run OMR (oemer — weak on jazz fonts)",
                          disabled=not omr_available()):
                with st.spinner("Reading the score (oemer, several minutes)..."):
                    with tempfile.TemporaryDirectory() as td:
                        src = os.path.join(td, upload.name)
                        with open(src, "wb") as f:
                            f.write(raw)
                        png = pdf_to_png(src, td) if suffix == "pdf" else src
                        st.session_state.score_parsed = parse_score(run_omr(png, td))
                st.session_state.score_source = upload.name
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

    # ---- Review table: fix wrong pitches/chords before trusting the tab ----
    st.subheader("1 · Review the recognized notes")
    chords = parsed["chords"]
    rows = []
    for n in parsed["notes"]:
        rows.append({
            "bar": n.get("bar", 0),
            "start (beat)": n["start"],
            "pitch": midi_to_name(n["midi"]),
            "chord": chord_at(chords, n["start"]) or "",
            "after rest": n["phrase_start"],
        })
    edited = st.data_editor(
        pd.DataFrame(rows), num_rows="dynamic", use_container_width=True,
        key="score_editor",
        column_config={"start (beat)": st.column_config.NumberColumn(step=0.25)},
    )

    chord_txt = st.text_input(
        "Chords (auto-detected; edit as `beat:symbol, beat:symbol`)",
        value=", ".join(f"{c['start_beat']:g}:{c['symbol']}" for c in chords),
    )

    if st.button("2 · Generate tab", type="primary"):
        # Rebuild chords + line from the edited table.
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
        for _, r in edited.iterrows():
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
        line.sort(key=lambda n: n["start"])
        gaps = [b["start"] - a["start"] for a, b in zip(line, line[1:])]
        density = ("eighth" if gaps and sorted(gaps)[len(gaps) // 2] < 0.99
                   else "quarter")
        ctx = {"key": pos_key, "chords": edited_chords,
               "beats_per_bar": parsed["beats_per_bar"], "density": density}
        cfg = FingeringConfig(beats_per_bar=parsed["beats_per_bar"])
        if score_position in POSITIONS:
            cfg, _ = position_config_for_key(score_position, pos_key, cfg)
        try:
            result = optimize_fingering(line, ctx, cfg)
        except ValueError as e:
            st.error(f"The written register does not fit "
                     f"'{score_position}': {e}")
            st.stop()

        for w in result.warnings:
            st.warning(w)
        st.subheader("3 · Tab")
        st.write(f"Total cost **{result.best.total_cost}** · "
                 f"{classify_position(result.best.placed, pos_key)} · "
                 f"density {density}")
        components.html(render_html(result, tempo=int(tempo)),
                        height=380, scrolling=True)
        with st.expander("Full report (per-note table, flags, cost)"):
            st.code(format_report(result), language="text")
        st.download_button("Download tab as SVG", render_svg(result, int(tempo)),
                           file_name="score_tab.svg", mime="image/svg+xml")
else:
    st.info("Upload MusicXML for exact results, or a PDF/image to run OMR. "
            "No file? Export MusicXML from MuseScore (free) — it reads most "
            "notation formats.")
