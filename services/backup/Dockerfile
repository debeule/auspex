ARG UV_VERSION=0.12.17
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
# pg_dump refuses a server of a newer major version, so the client tools come from the same image
# as the database server; Python is installed next to them by uv.
FROM postgres:18.6 AS runtime

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON=3.14.2 \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv python install "$UV_PYTHON" && uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONPATH=/app/src
EXPOSE 8002
ENTRYPOINT []
CMD ["uv", "run", "--no-project", "gunicorn", "auspex_backup.api:create_app()", \
     "--config", "config/gunicorn.conf.py"]
