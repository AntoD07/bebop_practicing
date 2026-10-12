"""Score -> Tab: MusicXML parsing (stdlib) and the Claude-vision reader."""

from __future__ import annotations

import base64
import binascii
import os
import tempfile
import time

from fastapi import APIRouter, HTTPException

from api.cache import plain
from api.schemas import ParseMusicXmlRequest, VisionRequest
from api.settings import get_settings
from scripts.fingering.pitch import midi_to_name
from scripts.fingering.score_import import chord_at, degree_for, parse_musicxml

router = APIRouter()


def _review_rows(parsed: dict) -> dict:
    chords = parsed["chords"]
    notes = []
    for i, n in enumerate(parsed["notes"]):
        sym = chord_at(chords, n["start"])
        notes.append({
            "i": i, "midi": n["midi"], "name": midi_to_name(n["midi"]), "start": n["start"],
            "duration": n.get("duration"), "phrase_start": bool(n["phrase_start"]),
            "bar": n.get("bar", 0), "chord": sym or "", "degree": degree_for(n["midi"], sym),
        })
    gaps = [b["start"] - a["start"] for a, b in zip(parsed["notes"], parsed["notes"][1:])]
    density = "eighth" if gaps and sorted(gaps)[len(gaps) // 2] < 0.99 else "quarter"
    return {"notes": notes, "chords": chords, "beats_per_bar": parsed["beats_per_bar"],
            "density": density, "uncertain": parsed.get("uncertain", [])}


@router.post("/score/parse-musicxml")
def parse(body: ParseMusicXmlRequest):
    t0 = time.perf_counter()
    try:
        data = base64.b64decode(body.data_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "data_b64 is not valid base64")
    if len(data) > 8_000_000:
        raise HTTPException(413, "score file too large")
    try:
        parsed = parse_musicxml(data)
    except Exception as e:  # noqa: BLE001 — malformed XML, no notes, ...
        raise HTTPException(422, f"could not parse the score: {e}")
    out = _review_rows(parsed)
    out["filename"] = body.filename
    return plain(out, (time.perf_counter() - t0) * 1000.0)


@router.post("/score/read-vision")
def read_vision(body: VisionRequest):
    s = get_settings()
    if not s.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured on the API")
    try:
        from scripts.fingering import vision_omr   # anthropic/PIL/numpy: imported lazily
    except ImportError as e:
        raise HTTPException(503, f"vision reader unavailable: {e}")
    if s.vision_model:
        vision_omr.MODEL = s.vision_model
    t0 = time.perf_counter()
    merged = {"notes": [], "chords": [], "beats_per_bar": 4, "uncertain": []}
    onset_base, bar_base = 0.0, 0
    with tempfile.TemporaryDirectory() as td:
        for k, img in enumerate(body.images):
            try:
                png = base64.b64decode(img, validate=True)
            except (binascii.Error, ValueError):
                raise HTTPException(422, f"image {k} is not valid base64")
            path = os.path.join(td, f"page_{k + 1}.png")
            with open(path, "wb") as f:
                f.write(png)
            work = os.path.join(td, f"work_{k + 1}")
            os.makedirs(work, exist_ok=True)
            try:
                page = vision_omr.read_score_with_claude(path, work, api_key=s.anthropic_api_key)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(502, f"vision reader failed on page {k + 1}: {e}")
            bpb = page["beats_per_bar"]
            merged["beats_per_bar"] = bpb
            for n in page["notes"]:
                merged["notes"].append({**n, "start": n["start"] + onset_base,
                                        "bar": n.get("bar", 0) + bar_base})
            for c in page["chords"]:
                merged["chords"].append({**c, "start_beat": c["start_beat"] + onset_base})
            merged["uncertain"].extend({**u, "measure": u.get("measure", 0) + bar_base}
                                       for u in page.get("uncertain", []))
            if page["notes"]:
                last = page["notes"][-1]
                end = last["start"] + last.get("duration", 1.0)
                bars = int((end + bpb - 1e-6) // bpb)
                onset_base += bars * bpb
                bar_base += max(bars, max(n.get("bar", 0) for n in page["notes"]))
    if not merged["notes"]:
        raise HTTPException(422, "the vision reader returned no notes")
    out = _review_rows(merged)
    out["pages"] = len(body.images)
    return plain(out, (time.perf_counter() - t0) * 1000.0)
