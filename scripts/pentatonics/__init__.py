"""Pentatonic practice: scale/pattern generators that feed the fingering engine.

Every generator returns an engine ``line`` — a list of
``{"pitch": <midi int>, "role": <degree>, "degree": <degree>}`` dicts — that plugs
directly into ``scripts.fingering.optimize_fingering``.
"""
