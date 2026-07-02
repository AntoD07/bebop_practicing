import os
import pandas as pd
import ast
import streamlit as st
import json
import datetime
import random

from scripts.paths import PRACTICE_DETAILS, MELODIC_LINES_LOG

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
        keys = [
            "C",
            "G",
            "D",
            "A",
            "E",
            "B",
            "F#",
            "F",
            "Bb",
            "Eb",
            "Ab",
            "Db",
        ]
        positions = list(range(1, 6))
        practice_details = {
            "date": today,
            "key": random.choice(keys),
            "position": random.choice(positions),
        }

        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        with open(filename, "w") as file:
            json.dump(practice_details, file)

    return practice_details["key"], practice_details["position"]


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
