import pytest

from app import create_app
from app.config import ProductionConfig
from app.extensions import db


def test_health_endpoint_reports_database(client):
    response = client.get("/health")
    assert response.status_code == 200 and response.get_json() == {"status": "ok", "database": True}


def test_health_returns_503_when_database_is_down(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def broken(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("caída"))

    monkeypatch.setattr(db.session, "execute", broken)
    response = client.get("/health")
    assert response.status_code == 503 and response.get_json()["database"] is False


def test_production_requires_real_secret_key(monkeypatch):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_production_settings_are_safe(tmp_path, monkeypatch):
    class Config(ProductionConfig):
        SECRET_KEY = "una-clave-real-y-larga-para-la-prueba"
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        UPLOAD_FOLDER = str(tmp_path)
        LOG_TO_FILE = False

    app = create_app(Config)
    assert not app.debug and app.config["SESSION_COOKIE_SECURE"] and app.config["TRUST_PROXY"]
    with app.app_context():
        db.create_all()
        response = app.test_client().get("/", headers={"X-Forwarded-Proto": "https"})
        assert response.status_code == 200
        assert "max-age" in response.headers["Strict-Transport-Security"]
        assert app.test_client().get("/ruta-que-no-existe").status_code == 404
        db.drop_all()


def _root():
    import pathlib

    return pathlib.Path(__file__).resolve().parents[2]


def test_docker_image_is_ready_for_coolify():
    root = _root()
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile and "curl" in dockerfile and "gunicorn.conf.py" in dockerfile
    assert "EXPOSE 8000" in dockerfile and "requirements/prod.txt" in dockerfile
    ignore = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for secret_or_heavy in (".env", ".venv", ".git", "node_modules", "instance"):
        assert secret_or_heavy in ignore, f"{secret_or_heavy} debe estar en .dockerignore"
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes  # CRLF rompería entrypoint.sh dentro de Linux


def test_entrypoint_migrates_seeds_and_can_start_the_scheduler():
    script = (_root() / "entrypoint.sh").read_bytes()
    assert b"\r" not in script, "entrypoint.sh debe usar saltos de línea LF"
    text = script.decode("utf-8")
    assert text.startswith("#!/bin/sh") and "set -e" in text
    assert text.index("flask db upgrade") < text.index("flask seed --sin-ejemplos") < text.index('exec "$@"')
    assert "RUN_SCHEDULER" in text and "deploy/scheduler.sh" in text


def test_gunicorn_config_follows_environment(monkeypatch):
    import runpy

    path = _root() / "gunicorn.conf.py"
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    defaults = runpy.run_path(str(path))
    assert defaults["bind"] == "0.0.0.0:8000" and defaults["workers"] == 3
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    custom = runpy.run_path(str(path))
    assert custom["bind"] == "0.0.0.0:9000" and custom["workers"] == 2


def test_coolify_env_example_only_uses_variables_the_app_reads():
    import re

    root = _root()
    names = re.findall(r"^([A-Z][A-Z0-9_]+)=", (root / ".env.coolify.example").read_text(encoding="utf-8"), re.M)
    assert {"SECRET_KEY", "SQLITE_WAL", "ADMIN_PHONE", "ADMIN_PASSWORD", "MAIL_SERVER", "RUN_SCHEDULER"} <= set(names)
    assert "DATABASE_URL" not in names  # el despliegue en Coolify usa SQLite: sin esa variable
    sources = "".join(
        (root / name).read_text(encoding="utf-8")
        for name in ("app/config.py", "gunicorn.conf.py", "entrypoint.sh", "app/__init__.py")
    )
    unknown = [name for name in names if name not in sources]
    assert not unknown, f"Variables que la app no lee (¿error de escritura?): {unknown}"
    guide = (root / "DEPLOY-COOLIFY.md").read_text(encoding="utf-8")
    assert "/srv/app/static/uploads" in guide and "/srv/instance" in guide and "8000" in guide and "SQLite" in guide


def test_coolify_compose_declares_domain_and_reads_variables_from_the_ui():
    import re

    import yaml

    root = _root()
    raw = (root / "docker-compose.coolify.yml").read_text(encoding="utf-8")
    compose = yaml.safe_load(raw)
    assert list(compose["services"]) == ["app"]  # SQLite: no hay servicio de base de datos
    app = compose["services"]["app"]
    assert "env_file" not in app and "depends_on" not in app  # el archivo .env no existe en el servidor
    assert "ports" not in app and app["expose"] == ["8000"]  # el puerto lo enruta el proxy de Coolify
    env = app["environment"]
    assert "SERVICE_FQDN_APP_8000" in env  # esto es lo que hace aparecer el campo «Domains»
    pairs = dict(item.split("=", 1) for item in env if "=" in item)
    assert pairs["FLASK_ENV"] == "production" and pairs["PORT"] == "8000"
    assert "DATABASE_URL" not in pairs and pairs["SQLITE_WAL"] == "true"
    assert pairs["ADMIN_PHONE"].startswith("${ADMIN_PHONE:?") and pairs["ADMIN_PASSWORD"].startswith(
        "${ADMIN_PASSWORD:?"
    )
    assert pairs["SECRET_KEY"] == "${SERVICE_PASSWORD_64_FLASKSECRET}"
    # La base (campo.db) y las fotos viven en volúmenes: sin ellos se pierden en cada despliegue
    assert "data:/srv/instance" in app["volumes"] and "uploads:/srv/app/static/uploads" in app["volumes"]
    assert set(compose["volumes"]) == {"data", "uploads"} and "healthcheck" in app

    sources = "".join(
        (root / name).read_text(encoding="utf-8")
        for name in ("app/config.py", "gunicorn.conf.py", "entrypoint.sh", "app/__init__.py")
    )
    names = [item.split("=", 1)[0] for item in env if "=" in item]
    unknown = [name for name in names if name not in sources and name != "PORT"]
    assert not unknown, f"Variables que la app no lee: {unknown}"
    assert re.search(r"docker-compose\.coolify\.yml", (root / "DEPLOY-COOLIFY.md").read_text(encoding="utf-8"))


def test_ssh_deploy_job_is_opt_in_so_coolify_users_get_no_red_builds():
    workflow = (_root() / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "vars.USE_SSH_DEPLOY == 'true'" in workflow


def test_deploy_files_exist_and_reference_each_other():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.prod.yml").read_text(encoding="utf-8")
    for needed in ("nginx", "certbot", "backup", "scheduler", "postgres:16", "healthcheck"):
        assert needed in compose
    for path in ("deploy/backup.sh", "deploy/scheduler.sh", "deploy/init-letsencrypt.sh",
                 "deploy/nginx/default.conf.template", "deploy/nginx/Dockerfile", "DEPLOY.md",
                 ".env.production.example"):  # fmt: skip
        assert (root / path).exists(), path
    env = (root / ".env.production.example").read_text(encoding="utf-8")
    assert "SECRET_KEY" in env and "DOMAIN" in env and "POSTGRES_PASSWORD" in env
