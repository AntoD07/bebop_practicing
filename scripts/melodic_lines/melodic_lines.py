"""Melodic-line sampling (legacy page 2 entry points over ``scripts.domain``).

The structures, the sampler and the combo helpers live in
``scripts.domain.sampling`` / ``scripts.domain.notes``; this module keeps the
names and return shapes the Streamlit page imports.
"""

from scripts.domain.notes import (  # noqa: F401 — re-exported
    CHORD_TONES,
    combo_chord_tone_connecting_notes,
    combo_chord_tones_info,
    combo_mapping_info,
    harmony_caption,
)
from scripts.domain.sampling import (  # noqa: F401 — re-exported
    MYXO_TO_DORIAN_LINE_TYPE,
    line_structure_dic,
    line_structure_mapping,
    sample_line,
)


def sample_line_from_path_with_connecting_note(
    line_type,
    include_bonus,
    mode_filter,
    loc_to_dom,
    dom_to_minor,
    sus_to_loc_dorian,
    length,
    movement=None,
    starting_note=None,
    ending_note=None,
    connecting_notes=None,
    n_dorian=1,
    n_myxo=1,
):
    """Legacy signature: ``(cell names, note-representation strings, mode
    list)`` or None. ``mode_filter`` is accepted for parity and ignored (every
    page passed False)."""
    out = sample_line(
        line_type, bonus=include_bonus, dom_to_minor=dom_to_minor,
        sus4=sus_to_loc_dorian, loc_to_dom=loc_to_dom, length=length,
        movement=movement, starting_note=starting_note, ending_note=ending_note,
        connecting_notes=connecting_notes, n_dorian=n_dorian, n_myxo=n_myxo,
    )
    if out is None:
        return None
    return out.names, [str(list(c.degrees)) for c in out.cells], out.structure
