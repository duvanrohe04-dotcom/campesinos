# --- Etapa 1: compilar Tailwind (CSS) ---
FROM node:20-alpine AS css
WORKDIR /build
COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci
COPY app/static/src app/static/src
COPY app/templates app/templates
COPY app/static/js app/static/js
RUN npm run build:css

# --- Etapa 2: aplicación ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv
# curl: lo usa el chequeo de salud de Coolify
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt
COPY . .
COPY --from=css /build/app/static/css/app.css app/static/css/app.css
RUN chmod +x entrypoint.sh && mkdir -p app/static/uploads instance
EXPOSE 8000
# Da tiempo a que corran las migraciones al arrancar
HEALTHCHECK --interval=30s --timeout=6s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
