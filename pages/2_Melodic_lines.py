import streamlit as st
import datetime
import time

from scripts.routine import (
    get_or_update_practice_details,
    save_practice_session,
)
from scripts.practice_cells import (
    get_all_cells,
    find_combinations_on_pivot,
    join_notes,
)
from scripts.cells.melodic_lines import (
    sample_melodic_line_with_connecting_note,
    sample_melodic_line_backward_for_251,
)
from scripts.cells.modes import translate_sus4_to_other_mode

from scripts.database import fetch_and_update_data_base


import random

st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Melodic Lines")

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
        "Whether to change to translate Locrian to Dominant", value=False
    )
    if st.session_state.loc_2_dom:
        st.error("Not Implemented yet!")


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
st.session_state.line_length = st.number_input(
    "Select line length generated randomly", min_value=2, max_value=50, value=4
)
st.session_state.kept_notes = st.multiselect(
    "Select pivot notes for constructing the line",
    list(df_cells["Start Note"].unique()),
    default=list(list(df_cells["Start Note"].unique())),
)
if st.button("Generate melodic line", type="primary"):
    st.session_state.tmp = True
    if st.session_state.chord in ["Maj7", "7sus4", "Dorian", "Myxolidian", "Locrian"]:
        st.session_state.melodic_line, df_cells = (
            sample_melodic_line_with_connecting_note(
                df_cells,
                st.session_state.chord,
                st.session_state.line_length,
                st.session_state.tone,
                st.session_state.kept_notes,
            )
        )
    else:
        st.session_state.melodic_line, df_cells = sample_melodic_line_backward_for_251(
            df_cells,
            st.session_state.chord,
            st.session_state.line_length,
            st.session_state.tone,
        )
    for n in st.session_state.melodic_line:
        c1, c2 = st.columns((0.5, 0.5))
        c1.write(f"##### {n}")
        if n in all_cells.keys():
            # c1.caption(df_cells.set_index("Cell Name").loc[n, "Mode scores"])
            c2.write(
                join_notes(df_cells.loc[df_cells["Cell Name"] == n, "Notes"].iloc[0])
            )
        else:
            dom_cells, _, _ = get_all_cells("7sus4", True)
            c2.write(join_notes(dom_cells[n]))

    df_cells.to_csv("{}_sampling.csv".format(st.session_state.chord), index=False)

    st.session_state.grade = st.number_input(
        "How good is it?", min_value=1, max_value=5, value=5
    )
if st.session_state.get("tmp"):
    # Prepare the session details
    st.session_state.text = st.text_input("Enter message")
    if st.button("Save line"):
        session_details = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "ChordType": st.session_state.chord,
            "PivotNote": st.session_state.tone,
            "Line": st.session_state.melodic_line,
            "Grade": st.session_state.grade,
            "Comment": st.session_state.text,
        }
        # Save the session details to CSV
        save_practice_session(session_details, "melodic_lines.csv")

        st.success("Line saved successfully!")
