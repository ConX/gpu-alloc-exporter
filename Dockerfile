FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked

COPY exporter ./

# Expose Prometheus metrics port
EXPOSE 8000

ENTRYPOINT ["uv", "run", "python", "gpu_alloc_exporter.py"]
