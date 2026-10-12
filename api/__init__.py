"""The stateless FastAPI compute service in front of the fingering engine.

``api/index.py`` exports ``app`` (the Vercel Python function; also served by
uvicorn locally and in the container fallback). Every route lives under
``/api/py``; every response carries ``meta: {engine_version, elapsed_ms,
cached}`` and an ``ETag``.
"""
