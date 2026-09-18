ARG UV_VERSION=0.12.17
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:3.14.2-slim AS runtime

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY config/ ./config/
COPY prompts/ ./prompts/

ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uv", "run", "--no-project", "gunicorn", "auspex_ingest.api:create_app()", \
     "--config", "config/gunicorn.conf.py"]
