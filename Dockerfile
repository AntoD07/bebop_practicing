# Container fallback for the compute API (Fly.io / any Docker host).
#   docker build -t bebop-api . && docker run -p 8080:8080 -e BEBOP_API_KEY=... bebop-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    BEBOP_MAX_LAYOUTS=10000 BEBOP_TIME_BUDGET_MS=20000

WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir "fastapi>=0.115" "pydantic>=2.9" "uvicorn[standard]>=0.30" \
        "anthropic>=0.115" "pillow>=10" "numpy>=2"

COPY api ./api
COPY scripts ./scripts
COPY data/sampling ./data/sampling
COPY data/pentatonics ./data/pentatonics

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/py/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
