"""Comandos de Flask CLI (flask seed, create-admin, expire-listings)."""

import click
from flask import Flask, current_app

from ..extensions import db
from ..models import User
from ..services import mailer
from ..services.backup import BackupError, backup_sqlite, sqlite_path
from ..services.expiry import expire_listings
from ..services.prices import update_snapshots
from ..services.saved_searches import run_saved_searches
from ..services.seeding import SeedConfigError, seed_all
from ..utils import normalize_phone


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    @click.option("--sin-ejemplos", is_flag=True, help="No crear usuarios ni anuncios de ejemplo.")
    @click.option("--sin-extras", is_flag=True, help="Solo los pocos ejemplos básicos (sin la demo abundante).")
    def seed(sin_ejemplos: bool, sin_extras: bool) -> None:
        """Carga categorías, atributos, municipios, consejos y admin (ADMIN_PHONE/ADMIN_PASSWORD del entorno).
        Sin `--sin-ejemplos` agrega usuarios, eventos y anuncios de demostración (requiere DEMO_PASSWORD)."""
        try:
            created = seed_all(samples=not sin_ejemplos, extra=not sin_ejemplos and not sin_extras)
        except SeedConfigError as error:
            raise click.ClickException(str(error)) from None
        click.echo(f"Listo. Anuncios de ejemplo creados: {created}")
        if current_app.config.get("ADMIN_PHONE"):
            click.echo(f"Admin: {current_app.config['ADMIN_PHONE']} (clave: variable ADMIN_PASSWORD)")
        else:
            click.echo("No hay admin: define ADMIN_PHONE y ADMIN_PASSWORD, o usa `flask create-admin`.")
        if not sin_ejemplos:
            click.echo("Usuarios de ejemplo creados (clave: variable DEMO_PASSWORD).")

    @app.cli.command("create-admin")
    @click.argument("phone")
    @click.password_option()
    @click.option("--name", default="Administrador")
    def create_admin(phone: str, password: str, name: str) -> None:
        """Crea o promueve un administrador."""
        normalized = normalize_phone(phone)
        if not normalized:
            raise click.ClickException("Celular inválido (10 dígitos, empieza por 3).")
        user = User.by_phone(normalized) or User(name=name, phone=normalized)
        user.role = "admin"
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin listo: {normalized}")

    @app.cli.command("expire-listings")
    def expire_command() -> None:
        """Marca como vencidas las publicaciones activas pasadas de fecha (ejecutar con cron)."""
        click.echo(f"Publicaciones vencidas: {expire_listings()}")

    @app.cli.command("update-prices")
    def update_prices_command() -> None:
        """Recalcula los precios de referencia y guarda el histórico de hoy (ejecutar con cron, una vez al día)."""
        click.echo(f"Precios actualizados: {update_snapshots()}")

    @app.cli.command("backup-db")
    def backup_db_command() -> None:
        """Copia segura de la base SQLite a instance/backups (o BACKUP_DIR) y borra las viejas (una vez al día).
        Con PostgreSQL no hace nada: allí las copias las hace pg_dump."""
        try:
            target, removed = backup_sqlite()
        except BackupError as error:
            if sqlite_path() is None:
                click.echo(str(error))  # PostgreSQL / en memoria: se omite sin error
                return
            raise click.ClickException(str(error)) from None
        click.echo(f"Copia lista: {target} ({target.stat().st_size // 1024} KB). Copias viejas borradas: {removed}")

    @app.cli.command("test-mail")
    @click.argument("to")
    def test_mail_command(to: str) -> None:
        """Envía un correo de prueba a TO y muestra la configuración (sin la clave) y el error exacto si falla.

        Úsalo en la terminal de Coolify cuando no lleguen los códigos: `flask test-mail tucorreo@gmail.com`."""
        click.echo("\n".join(mailer.diagnose(current_app.config)))
        try:
            mailer.send_email(
                to, f"Prueba de correo · {current_app.config['SITE_NAME']}", "Si lees esto, el correo funciona."
            )
        except mailer.MailError as error:
            raise click.ClickException(f"No se pudo enviar: {error}") from None
        click.echo(f"\nListo: se pidió el envío a {to}. Revisa la bandeja de entrada y la carpeta de spam.")

    @app.cli.command("check-saved-searches")
    def check_saved_searches_command() -> None:
        """Revisa las búsquedas guardadas y crea avisos por anuncios nuevos (ejecutar con cron, p. ej. cada 30 min)."""
        click.echo(f"Avisos creados: {run_saved_searches()}")
