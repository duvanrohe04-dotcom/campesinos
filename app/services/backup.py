"""Copia de seguridad de la base SQLite. Usa la API de respaldo de SQLite: es consistente aunque la app esté escribiendo
(copiar el archivo a mano mientras se usa puede dejar una copia dañada)."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..utils import utcnow

PREFIX, SUFFIX = "campo-", ".db"


class BackupError(RuntimeError):
    """No se pudo hacer la copia. El mensaje está en español."""


def sqlite_path() -> Path | None:
    """Ruta del archivo de la base si es SQLite en disco; None si es PostgreSQL o SQLite en memoria."""
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


def backup_directory() -> Path:
    configured = current_app.config.get("BACKUP_DIR")
    return Path(configured) if configured else Path(current_app.instance_path) / "backups"


def prune(directory: Path, keep_days: int, now: datetime) -> int:
    """Borra las copias más viejas que `keep_days`. Siempre deja la más reciente. Devuelve cuántas borró."""
    copies = sorted(directory.glob(f"{PREFIX}*{SUFFIX}"), key=lambda path: path.stat().st_mtime, reverse=True)
    removed = 0
    for path in copies[1:]:
        if datetime.fromtimestamp(path.stat().st_mtime) < now - timedelta(days=keep_days):
            path.unlink()
            removed += 1
    return removed


def backup_sqlite() -> tuple[Path, int]:
    """Crea la copia y borra las viejas. Devuelve (archivo de la copia, cuántas copias viejas se borraron)."""
    source_path = sqlite_path()
    if source_path is None:
        raise BackupError("La base de datos no es un archivo SQLite: esta copia no aplica.")
    if not source_path.exists():
        raise BackupError(f"No existe la base de datos en {source_path}.")
    directory = backup_directory()
    directory.mkdir(parents=True, exist_ok=True)
    now = utcnow()
    target = directory / f"{PREFIX}{now:%Y%m%d-%H%M%S}{SUFFIX}"
    source, copy = sqlite3.connect(source_path), sqlite3.connect(target)
    try:
        source.backup(copy)
    except sqlite3.Error as error:
        target.unlink(missing_ok=True)
        raise BackupError(f"Falló la copia: {error}") from error
    finally:
        copy.close()
        source.close()
    return target, prune(directory, current_app.config["BACKUP_RETENTION_DAYS"], datetime.now())
