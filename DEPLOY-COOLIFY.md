# Desplegar en Coolify

Coolify construye el proyecto, le pone HTTPS (Let's Encrypt) y el dominio. **No uses** `docker-compose.yml` (es para desarrollo local) ni
`docker-compose.prod.yml` (es para un VPS sin Coolify, con Nginx): en Coolify fallan o chocan con su proxy.

Hay dos caminos. Ambos dejan la app con sus tareas programadas incluidas:

| | **A. Docker Compose** (el más fácil) | **B. Dockerfile + PostgreSQL de Coolify** |
|---|---|---|
| Archivo | `docker-compose.coolify.yml` | `Dockerfile` |
| Base de datos | dentro del mismo despliegue | recurso aparte que administra Coolify |
| Copias automáticas de la base | **No** (hay que hacerlas a mano) | **Sí** (Backups con destino S3) |
| Recomendado si | quieres arrancar rápido y probar | vas a tener usuarios reales |

> Estos pasos no se pudieron ejecutar desde el equipo de desarrollo (no hay Docker ni Coolify). La primera vez puede pedir algún ajuste menor.
> Lo que sí se verificó: las 300 pruebas, que el compose es YAML válido y que las migraciones y el `seed` corren sobre una base vacía
> (en SQLite; **PostgreSQL no se probó**).

## 0. Antes de empezar
- Un servidor con Coolify y un **dominio** apuntando a su IP (registro `A`). Sin HTTPS **no podrás iniciar sesión**: en producción las cookies son seguras.
- El código en GitHub (rama `main`). Desde tu terminal, en la carpeta del proyecto:
  ```
  git add .
  git commit -m "Compose para Coolify"
  git push origin main
  ```
- Una cuenta de correo para enviar códigos (Gmail con «contraseña de aplicación», Brevo, Mailjet o Zoho).

---

## Camino A: Docker Compose

1. En la aplicación → **Configuration → General**:
   - **Build Pack:** `Docker Compose`
   - **Docker Compose Location:** `/docker-compose.coolify.yml`  ← cámbialo (por defecto dice `/docker-compose.yml`, que es el de desarrollo)
   - Pulsa **Save** y luego **Reload Compose File**.
2. **Environment Variables:** ahora sí aparecen las variables. Completa las obligatorias:
   - `ADMIN_PHONE` y `ADMIN_PASSWORD` (tu usuario administrador).
   - `MAIL_USERNAME`, `MAIL_PASSWORD` y `MAIL_FROM` (y `MAIL_SERVER` si no usas Gmail). Sin esto no llegan los códigos por correo.
   - Opcionales: `CONTACT_EMAIL`, `CONTACT_WHATSAPP`, `SITE_NAME`…
   - **No** tienes que poner `SECRET_KEY` ni la clave de la base de datos: Coolify las genera y las guarda.
3. **Domains:** debajo del servicio `app` aparece el campo para el dominio. Escribe `https://tu-dominio.com` (si Coolify muestra el puerto, déjalo como `:8000`).
4. **Persistent Storage:** deben aparecer dos volúmenes, `uploads` (las fotos) y `pgdata` (la base). Sin ellos los datos se pierden al redesplegar.
5. Pulsa **Deploy**.

## Camino B: Dockerfile + PostgreSQL de Coolify
1. **+ New → Database → PostgreSQL 16** → Start → copia la **Postgres URL (internal)**.
2. **+ New → Application** → tu repositorio, rama `main`. **Build Pack: `Dockerfile`**. **Ports Exposes: `8000`**. **Domains:** `https://tu-dominio.com`.
3. **Environment Variables → Developer view:** pega `.env.coolify.example` y completa `SECRET_KEY`, `DATABASE_URL` (la del paso 1), `ADMIN_*` y `MAIL_*`.
4. **Persistent Storage → + Add → Volume Mount:** Name `campo-uploads`, Destination `/srv/app/static/uploads`.
5. **Healthcheck:** `GET`, ruta `/health`, puerto `8000`.
6. **Deploy.** Para copias: en el recurso PostgreSQL → **Backups** → programa copias diarias con un destino S3.

---

## Qué pasa al arrancar
El contenedor, solo: espera a la base de datos → aplica migraciones → carga categorías, municipios y el administrador (sin datos de ejemplo) →
inicia las tareas programadas (vencer anuncios, alertas, precios) → inicia Gunicorn. Activa **Auto Deploy** si quieres que cada `git push` a `main` se despliegue solo.

## Probar que quedó bien
- `https://tu-dominio.com/health` → `{"database": true, "status": "ok"}`.
- Entra con `ADMIN_PHONE` / `ADMIN_PASSWORD` y abre `/admin/`.
- Crea una cuenta con un correo real: debe llegar el código. Prueba «¿Olvidaste tu contraseña?».
- Publica un anuncio con foto, vuelve a desplegar y confirma que la foto sigue ahí.

## Copias de seguridad
- **Camino B:** las de la base las hace Coolify (con destino S3 externo; sin él, si se pierde el servidor se pierde todo).
- **Camino A:** Coolify **no** respalda una base que va dentro de un compose. Antes de tener usuarios reales, pasa al camino B o programa un `pg_dump` hacia fuera del servidor.
- **Fotos (ambos):** Coolify no las respalda solo; copia el volumen de fotos de vez en cuando.
- Haz una **prueba de restauración** al menos una vez.

## Cosas a tener presentes
- **Una sola réplica.** Las tareas programadas corren dentro del contenedor; con varias se duplicarían (`RUN_SCHEDULER=false` en todas menos una).
- **Límites de velocidad:** con `memory://` cada proceso cuenta aparte. Para compartirlos, agrega un servicio **Redis** y pon su URL en `RATELIMIT_STORAGE_URI`.
- **Textos legales** (`terminos`, `privacidad`): siguen siendo borrador pendiente de abogado. **Veredas:** las del seed son de ejemplo.

## Si algo falla
| Síntoma | Causa probable |
|---|---|
| Estado **Exited** al desplegar con Docker Compose | Estás usando `/docker-compose.yml` (desarrollo). Cambia a `/docker-compose.coolify.yml`. |
| No aparece el campo de dominio / no hay variables | Mismo motivo: recarga el compose después de cambiar la ubicación. |
| El despliegue falla diciendo que falta `ADMIN_PHONE`/`ADMIN_PASSWORD` | Son obligatorias: complétalas en Environment Variables. |
| «Bad Gateway» | Puerto equivocado (debe ser `8000`) o el contenedor no arrancó: mira **Logs**. |
| Error de base de datos al arrancar | Camino B: `DATABASE_URL` incorrecta; usa la **internal** de Coolify. |
| Inicias sesión y te saca | Entras por `http://` o por IP:puerto: usa `https://` con el dominio. |
| No llegan los códigos por correo | `MAIL_*` incompleto. Con Gmail, usa una «contraseña de aplicación». |
| Las fotos desaparecen al desplegar | Falta el volumen de fotos. |
