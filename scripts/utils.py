import streamlit as st
import json
import datetime
import random


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
    return "-".join(cell)


@st.cache_data
def cell_from_string(string):
    return "-".join(string.split(" "))


def get_or_update_practice_details():
    """
    Fetches or updates the practice details (key and position) from/to a JSON file.

    Returns:
    - A tuple containing the key and position for today's practice.
    """
    filename = "practice_details.json"
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

        with open(filename, "w") as file:
            json.dump(practice_details, file)

    return practice_details["key"], practice_details["position"]
