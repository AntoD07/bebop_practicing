from scripts.domain.catalog import build_catalog, load_catalog


def test_every_mode_loads(api):
    for mode in ["Maj7", "Minor", "Dorian", "Myxolidian", "Locrian",
                 "MajorResolutions", "MinorResolutions", "7sus4"]:
        status, body = api("GET", f"/cells?mode={mode}&bonus=true")
        assert status == 200, body
        assert body["cells"], mode
        for c in body["cells"]:
            assert c["degrees"] and c["start"] and c["end"]
            assert c["id"].startswith(mode + ":")
            # every token stripped
            assert all(t == t.strip() for t in c["degrees"])
            assert c["start"] == c["start"].strip()


def test_7sus4_is_all_essential(api):
    status, body = api("GET", "/cells?mode=7sus4")
    assert status == 200 and len(body["cells"]) == 43


def test_essential_filter(api):
    _, all_ = api("GET", "/cells?mode=Maj7&bonus=true")
    _, ess = api("GET", "/cells?mode=Maj7")
    assert len(ess["cells"]) < len(all_["cells"])
    assert all(c["type"] == "Essential" for c in ess["cells"])


def test_unknown_mode_404(api):
    status, _ = api("GET", "/cells?mode=Phrygian")
    assert status == 404


def test_ids_are_stable_and_unique():
    a = build_catalog()
    b = build_catalog()
    assert [c.id for m in a.cells_by_mode for c in a.cells_by_mode[m]] == \
           [c.id for m in b.cells_by_mode for c in b.cells_by_mode[m]]
    ids = [c.id for m in a.cells_by_mode for c in a.cells_by_mode[m]]
    assert len(ids) == len(set(ids))


def test_maj7_strip_typo_fixed():
    cat = load_catalog()
    c = cat.find("Maj7", "Whole Step Double Enclosure")
    assert c.end == "5" and not c.nominal_mismatch


def test_warnings_surface_mismatches_and_duplicates(api):
    status, body = api("GET", "/health")
    assert status == 200
    w = "\n".join(body["warnings"])
    assert "Hank Mobley to 5th (+root)" in w
    assert "duplicate cell name 'Super Locrian scale (from #9)'" in w
    assert body["catalog"]["Myxolidian"]["essential"] == 30


def test_translate_endpoint(api):
    status, body = api("POST", "/translate", {"tokens": ["1", "#7", "9(lower)"],
                                               "mapping": "dom_to_minor"})
    assert status == 200 and body["tokens"] == ["5", "#11", "6(lower)"]


def test_translate_gap_is_422(api):
    status, body = api("POST", "/translate", {"tokens": ["maj5"], "mapping": "dom_to_minor"})
    assert status == 422
    assert body["token"] == "maj5" and body["mapping"] == "dom_to_minor"


def test_cells_translation_errors_are_per_cell(api):
    status, body = api("GET", "/cells?mode=Locrian&translate=dom_to_minor")
    assert status == 200
    assert all(c["error"] is None for c in body["cells"]), [c for c in body["cells"] if c["error"]]
    status, body = api("GET", "/cells?mode=Maj7&translate=dom_to_minor")
    assert status == 200 and any(c["error"] for c in body["cells"])  # Maj7 has '2', '#4', ...


def test_positions_and_constants(api):
    status, body = api("GET", "/positions?key=Eb")
    assert status == 200
    names = [p["name"] for p in body["positions"]]
    assert names[0] == "CAGED E string root" and len(names) == 5
    boxes = {p["name"]: [(b["fret_lo"], b["fret_hi"]) for b in p["boxes"]] for p in body["positions"]}
    assert boxes["CAGED A string root"] == [(5, 10)]
    assert boxes["Diagonal A string root"] == [(3, 6)]
    assert body["constants"]["keys"][0] == "C" and "3" in body["constants"]["degree_order"]
