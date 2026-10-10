from flask import abort, jsonify, render_template, request

from . import bp, services


@bp.route("/precios")
def index():
    data = services.price_index(request.args.get("cat"))
    return render_template("prices/index.html", roots=data.roots, selected=data.selected, rows=data.rows)


@bp.route("/precios/referencia")
def reference():
    """Precio de referencia en JSON liviano: lo consulta el formulario de publicar."""
    summary, scope = services.reference_for_form(
        request.args.get("categoria", ""), request.args.get("unidad", ""), request.args.get("municipio", "")
    )
    if not summary:
        return jsonify(available=False)
    return jsonify(
        available=True,
        scope=scope,
        average=summary.average,
        minimum=summary.minimum,
        maximum=summary.maximum,
        sample_size=summary.sample_size,
    )


@bp.route("/precios/<slug>")
def detail(slug):
    data = services.price_detail(slug, request.args.get("unidad"))
    if not data:
        abort(404)
    return render_template("prices/detail.html", d=data)
