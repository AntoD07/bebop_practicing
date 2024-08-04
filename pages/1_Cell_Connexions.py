import streamlit as st
import time

from scripts.utils import (
    get_or_update_practice_details,
    join_notes,
)

from scripts.melodic_lines.combinations import find_combinations_on_pivot_new


from scripts.modes.mode_transposition import (
    translate_sus4_to_other_mode,
    translate_loc_to_dominant,
    translate_dom_to_minor,
    translate_dom_to_major,
)

from scripts.load_cells import create_cell_frames

st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Bebop Cell combinations")

st.session_state.key, st.session_state.position = get_or_update_practice_details()
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.key}]")
st.sidebar.subheader(
    f"Today's Position (for guitar): :blue[{st.session_state.position}]"
)
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)
# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))

with c1:
    st.session_state.chord1 = st.selectbox(
        "Select first chord to practice",
        [
            "Maj7",
            #   "7sus4",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ],
        index=[
            "Maj7",
            # "7sus4",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ].index(st.session_state.get("chord1", "Dorian")),
    )
    # st.session_state.permute1 = st.checkbox(
    #     "Whether to change to translate the intervals for other modes", value=False
    # )
    # st.session_state.mode_filter1 = st.checkbox(
    #     "Whether to filter cells with high mode score", value=False
    # )
    # if st.session_state.chord1 == "Locrian":
    #     st.session_state.loc_2_dom1 = st.checkbox(
    #         "Translate Locrian to Dominant", value=False
    #     )
    # else:
    #     st.session_state.loc_2_dom1 = False
    # if st.session_state.chord1 in [
    #     "MinorResolutions",
    #     "MajorResolutions",
    #     "Locrian",
    # ]:
    #     st.session_state.dom_to_minor1 = st.checkbox(
    #         "Translate Dominant to Minor/Major-I", value=False
    #     )
    # else:
    st.session_state.dom_to_minor1 = False

    df_cells_1, mapped_names_1, mapping_1 = create_cell_frames(
        st.session_state.chord1,
        False,
        False,
        st.session_state.include_bonus,
        "End Note",
        False,
        False,
    )

with c2:
    st.session_state.chord2 = st.selectbox(
        "Select second chord to connect to",
        [
            "Maj7",
            "7sus4",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ],
        index=[
            "Maj7",
            "7sus4",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ].index(st.session_state.get("chord2", st.session_state.get("chord1"))),
    )
    # st.session_state.mode_filter_2 = st.checkbox(
    #     "Whether to filter cells with high mode score ", value=False
    # )
    # Locrian to dominant
    # if st.session_state.chord2 == "Locrian":
    #     st.session_state.loc_2_dom_2 = st.checkbox(
    #         "Translate Locrian to Dominant ", value=False
    #     )
    # else:
    #     st.session_state.loc_2_dom_2 = False
    # # Minor Resolution Cell transposition
    # if st.session_state.chord2 in [
    #     "MinorResolutions",
    #     "MajorResolutions",
    #     "Myxolidian",
    # ]:
    #     st.session_state.dom_to_minor2 = st.checkbox(
    #         "Translate Dominant to Minor/Major-I ", value=False
    #     )
    # else:
    st.session_state.dom_to_minor2 = False

    df_cells_2, mapped_names_2, mapping_2 = create_cell_frames(
        st.session_state.chord2,
        False,
        False,
        st.session_state.include_bonus,
        "Start Note",
        False,
        False,
    )


st.subheader("", divider="red")


st.session_state.tone_modified = st.selectbox(
    "Select a pivot note (starting second cell)",
    set(
        list(
            set(mapped_names_2.astype(str)).intersection(
                set(mapped_names_1.astype(str))
            )
        )
        + list(
            set(mapped_names_1.astype(str)).intersection(
                set(mapped_names_2.astype(str))
            )
        )
    ),
)

st.session_state.movement = st.sidebar.selectbox(
    "Select the line movement (optional) ",
    [None, "A", "D"],
    index=[None, "A", "D"].index(st.session_state.get("movement", None)),
)
st.session_state.tone = mapping_2[st.session_state.tone_modified]
if st.session_state.movement is None:
    movements = ["N", "A", "D"]
else:
    movements = ["N", st.session_state.movement]

starting_cells = df_cells_2.loc[
    (df_cells_2["Start Note"] == st.session_state.tone)
    & df_cells_2["Movement"].astype(str).isin(movements)
]
ending_cells = df_cells_1.loc[
    (df_cells_1["End Note"] == mapping_1[st.session_state.tone_modified])
    & df_cells_1["Movement"].astype(str).isin(movements)
]

combinations, names = find_combinations_on_pivot_new(
    st.session_state.tone, starting_cells, ending_cells
)

st.subheader(
    "Practicing cells around chord tone :blue[{}] - All :red[{}] combinaisons".format(
        st.session_state.tone_modified, len(combinations)
    ),
)

# if st.session_state.permute1 and (st.session_state.chord1 in ["Dorian", "Locrian"]):
#     ending_cells = translate_sus4_to_other_mode(ending_cells, st.session_state.chord1)
#     if st.session_state.chord1 == "Locrian" and st.session_state.loc_2_dom1:
#         ending_cells = translate_loc_to_dominant(ending_cells)
# if (
#     st.session_state.chord1 in ["MinorResolutions", "Locrian"]
# ) and st.session_state.dom_to_minor1:
#     ending_cells = translate_dom_to_minor(ending_cells)
# elif (
#     st.session_state.chord1 in ["Myxolidian", "MajorResolutions"]
# ) and st.session_state.dom_to_minor1:
#     ending_cells = translate_dom_to_major(ending_cells)

# if st.session_state.permute_2 and (st.session_state.chord2 in ["Dorian", "Locrian"]):
#     starting_cells = translate_sus4_to_other_mode(
#         starting_cells, st.session_state.chord2
#     )
#     if st.session_state.chord2 == "Locrian" and st.session_state.loc_2_dom_2:
#         starting_cells = translate_loc_to_dominant(starting_cells)
# if (
#     st.session_state.chord2 in ["MinorResolutions", "Locrian"]
# ) and st.session_state.dom_to_minor2:
#     starting_cells = translate_dom_to_minor(starting_cells)
# elif (
#     st.session_state.chord2 in ["Myxolidian", "MajorResolutions"]
# ) and st.session_state.dom_to_minor2:
#     starting_cells = translate_dom_to_major(starting_cells)

with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    for i, cell in ending_cells.reset_index().iterrows():
        n = cell["Cell Name"]
        notes = cell["Notes"]
        mvt = cell["Movement"]

        c1.write(f"##### {n}")
        c1.write(join_notes(notes) + "  " + mvt)

    for i, cell in starting_cells.reset_index().iterrows():
        n = cell["Cell Name"]
        notes = cell["Notes"]
        mvt = cell["Movement"]

        c2.write(f"##### {n}")
        c2.write(join_notes(notes) + "  " + mvt)

st.session_state.tempo = st.number_input(
    "Metronome [Bpms] [link](https://www.imusic-school.com/app/v3sap/src/index.html#/access/metronome)",
    min_value=30,
    max_value=300,
    value=st.session_state.get("tempo", 80),
    help="Setup the metronome to 2 beats, stressing first beat, without time",
)

combinations, names = find_combinations_on_pivot_new(
    st.session_state.tone, starting_cells, ending_cells
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
            c2.markdown(f"##### {current_combination[1]}")
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
