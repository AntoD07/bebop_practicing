"""The live API must reproduce the golden responses (floats to 1e-6)."""

import json
import os

import pytest

from scripts.golden.dump import RESPONSES, load_requests, strip_meta


def _approx_equal(a, b, path=""):
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, (int, float)) and isinstance(b, (int, float)), f"{path}: {a!r} != {b!r}"
        assert a == pytest.approx(b, abs=1e-6), f"{path}: {a!r} != {b!r}"
        return
    if isinstance(a, dict):
        assert isinstance(b, dict), f"{path}: type mismatch"
        assert set(a) == set(b), f"{path}: keys {sorted(set(a) ^ set(b))}"
        for k in a:
            _approx_equal(a[k], b[k], f"{path}.{k}")
        return
    if isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            _approx_equal(x, y, f"{path}[{i}]")
        return
    assert a == b, f"{path}: {a!r} != {b!r}"


@pytest.mark.parametrize("req", load_requests(), ids=lambda r: r["name"])
def test_golden(client, req):
    path = os.path.join(RESPONSES, f"{req['name']}.json")
    if not os.path.exists(path):
        pytest.skip(f"no fixture — run `python -m scripts.golden.dump` ({req['name']})")
    with open(path, encoding="utf-8") as f:
        expected = json.load(f)
    r = client.request(req["method"], "/api/py" + req["path"], json=req.get("body"))
    assert r.status_code == expected["status"]
    _approx_equal(strip_meta(r.json()), expected["body"])
