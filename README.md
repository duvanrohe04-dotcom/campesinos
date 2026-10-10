# Campo Directo

Marketplace rural para campesinos de la provincia de Vélez (Santander, Colombia), pensado para crecer a cualquier región.
Conecta vendedores y compradores por WhatsApp o llamada. No hay pagos en línea.

**Stack:** Flask (monolito, plantillas Jinja2) · SQLAlchemy · Flask-Migrate · Flask-Login · Flask-WTF · Flask-Limiter · Tailwind CSS · Pillow · Gunicorn.
Base de datos: **SQLite** en local (por defecto) y **PostgreSQL** en Docker/producción.

> Convenciones de código, estructura y comandos para quien siga desarrollando: ver [CLAUDE.md](CLAUDE.md).
> Puesta en producción: con **Coolify** ver [DEPLOY-COOLIFY.md](DEPLOY-COOLIFY.md); en un VPS con Docker Compose ver [DEPLOY.md](DEPLOY.md).

## Correr en local (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt   # requirements/dev.txt
copy .env.example .env                                       # y edita SECRET_KEY
.\.venv\Scripts\python -m flask db upgrade
.\.venv\Scripts\python -m flask seed
.\.venv\Scripts\python run.py                                # http://localhost:5000
```

`flask seed` carga categorías, atributos, municipios de la provincia de Vélez, usuarios y 13 anuncios de ejemplo.

| Usuario | Celular | Clave |
|---|---|---|
| Admin | `ADMIN_PHONE` del `.env` (3000000000) | `ADMIN_PASSWORD` del `.env` |
| Vendedores de ejemplo | 3101112233 (verificado), 3112223344, 3123334455 | `campo123` |
| Comprador de ejemplo | 3134445566 | `campo123` |

> Las **veredas** del seed son ejemplos genéricos. Complétalas con las reales desde **Admin → Municipios**.
> El código de verificación de celular se escribe en la consola del servidor (proveedor `console`) hasta que se integre WhatsApp/SMS.

## Estilos (Tailwind)
El CSS compilado `app/static/css/app.css` va en el repo. Para modificar el diseño:

```powershell
npm install
npm run watch:css     # o: npm run build:css
```
Paleta y tipografía en `tailwind.config.js`; componentes en `app/templates/components/`; guía visual en `/estilos` (solo admin).

## Pruebas y calidad

```powershell
.\.venv\Scripts\python -m pytest --cov=app        # ~120 pruebas, cobertura ~96 %
.\.venv\Scripts\python -m ruff check app tests    # lint + orden de imports
.\.venv\Scripts\python -m black app tests         # formato
pre-commit install                                # ruff + black + archivos grandes en cada commit
```

## Docker

```bash
cp .env.example .env     # define SECRET_KEY, POSTGRES_PASSWORD y ADMIN_PASSWORD
docker compose up --build                                    # desarrollo: http://localhost:8000
docker compose -f docker-compose.prod.yml up -d --build      # producción: ver DEPLOY.md
```

## Comandos útiles

```powershell
.\.venv\Scripts\python -m flask expire-listings          # vence anuncios (>30 días) — cron/Tareas de Windows
.\.venv\Scripts\python -m flask check-saved-searches     # crea avisos de búsquedas guardadas — cada 30 min
.\.venv\Scripts\python -m flask create-admin 3001234567  # crear/promover admin
.\.venv\Scripts\python -m flask db migrate -m "mensaje"  # nueva migración tras cambiar modelos
```

## Qué incluye

- **Publicar por pasos** (categoría con tarjetas, fotos desde cámara o galería con compresión, orden y foto principal, borrador automático, duplicar anuncio, pantalla final para compartir por WhatsApp).
- **Datos específicos por categoría** administrables (JSON + `attribute_defs`), filtrables en el listado.
- **Listado** con filtros desplegables (móvil) / barra lateral (escritorio), chips eliminables, orden y paginación; **detalle** con galería con swipe y barra fija de WhatsApp/Llamar.
- **Confianza:** verificación de celular por código, insignia «Vendedor verificado» (admin), calificaciones con moderación, perfil con antigüedad/ventas/calificación y página «Consejos para comprar seguro».
- **Alertas:** búsquedas guardadas y centro de notificaciones con contador (WhatsApp/correo preparados detrás de una interfaz, sin integrar).
- **Panel del vendedor** con resumen semanal (Chart.js), acciones rápidas, avisos de vencimiento y foto de perfil.
- **Admin:** moderación, categorías, atributos, municipios/veredas, reportes, mensajes de contacto, calificaciones.
- **Páginas institucionales y legales** (Cómo funciona, FAQ, Contacto, Términos y Política de datos — Ley 1581, **borrador para revisión legal**).
- **SEO y PWA:** URLs amigables, Open Graph, schema.org, sitemap/robots, manifest, service worker, modo sin conexión.
- **Producción:** Nginx + HTTPS (Let's Encrypt), copias de seguridad diarias, tareas programadas, `/health`, páginas de error con el diseño de la app.

- **Mapa:** punto aproximado al publicar (redondeado a ~1 km, Leaflet + OpenStreetMap), vista «Ver en mapa» con clusters y tarjeta emergente, filtro «Cerca de mí» (5/10/25 km). Sin punto propio se usa el centro de la vereda/municipio.
- **Precios del campo:** promedio, mínimo y máximo por subcategoría y unidad (últimos 30 días, sin valores atípicos), tendencia semanal, guía de precio en el formulario y `flask update-prices` para el cron diario.
- **Carteles:** PDF tamaño carta con QR e imagen 1080×1080 para estados, desde el detalle y el panel.
- **Agenda del campo:** calendario mensual, próximos eventos, destacado en el inicio y exportación `.ics`; se administra desde el admin.
- **Consejos del campo:** blog administrable con editor Trix, HTML sanitizado (nh3) y 5 artículos iniciales.
- **Accesibilidad:** «Escuchar» (voz), dictado por voz en título/descripción, letra grande, revisión automática de etiquetas/alt/foco y mensajes de error en español sencillo.
- **Calidad y despliegue:** ruff + black + pre-commit, GitHub Actions (`.github/workflows/ci.yml`), `docker-compose.prod.yml` con Nginx/HTTPS/backups.

## Pendiente / ideas
Chat interno, admin con gráficos/CSV/auditoría/destacados, multi-región, tiendas por vendedor, encargos, asociaciones,
búsqueda full-text de PostgreSQL, Redis/RQ, WhatsApp Business real, Sentry y analítica avanzada.
Sin ejecutar todavía: Lighthouse, PostgreSQL y Docker (no están instalados en el equipo de desarrollo; el CI los prueba).
