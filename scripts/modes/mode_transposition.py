"""DataFrame wrappers over the degree translations (legacy Streamlit pages).

The mappings and the marker-aware token translator live in
``scripts.domain.transposition``; this module keeps the pandas-facing
signatures the legacy pages call (``translate_dom_to_minor(df)`` etc.) and
applies the translator row-wise. A token a mapping does not know raises
``TranslationError`` (a KeyError subclass) naming the token and the mapping.
"""

from scripts.domain.notes import parse_degrees
from scripts.domain.transposition import (  # noqa: F401 — re-exported names
    TranslationError,
    dom_to_dorian_mapping,
    dom_to_maj_mapping,
    dom_to_min_mapping,
    loc_to_dom_mapping,
    sus4_token,
    translate_token,
)


def _listify(note_cells):
    if isinstance(note_cells, str):
        return [note_cells], True
    return list(note_cells), False


def translate_note_cells(note_cells, mode):
    """The 7sus4 arithmetic shift into ``mode`` (Minor/Dorian +3, Locrian +5)."""
    cells, simple = _listify(note_cells)
    out = [sus4_token(n, mode) for n in cells]
    return out[0] if simple else out


def _map_with(mapping_name):
    def _map(note_cells):
        cells, simple = _listify(note_cells)
        out = [translate_token(n, mapping_name) for n in cells]
        return out[0] if simple else out
    return _map


map_loc_to_dom_notes = _map_with("loc_to_dom")
map_dom_to_minor = _map_with("dom_to_minor")
map_dom_to_dorian = _map_with("dom_to_dorian")
map_dom_to_major = _map_with("dom_to_major")


def _translate_frame(df_cells, fn, copy=True):
    new_df = df_cells.copy() if copy else df_cells
    new_df["Notes"] = new_df["Notes"].apply(parse_degrees).apply(fn)
    new_df["Start Note"] = new_df["Start Note"].astype(str).apply(fn)
    new_df["End Note"] = new_df["End Note"].astype(str).apply(fn)
    return new_df


def translate_sus4_to_other_mode(df_cells, mode):
    return _translate_frame(df_cells, lambda cells: translate_note_cells(cells, mode))


def translate_loc_to_dominant(df_cells):
    return _translate_frame(df_cells, map_loc_to_dom_notes, copy=False)


def translate_dom_to_minor(df_cells):
    return _translate_frame(df_cells, map_dom_to_minor)


def translate_dom_to_dorian(df_cells):
    """Re-spell Myxolidian (V-relative) cells in the ii-relative Dorian degrees."""
    return _translate_frame(df_cells, map_dom_to_dorian)


def translate_dom_to_major(df_cells):
    return _translate_frame(df_cells, map_dom_to_major)


def change_note_representation(
    df_cells, mode, loc_to_dom, dom_to_minor, sus_to_loc_dorian, myxo_to_dorian=False
):
    if (mode in ["Minor", "Dorian", "Locrian"]) and sus_to_loc_dorian:
        df_cells = translate_sus4_to_other_mode(df_cells, mode)
    if (mode in ["Locrian"]) and loc_to_dom:
        df_cells = translate_loc_to_dominant(df_cells)
    if (mode in ["Locrian", "MinorResolutions"]) and dom_to_minor:
        df_cells = translate_dom_to_minor(df_cells)
    if (mode in ["MajorResolutions"]) and dom_to_minor:
        df_cells = translate_dom_to_major(df_cells)
    if (mode == "Myxolidian") and myxo_to_dorian:
        df_cells = translate_dom_to_dorian(df_cells)
    return df_cells
