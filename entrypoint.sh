#!/bin/sh
set -e
export FLASK_APP=wsgi.py
export FLASK_ENV=${FLASK_ENV:-production}

# Espera a que PostgreSQL acepte conexiones y aplica migraciones
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
if url:
    for _ in range(30):
        try:
            create_engine(url).connect().execute(text("select 1")); break
        except Exception:
            time.sleep(1)
PY
flask db upgrade
# Datos base (categorías, municipios, admin). Es idempotente.
flask seed --sin-ejemplos

# Tareas programadas (vencer anuncios, avisos de búsquedas guardadas, precios) dentro de este mismo contenedor.
# Con RUN_SCHEDULER=false no se inician (úsalo si el contenedor corre en varias réplicas o si hay un servicio aparte).
if [ "${RUN_SCHEDULER:-true}" = "true" ] && [ -f /srv/deploy/scheduler.sh ]; then
  sh /srv/deploy/scheduler.sh &
fi

exec "$@"
