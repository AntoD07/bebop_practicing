"""Gypsy-jazz fingering + picking optimizer.

Public API
----------
``optimize_fingering(line, context, config)`` — the entry point described in the
project spec. Given a melodic *line* whose pitches are already fixed (produced by
the cell engine), it finds the best guitar string/fret positions for Gypsy-jazz
phrasing and *derives* the picking (down/up strokes) from that fingering.

The picking is never chosen independently: it falls out of the fingering by the
orthodox "la pompe"/rest-stroke rules encoded in :mod:`scripts.fingering.picking`.

See the module docstrings for the picking model, the cost function, and the
Viterbi/DP search.
"""

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering, FingeringResult
from scripts.fingering.picking import verify_conventions, ConventionError

__all__ = [
    "optimize_fingering",
    "FingeringResult",
    "FingeringConfig",
    "verify_conventions",
    "ConventionError",
]
