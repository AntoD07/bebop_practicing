"""Centralized, CWD-independent paths to the project's data files.

All paths derive from this file's location, so the app works regardless of the current
working directory.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SAMPLING_DIR = DATA_DIR / "sampling"
LOGS_DIR = DATA_DIR / "logs"


def sampling_file(chord):
    """Path to the sampling CSV for a given chord/mode (e.g. ``"Dorian"``)."""
    return str(SAMPLING_DIR / f"{chord}_sampling.csv")


PRACTICE_DETAILS = str(LOGS_DIR / "practice_details.json")
MELODIC_LINES_LOG = str(LOGS_DIR / "melodic_lines.csv")
TABS_DIR = str(LOGS_DIR / "tabs")  # saved fingering tabs (SVG), one per saved line
