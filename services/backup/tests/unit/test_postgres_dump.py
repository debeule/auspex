from pathlib import Path

from fakes import FakeRunner

from auspex_backup.postgres import dump_databases, pg_env

_ENVIRON = {
    "PGHOST": "postgres",
    "PGUSER": "auspex_app",
    "PGPASSWORD": "s3cret",
    "PATH": "/usr/bin",
    "MINIO_SECRET_KEY": "not-for-pg",
}


def test_postgres_dump_runs_custom_format_pg_dump_for_both_databases_with_password_only_in_env(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(output=b"PGDMP-archive")

    sizes = dump_databases(runner, ["auspex", "airflow"], tmp_path, pg_env(_ENVIRON))

    assert [c.argv for c in runner.calls] == [
        ["pg_dump", "--format=custom", "--dbname=auspex"],
        ["pg_dump", "--format=custom", "--dbname=airflow"],
    ]
    for call in runner.calls:
        assert not any("s3cret" in arg for arg in call.argv)
        assert call.env["PGPASSWORD"] == "s3cret"
        assert "MINIO_SECRET_KEY" not in call.env
    assert (tmp_path / "auspex.dump").read_bytes() == b"PGDMP-archive"
    assert (tmp_path / "airflow.dump").read_bytes() == b"PGDMP-archive"
    assert sizes == {"auspex": 13, "airflow": 13}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["airflow.dump", "auspex.dump"]


def test_a_failed_dump_leaves_no_partial_dump_file(tmp_path: Path) -> None:
    runner = FakeRunner(fail_on="--dbname=airflow")
    try:
        dump_databases(runner, ["auspex", "airflow"], tmp_path, pg_env(_ENVIRON))
    except RuntimeError:
        pass
    assert sorted(p.name for p in tmp_path.iterdir()) == ["auspex.dump"]
