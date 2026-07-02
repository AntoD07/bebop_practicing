"""Gypsy-jazz fingering + picking optimizer — Streamlit page.

The line creator mirrors the "Practicing Melodic Lines" page: same line types,
same connecting-note / movement / translation controls. Once a line is
generated (or typed as pitches), the Viterbi/DP fingering search runs and a
SoundSlice-style tab is rendered with cell + chord-tone labels, picking marks,
and a play-along playhead.
"""

import ast

import streamlit as st
import streamlit.components.v1 as components

from scripts.utils import get_or_update_practice_details, join_notes
from scripts.melodic_lines.melodic_lines import (
    sample_line_from_path_with_connecting_note,
    line_structure_mapping,
)
from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering
from scripts.fingering.picking import ConventionError
from scripts.fingering.render import format_report, render_html, render_svg
from scripts.fingering import cell_bridge
from scripts.fingering.cell_bridge import DEFAULT_MODE_ROOT_OFFSET, root_pc

_PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MODE_QUALITY = {
    "Myxolidian": "7", "7sus4": "7", "Locrian": "m7b5", "Dorian": "m7",
    "Maj7": "maj7", "MajorResolutions": "maj7", "MinorResolutions": "m6",
}


def _chord_symbol(key: str, mode: str, offset: int) -> str:
    pc = (root_pc(key) + offset) % 12
    return _PC_NAMES[pc] + _MODE_QUALITY.get(mode, "")


st.set_page_config(layout="wide")
st.title("Gypsy-jazz Fingering & Picking")
st.caption(
    "Pitches are fixed — the solver finds string/fret positions and DERIVES the "
    "picking (rest-stroke downstrokes maximised; upstrokes spent only to turn a "
    "descending D→D drop into a clean U→D)."
)

st.session_state.key, st.session_state.position = get_or_update_practice_details()

# --------------------------------------------------------------------------- #
# Sidebar — same practice context as page 2, plus fingering knobs.
# --------------------------------------------------------------------------- #
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.key}]")
st.sidebar.subheader(
    f"Today's Position (for guitar): :blue[{st.session_state.position}]"
)
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)
st.session_state.length = st.sidebar.number_input(
    "Select the line length (depends on the line type) ",
    min_value=2, max_value=8, value=4,
)
st.session_state.movement = st.sidebar.selectbox(
    "Select the line movement (optional) ",
    [None, "A and N", "D and N", "A", "D"],
    index=[None, "A and N", "D and N", "A", "D"].index(
        st.session_state.get("movement", None)
    ),
)

with st.sidebar.expander("Fingering cost weights"):
    cfg = FingeringConfig(
        max_stretch=st.slider("max_stretch", 3, 6, 4),
        u_cost=st.slider("u_cost (upstroke)", 0.0, 5.0, 1.0, 0.25),
        drop_cost=st.slider("drop_cost", 0.0, 30.0, 10.0, 1.0),
        shift_cost=st.slider("shift_cost /fret", 0.0, 3.0, 0.5, 0.25),
        break_cost=st.slider("break_cost (2npS)", 0.0, 10.0, 3.0, 0.5),
        sweep_bonus=st.slider("sweep_bonus", 0.0, 3.0, 0.5, 0.25),
        ornament_engine_enabled=st.checkbox("Phase-2 ornament engine", value=False),
    )
tempo = st.sidebar.number_input("Play-along tempo (bpm)", 30, 300, 160)

# --------------------------------------------------------------------------- #
# Line creator — mirrors "Practicing Melodic Lines".
# --------------------------------------------------------------------------- #
c1, c2 = st.columns((0.5, 0.5))

st.session_state.sus_to_loc_dorian = c2.checkbox(
    "Whether to change to translate the intervals for other modes", value=False
)
st.session_state.dom_to_minor = c2.checkbox(
    "Whether to translate Dominant and Locrian cells to Minor/Major-I", value=False
)

_NOTES = ["None", "1", "9", "3", "11", "#11", "5", "6", "7", "b7", "b6", "b9", "#9"]

with c1:
    st.session_state.line_type = st.selectbox(
        "Type of line to practice",
        options=[
            "Maj7", "Dorian", "Myxolidian", "Locrian",
            "Short Maj 2-5-1", "Long Maj 2-5-1",
            "Short Minor 2-5-1", "Long Minor 2-5-1",
            "Long Minor with double resolution", "Double resolution",
            "Dorian and Dominant 2-cells alternated", "Dorian x Dominant",
            "Major x Dominant",
        ],
        index=5,  # Default to "Long Maj 2-5-1"
    )

    sample_path = line_structure_mapping(
        st.session_state.line_type, st.session_state.length
    )
    if st.session_state.line_type not in [
        "Long Minor 2-5-1 with Dorian ending",
        "Long Maj 2-5-1 with Maj7 ending",
        "Dorian and Dominant 2-cells alternated",
    ]:
        st.session_state.starting_note = st.selectbox(
            "Select the first note (optional) ", options=_NOTES)
        st.session_state.ending_note = st.selectbox(
            "Select the end note (optional) ", options=_NOTES)
    else:
        st.session_state.starting_note = "None"
        st.session_state.ending_note = "None"

    used_notes = ["1", "9", "3", "11", "#11", "5", "6", "7", "b7", "b6", "b9", "#9", None]
    st.write("Melodic Lines sampled according to the following cells : ", sample_path)
    connecting_notes = st.multiselect(
        "Select connecting notes",
        options=used_notes,
        default=(
            ["1", "3", "5", "7"]
            if st.session_state.line_type
            not in ["Long Minor 2-5-1", "Short Minor 2-5-1", "Double resolution"]
            else used_notes
        ),
    )
    connecting_notes = [list(connecting_notes) for _ in range(len(sample_path))]

chord_tones = st.checkbox("Connecting note are chord tones", value=False)
if chord_tones and ("2-5-1" in st.session_state.line_type):
    connecting_notes = [
        ["9", "6", "b6", "b9", "#9", "11", "#11", "5"],
        ["9", "6", "b6", "b9", "#9", "11", "#11", "5"],
        ["1", "3", "5", "7"],
        ["1", "3", "5", "7"],
    ]

if st.button("Generate melodic line", type="primary"):
    out = sample_line_from_path_with_connecting_note(
        line_type=st.session_state.line_type,
        include_bonus=st.session_state.include_bonus,
        mode_filter=False,
        loc_to_dom=False,
        dom_to_minor=st.session_state.dom_to_minor,
        sus_to_loc_dorian=st.session_state.sus_to_loc_dorian,
        length=st.session_state.length,
        movement=st.session_state.movement,
        starting_note=st.session_state.starting_note,
        ending_note=st.session_state.ending_note,
        connecting_notes=connecting_notes,
    )
    if out is None:
        st.error("Could not sample a line with those settings — try relaxing the "
                 "start/end/connecting-note constraints.")
        st.session_state.pop("fing_line", None)
    else:
        melodic_line, note_reps, gen_path = out
        d1, d2, d3 = st.columns((0.2, 0.5, 0.3))
        for mode, name, notes in zip(gen_path, melodic_line, note_reps):
            d1.write(f"##### :blue[{mode}]")
            d2.write(f"##### {name}")
            d3.write(join_notes(notes))
        st.session_state.fing_line = {
            "melodic_line": melodic_line,
            "note_reps": [str(n) for n in note_reps],
            "mode_list": list(gen_path),
            "line_type": st.session_state.line_type,
        }

# --------------------------------------------------------------------------- #
# Optional: type explicit pitches instead of generating.
# --------------------------------------------------------------------------- #
with st.expander("…or type an explicit pitch line (bypasses the cell engine)"):
    raw = st.text_area(
        "Comma-separated `pitch` or `pitch:role` (scientific like `A4`/`F#3`, or MIDI)",
        value="A3:1, D4:5, F4:b3, A4:5, G4:b3, F4:11, E4:9, D4:1", height=70)
    chord_txt = st.text_input("Chord(s) — `symbol` or `beat:symbol`", value="Dm7")
    if st.button("Optimize typed line"):
        toks = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
        parsed = []
        for t in toks:
            if ":" in t:
                p, role = t.split(":", 1)
                parsed.append({"pitch": p.strip(), "role": role.strip(), "degree": role.strip()})
            else:
                parsed.append({"pitch": t.strip()})
        chords = []
        for c in chord_txt.split(","):
            c = c.strip()
            if not c:
                continue
            if ":" in c:
                b, sym = c.split(":", 1)
                chords.append({"start_beat": int(b), "symbol": sym.strip()})
            else:
                chords.append({"start_beat": 0, "symbol": c})
        st.session_state.fing_typed = {"line": parsed, "chords": chords}
        st.session_state.pop("fing_line", None)

# --------------------------------------------------------------------------- #
# Build the pitch line + run the optimizer + render.
# --------------------------------------------------------------------------- #
line, context, cfg_run = None, None, cfg

if st.session_state.get("fing_line"):
    g = st.session_state.fing_line
    degs = [ast.literal_eval(n) if isinstance(n, str) else n for n in g["note_reps"]]
    mode_list = g["mode_list"]
    # Single-mode lines sit on the key; multi-mode (2-5-1) uses the ii–V–i roots.
    if len(set(mode_list)) == 1:
        offsets = {m: 0 for m in mode_list}
    else:
        offsets = DEFAULT_MODE_ROOT_OFFSET
    line = cell_bridge.line_from_engine(
        g["melodic_line"], degs, mode_list, st.session_state.key,
        mode_root_offset=offsets)
    # Cell length -> "bar", chord label per cell (so each chord's beat 1 = a cell start).
    cell_len = len(degs[0]) if degs else 4
    chords = []
    acc = 0
    for mode in mode_list:
        off = 0 if len(set(mode_list)) == 1 else DEFAULT_MODE_ROOT_OFFSET.get(mode, 0)
        chords.append({"start_beat": acc, "symbol": _chord_symbol(st.session_state.key, mode, off)})
        acc += cell_len
    context = {"key": st.session_state.key, "beats_per_bar": cell_len, "chords": chords}
    cfg_run = cfg.with_overrides(beats_per_bar=cell_len)

elif st.session_state.get("fing_typed"):
    t = st.session_state.fing_typed
    line = t["line"]
    context = {"key": st.session_state.key, "chords": t["chords"]}

if line:
    try:
        result = optimize_fingering(line, context, cfg_run)
    except ConventionError as e:
        st.error(f"Convention check failed — halted: {e}")
        st.stop()
    except ValueError as e:
        st.error(f"Could not finger this line: {e}")
        st.stop()

    for w in result.warnings:
        st.warning(w)

    st.subheader("Tab (SoundSlice-style) — press ▶ to hear it")
    components.html(render_html(result, tempo=int(tempo)), height=380, scrolling=True)

    with st.expander("Full report (per-note table, flags, cost, alternate, ornaments)",
                     expanded=True):
        st.code(format_report(result), language="text")

    st.download_button("Download tab as SVG", render_svg(result, int(tempo)),
                       file_name="fingering_tab.svg", mime="image/svg+xml")
