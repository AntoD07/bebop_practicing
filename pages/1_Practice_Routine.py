import streamlit as st
import datetime
import time

from scripts.cells.major7 import (
    maj_essential_starting_cells,
    maj_essential_ending_cells,
)
from scripts.cells.sus4 import (
    dominant_essential_starting_cells,
    dominant_essential_ending_cells,
)
from scripts.routine import (
    update_focus_progress,
    randomize_key,
    randomize_position,
    save_practice_session,
)
from scripts.practice_cells import (
    load_cells,
    get_all_cells,
    find_combinations_on_pivot,
    join_notes,
)


import random

st.set_page_config(layout="wide")
st.markdown(
    """
<script>
window.scrollTo(0,document.body.scrollHeight);
</script>
""",
    unsafe_allow_html=True,
)
# Example of setting up the practice routine
st.title("Bebop Practice Routine")

c1, c2 = st.columns((0.5, 0.5))
# Display the key for today's practice
key = randomize_key()
c1.subheader(f"Today's Key: :blue[{key}]", divider="red")
# Display today's position of practice
position = randomize_position([2])
c2.subheader(f"Today's Position: :blue[{position}]", divider="red")

chord = st.sidebar.selectbox("What you want to practice today : ", ["Maj7", "7sus4"])
starting_cells, ending_cells = load_cells(chord)
all_cells = get_all_cells(starting_cells, ending_cells)

st.session_state.tone = c1.selectbox(
    "Select a note ",
    list(starting_cells.keys()),
    index=list(starting_cells.keys()).index(
        st.session_state.get(
            "starting_note", random.choice(list(starting_cells.keys()))
        )
    ),
)
combinations = find_combinations_on_pivot(
    st.session_state.tone, starting_cells, ending_cells
)
st.subheader(
    "Session 1 - Practicing cells around chord tone :blue[{}] - All :red[{}] combinaisons".format(
        st.session_state.tone, len(combinations)
    ),
    divider="red",
)
with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    for n, notes in ending_cells[st.session_state.tone].items():
        c1.write(f"##### {n}")
        c1.write(join_notes(notes))
    for n, notes in starting_cells[st.session_state.tone].items():
        c2.write(f"##### {n}")
        c2.write(join_notes(notes))


st.session_state.tempo = st.number_input(
    "Metronome [Bpms] [link](https://www.imusic-school.com/app/v3sap/src/index.html#/access/metronome)",
    min_value=30,
    max_value=300,
    value=st.session_state.get("tempo", 80),
    help="Setup the metronome to 2 beats, stressing first beat, without time",
)


# Total duration for practicing all combinations
total_duration_minutes = st.sidebar.number_input(
    "Part 1 Duration : ", min_value=1, max_value=30, value=10
)

# Calculate display time per combination
if combinations:
    time_per_combination = total_duration_minutes / len(combinations)
    st.write(
        f"Each combination will be displayed for :green[{time_per_combination:.2f}] minutes. Press 'Next Combination' to rotate through the combinations."
    )
else:
    st.write("No combinations available for the selected pivot note.")

# Initialize or update the current combination index
if "current_combination_index" not in st.session_state:
    st.session_state.current_combination_index = 0


# Function to advance to the next combination
def next_combination():
    if "current_combination_index" in st.session_state:
        st.session_state.current_combination_index = (
            st.session_state.current_combination_index + 1
        )


# Display the current combination
if st.button("Start exercise 1", type="primary"):
    for i, _ in enumerate(combinations):
        # Inject JavaScript for auto-scrolling
        js = """
        <script>
        window.scrollTo(0, document.body.scrollHeight);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        c1, c2, c3 = st.columns((0.45, 0.45, 0.1))
        try:
            current_combination = combinations[
                st.session_state.current_combination_index
            ]
            c1.markdown(f"##### {current_combination[0]}")
            c2.markdown(f"##### {current_combination[1]}")
            ph = c3.empty()
            N = int(time_per_combination * 60)
            for secs in range(N, 0, -1):
                mm, ss = secs // 60, secs % 60
                ph.metric(
                    f"{i+1}/{len(combinations)}",
                    f"{mm:02d}:{ss:02d}",
                    label_visibility="collapsed",
                )
                time.sleep(1)
            next_combination()

        except IndexError:
            st.success("Completed all combinaisons")
            st.session_state.current_combination_index = 0


# Button to manually rotate to the next combination
if st.button("Next Combination"):
    next_combination()

if st.sidebar.button("Randomize again "):
    st.session_state.starting_note = random.choice(list(starting_cells.keys()))
    st.session_state.ending_note = random.choice(list(ending_cells.keys()))


with st.expander("Saving Part 1 results"):
    grade = st.number_input("How easy was it ?", min_value=1, max_value=5, value=5)
    # Prepare the session details
    if st.button("Save to database"):
        session_details = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "ChordType": chord,
            "PivotNote": st.session_state.tone,
            "Tempo": st.session_state.tempo,
            "Grade": grade,
        }
        # Save the session details to CSV
        save_practice_session(session_details)

        st.success("Practice session saved successfully!")
