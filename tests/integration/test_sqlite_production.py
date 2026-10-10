"""SQLite en producción: modo WAL, espera ante bloqueos y copias de seguridad consistentes."""

import os
import sqlite3
import time
from pathlib import Path

from sqlalchemy import text

from app import create_app
from app.config import ProductionConfig, TestingConfig
from app.extensions import db
from app.models import User
from app.services import backup
from app.services.seeding import seed_all


def make_app(tmp_path, **extra):
    attrs = {
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "campo.db").replace("\\", "/"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "BACKUP_DIR": str(tmp_path / "copias"),
        **extra,
    }
    return create_app(type("Config", (TestingConfig,), attrs))


def test_production_defaults_to_wal_and_development_does_not():
    assert ProductionConfig.SQLITE_WAL is True
    from app.config import Config, DevelopmentConfig

    assert Config.SQLITE_WAL is False and DevelopmentConfig.SQLITE_WAL is False


def test_wal_and_busy_timeout_are_applied_to_every_connection(tmp_path):
    app = make_app(tmp_path, SQLITE_WAL=True, SQLITE_FOREIGN_KEYS=False)
    with app.app_context():
        db.create_all()
        assert db.session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert db.session.execute(text("PRAGMA busy_timeout")).scalar() == 15000
        db.session.remove()
        db.engine.dispose()


def test_wal_off_keeps_the_default_journal(tmp_path):
    app = make_app(tmp_path, SQLITE_WAL=False)
    with app.app_context():
        db.create_all()
        assert db.session.execute(text("PRAGMA journal_mode")).scalar() == "delete"
        db.session.remove()
        db.engine.dispose()


def test_a_reader_is_not_blocked_while_another_connection_writes(tmp_path):
    """Con WAL se puede leer mientras se escribe: lo que pasa entre Gunicorn y las tareas programadas."""
    app = make_app(tmp_path, SQLITE_WAL=True)
    with app.app_context():
        db.create_all()
        seed_all(samples=False)
        path = backup.sqlite_path()
        writer = sqlite3.connect(path, timeout=1, isolation_level=None)
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE users SET name = 'cambio sin confirmar'")
        started = time.monotonic()
        assert User.query.count() >= 0  # leer no espera al escritor
        assert time.monotonic() - started < 2
        writer.execute("ROLLBACK")
        writer.close()
        db.session.remove()
        db.engine.dispose()


def test_backup_is_a_consistent_copy_and_old_ones_are_pruned(tmp_path):
    app = make_app(tmp_path, SQLITE_WAL=True, BACKUP_RETENTION_DAYS=14)
    with app.app_context():
        db.create_all()
        seed_all(samples=True)
        users = User.query.count()

        old = Path(app.config["BACKUP_DIR"])
        old.mkdir(parents=True)
        stale = old / "campo-20200101-000000.db"
        stale.write_bytes(b"vieja")
        long_ago = time.time() - 40 * 86400
        os.utime(stale, (long_ago, long_ago))

        target, removed = backup.backup_sqlite()
        assert target.exists() and removed == 1 and not stale.exists()
        copy = sqlite3.connect(target)
        try:
            assert copy.execute("SELECT count(*) FROM users").fetchone()[0] == users
            assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            copy.close()
        db.session.remove()
        db.engine.dispose()


def test_prune_always_keeps_the_newest_copy(tmp_path):
    from datetime import datetime

    only = tmp_path / "campo-20200101-000000.db"
    only.write_bytes(b"unica")
    long_ago = time.time() - 400 * 86400
    os.utime(only, (long_ago, long_ago))
    assert backup.prune(tmp_path, 14, datetime.now()) == 0 and only.exists()


def test_backup_command_reports_and_skips_when_not_sqlite_on_disk(app):
    result = app.test_cli_runner().invoke(args=["backup-db"])  # la base de las pruebas está en memoria
    assert result.exit_code == 0 and "no es un archivo SQLite" in result.output


def test_backup_command_on_a_real_file(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        result = app.test_cli_runner().invoke(args=["backup-db"])
        assert result.exit_code == 0 and "Copia lista" in result.output
        assert len(list(Path(app.config["BACKUP_DIR"]).glob("campo-*.db"))) == 1
        db.session.remove()
        db.engine.dispose()
