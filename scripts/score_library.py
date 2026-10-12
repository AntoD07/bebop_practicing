"""Score library: persist imported MusicXML sequences and their best fingering.

Layout under ``data/scores/`` (all paths from :mod:`scripts.paths`):

  index.csv  — one row per named sequence: when it was saved, where its
               MusicXML lives, and (once chosen on the Score → Tab page) the
               best fingering — label, cost, register, compact string/fret/
               stroke encoding and the rendered SVG tab.
  files/     — the saved MusicXML bytes, one file per sequence.
  tabs/      — the saved best-fingering SVG, one per sequence.

Unlike ``data/logs/`` this is NOT regenerable runtime data — the user's
uploaded scores live here — so the directory is meant to be versioned.
File paths in the index are stored relative to the repo ROOT, keeping the
library CWD-independent like every other data path.
"""

import datetime
import os
import re

import pandas as pd

from scripts.paths import ROOT, SCORES_INDEX, SCORE_FILES_DIR, SCORE_TABS_DIR

INDEX_COLUMNS = [
    "Name", "Saved", "File",
    "Best fingering", "Best cost", "Best played at", "Tab", "Tab file",
]


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip()).strip("_")
    if not s:
        raise ValueError("sequence name must contain at least one letter/digit")
    return s


def load_index() -> pd.DataFrame:
    """The library index; empty (correctly-columned) when none exists yet."""
    if os.path.exists(SCORES_INDEX) and os.path.getsize(SCORES_INDEX) > 0:
        df = pd.read_csv(SCORES_INDEX)
        for c in INDEX_COLUMNS:
            if c not in df.columns:
                df[c] = None
        return df
    return pd.DataFrame(columns=INDEX_COLUMNS)


def _write_index(df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(SCORES_INDEX), exist_ok=True)
    cols = [c for c in INDEX_COLUMNS if c in df.columns] + \
           [c for c in df.columns if c not in INDEX_COLUMNS]
    df[cols].to_csv(SCORES_INDEX, index=False)


def save_score(name: str, data: bytes, original_filename: str = "score.musicxml") -> str:
    """Save (or overwrite) the MusicXML for ``name``; returns the stored path.

    Re-saving an existing sequence updates its file and date but keeps any
    best-fingering columns already chosen for it.
    """
    ext = (original_filename.rsplit(".", 1)[-1].lower()
           if "." in original_filename else "musicxml")
    if ext not in ("xml", "musicxml", "mxl"):
        raise ValueError(f"not a MusicXML file: {original_filename!r}")
    os.makedirs(SCORE_FILES_DIR, exist_ok=True)
    path = os.path.join(SCORE_FILES_DIR, f"{_slug(name)}.{ext}")
    with open(path, "wb") as f:
        f.write(data)

    df = load_index()
    rel = os.path.relpath(path, ROOT)
    today = datetime.date.today().strftime("%Y-%m-%d")
    mask = df["Name"] == name
    if mask.any():
        df.loc[mask, ["Saved", "File"]] = [today, rel]
    else:
        row = {c: None for c in INDEX_COLUMNS}
        row.update({"Name": name, "Saved": today, "File": rel})
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _write_index(df)
    return path


def score_path(name: str):
    """Absolute path of the saved MusicXML for ``name``, or None."""
    df = load_index()
    hit = df.loc[df["Name"] == name, "File"]
    if hit.empty or not isinstance(hit.iloc[0], str):
        return None
    path = os.path.join(ROOT, hit.iloc[0])
    return path if os.path.exists(path) else None


def load_score_bytes(name: str) -> bytes:
    path = score_path(name)
    if path is None:
        raise FileNotFoundError(f"no saved score named {name!r}")
    with open(path, "rb") as f:
        return f.read()


def save_best_fingering(name: str, svg: str, encoding: str,
                        label: str, cost: float, where: str) -> str:
    """Attach the chosen best fingering to ``name``; returns the SVG path.

    ``encoding`` is the compact ``string/fret+stroke`` form also used by the
    melodic-lines log (e.g. ``"5/3D 4/2D 4/5U"``).
    """
    df = load_index()
    mask = df["Name"] == name
    if not mask.any():
        raise KeyError(f"no saved score named {name!r} — save the MusicXML first")
    os.makedirs(SCORE_TABS_DIR, exist_ok=True)
    path = os.path.join(SCORE_TABS_DIR, f"{_slug(name)}.svg")
    with open(path, "w") as f:
        f.write(svg)
    cols = ["Best fingering", "Best cost", "Best played at", "Tab", "Tab file"]
    # All-NaN columns load as float64; cast so string assignment stays clean.
    df[cols] = df[cols].astype(object)
    df.loc[mask, cols] = [label, cost, where, encoding,
                          os.path.relpath(path, ROOT)]
    _write_index(df)
    return path


def tab_path(name: str):
    """Absolute path of the saved best-fingering SVG for ``name``, or None."""
    df = load_index()
    hit = df.loc[df["Name"] == name, "Tab file"]
    if hit.empty or not isinstance(hit.iloc[0], str):
        return None
    path = os.path.join(ROOT, hit.iloc[0])
    return path if os.path.exists(path) else None


def delete_score(name: str) -> None:
    """Remove ``name`` from the index and delete its stored files."""
    for p in (score_path(name), tab_path(name)):
        if p is not None:
            os.remove(p)
    df = load_index()
    _write_index(df.loc[df["Name"] != name])
