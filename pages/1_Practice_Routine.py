import streamlit as st
import datetime
import time

from scripts.routine import (
    get_or_update_practice_details,
    save_practice_session,
)
from scripts.practice_cells import (
    get_all_cells,
    create_starting_ending_cells,
    find_combinations_on_pivot,
    join_notes,
)
from scripts.cells.melodic_lines import (
    sample_melodic_line_with_connecting_note,
)
from scripts.database import fetch_and_update_data_base


import random

st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Bebop Practice Routine")

key, position = get_or_update_practice_details()

# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))
c1.subheader(f"Today's Key: :blue[{key}]")
c2.subheader(f"Today's Position (for guitar): :blue[{position}]")

previous_chord = st.session_state.get("chord")
st.session_state.chord = c1.selectbox(
    "Select chord to practice",
    ["Maj7", "7sus4", "Dorian", "Myxolidian", "Locrian", "MajorResolutions"],
    index=1,
)
all_cells, starting_cells, ending_cells = get_all_cells(st.session_state.chord, True)
names = list(all_cells.keys())

if st.session_state.chord != previous_chord:
    st.write(starting_cells.keys())
    st.session_state.name = random.choice(list(all_cells.keys()))
    st.session_state.tone = random.choice(list(starting_cells.keys()))

df_cells = fetch_and_update_data_base(
    "{}_sampling.csv".format(st.session_state.chord),
    all_cells,
    majchord=st.session_state.chord == "Maj7",
)

st.session_state.tone = c1.selectbox(
    "Select a note ",
    list(starting_cells.keys()),
    index=list(starting_cells.keys()).index(
        st.session_state.get("tone", random.choice(list(starting_cells.keys())))
    ),
)
combinations, names = find_combinations_on_pivot(
    st.session_state.tone, starting_cells, ending_cells
)
st.subheader("", divider="red")
st.subheader(
    "Session 1 - Practicing cells around chord tone :blue[{}] - All :red[{}] combinaisons".format(
        st.session_state.tone, len(combinations)
    ),
)
with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    for n, notes in ending_cells[st.session_state.tone].items():
        c1.write(f"##### {n}")
        c1.write(join_notes(notes))
        if st.session_state.chord == "7sus4":
            c1.caption(str(df_cells.loc[n, "Mode scores"]))
    for n, notes in starting_cells[st.session_state.tone].items():
        c2.write(f"##### {n}")
        c2.write(join_notes(notes))
        if st.session_state.chord == "7sus4":
            c2.caption(str(df_cells.loc[n, "Mode scores"]))


st.session_state.tempo = st.number_input(
    "Metronome [Bpms] [link](https://www.imusic-school.com/app/v3sap/src/index.html#/access/metronome)",
    min_value=30,
    max_value=300,
    value=st.session_state.get("tempo", 80),
    help="Setup the metronome to 2 beats, stressing first beat, without time",
)


# Total duration for practicing all combinations
total_duration_minutes = st.sidebar.number_input(
    "Part 1 Duration : ", min_value=1, max_value=30, value=15
)
# Calculate display time per combination
if combinations:
    time_per_combination = total_duration_minutes / len(combinations)
    st.write(
        f"Each combination will be displayed for :green[{int(time_per_combination*60)}] seconds. Press 'Next Combination' to rotate through the combinations."
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
    st.session_state.current_combination_index = 0
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
            current_name = names[st.session_state.current_combination_index]

            c1.markdown(f"##### {current_combination[0]}")
            if st.session_state.chord == "7sus4":
                c1.caption(str(df_cells.loc[current_name[0], "Mode scores"]))
            c2.markdown(f"##### {current_combination[1]}")
            if st.session_state.chord == "7sus4":
                c2.caption(str(df_cells.loc[current_name[1], "Mode scores"]))
            ph = c3.empty()
            N = int(time_per_combination * 60)
            for secs in range(N, -1, -1):
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
            # st.session_state.current_combination_index = 0

if st.sidebar.button("Randomize again "):
    st.session_state.starting_note = random.choice(list(starting_cells.keys()))
    st.session_state.ending_note = random.choice(list(ending_cells.keys()))


with st.expander("Saving Part 1 results"):
    grade = st.number_input("How easy was it ?", min_value=1, max_value=5, value=5)
    # Prepare the session details
    if st.button("Save to database"):
        session_details = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "ChordType": st.session_state.chord,
            "PivotNote": st.session_state.tone,
            "Tempo": st.session_state.tempo,
            "Grade": grade,
        }
        # Save the session details to CSV
        save_practice_session(session_details)

        st.success("Practice session saved successfully!")

st.subheader("", divider="red")
st.subheader(
    "Session 2 - Practicing longer lines involving chord tone :blue[{}]".format(
        st.session_state.tone
    ),
)
st.session_state.line_length = st.number_input(
    "Select line length generated randomly", min_value=2, max_value=50, value=4
)
st.session_state.kept_notes = st.multiselect(
    "Select pivot notes for constructing the line",
    list(starting_cells.keys()),
    default=list(starting_cells.keys()),
)
if st.button("Generate melodic line", type="primary"):
    st.session_state.tmp = True
    st.session_state.melodic_line, df_cells = sample_melodic_line_with_connecting_note(
        df_cells,
        st.session_state.chord,
        st.session_state.line_length,
        st.session_state.tone,
        st.session_state.kept_notes,
    )
    for n in st.session_state.melodic_line:
        c1, c2 = st.columns((0.5, 0.5))
        c1.write(f"##### {n}")
        c1.caption(df_cells.set_index("Cell Name").loc[n, "Mode scores"])
        c2.write(join_notes(all_cells[n]))
    df_cells.to_csv("{}_sampling.csv".format(st.session_state.chord), index=False)

    grade = st.number_input("How good is it?", min_value=1, max_value=5, value=5)
if st.session_state.get("tmp"):
    # Prepare the session details
    if st.button("Save line"):
        session_details = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "ChordType": st.session_state.chord,
            "PivotNote": st.session_state.tone,
            "Line": st.session_state.melodic_line,
            "Grade": grade,
        }
        # Save the session details to CSV
        save_practice_session(session_details, "melodic_lines.csv")

        st.success("Line saved successfully!")
