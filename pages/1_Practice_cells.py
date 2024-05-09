import streamlit as st
import datetime
import time

from scripts.utils import (
    get_or_update_practice_details,
    join_notes,
)
from scripts.practice_cells import (
    get_all_cells,
    find_combinations_on_pivot,
    join_notes,
)

from scripts.database import fetch_and_update_data_base


import random

st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Bebop Cell combinations")

st.session_state.key, st.session_state.position = get_or_update_practice_details()
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)

# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))
c1.subheader(f"Today's Key: :blue[{st.session_state.key}]")
c2.subheader(f"Today's Position (for guitar): :blue[{st.session_state.position}]")

previous_chord = st.session_state.get("chord")
st.session_state.chord = c1.selectbox(
    "Select chord to practice",
    ["Maj7", "7sus4", "Dorian", "Myxolidian", "Locrian", "MajorResolutions"],
    index=[
        "Maj7",
        "7sus4",
        "Dorian",
        "Myxolidian",
        "Locrian",
        "MajorResolutions",
    ].index(st.session_state.get("chord", "7sus4")),
)
all_cells, _, _ = get_all_cells(st.session_state.chord, st.session_state.include_bonus)
names = list(all_cells.keys())

df_cells = fetch_and_update_data_base(
    "{}_sampling.csv".format(st.session_state.chord),
    all_cells,
    majchord=st.session_state.chord == "Maj7",
)
st.session_state.permute = c2.checkbox(
    "Whether to change to translate the intervals for other modes", value=False
)
st.session_state.mode_filter = c2.checkbox(
    "Whether to filter cells with high mode score", value=False
)

if st.session_state.mode_filter and (
    st.session_state.chord in ["Dorian", "Locrian", "Myxolidian"]
):
    df_cells = df_cells[df_cells["Modes"].apply(lambda x: st.session_state.chord in x)]
if st.session_state.permute and (st.session_state.chord in ["Dorian", "Locrian"]):
    df_cells = translate_sus4_to_other_mode(df_cells, st.session_state.chord)
if st.session_state.chord in ["Locrian"]:
    st.session_state.loc_2_dom = c2.checkbox(
        "Translate Locrian to Dominant", value=True
    )
    if st.session_state.loc_2_dom:
        df_cells = translate_loc_to_dominant(df_cells)

if st.session_state.chord != previous_chord:
    st.session_state.name = random.choice(list(df_cells.index))
    st.session_state.tone = random.choice(list(df_cells["Start Note"].unique()))


st.session_state.tone = c1.selectbox(
    "Select a note ",
    list(df_cells["Start Note"].unique()),
    index=list(df_cells["Start Note"].unique()).index(
        st.session_state.get(
            "tone", random.choice(list(df_cells["Start Note"].unique()))
        )
    ),
)
starting_cells = df_cells.loc[df_cells["Start Note"] == st.session_state.tone]
ending_cells = df_cells.loc[df_cells["End Note"] == st.session_state.tone]

combinations, names = find_combinations_on_pivot(st.session_state.tone, df_cells)
st.subheader("", divider="red")
st.subheader(
    "Practicing cells around chord tone :blue[{}] - All :red[{}] combinaisons".format(
        st.session_state.tone, len(combinations)
    ),
)
with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    for i, cell in ending_cells.reset_index().iterrows():
        n = cell["Cell Name"]
        notes = cell["Notes"]
        c1.write(f"##### {n}")
        c1.write(join_notes(notes))
        if st.session_state.chord == "7sus4":
            c1.caption(str(df_cells.loc[n, "Mode scores"]))
    for i, cell in starting_cells.reset_index().iterrows():
        n = cell["Cell Name"]
        notes = cell["Notes"]
        c2.write(f"##### {n}")
        c2.write(join_notes(notes))
        if st.session_state.chord == "7sus4":
            c2.caption(str(df_cells.loc[n, "Mode scores"]))

with st.expander("Show Combinations"):
    for i, combi in enumerate(combinations):
        # Inject JavaScript for auto-scrolling
        c1, c2 = st.columns((0.5, 0.5))
        current_name = names[i]
        c1.markdown(f"##### {combi[0]}")
        if st.session_state.chord == "7sus4":
            c1.caption(str(df_cells.loc[current_name[0], "Mode scores"]))
        c2.markdown(f"##### {combi[1]}")
        if st.session_state.chord == "7sus4":
            c2.caption(str(df_cells.loc[current_name[1], "Mode scores"]))


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
    st.session_state.starting_note = random.choice(df_cells["Start Note"].unique())
    st.session_state.ending_note = random.choice(df_cells["End Note"].unique())
