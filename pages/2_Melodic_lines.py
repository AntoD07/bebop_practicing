import streamlit as st
import streamlit.components.v1 as components
import ast
import pandas as pd
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
    sample_line_from_path_with_connecting_note,
    line_structure_mapping,
)
from scripts.modes.mode_transposition import change_note_representation

from scripts.database import fetch_data_base


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
    "Whether to change to translate the intervals for other modes", value=False
)


st.session_state.dom_to_minor = c2.checkbox(
    "Whether to translate Dominant and Locrian cells to Minor/Major-I", value=False
)
st.session_state.length = st.sidebar.number_input(
    "Select the line length (depends on the line type) ",
    min_value=2,
    max_value=6,
    value=4,
)
with c1:
    st.session_state.line_type = st.selectbox(
        "Type of line to practice",
        options=[
            "Maj7",
            # "7sus4 Infinity Loop",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "Short Maj 2-5-1",
            "Long Maj 2-5-1",
            "Short Minor 2-5-1",
            "Long Minor 2-5-1",
            "Double resolution",
            "Dorian and Dominant 2-cells alternated",
            "Dorian x Dominant",
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
        # tmp_df, _, _ = create_cell_frames(
        #     sample_path[-1],
        #     False,
        #     st.session_state.sus_to_loc_dorian,
        #     st.session_state.include_bonus,
        #     field="Start Note",
        #     loc_to_dominant=st.session_state.loc_to_dom,
        #     dom_to_minor=st.session_state.dom_to_minor,
        # )
        # tmp_df = change_note_representation(
        #     tmp_df,
        #     sample_path[-1],
        #     st.session_state.sus_to_loc_dorian,
        #     st.session_state.loc_to_dom,
        #     st.session_state.dom_to_minor,
        # )
        st.session_state.starting_note = st.selectbox(
            "Select the first note (optional) ",
            options=[
                "None",
                "1",
                "9",
                "3",
                "11",
                "#11",
                "5",
                "6",
                "7",
                "b7",
                "b6",
                "b9",
                "#9",
            ],
            # st.session_state.get("starting_note", None),
        )
        st.session_state.ending_note = st.selectbox(
            "Select the end note (optional) ",
            options=[
                "None",
                "1",
                "9",
                "3",
                "11",
                "#11",
                "5",
                "6",
                "7",
                "b7",
                "b6",
                "b9",
                "#9",
            ],
            # st.session_state.get("ending_note", None),
        )

    st.session_state.movement = st.sidebar.selectbox(
        "Select the line movement (optional) ",
        [None, "A and N", "D and N", "A", "D"],
        index=[None, "A and N", "D and N", "A", "D"].index(
            st.session_state.get("movement", None)
        ),
    )
    used_notes = ["1", "9", "3", "11", "#11", "5", "6", "7", "b7", "b6", "b9", "#9"]
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
    (
        st.session_state.melodic_line,
        st.session_state.note_representations,
        sample_path,
    ) = sample_line_from_path_with_connecting_note(
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
    c1, c2, c3 = st.columns((0.2, 0.5, 0.3))
    for mode, name, notes in zip(
        sample_path,
        st.session_state.melodic_line,
        st.session_state.note_representations,
    ):
        c1.write(f"##### :blue[{mode}]")
        c2.write(f"##### {name}")
        c3.write(join_notes(notes))
    st.session_state.tmp = True

st.session_state.tempo = st.number_input(
    "Metronome tempo (bpm) : ",
    min_value=30,
    max_value=300,
    value=60,
    help="Setup the metronome to 2 beats, stressing first beat, without time",
)
metronome_html = f"""
<iframe src="https://guitarapp.com/metronome.html?embed=true&tempo={st.session_state.tempo}&timeSignature=2&pattern=0"
        title="Online Metronome"
        style="width: 360px; height:520px; border:none; border-radius:4px;">
</iframe>
"""
components.html(metronome_html, height=540, width=380)

st.session_state.grade = st.number_input(
    "How good was it?", min_value=1, max_value=5, value=5
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
            "Movement": st.session_state.movement,
        }
        # Save the session details to CSV
        save_practice_session(session_details, "melodic_lines.csv")

        st.success("Line saved successfully!")


st.write("---")
st.write("## Saved melodic lines")

lines = pd.read_csv("melodic_lines.csv")

filtered_lines = lines.loc[lines["Line type"] == st.session_state.line_type]
filtered_lines["Start Note"] = filtered_lines["Note sequence"].str[4]
filtered_lines["Last Note"] = filtered_lines["Note sequence"].str[-5]


filtered_lines["sort_key"] = filtered_lines["Movement"].apply(
    lambda x: 0 if x == st.session_state.movement else 1
)
filtered_lines = filtered_lines.sort_values(
    by=["sort_key", "Grade"], ascending=[True, False]
).drop("sort_key", axis=1)
st.dataframe(
    filtered_lines.drop(columns=["Note sequence"]),
    use_container_width=True,
    selection_mode="single-row",
    on_select="rerun",
    key="selected_line_cb",
)

if len(st.session_state.selected_line_cb.selection["rows"]) > 0:
    (
        c1,
        c2,
    ) = st.columns((0.5, 0.5))
    line = filtered_lines.iloc[st.session_state.selected_line_cb.selection["rows"][0]]
    for name, notes in zip(
        ast.literal_eval(line["Line"]),
        ast.literal_eval(line["Note sequence"]),
    ):

        c1.write(f"##### {name}")
        c2.write(join_notes(notes))
