"""Manejo de errores centralizado y logging."""

import logging
import os
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

from flask import Flask, flash, redirect, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from .extensions import db
from .utils import is_safe_next


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(_error: HTTPException):
        return render_template("errors/404.html"), 404

    @app.errorhandler(CSRFError)
    def csrf_failed(_error: CSRFError):
        """Formulario viejo o sesión vencida: si se sabe de dónde venía, se vuelve ahí con un aviso."""
        previous = urlparse(request.referrer or "")
        if previous.netloc == request.host and is_safe_next(previous.path):
            flash("Esa página estuvo abierta mucho tiempo o tu sesión venció. Inténtalo de nuevo.", "error")
            return redirect(previous.path + (f"?{previous.query}" if previous.query else ""))
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(_error: HTTPException):
        return render_template("errors/403.html"), 403

    @app.errorhandler(405)
    def method_not_allowed(_error: HTTPException):
        return render_template("errors/405.html"), 405

    @app.errorhandler(413)
    def too_large(_error: HTTPException):
        return render_template("errors/413.html"), 413

    @app.errorhandler(429)
    def too_many_requests(_error: HTTPException):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(_error: Exception):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def configure_logging(app: Flask) -> None:
    """Logger de Flask a consola y, en producción, a archivo con rotación (instance/logs)."""
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    app.logger.setLevel(level)
    if app.config.get("LOG_TO_FILE") and not app.testing:
        log_dir = os.path.join(app.instance_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, "app.log"), maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        app.logger.addHandler(handler)
