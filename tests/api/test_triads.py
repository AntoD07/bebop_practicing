"""Triad pairs: the zig-zag progress guard, run-oriented weights, favourites."""

import pytest

from scripts.fingering.config import FingeringConfig
from scripts.triad_pairs.favorites import run_config
from scripts.triad_pairs.triads import ALTERNATING_DIRECTIONS, Triad, TriadPair, alternating_triads_run


def test_zigzag_progress_guard_terminates():
    # F#+ + G° with x=2 used to cycle forever: the partner's descent outran the lead.
    pair = TriadPair(Triad("F#", "augmented"), Triad("G", "diminished"))
    for d in ALTERNATING_DIRECTIONS:
        for x in (2, 3, 4):
            line = alternating_triads_run(pair, 2, 2, x, d)
            assert 0 < len(line) < 400, (d, x, len(line))


def test_run_config_neutralises_downbeat_dd():
    base = FingeringConfig()
    cfg = run_config(base)
    assert cfg.downbeat_dd_penalty == base.same_string_dd_penalty
    assert run_config(base.with_overrides(shift_cost=2.0)).shift_cost == 2.0


def _ranked(api, run_weights=True):
    status, gen = api("POST", "/triads/generate", {
        "root1": "Eb", "root2": "F", "exercise": "scale", "direction": "ascending",
        "n_octaves": 1, "low_octave": 3, "start_degs": [0]})
    assert status == 200, gen
    label, line = next(iter(gen["lines_by_start"].items()))
    status, rank = api("POST", "/pentatonics/rank", {
        "key": "Eb", "line": line, "generic": True, "run_weights": run_weights,
        "start_label": label, "config": {"shift_cost": 1.0}})
    assert status == 200, rank
    row = next(r for r in rank["rows"] if r["fingering"])
    return gen, row, rank


def test_rank_run_weights_flag(api):
    _, _, on = _ranked(api, True)
    _, _, off = _ranked(api, False)
    assert on["config"]["downbeat_dd_penalty"] == FingeringConfig().same_string_dd_penalty
    assert "downbeat_dd_penalty" not in off["config"]


def test_favorite_make_and_render(api):
    gen, row, _ = _ranked(api)
    f = row["fingering"]
    pair = {"roots": ["Eb", "F"], "qualities": ["major", "major"]}
    position = row["position"] if row["position"].startswith(("CAGED", "Diagonal", "More")) else None
    status, made = api("POST", "/triads/favorites/make", {
        "pair": pair, "key": "Eb", "position": position, "exercise": "scale",
        "params": {"direction": "ascending", "octaves": 1}, "start": row["start"],
        "title": gen["title"], "cost": row["cost"],
        "placed": [{"midi": p["midi"], "string": p["string"], "fret": p["fret"],
                    "degree": p["degree"], "cell": p["cell"]} for p in f["placed"]]})
    assert status == 200, made
    fav = made["favorite"]
    assert " ".join(f"{s}/{fr}" for s, fr in fav["layout"]) == f["layout"]
    assert all(n["k"] in (0, 1) for n in fav["line"])

    # as saved: the same layout, labels rebuilt from the pair
    status, same = api("POST", "/triads/favorites/render", {"favorite": fav, "key": "Eb"})
    assert status == 200, same
    assert same["as_saved"] and same["fingering"]["layout"] == f["layout"]
    assert [p["degree"] for p in same["fingering"]["placed"]] == [p["degree"] for p in f["placed"]]

    # mimicked in C: every fret slides by the same delta, pitches follow, labels move with the key
    status, moved = api("POST", "/triads/favorites/render", {"favorite": fav, "key": "C"})
    assert status == 200, moved
    assert not moved["as_saved"]
    d = moved["fret_delta"]
    assert d % 12 == 9 and moved["fingering"] is not None
    assert moved["pair_title"].startswith("C")
    for a, b in zip(f["placed"], moved["fingering"]["placed"]):
        assert (b["string"], b["fret"], b["midi"]) == (a["string"], a["fret"] + d, a["midi"] + d)
        assert b["degree"].split(":")[1] == a["degree"].split(":")[1]


def test_favorite_render_rejects_bad_input(api):
    fav = {"key": "H", "position": None, "pair": {"roots": ["C", "D"], "qualities": ["major", "major"]},
           "layout": [[3, 5], [3, 7]], "line": [{"pitch": 60, "k": 0, "deg": "1"}, {"pitch": 62, "k": 1, "deg": "1"}]}
    status, _ = api("POST", "/triads/favorites/render", {"favorite": fav, "key": "C"})
    assert status == 422
    fav["key"] = "C"
    fav["layout"] = [[3, 5]]
    status, _ = api("POST", "/triads/favorites/render", {"favorite": fav, "key": "C"})
    assert status == 422
