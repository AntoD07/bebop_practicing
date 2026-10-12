"""``ENGINE_VERSION``: a sha1 over everything that can change a result —
the engine, the generators, the domain layer, the serializer and the cell
CSVs. Computed once at import; replaces the Streamlit ``st.cache_data`` keys
and ``shape_sig``: it is part of every cache key and every ETag.
"""

from __future__ import annotations

import glob
import hashlib
import os

from scripts.paths import ROOT

ENGINE_PATTERNS = (
    "scripts/fingering/*.py",
    "scripts/pentatonics/*.py",
    "scripts/triad_pairs/*.py",
    "scripts/domain/*.py",
    "scripts/paths.py",
    "api/serialize.py",
    "data/sampling/*.csv",
    "data/pentatonics/*.json",
)


def engine_files() -> list:
    out = []
    for pat in ENGINE_PATTERNS:
        out.extend(glob.glob(os.path.join(str(ROOT), pat)))
    return sorted(set(out))


def compute_engine_version() -> str:
    h = hashlib.sha1()
    for path in engine_files():
        h.update(os.path.relpath(path, str(ROOT)).encode())
        h.update(b"\0")
        with open(path, "rb") as f:
            h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()


ENGINE_VERSION = compute_engine_version()
