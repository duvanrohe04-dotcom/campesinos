"""Un recorrido de punta a punta por cada flujo importante, tal como lo haría una persona.

Flujos: 1 registrarse, verificar y completar perfil · 2 publicar, editar, pausar, renovar y vender ·
3 buscar, filtrar, mapa, favorito y contactar · 4 guardar búsqueda y recibir alerta · 6 reportar, moderar y bloquear.
El flujo 7 (recuperar contraseña) está en test_password_recovery.py.
El flujo 5 (encargos) no se prueba porque esa función todavía no existe en la plataforma.
"""

import re

from app.extensions import db
from app.models import Category, Listing, Municipality, Notification, User
from app.services import mailer, saved_searches
from app.services.attributes import defs_for

from ..conftest import login, png_bytes, url_of

BUYER = "3134445566"
SELLER = "3101112233"


def velez_id() -> int:
    return Municipality.query.filter_by(slug="velez").one().id


def listing_data(root_slug: str, title: str, ad_type: str = "vendo", **overrides) -> dict:
    """Formulario válido para la primera subcategoría de una categoría, llenando sus datos obligatorios."""
    category = Category.root_by_slug(root_slug).active_children[0]
    data = {
        "ad_type": ad_type,
        "category_id": category.id,
        "title": title,
        "description": "Prueba de punta a punta.",
        "price": "" if ad_type == "compro" else "150.000",
        "price_unit": category.units[0],
        "quantity": "2",
        "municipality_id": velez_id(),
    }
    for definition in defs_for(category):
        if definition.required:
            data[f"attr_{definition.key}"] = (definition.choices or ["10"])[0]
    return {**data, **overrides}


def publish(client, data: dict, photo: bool = False):
    if photo:
        data = {**data, "photos": (png_bytes(), "foto.png")}
    return client.post("/publicar", data=data, content_type="multipart/form-data")


def listing_titled(title: str) -> Listing:
    return Listing.query.filter_by(title=title).one()


# ---------- 1. Registrarse, verificar el correo y completar el perfil ----------
def test_flow_register_verify_and_complete_profile(client):
    mailer.outbox.clear()
    register = client.post(
        "/registro",
        data={
            "name": "Rosa Pérez", "phone": "3157771122", "password": "secreto1", "email": "rosa@example.com",
            "municipality_id": velez_id(), "village_id": "0", "village_other": "La Palma", "accept_terms": "y",
        },
    )  # fmt: skip
    assert register.headers["Location"].endswith("/verificar-correo")
    rosa = User.by_phone("3157771122")
    assert rosa.village_other == "La Palma" and not rosa.email_verified

    code = re.search(r"\b(\d{6})\b", mailer.outbox[-1].body).group(1)
    assert client.post("/verificar-correo", data={"code": code}).headers["Location"].endswith("/panel")
    assert db.session.get(User, rosa.id).email_verified

    profile = client.post(
        "/panel/perfil",
        data={
            "name": "Rosa Pérez", "farm_name": "Finca El Mirador", "bio": "Cultivo guayaba hace 10 años.",
            "email": "rosa@example.com", "municipality_id": velez_id(),
        },
    )  # fmt: skip
    assert profile.status_code == 302 and profile.headers["Location"].endswith("/panel")
    assert db.session.get(User, rosa.id).email_verified  # el mismo correo no pide verificar de nuevo
    public = client.get(f"/vendedor/{rosa.id}").get_data(as_text=True)
    assert "Finca El Mirador" in public and "Correo verificado" in public and "Cultivo guayaba" in public


# ---------- 2. Publicar cualquier tipo, editar, pausar, renovar, vender ----------
def test_flow_publish_every_kind_and_manage_it(seller):
    kinds = {
        "producto": ("agricolas", "vendo"),
        "animal": ("bovinos", "vendo"),
        "servicio": ("servicios", "vendo"),
        "maquinaria": ("maquinaria", "vendo"),
        "compro": ("insumos", "compro"),
    }
    for kind, (root, ad_type) in kinds.items():
        response = publish(seller, listing_data(root, f"Flujo {kind} completo", ad_type), photo=kind == "animal")
        assert response.status_code == 302 and response.headers["Location"].endswith("/listo"), kind
    animal = listing_titled("Flujo animal completo")
    assert animal.images and listing_titled("Flujo compro completo").ad_type == "compro"
    assert "Flujo servicio completo" in seller.get("/panel").get_data(as_text=True)

    edit_url = f"/panel/anuncio/{animal.id}/editar"
    assert "Flujo animal completo" in seller.get(edit_url).get_data(as_text=True)
    edited = seller.post(edit_url, data={**listing_data("bovinos", "Flujo animal editado"), "price": "200.000"})
    assert edited.headers["Location"].endswith("/panel")
    db.session.refresh(animal)
    assert animal.title == "Flujo animal editado" and animal.price == 200000

    assert seller.get(url_of(animal)).status_code == 200
    seller.post(f"/panel/anuncio/{animal.id}/pausar")
    db.session.refresh(animal)
    assert animal.status == "paused"
    seller.post("/salir")
    assert seller.get(url_of(animal)).status_code == 410  # un visitante ve que ya no está disponible
    login(seller, SELLER)
    seller.post(f"/panel/anuncio/{animal.id}/activar")
    seller.post(f"/panel/anuncio/{animal.id}/renovar")
    db.session.refresh(animal)
    assert animal.status == "active" and animal.renewed_at
    seller.post(f"/panel/anuncio/{animal.id}/vendido")
    db.session.refresh(animal)
    assert animal.status == "sold"
    seller.post(f"/panel/anuncio/{animal.id}/eliminar")
    assert db.session.get(Listing, animal.id) is None


# ---------- 3. Buscar, filtrar, mapa, favorito y contactar ----------
def test_flow_search_filter_map_favorite_and_contact(client):
    login(client, BUYER)
    results = client.get("/anuncios", query_string={"q": "novillo"}).get_data(as_text=True)
    assert "Novillo cebú" in results
    filtered = client.get("/anuncios", query_string={"cat": "bovinos", "mun": velez_id(), "pmax": "10000000"})
    assert filtered.status_code == 200 and "Ganado bovino" in filtered.get_data(as_text=True)
    nothing = client.get("/anuncios", query_string={"q": "zzzzzz-no-existe"}).get_data(as_text=True)
    assert "No encontramos anuncios" in nothing

    assert client.get("/anuncios/mapa", query_string={"cat": "bovinos"}).status_code == 200
    points = client.get("/anuncios/mapa.json", query_string={"cat": "bovinos"}).get_json()["points"]
    assert points and all({"lat", "lng", "title", "url"} <= set(p) for p in points)

    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    detail = url_of(listing)
    assert "Guardar en favoritos" in client.get(detail).get_data(as_text=True)
    client.post(f"/favoritos/{listing.id}", data={"next": detail})
    assert "Novillo cebú" in client.get("/favoritos").get_data(as_text=True)
    assert "Quitar de favoritos" in client.get(detail).get_data(as_text=True)

    whatsapp = client.get(f"/anuncio/{listing.id}/whatsapp")
    assert whatsapp.status_code == 302 and whatsapp.headers["Location"].startswith("https://wa.me/57")
    assert listing.user.phone in client.get(f"/anuncio/{listing.id}/contacto").get_data(as_text=True)
    db.session.refresh(listing)
    assert listing.whatsapp_clicks == 1 and listing.call_clicks == 1


# ---------- 4. Guardar una búsqueda y recibir la alerta ----------
def test_flow_saved_search_alerts_the_buyer(client):
    login(client, BUYER)
    client.post("/busquedas-guardadas/guardar", data={"query": f"sub=cerdos-de-engorde&mun={velez_id()}&pmax=900000"})
    assert "Cerdos de engorde" in client.get("/busquedas-guardadas").get_data(as_text=True)
    client.post("/salir")

    login(client, SELLER)
    pigs = Category.sub_by_slug("cerdos-de-engorde")
    pig = {**listing_data("porcinos", "Cerdos para la alerta", category_id=pigs.id, price="800.000")}
    pig["price_unit"] = pigs.units[0]
    assert publish(client, pig).status_code == 302
    expensive = {**pig, "title": "Cerdos demasiado caros", "price": "2.000.000"}
    assert publish(client, expensive).status_code == 302
    client.post("/salir")

    assert saved_searches.run_saved_searches() == 1  # solo el que cumple el precio
    login(client, BUYER)
    inbox = client.get("/notificaciones").get_data(as_text=True)
    assert "Cerdos para la alerta" in inbox and "Cerdos demasiado caros" not in inbox
    note = Notification.query.filter_by(user_id=User.by_phone(BUYER).id).one()
    opened = client.get(f"/notificaciones/{note.id}/abrir")
    assert opened.status_code == 302 and "cerdos-para-la-alerta" in opened.headers["Location"]
    assert saved_searches.run_saved_searches() == 0  # no repite el mismo aviso


# ---------- 6. Reportar, moderar y bloquear ----------
def test_flow_report_moderate_and_block(client):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    seller_phone = listing.user.phone
    login(client, BUYER)
    sent = client.post(f"/anuncio/{listing.id}/reportar", data={"reason": "fraude", "detail": "Pide dinero antes"})
    assert sent.status_code == 302
    client.post("/salir")

    login(client, "3000000000", "admin12345")
    queue = client.get("/admin/reportes").get_data(as_text=True)
    assert "Pide dinero antes" in queue
    from app.models import Report

    report = Report.query.one()
    client.post(f"/admin/reportes/{report.id}/retirar")
    db.session.refresh(listing)
    assert listing.status == "removed"

    owner = listing.user
    client.post(f"/admin/usuarios/{owner.id}/estado")
    db.session.refresh(owner)
    assert not owner.is_enabled
    assert Listing.query.filter_by(user_id=owner.id, status="active").count() == 0
    client.post("/salir")
    assert client.get(url_of(listing)).status_code == 404  # retirado: ni siquiera se sabe que existió

    blocked = client.post("/ingresar", data={"phone": seller_phone, "password": "campo123"})
    assert "cuenta está suspendida" in blocked.get_data(as_text=True)
    assert client.get("/panel").status_code == 302  # sigue sin sesión
