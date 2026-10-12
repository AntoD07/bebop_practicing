import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("BEBOP_DEV", "1")
os.environ.pop("BEBOP_API_KEY", None)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import api.index as ix

    with TestClient(ix.app) as c:
        yield c


@pytest.fixture
def api(client):
    """``api(method, path, json)`` -> (status, body); paths are relative to /api/py."""
    def _call(method, path, json=None, headers=None):
        r = client.request(method, "/api/py" + path, json=json, headers=headers or {})
        try:
            body = r.json()
        except ValueError:
            body = r.text
        return r.status_code, body
    return _call


@pytest.fixture(scope="session")
def myxo_pair(client):
    r = client.post("/api/py/connections/pairs",
                    json={"chord1": "Myxolidian", "chord2": "Myxolidian", "key": "C"})
    assert r.status_code == 200
    return r.json()
