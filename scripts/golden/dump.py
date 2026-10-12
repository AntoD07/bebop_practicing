"""Write (or check) the golden responses.

    python -m scripts.golden.dump            # writes missing fixtures only
    python -m scripts.golden.dump --update   # rewrites every fixture
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("BEBOP_DEV", "1")

REQUESTS = os.path.join(ROOT, "scripts", "golden", "requests.json")
RESPONSES = os.path.join(ROOT, "tests", "golden", "responses")


def load_requests() -> list:
    with open(REQUESTS, encoding="utf-8") as f:
        return json.load(f)


VOLATILE = {"meta", "elapsed_ms"}   # timings never match between runs


def strip_meta(body):
    if isinstance(body, dict):
        return {k: strip_meta(v) for k, v in body.items() if k not in VOLATILE}
    if isinstance(body, list):
        return [strip_meta(v) for v in body]
    return body


def run_all(client) -> dict:
    out = {}
    for req in load_requests():
        r = client.request(req["method"], "/api/py" + req["path"], json=req.get("body"))
        out[req["name"]] = {"status": r.status_code, "body": strip_meta(r.json())}
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    update = "--update" in argv
    from fastapi.testclient import TestClient
    import api.index as ix

    os.makedirs(RESPONSES, exist_ok=True)
    with TestClient(ix.app) as client:
        results = run_all(client)
    written = 0
    for name, res in results.items():
        path = os.path.join(RESPONSES, f"{name}.json")
        if os.path.exists(path) and not update:
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        written += 1
    print(f"{written} fixture(s) written to {os.path.relpath(RESPONSES, ROOT)} "
          f"({len(results)} requests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
