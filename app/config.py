"""Configuración por entorno.

Todo valor ajustable o sensible se lee de variables de entorno (archivo `.env`); el código solo trae valores
por defecto inofensivos. Los secretos (SECRET_KEY, claves de admin y de demostración) NO tienen valor por defecto.
Ver `.env.example` (desarrollo) y `.env.production.example` (producción) para la lista completa.
"""

import os
import secrets


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        raise RuntimeError(f"La variable {name} debe ser un número entero (valor actual: {raw!r}).") from None


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw.replace(",", ".")) if raw else default
    except ValueError:
        raise RuntimeError(f"La variable {name} debe ser un número (valor actual: {raw!r}).") from None


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "si", "sí", "on")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


class Config:
    # --- Secretos: sin valor por defecto. Si falta SECRET_KEY se genera una al iniciar (las sesiones se cierran
    #     al reiniciar); en desarrollo se guarda en instance/ (ver dev_secret_key). En producción es obligatoria
    #     (ver ProductionConfig.validate).
    SECRET_KEY = env_str("SECRET_KEY") or secrets.token_hex(32)
    ADMIN_PHONE = env_str("ADMIN_PHONE")
    ADMIN_PASSWORD = env_str("ADMIN_PASSWORD")
    DEMO_PASSWORD = env_str("DEMO_PASSWORD")  # clave de los usuarios de ejemplo (solo `flask seed` con ejemplos)

    # --- Base de datos y archivos ---
    # Vacío = SQLite en instance/campo.db (lo resuelve create_app)
    SQLALCHEMY_DATABASE_URI = env_str("DATABASE_URL") or None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLITE_WAL = env_bool("SQLITE_WAL", False)  # modo WAL de SQLite (ver app/__init__.py); producción lo activa
    BACKUP_DIR = env_str("BACKUP_DIR")  # vacío = instance/backups (flask backup-db)
    BACKUP_RETENTION_DAYS = env_int("BACKUP_RETENTION_DAYS", 14)
    MAX_CONTENT_LENGTH = env_int("MAX_CONTENT_LENGTH", 40 * 1024 * 1024)
    UPLOAD_FOLDER = env_str("UPLOAD_FOLDER") or None  # por defecto app/static/uploads
    MAX_IMAGES = env_int("MAX_IMAGES", 6)
    MAX_IMAGE_BYTES = env_int("MAX_IMAGE_BYTES", 10 * 1024 * 1024)

    # --- Sitio y contacto ---
    SITE_NAME = env_str("SITE_NAME", "Campo Directo")
    SITE_REGION = env_str("SITE_REGION", "Vélez, Santander, Colombia")
    CONTACT_EMAIL = env_str("CONTACT_EMAIL", "contacto@campodirecto.example")
    CONTACT_WHATSAPP = env_str("CONTACT_WHATSAPP")  # 10 dígitos; vacío = no se muestra
    SOCIAL_FACEBOOK = env_str("SOCIAL_FACEBOOK")
    SOCIAL_INSTAGRAM = env_str("SOCIAL_INSTAGRAM")
    LEGAL_VERSION = env_str("LEGAL_VERSION", "2026-10-borrador")

    # --- Mapa: centro por defecto (lat, lng) ---
    MAP_DEFAULT_CENTER = (env_float("MAP_CENTER_LAT", 6.0139), env_float("MAP_CENTER_LNG", -73.6736))

    # --- Notificaciones y verificación ---
    NOTIFICATION_CHANNELS = env_list("NOTIFICATION_CHANNELS", "in_app")  # in_app,whatsapp,email

    # --- Correo saliente (códigos de verificación y recuperación de clave) ---
    # MAIL_BACKEND: console (desarrollo: imprime el correo en el log) | smtp (real) | memory (pruebas)
    MAIL_BACKEND = env_str("MAIL_BACKEND", "console")
    MAIL_SERVER = env_str("MAIL_SERVER")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USERNAME = env_str("MAIL_USERNAME")
    MAIL_PASSWORD = env_str("MAIL_PASSWORD")
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)  # STARTTLS (587); con puerto 465 se usa SSL directo
    MAIL_FROM = env_str("MAIL_FROM") or env_str("MAIL_USERNAME") or "no-responder@campodirecto.example"
    MAIL_TIMEOUT = env_int("MAIL_TIMEOUT", 10)

    # --- Reglas del negocio ---
    LISTING_DURATION_DAYS = env_int("LISTING_DURATION_DAYS", 30)
    EXPIRING_SOON_DAYS = env_int("EXPIRING_SOON_DAYS", 5)
    PER_PAGE = env_int("PER_PAGE", 12)
    MAX_LOGIN_ATTEMPTS = env_int("MAX_LOGIN_ATTEMPTS", 5)
    LOCKOUT_MINUTES = env_int("LOCKOUT_MINUTES", 15)
    # Anti-spam al publicar: tope de anuncios activos (más bajo las primeras horas de una cuenta nueva)
    MAX_ACTIVE_LISTINGS = env_int("MAX_ACTIVE_LISTINGS", 40)
    NEW_ACCOUNT_HOURS = env_int("NEW_ACCOUNT_HOURS", 24)
    NEW_ACCOUNT_MAX_LISTINGS = env_int("NEW_ACCOUNT_MAX_LISTINGS", 5)

    # --- Límite de peticiones por IP (Flask-Limiter) ---
    RATELIMIT_ENABLED = env_bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = env_str("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    LOGIN_RATE_LIMIT = env_str("LOGIN_RATE_LIMIT", "20 per minute")
    REGISTER_RATE_LIMIT = env_str("REGISTER_RATE_LIMIT", "10 per hour")
    REPORT_RATE_LIMIT = env_str("REPORT_RATE_LIMIT", "10 per hour")
    CONTACT_RATE_LIMIT = env_str("CONTACT_RATE_LIMIT", "10 per hour")
    VERIFY_RATE_LIMIT = env_str("VERIFY_RATE_LIMIT", "10 per hour")
    POSTER_RATE_LIMIT = env_str("POSTER_RATE_LIMIT", "60 per hour")
    PUBLISH_RATE_LIMIT = env_str("PUBLISH_RATE_LIMIT", "20 per hour")
    ACCOUNT_RATE_LIMIT = env_str("ACCOUNT_RATE_LIMIT", "10 per hour")  # exportar o eliminar la cuenta
    CONTACT_REVEAL_RATE_LIMIT = env_str("CONTACT_REVEAL_RATE_LIMIT", "40 per hour")  # ver celular / ir a WhatsApp
    RATING_RATE_LIMIT = env_str("RATING_RATE_LIMIT", "20 per hour")

    # --- Seguridad de sesión y formularios ---
    WTF_CSRF_TIME_LIMIT = None
    WTF_I18N_ENABLED = False  # usa los textos en español de WTForms (BaseForm.Meta.locales)
    # Nombres propios: dos apps Flask en localhost (otro puerto) comparten cookies y se invalidan la sesión
    SESSION_COOKIE_NAME = "campo_directo_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_NAME = "campo_directo_remember"
    REMEMBER_COOKIE_HTTPONLY = True

    # --- Logs ---
    LOG_LEVEL = env_str("LOG_LEVEL", "INFO")
    LOG_TO_FILE = env_bool("LOG_TO_FILE", False)


def dev_secret_key(path: str | None = None) -> str:
    """Clave estable para desarrollo, guardada en instance/.dev_secret_key.

    El recargador de Flask reinicia el servidor con cada cambio de código; con una clave aleatoria nueva
    cada vez, todas las sesiones se cierran y los formularios abiertos fallan por CSRF vencido."""
    path = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", ".dev_secret_key"
    )
    try:
        with open(path, encoding="utf-8") as file:
            if key := file.read().strip():
                return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(key)
    except OSError:
        pass  # sin permiso de escritura: se usa la clave de este arranque
    return key


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = env_str("SECRET_KEY") or dev_secret_key()


class TestingConfig(Config):
    """Valores fijos y públicos a propósito: solo se usan en las pruebas automáticas."""

    TESTING = True
    # En CI se puede probar contra PostgreSQL con TEST_DATABASE_URL; por defecto, SQLite en memoria
    SQLALCHEMY_DATABASE_URI = env_str("TEST_DATABASE_URL") or "sqlite://"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SECRET_KEY = "clave-solo-para-pruebas"
    ADMIN_PHONE = "3000000000"
    ADMIN_PASSWORD = "admin12345"
    DEMO_PASSWORD = "campo123"
    MAIL_BACKEND = "memory"
    NEW_ACCOUNT_HOURS = 0  # los topes anti-spam se prueban aparte, bajándolos a propósito
    MAX_ACTIVE_LISTINGS = 1000
    SQLITE_FOREIGN_KEYS = (
        True  # SQLite sí hace cumplir las llaves foráneas en pruebas: así se ven antes los errores de PostgreSQL
    )
    MAP_DEFAULT_CENTER = (6.0139, -73.6736)


class ProductionConfig(Config):
    DEBUG = False
    SQLITE_WAL = env_bool("SQLITE_WAL", True)
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    TRUST_PROXY = True
    LOG_TO_FILE = env_bool("LOG_TO_FILE", True)

    @classmethod
    def validate(cls) -> None:
        """En producción no se arranca sin SECRET_KEY propia ni con la clave de admin vacía si hay admin."""
        if not env_str("SECRET_KEY") and cls.SECRET_KEY == Config.SECRET_KEY:
            raise RuntimeError("Define SECRET_KEY en el entorno para producción.")
        if bool(cls.ADMIN_PHONE) != bool(cls.ADMIN_PASSWORD):
            raise RuntimeError("Define ADMIN_PHONE y ADMIN_PASSWORD juntos (o ninguno).")


CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}


def resolve_config(name_or_class=None):
    """Acepta un nombre ('production'), una clase de configuración o None (usa FLASK_ENV)."""
    if name_or_class is None:
        name_or_class = env_str("FLASK_ENV", "development")
    return CONFIGS.get(name_or_class, DevelopmentConfig) if isinstance(name_or_class, str) else name_or_class
