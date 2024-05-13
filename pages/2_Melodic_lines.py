import streamlit as st
import datetime
import time

from scripts.utils import (
    get_or_update_practice_details,
    join_notes,
    save_practice_session,
)
from scripts.load_cells import get_all_cells, create_cell_frames
from scripts.melodic_lines.melodic_lines import (
    line_structure_dic,
    sample_melodic_line_with_connecting_note,
    sample_melodic_line_backward_for_251,
    sample_line_from_path_with_connecting_note,
)
from scripts.modes.mode_transposition import change_note_representation

from scripts.database import fetch_and_update_data_base


import random

st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Melodic Lines")

st.session_state.key, st.session_state.position = get_or_update_practice_details()

# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.key}]")
st.sidebar.subheader(
    f"Today's Position (for guitar): :blue[{st.session_state.position}]"
)
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)

st.session_state.sus_to_loc_dorian = c2.checkbox(
    "Whether to change to translate the intervals for other modes", value=True
)
st.session_state.mode_filter = c2.checkbox(
    "Whether to filter cells with high mode score", value=False
)
st.session_state.loc_to_dom = c2.checkbox(
    "Whether to translate Locrian cells to Dominant", value=True
)

st.session_state.dom_to_minor = c2.checkbox(
    "Whether to translate Dominant and Locrian cells to Minor-I", value=True
)
with c1:
    st.session_state.line_type = st.selectbox(
        "Type of line to practice",
        options=[
            "Maj7",
            "7sus4 Infinity Loop",
            "Short Maj 2-5-1",
            "Long Maj 2-5-1",
            "Long Maj 2-5-1 with Maj7 ending",
            "Short Minor 2-5-1",
            "Long Minor 2-5-1",
            "Long Minor 2-5-1 with Dorian ending",
            "Double resolution",
            "Dorian and Dominant 2-cells alternated",
        ],
        index=[
            "Maj7",
            "7sus4 Infinity Loop",
            "Short Maj 2-5-1",
            "Long Maj 2-5-1",
            "Long Maj 2-5-1 with Maj7 ending",
            "Short Minor 2-5-1",
            "Long Minor 2-5-1",
            "Long Minor 2-5-1 with Dorian ending",
            "Double resolution",
            "Dorian and Dominant 2-cells alternated",
        ].index(st.session_state.get("line_type", "7sus4 Infinity Loop")),
    )

    sample_path = line_structure_dic[st.session_state.line_type]
    if st.session_state.line_type not in [
        "Long Minor 2-5-1 with Dorian ending",
        "Long Maj 2-5-1 with Maj7 ending",
        "Dorian and Dominant 2-cells alternated",
    ]:
        tmp_df, _, _ = create_cell_frames(
            sample_path[-1],
            st.session_state.mode_filter,
            st.session_state.sus_to_loc_dorian,
            st.session_state.include_bonus,
            field="Start Note",
            loc_to_dominant=st.session_state.loc_to_dom,
            dom_to_minor=st.session_state.dom_to_minor,
        )
        tmp_df = change_note_representation(
            tmp_df,
            sample_path[-1],
            st.session_state.sus_to_loc_dorian,
            st.session_state.loc_to_dom,
            st.session_state.dom_to_minor,
        )
        st.session_state.ending_note = st.selectbox(
            "Select the last connecting note (optional) ",
            list(tmp_df["Start Note"].unique()),
            index=list(tmp_df["Start Note"].unique()).index(
                random.choice(list(tmp_df["Start Note"].unique()))
            ),
        )
    else:
        st.session_state.ending_note = None
    st.write("Melodic Lines sampled according to the following cells : ", sample_path)
    # st.write(st.session_state.ending_note)


if st.button("Generate melodic line", type="primary"):
    st.session_state.melodic_line, st.session_state.note_representations = (
        sample_line_from_path_with_connecting_note(
            sample_path,
            st.session_state.include_bonus,
            st.session_state.mode_filter,
            st.session_state.loc_to_dom,
            st.session_state.dom_to_minor,
            st.session_state.sus_to_loc_dorian,
            st.session_state.ending_note,
        )
    )
    c1, c2, c3 = st.columns((0.2, 0.5, 0.3))
    for mode, name, notes in zip(
        sample_path,
        st.session_state.melodic_line,
        st.session_state.note_representations,
    ):
        c1.write(f"##### :blue[{mode}]")
        c2.write(f"##### {name}")
        c3.write(join_notes(notes))

st.session_state.grade = st.number_input(
    "How good is it?", min_value=1, max_value=5, value=5
)
if st.session_state.get("tmp"):
    # Prepare the session details
    st.session_state.text = st.text_input("Enter message")
    if st.button("Save line"):
        session_details = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "Line type": st.session_state.line_type,
            "Line": st.session_state.melodic_line,
            "Note sequence": st.session_state.note_representations,
            "Grade": st.session_state.grade,
            "Comment": st.session_state.text,
        }
        # Save the session details to CSV
        save_practice_session(session_details, "melodic_lines.csv")

        st.success("Line saved successfully!")
