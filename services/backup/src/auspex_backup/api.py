"""HTTP API the `auspex_backup` DAG calls; reachable only on the compose network."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path

from flask import Flask, jsonify
from flask.typing import ResponseReturnValue
from minio import Minio
from neo4j import GraphDatabase

from auspex_backup.backup import Backup, StoreFailedError, build_stores
from auspex_backup.postgres import pg_env, run_command

BACKUP_ROOT = Path("/backup")


def create_app(backup_factory: Callable[[], Backup] | None = None) -> Flask:
    factory = backup_factory or backup_from_env
    running = threading.Lock()
    app = Flask(__name__)

    @app.get("/health")
    def health() -> ResponseReturnValue:
        return jsonify(status="ok")

    @app.post("/backup")
    def backup() -> ResponseReturnValue:
        if not running.acquire(blocking=False):
            return jsonify(error="a backup is already running"), 409
        try:
            return jsonify(factory().run()), 200
        except StoreFailedError as exc:
            return jsonify(error=str(exc), failed_stores=exc.stores), 500
        finally:
            running.release()

    return app


def backup_from_env() -> Backup:
    env = os.environ
    driver = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))
    stores = build_stores(
        BACKUP_ROOT,
        runner=run_command,
        pg_environment=pg_env(env),
        databases=env["BACKUP_DATABASES"].split(","),
        driver=driver,
        minio=minio_from_env(),
        buckets=env["BACKUP_BUCKETS"].split(","),
    )
    return Backup(
        BACKUP_ROOT, stores, keep_days=int(env["BACKUP_KEEP_DAYS"]), close=driver.close
    )


def minio_from_env() -> Minio:
    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
