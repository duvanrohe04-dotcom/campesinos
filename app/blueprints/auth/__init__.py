from flask import Blueprint

bp = Blueprint("auth", __name__)

from . import routes  # noqa: F401  (registra las rutas)
