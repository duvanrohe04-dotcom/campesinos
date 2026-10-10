"""Servidor de desarrollo: python run.py (en producción se usa wsgi.py con gunicorn)."""

import os
import socket

from wsgi import app


def lan_ip() -> str | None:
    """IP de este computador en la red local, para abrir el sitio desde otro celular. None si no hay red."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))  # no envía nada: solo deja que el sistema elija la tarjeta de red
            return probe.getsockname()[0]
    except OSError:
        return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":  # el recargador arranca dos veces: avisa una sola
        app.logger.info("En este computador: http://localhost:%s", port)
        if ip := lan_ip():
            app.logger.info("Desde otro celular en la misma red Wi-Fi (usa http, no https): http://%s:%s", ip, port)
    app.run(debug=True, host="0.0.0.0", port=port)
