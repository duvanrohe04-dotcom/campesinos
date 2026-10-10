from flask import Blueprint

bp = Blueprint("tips", __name__)

from . import routes  # noqa: E402,F401  (registra las rutas)
