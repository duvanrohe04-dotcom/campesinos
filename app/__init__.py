"""Fábrica de la aplicación: configura extensiones, blueprints, errores y logging."""

import os

from flask import Flask
from sqlalchemy import event
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import resolve_config
from .errors import configure_logging, register_error_handlers
from .extensions import csrf, db, limiter, login_manager, migrate


def _resolve_database_uri(app: Flask) -> str:
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or "sqlite:///" + os.path.join(app.instance_path, "campo.db")
    return uri.replace("postgres://", "postgresql://", 1) if uri.startswith("postgres://") else uri


def _configure_sqlite(app: Flask) -> None:
    """Ajustes de cada conexión a SQLite (no hacen nada con PostgreSQL).

    - busy_timeout: si otro proceso está escribiendo, espera en vez de fallar con «database is locked».
    - WAL (SQLITE_WAL, activo en producción): lecturas y escritura a la vez entre los procesos de Gunicorn y las tareas
      programadas. No va en desarrollo por defecto: crea archivos extra que OneDrive/antivirus pueden molestar.
    - Llaves foráneas (SQLITE_FOREIGN_KEYS, solo pruebas): SQLite las ignora salvo que se pida, PostgreSQL siempre las
      exige. No va en desarrollo: las migraciones por lotes de SQLite recrean tablas y fallan con ellas.
    """
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return
    wal, foreign_keys = app.config.get("SQLITE_WAL"), app.config.get("SQLITE_FOREIGN_KEYS")

    def configure(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA busy_timeout=15000")
        if wal:
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
            dbapi_connection.execute("PRAGMA synchronous=NORMAL")
        if foreign_keys:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with app.app_context():
        event.listen(db.engine, "connect", configure)


def _register_blueprints(app: Flask) -> None:
    from .blueprints.admin import bp as admin_bp
    from .blueprints.agenda import bp as agenda_bp
    from .blueprints.alerts import bp as alerts_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.listings import bp as listings_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.prices import bp as prices_bp
    from .blueprints.profiles import bp as profiles_bp
    from .blueprints.tips import bp as tips_bp

    # La ruta de detalle /<cat>/<sub>/<slug-id> es la más genérica: va al final
    for blueprint in (main_bp, auth_bp, profiles_bp, alerts_bp, prices_bp, agenda_bp, tips_bp, admin_bp, listings_bp):
        app.register_blueprint(blueprint)


def _add_security_headers(app: Flask) -> None:
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(self), microphone=()")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def create_app(config=None) -> Flask:
    """Crea la app. `config` puede ser un nombre ('production'), una clase o None (usa FLASK_ENV)."""
    config_class = resolve_config(config)
    validate = getattr(config_class, "validate", None)  # solo las configuraciones de producción validan
    if callable(validate):
        validate()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = _resolve_database_uri(app)
    if not app.config.get("UPLOAD_FOLDER"):
        app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    if app.config.get("TRUST_PROXY"):  # detrás de Nginx: IP real del cliente y esquema https
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    _configure_sqlite(app)
    migrate.init_app(app, db, render_as_batch=app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"))
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  (registra los modelos para las migraciones)
    from .cli import register_cli
    from .templating import register_template_helpers

    _register_blueprints(app)
    register_template_helpers(app)
    register_cli(app)
    register_error_handlers(app)
    configure_logging(app)
    _add_security_headers(app)
    return app
