import base64

import pytest

TINY_XML = b"""<?xml version="1.0"?><score-partwise><part id="P1"><measure number="1">
<attributes><divisions>2</divisions><time><beats>4</beats></time></attributes>
<harmony><root><root-step>C</root-step></root><kind>major-seventh</kind></harmony>
<note><pitch><step>E</step><octave>4</octave></pitch><duration>2</duration></note>
<note><pitch><step>G</step><octave>4</octave></pitch><duration>2</duration></note>
<note><rest/><duration>2</duration></note>
<note><pitch><step>B</step><octave>4</octave></pitch><duration>2</duration></note>
</measure><measure number="2">
<harmony><root><root-step>A</root-step></root><kind>minor-seventh</kind></harmony>
<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration></note>
<note><pitch><step>A</step><octave>4</octave></pitch><duration>4</duration></note>
</measure></part></score-partwise>"""


def test_positions_fingering_home(api):
    _, cells = api("GET", "/cells?mode=Minor")
    cell = cells["cells"][0]
    status, body = api("POST", "/fingering/positions", {"key": "Eb", "mode": "Minor", "cell": {"id": cell["id"]}})
    assert status == 200, body
    assert len(body["positions"]) == 5
    assert body["cell"]["name"] == cell["name"]
    for p in body["positions"]:
        for o in p["octaves"]:
            assert o["fingering"]["placed"] and o["register"]
    costs = [p["best_cost"] for p in body["positions"] if p["best_cost"] is not None]
    assert costs == sorted(costs, reverse=True)


def test_rank_absolute(api):
    status, body = api("POST", "/fingering/rank-absolute", {
        "key": "C", "beats_per_bar": 4,
        "line": [{"pitch": "E4", "start": 0}, {"pitch": "G4", "start": 0.5}, {"pitch": "C5", "start": 1},
                 {"pitch": "B4", "start": 1.5}, {"pitch": "G4", "start": 2}],
        "chords": [{"start_beat": 0, "symbol": "Cmaj7"}]})
    assert status == 200, body
    assert body["density"] == "eighth"
    labels = [r["label"] for r in body["rows"]]
    assert labels[0].startswith("Free")
    assert any(l == "CAGED A string root" for l in labels)
    feasible = [r for r in body["rows"] if r["fingering"]]
    assert feasible and feasible[0]["shift"] == 0 and feasible[0]["shift_text"] == "as written"


def test_rank_absolute_limits(api):
    status, _ = api("POST", "/fingering/rank-absolute", {"key": "C", "line": [{"pitch": 60}] * 65})
    assert status == 422
    status, _ = api("POST", "/fingering/rank-absolute", {"key": "C", "line": [{"pitch": "H4"}]})
    assert status == 422


def test_parse_musicxml(api):
    status, body = api("POST", "/score/parse-musicxml",
                       {"filename": "t.xml", "data_b64": base64.b64encode(TINY_XML).decode()})
    assert status == 200, body
    names = [n["name"] for n in body["notes"]]
    assert names == ["E4", "G4", "B4", "C5", "A4"]
    assert [n["phrase_start"] for n in body["notes"]] == [True, False, True, False, False]
    assert body["notes"][3]["chord"] == "Am7" and body["notes"][3]["degree"] == "b3"
    assert body["beats_per_bar"] == 4


def test_parse_musicxml_bad_input(api):
    status, _ = api("POST", "/score/parse-musicxml", {"data_b64": "!!!"})
    assert status == 422
    status, _ = api("POST", "/score/parse-musicxml", {"data_b64": base64.b64encode(b"<nope/>").decode()})
    assert status == 422


def test_vision_without_key_is_503(api, monkeypatch):
    from api.settings import get_settings
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        status, _ = api("POST", "/score/read-vision", {"images": ["aGVsbG8="]})
        assert status == 503
    finally:
        get_settings.cache_clear()


def test_pentatonics_flow(api):
    status, pats = api("GET", "/pentatonics/patterns")
    assert status == 200 and len(pats["patterns"]) == 8
    status, gen = api("POST", "/pentatonics/generate", {"key": "A", "penta": "minor", "exercise": "scale",
                                                        "n_octaves": 2, "low_octave": 2, "start_degs": [0]})
    assert status == 200 and list(gen["lines_by_start"]) == ["1"]
    line = gen["lines_by_start"]["1"]
    assert len(line) == 11
    status, rk = api("POST", "/pentatonics/rank", {"key": "A", "line": line, "penta": "minor"})
    assert status == 200 and rk["rows"]
    assert rk["rows"][0]["cpn"] is not None
    labels = [r["position"] for r in rk["rows"]]
    assert "3+2 per string (your fingering)" in labels
    status, rk2 = api("POST", "/pentatonics/rank", {"key": "A", "line": line, "penta": "minor",
                                                    "position": "CAGED E string root"})
    assert status == 200
    for r in rk2["rows"]:
        assert r["layout"] and r["fingering"]
    status, berg = api("POST", "/pentatonics/generate", {"key": "A", "exercise": "bergonzi",
                                                         "formula": pats["patterns"][4]["name"]})
    assert status == 200 and berg["group"] == 4
    status, _ = api("POST", "/pentatonics/generate", {"key": "A", "exercise": "bergonzi", "formula": "nope"})
    assert status == 422


def test_triads_flow(api):
    status, p = api("GET", "/triads/pair?root1=C&root2=D&key=C")
    assert status == 200 and p["hexatonic_names"] == ["C", "D", "E", "F#", "G", "A"]
    assert set(p["boxes"]) == {"CAGED E string root", "CAGED A string root", "Diagonal E string root",
                               "Diagonal A string root", "More Horizontal, D string root"}
    status, g = api("POST", "/triads/generate", {"root1": "C", "root2": "D", "exercise": "alternating",
                                                 "direction": "ascending", "x": 3, "start_degs": [0]})
    assert status == 200
    line = g["lines_by_start"]["C"]
    assert line[0]["degree"] == "C:1" and line[3]["degree"] == "D:1"
    status, rk = api("POST", "/pentatonics/rank", {"key": "C", "line": line, "generic": True, "group": 3})
    assert status == 200 and rk["rows"]
    assert all(r["position"] in ["Free (best on the neck)"] + list(p["boxes"]) for r in rk["rows"])


def test_etag_and_304(client):
    body = {"chord1": "Maj7", "chord2": "Maj7", "key": "C"}
    r1 = client.post("/api/py/connections/pairs", json=body)
    assert r1.status_code == 200 and r1.headers.get("etag")
    r2 = client.post("/api/py/connections/pairs", json=body, headers={"If-None-Match": r1.headers["etag"]})
    assert r2.status_code == 304
    r3 = client.post("/api/py/connections/pairs", json=body)
    assert r3.json()["meta"]["cached"] is True
