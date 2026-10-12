import pytest

from scripts.domain.budget import LayoutBudget
from scripts.domain.connections import pair_key, pairs_for_pivot, pick_key, score_connection_pair
from scripts.fingering.positions import POSITIONS

ALL = [None] + POSITIONS


def _req(p, pair, position, **kw):
    return {"key": "C", "chord1": "Myxolidian", "chord2": "Myxolidian",
            "cell1": {"id": pair["end_id"]}, "cell2": {"id": pair["start_id"]},
            "position": position, "anchor": "key", **kw}


def test_pairs_shape(myxo_pair):
    p = myxo_pair
    assert p["pivot"] == "3" and p["single_chord"] is True and p["sym1"] == "C7"
    assert p["pairs"] and p["pairs"][0]["pair_key"].count("→") == 1
    assert [x["value"] for x in p["pivots"]] == ["1", "9", "3", "#11", "5", "6", "7"]


@pytest.mark.parametrize("position", ALL)
def test_connection_every_position(api, myxo_pair, position):
    pair = myxo_pair["pairs"][0]
    status, body = api("POST", "/fingering/connection", _req(myxo_pair, pair, position))
    assert status == 200, body
    assert body["fingerings"], position
    costs = [f["cost"] for f in body["fingerings"]]
    assert costs == sorted(costs)
    f0 = body["fingerings"][0]
    assert f0["layout"].count("/") == len(f0["placed"])
    assert f0["encoding"].split()[0].endswith(("D", "U"))
    assert len(f0["placed"]) == 9 and body["pivot"]["index"] == 4
    assert f0["report"].startswith("=")
    if position is not None:
        assert all(position in f["positions"] for f in body["fingerings"])
        assert body["position"] == position
    else:
        assert f0["mode"] == "free" and body["position"].startswith("Free")


def test_truncated_flips_with_max_layouts(api, myxo_pair):
    pair = myxo_pair["pairs"][0]
    status, full = api("POST", "/fingering/connection",
                       _req(myxo_pair, pair, "More Horizontal, D string root"))
    status, small = api("POST", "/fingering/connection",
                        _req(myxo_pair, pair, "More Horizontal, D string root", max_layouts=1))
    assert full["truncated"] is False and small["truncated"] is True
    assert len(small["fingerings"]) < len(full["fingerings"])
    assert any(c["mode"] == "optimum" for c in small["chunks"])
    assert all(f["mode"] == "optimum" for f in small["fingerings"])


def test_box_split_covers_the_whole(api, myxo_pair):
    pair = myxo_pair["pairs"][0]
    _, full = api("POST", "/fingering/connection", _req(myxo_pair, pair, "More Horizontal, D string root"))
    _, b0 = api("POST", "/fingering/connection", _req(myxo_pair, pair, "More Horizontal, D string root", box=0))
    _, b1 = api("POST", "/fingering/connection", _req(myxo_pair, pair, "More Horizontal, D string root", box=1))
    layouts = {f["layout"] for f in b0["fingerings"]} | {f["layout"] for f in b1["fingerings"]}
    assert layouts == {f["layout"] for f in full["fingerings"]}


def test_identical_ordering_across_calls(api, myxo_pair):
    pair = myxo_pair["pairs"][1]
    _, a = api("POST", "/fingering/connection", _req(myxo_pair, pair, "CAGED A string root"))
    _, b = api("POST", "/fingering/connection", _req(myxo_pair, pair, "CAGED A string root"))
    assert [f["layout"] for f in a["fingerings"]] == [f["layout"] for f in b["fingerings"]]
    assert b["meta"]["cached"] is True
    assert a["fingerings"] == b["fingerings"]


def test_max_cost_filter(api, myxo_pair):
    pair = myxo_pair["pairs"][0]
    _, body = api("POST", "/fingering/connection", _req(myxo_pair, pair, "CAGED A string root", max_cost=0.0))
    assert body["fingerings"] == [] and body["n_total"] > 0


def test_combo_dorian_myxolidian(api):
    status, p = api("POST", "/connections/pairs", {"chord1": "Dorian", "chord2": "Myxolidian", "key": "Eb"})
    assert status == 200 and p["myxo_to_dorian"] and p["read2"] == "Dorian" and p["mapping_info"]
    pair = p["pairs"][0]
    status, body = api("POST", "/fingering/connection", {
        "key": "Eb", "chord1": "Dorian", "chord2": "Myxolidian",
        "cell1": {"id": pair["end_id"]}, "cell2": {"id": pair["start_id"]},
        "position": "CAGED E string root", "anchor": "chord2"})
    assert status == 200 and body["sym1"] == "Fm7" and body["sym2"] == "Bb7"
    assert body["anchor"]["pc"] == 10


def test_unknown_cell_id_404(api):
    status, body = api("POST", "/fingering/connection", {
        "key": "C", "chord1": "Myxolidian", "chord2": "Myxolidian",
        "cell1": {"id": "Myxolidian:deadbeef"}, "cell2": {"id": "Myxolidian:deadbeef"}})
    assert status == 404


def test_api_matches_domain_for_fixed_pairs(api, myxo_pair):
    """Parity: the endpoint reproduces ``score_connection_pair`` for 5 pairs."""
    pp = pairs_for_pivot("Myxolidian", "Myxolidian", pivot="3", key="C")
    for (e, s), pair in list(zip(pp["pairs"], myxo_pair["pairs"]))[:5]:
        assert pair["end_id"] == e.id and pair["start_id"] == s.id
        dom = score_connection_pair("C", pp["read1"], pp["read2"],
                                    {"name": e.name, "degrees": list(e.degrees), "movement": e.movement},
                                    {"name": s.name, "degrees": list(s.degrees), "movement": s.movement},
                                    position="CAGED A string root", anchor="key",
                                    single_chord=True, budget=LayoutBudget(2000, 6000))
        _, body = api("POST", "/fingering/connection", _req(myxo_pair, pair, "CAGED A string root"))
        dom_layouts = [" ".join(f"{p.string}/{p.fret}" for p in r.best.placed) for r, _ in dom["fingerings"]]
        assert [f["layout"] for f in body["fingerings"]] == dom_layouts
        assert [f["cost"] for f in body["fingerings"]] == pytest.approx(
            [r.best.total_cost for r, _ in dom["fingerings"]])


def test_pick_key_reproduces_legacy_keys():
    assert pick_key("Myxolidian", "Myxolidian", "6", False, "CAGED A string root", "key", True) == \
        "Myxolidian|Myxolidian|6|CAGED A string root"
    assert pick_key("Dorian", "Myxolidian", "3", True, "Free (best on the neck)", "key", False) == \
        "Dorian|Myxolidian|ii:3|Free (best on the neck)|anchor:key"
    assert pick_key("Myxolidian", "MajorResolutions", "b9", False, None, "chord2", False) == \
        "Myxolidian|MajorResolutions|b9|Free (best on the neck)|anchor:2nd"
    assert pick_key("Myxolidian", "MajorResolutions", "3", False, "CAGED E string root", "chord1", False) == \
        "Myxolidian|MajorResolutions|3|CAGED E string root"
    assert pair_key("a", "b") == "a → b"
