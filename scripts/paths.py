"""Centralized, CWD-independent paths to the project's data files.

All paths derive from this file's location, so the engine works regardless of
the current working directory (the Vercel function, uvicorn, pytest).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SAMPLING_DIR = DATA_DIR / "sampling"
PENTATONICS_DIR = DATA_DIR / "pentatonics"
# Runtime data of the local dev database (git-ignored); the app itself keeps
# its state in Turso / the local libSQL file, not in files here.
LOGS_DIR = DATA_DIR / "logs"


def sampling_file(chord):
    """Path to the sampling CSV for a given chord/mode (e.g. ``"Dorian"``)."""
    return str(SAMPLING_DIR / f"{chord}_sampling.csv")


BERGONZI_PATTERNS = str(PENTATONICS_DIR / "bergonzi_patterns.json")
