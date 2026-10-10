import pytest

from app import create_app
from app.config import (
    ProductionConfig,
    TestingConfig,
    dev_secret_key,
    env_bool,
    env_float,
    env_int,
    env_list,
    env_str,
)
from app.extensions import db
from app.models import Listing, User
from app.services import seeding


def test_env_helpers_parse_and_default(monkeypatch):
    monkeypatch.setenv("X_INT", "7")
    monkeypatch.setenv("X_FLOAT", "6,5")
    monkeypatch.setenv("X_BOOL", "Sí")
    monkeypatch.setenv("X_LIST", " a, b ,,c ")
    monkeypatch.setenv("X_STR", "  hola  ")
    assert env_int("X_INT", 1) == 7 and env_int("X_MISSING", 3) == 3
    assert env_float("X_FLOAT", 0) == 6.5 and env_float("X_MISSING", 1.5) == 1.5
    assert env_bool("X_BOOL") is True and env_bool("X_MISSING", True) is True
    monkeypatch.setenv("X_BOOL", "no")
    assert env_bool("X_BOOL", True) is False
    assert env_list("X_LIST") == ["a", "b", "c"] and env_list("X_MISSING", "in_app") == ["in_app"]
    assert env_str("X_STR") == "hola"


def test_dev_secret_key_is_stable_across_restarts(tmp_path):
    path = str(tmp_path / "instance" / ".dev_secret_key")
    first = dev_secret_key(path)
    assert len(first) == 64 and dev_secret_key(path) == first  # el reinicio no cambia la clave
    assert dev_secret_key(str(tmp_path / "otra")) != first


def test_invalid_numbers_fail_with_clear_message(monkeypatch):
    monkeypatch.setenv("X_INT", "abc")
    with pytest.raises(RuntimeError, match="X_INT"):
        env_int("X_INT", 1)
    monkeypatch.setenv("X_FLOAT", "uno")
    with pytest.raises(RuntimeError, match="X_FLOAT"):
        env_float("X_FLOAT", 1.0)


def test_settings_come_from_environment(monkeypatch):
    import importlib

    import app.config as config

    monkeypatch.setenv("LISTING_DURATION_DAYS", "45")
    monkeypatch.setenv("SITE_REGION", "Boyacá, Colombia")
    monkeypatch.setenv("MAP_CENTER_LAT", "5.5")
    monkeypatch.setenv("MAP_CENTER_LNG", "-73.3")
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "3 per minute")
    monkeypatch.setenv("NOTIFICATION_CHANNELS", "in_app,whatsapp")
    reloaded = importlib.reload(config)
    try:
        cfg = reloaded.Config
        assert cfg.LISTING_DURATION_DAYS == 45 and cfg.SITE_REGION == "Boyacá, Colombia"
        assert cfg.MAP_DEFAULT_CENTER == (5.5, -73.3) and cfg.LOGIN_RATE_LIMIT == "3 per minute"
        assert cfg.NOTIFICATION_CHANNELS == ["in_app", "whatsapp"]
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_no_default_secrets_in_base_config(monkeypatch):
    import importlib

    import app.config as config

    for name in ("SECRET_KEY", "ADMIN_PASSWORD", "ADMIN_PHONE", "DEMO_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    reloaded = importlib.reload(config)
    try:
        assert reloaded.Config.ADMIN_PASSWORD == "" and reloaded.Config.DEMO_PASSWORD == ""
        assert reloaded.Config.ADMIN_PHONE == ""
        assert len(reloaded.Config.SECRET_KEY) == 64  # generada al iniciar, nunca fija en el código
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_production_needs_secret_key_and_admin_pair(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")

    class NoPassword(ProductionConfig):
        SECRET_KEY = "x" * 40
        ADMIN_PHONE = "3000000001"
        ADMIN_PASSWORD = ""

    with pytest.raises(RuntimeError, match="ADMIN_PHONE y ADMIN_PASSWORD"):
        create_app(NoPassword)


def test_seed_without_samples_creates_no_demo_accounts(tmp_path):
    class Config(TestingConfig):
        UPLOAD_FOLDER = str(tmp_path)

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        assert seeding.seed_all(samples=False) == 0
        phones = {u.phone for u in User.query.all()}
        assert phones == {"3000000000"}  # solo el admin configurado
        assert Listing.query.count() == 0
        db.drop_all()


def test_demo_users_require_demo_password(tmp_path):
    class Config(TestingConfig):
        UPLOAD_FOLDER = str(tmp_path)
        DEMO_PASSWORD = ""

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        with pytest.raises(seeding.SeedConfigError, match="DEMO_PASSWORD"):
            seeding.seed_all(samples=True)
        result = app.test_cli_runner().invoke(args=["seed"])
        assert result.exit_code != 0 and "DEMO_PASSWORD" in result.output
        db.drop_all()


def test_admin_is_skipped_when_not_configured(tmp_path):
    class Config(TestingConfig):
        UPLOAD_FOLDER = str(tmp_path)
        ADMIN_PHONE = ""
        ADMIN_PASSWORD = ""

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        assert seeding.seed_admin() is False and User.query.count() == 0
        db.drop_all()


def test_pages_use_site_region_from_config(client, app):
    app.config["SITE_REGION"] = "Región de Prueba"
    assert "Región de Prueba" in client.get("/").get_data(as_text=True)
    assert "Región de Prueba" in client.get("/quienes-somos").get_data(as_text=True)
    assert "Vélez, Santander" not in client.get("/quienes-somos").get_data(as_text=True)
