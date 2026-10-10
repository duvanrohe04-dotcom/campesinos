from app.extensions import db
from app.models import AttributeDef, Category, ContactMessage, Listing, Municipality, Report, User, Village

from ..conftest import login

ADMIN_PAGES = ("/admin/", "/admin/usuarios", "/admin/anuncios", "/admin/reportes", "/admin/mensajes",
               "/admin/categorias", "/admin/municipios", "/estilos")  # fmt: skip


def test_admin_permissions(client):
    assert client.get("/admin/").status_code == 302  # anónimo → login
    login(client, "3101112233")
    assert client.get("/admin/").status_code == 403
    assert client.get("/estilos").status_code == 403


def test_admin_pages_render(admin):
    for path in ADMIN_PAGES:
        assert admin.get(path).status_code == 200, path


def test_admin_moderates_listing_and_users(admin):
    listing = Listing.query.first()
    admin.post(f"/admin/anuncios/{listing.id}/retirar")
    db.session.refresh(listing)
    assert listing.status == "removed"
    admin.post(f"/admin/anuncios/{listing.id}/restaurar")
    db.session.refresh(listing)
    assert listing.status == "active"
    assert admin.post(f"/admin/anuncios/{listing.id}/inventar").status_code == 404

    seller = User.by_phone("3112223344")
    admin.post(f"/admin/usuarios/{seller.id}/estado")
    db.session.refresh(seller)
    assert not seller.is_enabled
    assert Listing.query.filter_by(user_id=seller.id, status="active").count() == 0
    me = User.by_phone("3000000000")
    admin.post(f"/admin/usuarios/{me.id}/estado")
    assert db.session.get(User, me.id).is_enabled  # no puede desactivarse a sí mismo


def test_admin_resolves_reports(admin):
    listing = Listing.query.first()
    db.session.add(Report(listing_id=listing.id, reason="fraude"))
    db.session.commit()
    report = Report.query.first()
    admin.post(f"/admin/reportes/{report.id}/retirar")
    db.session.refresh(listing)
    db.session.refresh(report)
    assert listing.status == "removed" and report.status == "reviewed"


def test_admin_manages_categories_and_attributes(admin):
    response = admin.post(
        "/admin/categorias/nueva",
        data={"name": "Pescado fresco", "icon": "campo", "price_units": "kilo, libra", "is_active": "y"},
    )
    assert response.status_code == 302
    category = Category.query.filter_by(slug="pescado-fresco").one()
    assert category.price_units == ["kilo", "libra"]
    assert "Ya existe" in admin.post("/admin/categorias/nueva", data={"name": "Pescado fresco"}).get_data(as_text=True)

    response = admin.post(f"/admin/categorias/{category.id}/atributos/nuevo",
                          data={"label": "Especie", "type": "choice", "choices": "Tilapia, Cachama",
                                "is_filterable": "y"})  # fmt: skip
    assert response.status_code == 302
    attr = AttributeDef.query.filter_by(category_id=category.id, key="especie").one()
    assert attr.choices == ["Tilapia", "Cachama"] and attr.is_filterable
    html = admin.post(
        f"/admin/categorias/{category.id}/atributos/nuevo",
        data={"label": "Otra", "type": "choice", "choices": "solo una"},
    ).get_data(as_text=True)
    assert "al menos 2 opciones" in html

    assert (
        admin.post(f"/admin/atributos/{attr.id}/editar", data={"label": "Especie nueva", "type": "text"}).status_code
        == 302
    )
    assert db.session.get(AttributeDef, attr.id).label == "Especie nueva"
    admin.post(f"/admin/atributos/{attr.id}/eliminar")
    assert db.session.get(AttributeDef, attr.id) is None
    admin.post(f"/admin/categorias/{category.id}/eliminar")
    assert db.session.get(Category, category.id) is None


def test_admin_cannot_delete_category_in_use(admin):
    category = Category.root_by_slug("bovinos")
    admin.post(f"/admin/categorias/{category.id}/eliminar")
    assert db.session.get(Category, category.id) is not None


def test_admin_geography(admin):
    admin.post("/admin/municipios", data={"name": "Nuevo Pueblo", "department": "Santander"})
    municipality = Municipality.query.filter_by(slug="nuevo-pueblo").one()
    admin.post(f"/admin/municipios/{municipality.id}", data={"name": "La Loma"})
    village = Village.query.filter_by(municipality_id=municipality.id, name="La Loma").one()
    admin.post(f"/admin/veredas/{village.id}/eliminar")
    assert db.session.get(Village, village.id) is None
    used = Village.query.filter(Village.id.in_(db.session.query(Listing.village_id))).first()
    admin.post(f"/admin/veredas/{used.id}/eliminar")
    assert db.session.get(Village, used.id) is not None  # en uso: no se elimina


def test_contact_messages_reach_admin(client):
    bad = client.post(
        "/contacto",
        data={"name": "Ana", "contact": "no-valido", "subject": "ayuda", "message": "Necesito ayuda con mi cuenta"},
    )
    assert "celular de 10 números" in bad.get_data(as_text=True) and ContactMessage.query.count() == 0
    ok = client.post(
        "/contacto",
        data={
            "name": "Ana",
            "contact": "3101234567",
            "subject": "datos",
            "message": "Quiero actualizar mis datos personales",
        },
    )
    assert ok.status_code == 302 and ContactMessage.query.count() == 1
    login(client, "3000000000", "admin12345")
    assert "actualizar mis datos" in client.get("/admin/mensajes").get_data(as_text=True)
    message = ContactMessage.query.first()
    client.post(f"/admin/mensajes/{message.id}/leido")
    db.session.refresh(message)
    assert message.status == "read"
