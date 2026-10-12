"""Triad pairs & hexatonic scales — definitions, neck maps and exercise generators.

A *triad pair* is two triads (by default a whole tone apart, e.g. C + D) whose
union is a *hexatonic* scale. Every generator here returns an engine ``line`` —
``{"pitch": <midi>, "role", "degree", "cell"}`` dicts — that plugs straight into
``scripts.fingering.optimize_fingering`` and the pentatonic rankers.
"""
