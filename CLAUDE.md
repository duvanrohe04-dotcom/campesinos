# Campo Directo — guía para trabajar en este repo

Marketplace rural (Flask monolito, plantillas Jinja2) para campesinos de la provincia de Vélez, Santander.
Usuarios con baja alfabetización digital y celulares de gama baja: **simple, mobile-first, textos claros en español colombiano**.
Sin pagos en línea: la plataforma conecta; el contacto es por WhatsApp o llamada.

## Comandos

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt   # dev (incluye base)
.\.venv\Scripts\python run.py                               # http://localhost:5000 (usa wsgi.py)
.\.venv\Scripts\python -m flask db upgrade                  # aplicar migraciones
.\.venv\Scripts\python -m flask db migrate -m "mensaje"     # nueva migración (revisar el archivo generado)
.\.venv\Scripts\python -m flask seed                        # categorías, atributos, municipios, usuarios y ejemplos
.\.venv\Scripts\python -m flask expire-listings             # vence anuncios (cron cada hora)
.\.venv\Scripts\python -m flask check-saved-searches        # avisos de búsquedas guardadas (cron cada 30 min)
.\.venv\Scripts\python -m flask update-prices               # precios de referencia (cron diario)
.\.venv\Scripts\python -m pytest                            # todas las pruebas (tests/unit + tests/integration)
.\.venv\Scripts\python -m pytest --cov=app                  # con cobertura
.\.venv\Scripts\python -m ruff check app tests --fix        # lint + orden de imports
.\.venv\Scripts\python -m black app tests                   # formato
npm run build:css                                           # compila Tailwind → app/static/css/app.css
```
Docker: `docker compose up --build`. Entornos: `FLASK_ENV=development|testing|production` (ver `app/config.py`).

## Estructura

```
app/
  __init__.py     create_app(): extensiones, blueprints, errores, logging
  extensions.py   db, migrate, login_manager, csrf, limiter (sin app; evita imports circulares)
  config.py       Config, DevelopmentConfig, TestingConfig, ProductionConfig
  constants.py    constantes (roles, estados, límites, tipos). Nada de valores "quemados" en el código
  decorators.py   @admin_required, @owner_required
  errors.py       errorhandlers 403/404/429/500 y logging
  forms.py        helpers compartidos de formularios
  templating.py   filtros y globales de Jinja
  models/         un archivo por dominio; __init__ exporta todo; consultas reutilizables como classmethods
  blueprints/<nombre>/  __init__.py (bp) · routes.py · forms.py · services.py
      main · auth · listings (público, mapa, carteles) · profiles (panel + perfil público) · alerts · prices
      agenda · tips (consejos) · admin (routes + content_routes)
  services/       lógica de negocio reutilizable: attributes, images, search, listing_form, expiry, seeding
  utils/          helpers genéricos con type hints: dates, formatting, numbers, security, slugs
  cli/            comandos de Flask CLI
  templates/      base.html · components/ (macros) · una carpeta por blueprint
  static/         css · js · icons · uploads (fotos) · sw.js · manifest
tests/            conftest.py · unit/ · integration/
migrations/ · requirements/{base,dev,prod}.txt · wsgi.py · pyproject.toml
```

## Reglas de código

- **Rutas delgadas:** una vista recibe la petición, valida con el formulario, llama a un service y renderiza. Sin lógica de negocio ni consultas complejas en `routes.py`.
- **Lógica en `services.py`** (del blueprint) o `app/services/` si se reutiliza. Consultas reutilizables como métodos de clase en el modelo (`Listing.public_query()`, `Category.active_roots()`).
- **Un formulario Flask-WTF por acción** en el `forms.py` del blueprint. Los datos específicos por categoría son dinámicos: se validan con `app/services/attributes.py` contra `attribute_defs`.
- **Idioma:** código en inglés (variables, funciones, clases, archivos); textos visibles al usuario en español. Las URLs públicas y los valores guardados ya existentes (`/publicar`, `vendo`, `attr_sexo`) se mantienen en español: no los renombres.
- PEP 8, funciones cortas de una sola responsabilidad, type hints en `services/` y `utils/`, docstring breve en funciones públicas.
- **Sin duplicación:** repite 2 veces → extrae a macro Jinja (`templates/components/`), service o util.
- **Sin valores quemados:** constantes en `constants.py`; configuración en `config.py`/`.env`.
- **Errores y logs:** errorhandlers centralizados en `errors.py`; usa `current_app.logger`, nunca `print()`.
- **Permisos:** `@admin_required` y `@owner_required` (inyecta `listing`); no repitas comprobaciones a mano.
- Imports ordenados (ruff/isort) y sin ciclos: los blueprints importan de `services`/`models`, nunca al revés; las extensiones viven en `extensions.py`.
- **Seguridad:** CSRF global, contraseñas con hash, límite de intentos (columnas en `users` + Flask-Limiter por IP en login/registro/reportes/contacto), validación de imágenes (tipo, tamaño, Pillow → WebP 1200 px).
- **Rendimiento:** usa `Listing.card_query()`/`public_query()` (eager loading, evita N+1); imágenes con lazy loading; JS mínimo.
- **Diseño:** paleta y tipografía en `tailwind.config.js`; componentes en `templates/components/`; ve `/estilos` (solo admin). Botones ≥ 48 px, texto base 17 px, contraste AA. Después de tocar clases Tailwind: `npm run build:css`.
- **Base de datos:** SQLite en local (por defecto), PostgreSQL en Docker. Cambios de modelo → migración; revisa el archivo generado (si aparece `Text()` sin `sa.`, corrígelo a `sa.Text()`).

## Pruebas

Toda funcionalidad nueva lleva pruebas: lógica pura en `tests/unit/`, rutas/permisos/formularios en `tests/integration/`.
Fixtures en `tests/conftest.py` (`app`, `client`, `seller`, `admin`, `login`, `url_of`). Datos de ejemplo: vendedores `3101112233`, `3112223344`, `3123334455`, comprador `3134445566` (clave `campo123`), admin `3000000000` (`admin12345`).
No dejes pruebas fallando ni `ruff`/`black` con errores antes de dar algo por terminado.

## Cosas a tener presente

- Los textos legales (`templates/main/terms.html`, `privacy.html`) son **borrador pendiente de revisión por un abogado**.
- Las veredas del seed son ejemplos genéricos; el admin completa las reales.
- Las URLs de detalle son `/<categoría>/<subcategoría>/<slug>-<id>` y redirigen (301) a la forma canónica; la ruta es la más genérica y se registra al final.
