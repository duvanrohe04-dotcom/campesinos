from app.models import Category, Municipality
from app.services import prices

from ..conftest import login
from ..unit.test_prices import add_prices


def test_empty_state_before_any_snapshot(client):
    html = client.get("/precios").get_data(as_text=True)
    assert "Aún no hay suficientes anuncios" in html


def test_prices_page_detail_and_filters_after_update(client, app):
    add_prices([700000, 720000, 740000, 760000])
    app.test_cli_runner().invoke(args=["update-prices"])
    html = client.get("/precios").get_data(as_text=True)
    assert "Lechones" in html and "730.000" in html
    assert "Lechones" in client.get("/precios?cat=porcinos").get_data(as_text=True)
    assert "Aún no hay" in client.get("/precios?cat=bovinos").get_data(as_text=True)
    detail = client.get("/precios/lechones?unidad=animal").get_data(as_text=True)
    assert "$ 730.000" in detail and 'id="trend-data"' in detail and "Publicar el mío" in detail
    assert client.get("/precios/no-existe").status_code == 404
    assert "Todavía no hay precio" in client.get("/precios/novillos").get_data(as_text=True)


def test_reference_endpoint_for_publish_form(client):
    add_prices([700000, 720000, 740000], municipality="velez")
    category = Category.sub_by_slug("lechones")
    velez = Municipality.query.filter_by(slug="velez").one()
    data = client.get(
        "/precios/referencia", query_string={"categoria": category.id, "unidad": "animal", "municipio": velez.id}
    ).get_json()
    assert data["available"] and data["average"] == 720000 and data["scope"] == "municipio"
    assert client.get("/precios/referencia", query_string={"categoria": "x"}).get_json() == {"available": False}
    assert client.get("/precios/referencia", query_string={"categoria": category.id, "unidad": "kilo"}).get_json() == {
        "available": False
    }


def test_publish_form_includes_reference_hint_and_nav_links(client):
    login(client, "3101112233")
    form = client.get("/publicar").get_data(as_text=True)
    assert 'id="price-reference"' in form and "/precios/referencia" in form
    home = client.get("/").get_data(as_text=True)
    assert "/precios" in home and "Precios del campo" in home


def test_update_prices_command_output(app):
    add_prices([100000, 110000, 120000])
    result = app.test_cli_runner().invoke(args=["update-prices"])
    assert "Precios actualizados: 1" in result.output and prices.latest_rows()
