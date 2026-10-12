import os

import pytest

from api.settings import get_settings


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("BEBOP_API_KEY", "s3cret")
    monkeypatch.delenv("BEBOP_DEV", raising=False)
    get_settings.cache_clear()
    yield "s3cret"
    get_settings.cache_clear()


def test_health_is_open(client, with_key):
    assert client.get("/api/py/health").status_code == 200


def test_missing_key_is_401(client, with_key):
    r = client.get("/api/py/cells?mode=Maj7")
    assert r.status_code == 401


def test_wrong_key_is_401(client, with_key):
    r = client.get("/api/py/cells?mode=Maj7", headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_right_key_passes(client, with_key):
    r = client.get("/api/py/cells?mode=Maj7", headers={"X-API-Key": "s3cret"})
    assert r.status_code == 200


def test_unconfigured_without_dev_is_503(client, monkeypatch):
    monkeypatch.delenv("BEBOP_API_KEY", raising=False)
    monkeypatch.delenv("BEBOP_DEV", raising=False)
    get_settings.cache_clear()
    try:
        assert client.get("/api/py/cells?mode=Maj7").status_code == 503
    finally:
        get_settings.cache_clear()


def test_dev_mode_allows_localhost(client):
    assert os.environ.get("BEBOP_DEV") == "1"
    get_settings.cache_clear()
    assert client.get("/api/py/cells?mode=Maj7").status_code == 200
