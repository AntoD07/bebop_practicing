import os
import pandas as pd
import ast
import streamlit as st
import streamlit.components.v1 as components
import json
import datetime
import random

from scripts.paths import PRACTICE_DETAILS, MELODIC_LINES_LOG
from scripts.fingering.positions import POSITIONS

# Column order for the graded melodic-line log (data/logs/melodic_lines.csv).
PRACTICE_LOG_COLUMNS = [
    "Date",
    "Line type",
    "Line",
    "Note sequence",
    "Grade",
    "Comment",
    "Movement",
    "Tab",        # compact fingering: "5/3D 5/6D ..." (string/fret + stroke)
    "Tab file",   # saved SVG of the tab, relative to the repo root
]


@st.cache_data
def validate_results(answer, gt):
    # Keys in a but not in b
    extras = set(answer.keys()) - set(gt.keys())
    missing = set(gt.keys()) - set(answer.keys())
    return extras, missing


@st.cache_data
def names_to_notes(all_cells, names):
    return {name: all_cells[name] for name in names}


@st.cache_data
def join_notes(cell):
    # Extract numbers using regular expression
    try:
        notes_list = ast.literal_eval(cell)
    except ValueError:
        notes_list = cell
    # Join the extracted numbers with a hyphen
    return "-".join(notes_list)


@st.cache_data
def cell_from_string(string):
    return "-".join(string.split(" "))


# The 12 practice keys the daily rotation draws from (and the override list).
PRACTICE_KEYS = ["C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db"]


def get_or_update_practice_details():
    """
    Fetches or updates the practice details (key and position) from/to a JSON file.

    Returns:
    - A tuple containing the key and position for today's practice.
    """
    filename = PRACTICE_DETAILS
    today = datetime.date.today().isoformat()

    try:
        with open(filename, "r") as file:
            practice_details = json.load(file)
    except FileNotFoundError:
        practice_details = {}

    # If details for today are not present or the file doesn't exist, update them.
    if practice_details.get("date") != today:
        positions = list(range(1, 6))
        practice_details = {
            "date": today,
            "key": random.choice(PRACTICE_KEYS),
            "position": random.choice(positions),
        }

        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        with open(filename, "w") as file:
            json.dump(practice_details, file)

    return practice_details["key"], practice_details["position"]


def _set_practice_detail(field, value):
    """Override one of TODAY's practice details (persisted, so every page
    agrees). Only that field changes — the normal random rotation still kicks
    in tomorrow."""
    get_or_update_practice_details()  # ensure the file exists for today
    with open(PRACTICE_DETAILS, "r") as file:
        details = json.load(file)
    details[field] = value
    with open(PRACTICE_DETAILS, "w") as file:
        json.dump(details, file)


def set_practice_key(key):
    _set_practice_detail("key", key)


def set_practice_position(position):
    _set_practice_detail("position", int(position))


def sidebar_practice_key():
    """Sidebar 'Today's Key' + 'Today's Position' SELECTBOXES: each shows the
    daily draw, and changing it overrides it for the whole app (persisted).

    Returns ``(key, position)`` like get_or_update_practice_details();
    ``position`` is 1-based into ``POSITIONS``.
    """
    key, position = get_or_update_practice_details()
    sel = st.sidebar.selectbox(
        "Today's Key",
        PRACTICE_KEYS,
        index=PRACTICE_KEYS.index(key) if key in PRACTICE_KEYS else 0,
        key="today_key_selector",
        help="Drawn at random once a day; pick another key to override it "
             "everywhere (tomorrow's draw is unaffected).",
    )
    if sel != key:
        set_practice_key(sel)
        key = sel

    pos_numbers = list(range(1, len(POSITIONS) + 1))
    sel_pos = st.sidebar.selectbox(
        "Today's Position (for guitar)",
        pos_numbers,
        index=pos_numbers.index(position) if position in pos_numbers else 0,
        format_func=lambda i: f"{i} · {POSITIONS[i - 1]}",
        key="today_position_selector",
        help="Drawn at random once a day; pick another position to override it "
             "everywhere (tomorrow's draw is unaffected).",
    )
    if sel_pos != position:
        set_practice_position(sel_pos)
        position = sel_pos
    return key, position


DEFAULT_TEMPO = 85


def sidebar_metronome():
    """Shared metronome at the top of the sidebar; returns the tempo (bpm).

    Call it right after ``sidebar_practice_key()``, before anything that may
    ``st.stop()``: a fixed slot keeps the iframe mounted (it keeps ticking
    across reruns) and never vanishes on an early stop. The tempo lives in
    ``st.session_state.tempo`` so it carries across pages and drives the tab
    play-alongs too.
    """
    # Keyed widget (no ``value=``): passing back the value it just set would
    # rebuild the widget on every rerun and swallow every second change. The
    # re-assignment keeps the key alive across page switches.
    st.session_state.tempo = int(st.session_state.get("tempo", DEFAULT_TEMPO))
    st.sidebar.number_input(
        "Metronome tempo (bpm)",
        min_value=30,
        max_value=300,
        key="tempo",
        help="Also the play-along tempo of the tabs. Set the metronome to 2 "
             "beats, stressing the first beat.",
    )
    with st.sidebar.expander("🎵 Metronome"):
        components.html(
            f"""<iframe src="https://guitarapp.com/metronome.html?embed=true&tempo={int(st.session_state.tempo)}&timeSignature=2&pattern=0"
                title="Online Metronome"
                style="width:100%; height:520px; border:none; border-radius:4px;">
            </iframe>""",
            height=530,
        )
    return int(st.session_state.tempo)


def save_practice_session(details, file_path=MELODIC_LINES_LOG):
    """
    Appends practice session details to a CSV file, migrating the file's schema
    when new columns (e.g. "Tab", "Tab file") are introduced: the existing log
    is read, aligned to the union of columns, and rewritten — so old rows keep
    working and new rows never mis-align.
    """
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    new_row = pd.DataFrame([details])
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        existing = pd.read_csv(file_path)
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        combined = new_row
    # Stable column order: canonical first, any extras preserved at the end.
    cols = [c for c in PRACTICE_LOG_COLUMNS if c in combined.columns] + \
           [c for c in combined.columns if c not in PRACTICE_LOG_COLUMNS]
    combined[cols].to_csv(file_path, index=False)


def load_practice_lines(file_path=MELODIC_LINES_LOG):
    """
    Loads the graded melodic-line log, returning an empty (correctly-columned)
    DataFrame when the file doesn't exist yet — so the UI works on a fresh deploy
    where the runtime log isn't checked into git.
    """
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame(columns=PRACTICE_LOG_COLUMNS)
