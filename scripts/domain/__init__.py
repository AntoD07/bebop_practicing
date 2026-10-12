"""Pure-stdlib domain layer shared by the FastAPI compute service and the legacy
Streamlit app.

Modules
-------
``catalog``       the cell library (``data/sampling/*.csv``) as frozen dataclasses
``transposition`` degree translations between harmonic contexts (marker-aware)
``cells``         translated cell views + the (cells, pivots, mapping) triple
``connections``   pivot pairing and the per-pair fingering search (page 1)
``sampling``      line structures and the backward cell sampler (page 2)
``lines``         pivot-chained lines -> fingerings (page 2)
``budget``        layout-count / wall-clock planning for the enumerations
``notes``         shared constants and user-facing strings

Nothing here imports pandas or streamlit.
"""
