"""The API must import — and serve — without pandas or streamlit installed."""

import subprocess
import sys

from tests.api.conftest import ROOT

GUARD = r"""
import sys
sys.modules["streamlit"] = None
sys.modules["pandas"] = None
sys.path.insert(0, %r)
import api.index as ix
from fastapi.testclient import TestClient
with TestClient(ix.app) as c:
    r = c.get("/api/py/health")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
print("GUARD_OK")
""" % ROOT


def test_api_imports_without_pandas_or_streamlit():
    proc = subprocess.run([sys.executable, "-c", GUARD], capture_output=True, text=True,
                          env={**__import__("os").environ, "BEBOP_DEV": "1"})
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "GUARD_OK" in proc.stdout
