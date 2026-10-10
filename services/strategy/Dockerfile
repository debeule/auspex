# Built from services/ (compose context ../services): the runtime installs services/backtesting
# (market simulation) from source, as uv.lock pins it.
ARG UV_VERSION=0.12.17
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:3.14.2-slim AS runtime

COPY --from=uv /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backtesting/pyproject.toml /app/backtesting/pyproject.toml
COPY backtesting/src/ /app/backtesting/src/

WORKDIR /app/strategy
COPY strategy/pyproject.toml strategy/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY strategy/src/ ./src/

RUN useradd --system --uid 10001 --no-create-home auspex
USER auspex

ENV PYTHONPATH=/app/strategy/src
EXPOSE 8003
CMD ["/app/strategy/.venv/bin/python", "-m", "auspex_strategy.runtime.main"]
