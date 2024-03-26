import streamlit as st
import random
import datetime
import pandas as pd


# Function to update and display the progress bar for practice focus time
def update_focus_progress(total_practice_time=60, change_focus_time=30):
    """
    Update and display the progress bar based on the elapsed time.

    Parameters:
    - total_practice_time: Total time allocated for practice (in minutes).
    - change_focus_time: Time to switch from review to learning new cells (in minutes).
    """
    if "start_time" not in st.session_state:
        st.session_state["start_time"] = datetime.datetime.now()

    elapsed_time = (
        datetime.datetime.now() - st.session_state["start_time"]
    ).total_seconds() / 60  # Convert to minutes
    focus = "Review" if elapsed_time < change_focus_time else "Learn New"

    # Calculate progress
    if focus == "Review":
        progress = elapsed_time / change_focus_time
    else:
        progress = (elapsed_time - change_focus_time) / (
            total_practice_time - change_focus_time
        )

    progress = max(0, min(1, progress))  # Ensure progress is between 0 and 1

    # Display the progress bar
    progress_bar = st.sidebar.progress(0)
    progress_bar.progress(progress)

    st.sidebar.write(f"Part : {focus}")
    st.sidebar.write(f"Progress: {progress*100:.2f}%")

    return focus, progress


import json
import datetime
import random


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
            "C#",
            "F",
            "Bb",
            "Eb",
            "Ab",
            "Db",
            "Gb",
            "Cb",
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


# Function to append practice session details to a CSV file
def save_practice_session(details, file_path="practice_sessions.csv"):
    """
    Appends practice session details to a CSV file.

    Parameters:
    - details: A dictionary containing the session details (date, chord type, pivot note, tempo, grade).
    - file_path: Path to the CSV file where session details are saved.
    """
    # Convert the details dictionary to a DataFrame
    df = pd.DataFrame([details])

    # Try to append to the file if it exists, otherwise create a new file
    try:
        df.to_csv(file_path, mode="a", index=False, header=False)
    except FileNotFoundError:
        df.to_csv(file_path, mode="w", header=True, index=False)
