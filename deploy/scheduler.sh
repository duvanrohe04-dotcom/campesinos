#!/bin/sh
# Tareas programadas de la aplicación (reemplaza al cron del servidor).
#  - Cada hora: vence los anuncios pasados de fecha.
#  - Cada 30 minutos: revisa búsquedas guardadas y crea avisos.
export FLASK_APP=wsgi.py
cd /srv

minute=0
while true; do
  flask check-saved-searches || echo "[$(date)] ERROR en check-saved-searches"
  if [ $((minute % 60)) -eq 0 ]; then
    flask expire-listings || echo "[$(date)] ERROR en expire-listings"
  fi
  if [ $((minute % 1440)) -eq 0 ]; then
    flask update-prices || echo "[$(date)] ERROR en update-prices"
    flask backup-db || echo "[$(date)] ERROR en backup-db"  # SQLite: copia diaria; con PostgreSQL no hace nada
  fi
  minute=$((minute + 30))
  sleep 1800
done
