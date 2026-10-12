import pytest


def _sample(api, **kw):
    body = {"line_type": "Long Maj 2-5-1", "key": "Eb", "chord_tones": True, "seed": 11}
    body.update(kw)
    status, out = api("POST", "/lines/sample", body)
    assert status == 200, out
    return out


def test_seeded_sample_is_reproducible(api):
    a = _sample(api)
    b = _sample(api)
    assert a["lines"] and a["lines"][0]["signature"] == b["lines"][0]["signature"]
    assert a["lines"][0]["structure"] == ["Myxolidian", "Myxolidian", "Myxolidian", "MajorResolutions"]
    assert a["connecting_notes"][0] == ["1", "3", "5", "7"]


def test_sample_carries_its_structure(api):
    out = _sample(api, line_type="Major x Dominant", length=4, n=5, seed=2)
    for ln in out["lines"]:
        assert len(ln["structure"]) == 4
        assert set(ln["structure"]) <= {"Maj7", "MajorResolutions"}
        assert [c["mode"] for c in ln["cells"]] == ln["structure"]


def test_combo_reading_modes(api):
    out = _sample(api, line_type="Dorian x Myxolidian", n_dorian=1, n_myxo=2, seed=5)
    ln = out["lines"][0]
    assert ln["structure"] == ["Dorian", "Myxolidian", "Myxolidian"]
    assert ln["reading_modes"] == ["Dorian", "Dorian", "Dorian"]
    assert out["mapping_info"] and out["chord_tones_info"]
    assert out["connecting_notes"] == [["1", "3", "5", "7"], ["4", "6", "1", "3"], ["4", "6", "1", "3"]]


def test_pivots_chain(api):
    out = _sample(api, n=8, seed=4)
    for ln in out["lines"]:
        degs = [c["degrees"] for c in ln["cells"]]
        for a, b in zip(degs, degs[1:]):
            assert a[-1] == b[0]


def test_unknown_type_422(api):
    status, _ = api("POST", "/lines/sample", {"line_type": "Nope"})
    assert status == 422


def test_pairs_exhaustive(api):
    status, out = api("POST", "/lines/pairs", {"line_type": "Short Maj 2-5-1", "chord_tones": True})
    assert status == 200 and len(out["lines"]) > 20
    for ln in out["lines"]:
        # pairs match on the nominal Start/End Note columns (a nominal-mismatch
        # cell like "MJP Delayed Early b9/#9" pivots on its Start Note, not Notes[0])
        assert ln["cells"][0]["end"] == ln["cells"][1]["start"]


@pytest.mark.parametrize("position", [None, "CAGED A string root", "More Horizontal, D string root"])
def test_line_fingering(api, position):
    ln = _sample(api)["lines"][0]
    status, body = api("POST", "/fingering/line", {
        "key": "Eb", "position": position,
        "cells": [{"id": c["id"], "degrees": c["degrees"], "movement": c["movement"]} for c in ln["cells"]],
        "reading_modes": ln["reading_modes"], "movement_modes": ln["movement_modes"]})
    assert status == 200, body
    assert body["pivot_indices"] == [4, 8, 12]
    if body["fingerings"]:
        costs = [f["cost"] for f in body["fingerings"]]
        assert costs == sorted(costs)
        assert len(body["fingerings"][0]["placed"]) == 17
        if position:
            assert all(position in f["positions"] for f in body["fingerings"])
    else:
        assert body["error"]


def test_line_fingering_length_mismatch_422(api):
    status, _ = api("POST", "/fingering/line", {"key": "C", "cells": [{"name": "x", "degrees": ["1"]}],
                                                "reading_modes": ["Maj7", "Maj7"]})
    assert status == 422
