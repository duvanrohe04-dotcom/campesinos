from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/admin")

from . import content_routes, routes  # noqa: F401  (registran las rutas)
