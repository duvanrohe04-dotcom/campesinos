from sqlalchemy import event

from app.extensions import db
from app.models import Listing, User

from ..conftest import login, url_of


def count_queries(client, path, method="get"):
    statements = []

    def before(_conn, _cursor, statement, *_args):
        statements.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", before)
    try:
        response = getattr(client, method)(path)
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return response, len(statements)


# Techo de consultas por página. Si alguien introduce un N+1 estas pruebas fallan.
PAGES = {"/": 20, "/anuncios": 20, "/anuncios?cat=bovinos": 22, "/favoritos": 20, "/panel": 25}


def test_pages_do_not_have_n_plus_one_queries(client):
    login(client, "3101112233")
    for path, ceiling in PAGES.items():
        response, queries = count_queries(client, path)
        assert response.status_code == 200, path
        assert queries <= ceiling, f"{path} hizo {queries} consultas (máx. {ceiling})"


def test_listing_page_queries_do_not_grow_with_more_listings(client):
    _, before = count_queries(client, "/anuncios")
    template = Listing.query.first()
    for i in range(10):
        clone = Listing(
            user_id=template.user_id,
            category_id=template.category_id,
            title=f"Anuncio extra {i}",
            price=1000,
            price_unit="kilo",
            attrs={},
            municipality_id=template.municipality_id,
            village_id=template.village_id,
        )
        clone.set_expiry()
        db.session.add(clone)
    db.session.commit()
    _, after = count_queries(client, "/anuncios")
    assert after <= before + 1


def test_detail_page_query_budget(client):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    response, queries = count_queries(client, url_of(listing))
    assert response.status_code == 200 and queries <= 30


def test_403_page_and_forbidden_for_non_admin(client):
    login(client, "3101112233")
    response = client.get("/admin/")
    assert response.status_code == 403 and "No tienes permiso" in response.get_data(as_text=True)


def test_500_page_rolls_back_and_hides_details(app):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.testing = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("secreto interno")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert "Algo salió mal" in html and "secreto interno" not in html


def test_create_admin_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "311 000 1122", "--name", "Nueva Admin"], input="clave-segura\nclave-segura\n"
    )
    assert "Admin listo: 3110001122" in result.output
    admin = User.by_phone("3110001122")
    assert admin.is_admin and admin.check_password("clave-segura")
    bad = runner.invoke(args=["create-admin", "123"], input="x\nx\n")
    assert bad.exit_code != 0 and "Celular inválido" in bad.output


def test_seed_command_is_idempotent(app):
    runner = app.test_cli_runner()
    basic = Listing.query.count()
    first = runner.invoke(args=["seed"])  # agrega la demo abundante (los datos básicos ya estaban)
    assert first.exit_code == 0 and Listing.query.count() > basic
    after_first = Listing.query.count()
    second = runner.invoke(args=["seed"])
    assert second.exit_code == 0 and Listing.query.count() == after_first  # repetirlo no duplica
    only_basic = runner.invoke(args=["seed", "--sin-extras"])
    assert only_basic.exit_code == 0 and Listing.query.count() == after_first


def test_security_headers_present(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff" and headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Referrer-Policy" in headers
