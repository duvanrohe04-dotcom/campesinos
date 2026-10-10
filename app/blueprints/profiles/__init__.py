from flask import Blueprint

bp = Blueprint("profiles", __name__)

from . import routes  # noqa: F401  (registra las rutas)
