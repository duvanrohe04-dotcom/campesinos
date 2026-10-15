"""Extensiones sin app: se inicializan en create_app(). Evita imports circulares."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)

login_manager.login_view = "auth.login"
# «basic», no «strong»: con «strong», si cambia la IP o el navegador entre dos peticiones se cierra la sesión Y se
# ignora «recordarme». En el campo el celular salta entre Wi-Fi, datos móviles y antenas, y su IP cambia todo el
# tiempo: la gente quedaba fuera de su cuenta sin saber por qué. La cookie ya es HttpOnly, SameSite y Secure (prod).
login_manager.session_protection = "basic"
login_manager.login_message = "Ingresa con tu celular para continuar."
login_manager.login_message_category = "info"
