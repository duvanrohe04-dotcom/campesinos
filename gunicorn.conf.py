"""Configuración de Gunicorn para producción (Docker / Coolify). Todo se puede ajustar con variables de entorno."""

import os

# Coolify y la mayoría de plataformas indican el puerto con PORT; por defecto 8000.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "3"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))  # generar un cartel PDF puede tardar unos segundos
accesslog = "-"
errorlog = "-"
# Detrás del proxy (Traefik en Coolify, Nginx en el VPS): confía en X-Forwarded-* para saber que la conexión es https.
forwarded_allow_ips = "*"
