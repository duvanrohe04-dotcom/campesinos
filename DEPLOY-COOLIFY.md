# Desplegar en Coolify (con SQLite)

Coolify construye el proyecto con `docker-compose.coolify.yml`, le pone HTTPS (Let's Encrypt) y el dominio.
La base de datos es **SQLite**: un archivo (`campo.db`) en un volumen. No hay servicio de PostgreSQL.

> **No uses** `docker-compose.yml` (desarrollo local) ni `docker-compose.prod.yml` (VPS sin Coolify, con PostgreSQL y Nginx): en Coolify fallan o chocan con su proxy.
>
> Estos pasos no se pudieron ejecutar desde el equipo de desarrollo (no hay Docker ni Coolify). La primera vez puede pedir algún ajuste menor.
> Lo que sí se verificó: las pruebas, que el compose es YAML válido, que las migraciones y el `seed` corren sobre una base vacía,
> y SQLite en modo WAL con respaldos (ver abajo).

## 0. Antes de empezar
- Un servidor con Coolify y un **dominio** apuntando a su IP (registro `A`). Sin HTTPS **no podrás iniciar sesión**: en producción las cookies son seguras.
- El código en GitHub (rama `main`). Desde tu terminal, en la carpeta del proyecto:
  ```
  git add .
  git commit -m "SQLite en Coolify"
  git push origin main
  ```
- Una cuenta de correo para enviar códigos (Gmail con «contraseña de aplicación», Brevo, Mailjet o Zoho).

## 1. Configurar la aplicación
1. **Configuration → General:**
   - **Build Pack:** `Docker Compose`
   - **Docker Compose Location:** `/docker-compose.coolify.yml` (por defecto dice `/docker-compose.yml`, que es el de desarrollo)
   - **Save** y luego **Reload Compose File**.
2. **Environment Variables:** completa las obligatorias:
   - `ADMIN_PHONE` y `ADMIN_PASSWORD` (tu usuario administrador).
   - `MAIL_USERNAME`, `MAIL_PASSWORD` y `MAIL_FROM` (y `MAIL_SERVER` si no usas Gmail). Sin esto no llegan los códigos por correo.
   - Opcionales: `CONTACT_EMAIL`, `CONTACT_WHATSAPP`, `SITE_NAME`…
   - **No** pongas `SECRET_KEY` ni `DATABASE_URL`: la clave la genera Coolify y, sin `DATABASE_URL`, la app usa SQLite.
3. **Domains** (servicio `app`): escribe `https://tu-dominio.com:8000`. El `:8000` es el puerto interno del contenedor para que Coolify sepa a dónde
   enviar el tráfico; en el navegador la dirección es simplemente `https://tu-dominio.com`.
4. **Persistent Storage:** deben aparecer **dos volúmenes**:
   - `data` → `/srv/instance` (la base de datos y sus copias),
   - `uploads` → `/srv/app/static/uploads` (las fotos).

   Sin ellos, **la base y las fotos se pierden en cada despliegue**.
5. **Deploy.**

### «Me aparecen dos links» (el tuyo y otro de `…sslip.io`)
La dirección `sslip.io` era una dirección temporal que Coolify creaba sola porque una versión anterior de `docker-compose.coolify.yml` declaraba
`SERVICE_FQDN_APP_8000`. Esa línea ya no está. Después de subir el cambio: **Reload Compose File**, revisa que en **Domains** solo esté el tuyo,
**Save** y **Deploy**. Si el link viejo sigue saliendo, busca en **Environment Variables** las variables `SERVICE_FQDN_APP_8000` y `SERVICE_URL_APP_8000`
(las crea Coolify) y bórralas. Esa dirección no tiene HTTPS válido: por ahí no se puede iniciar sesión.

## Qué pasa al arrancar
El contenedor, solo: aplica migraciones → carga categorías, municipios y el administrador (sin datos de ejemplo) → inicia las tareas programadas
(vence anuncios, alertas, precios y **copia diaria de la base**) → inicia Gunicorn. Activa **Auto Deploy** si quieres que cada `git push` a `main` se despliegue solo.

## Probar que quedó bien
- `https://tu-dominio.com/health` → `{"database": true, "status": "ok"}`.
- Entra con `ADMIN_PHONE` / `ADMIN_PASSWORD` y abre `/admin/`.
- Crea una cuenta con un correo real: debe llegar el código. Prueba «¿Olvidaste tu contraseña?».
- Publica un anuncio con foto, vuelve a desplegar y confirma que **el anuncio y la foto siguen ahí** (prueba de los volúmenes).

## Copias de seguridad (importante con SQLite)
- Cada día el contenedor hace una **copia consistente** de la base en `/srv/instance/backups` (`flask backup-db`; conserva 14 días, ajustable con `BACKUP_RETENTION_DAYS`).
  Protege de errores y daños del archivo, **pero está en el mismo servidor**: si se pierde el servidor o el volumen, se pierden también las copias.
- **Saca una copia fuera del servidor** de vez en cuando (descargar `campo-*.db` del volumen `data`) y copia también el volumen `uploads` (las fotos).
  Coolify no respalda volúmenes de un compose por sí solo.
- Para restaurar: detén la app, reemplaza `campo.db` por una copia (cámbiale el nombre), y arranca de nuevo.
- Haz una **prueba de restauración** al menos una vez.

## Límites de SQLite que debes conocer
- **Un solo contenedor.** No subas las réplicas a más de 1: SQLite es un archivo y varias máquinas no pueden compartirlo.
- Aguanta bien un sitio pequeño o mediano (modo WAL y espera ante bloqueos están activados). Si algún día hay mucho tráfico de escritura
  (muchas publicaciones a la vez), el siguiente paso es migrar a PostgreSQL: la app ya lo soporta con `DATABASE_URL`, pero no se ha probado aquí.
- **Límites de velocidad:** con `memory://` cada proceso cuenta aparte; es aceptable para empezar.
- **Textos legales** (`terminos`, `privacidad`): siguen siendo borrador pendiente de abogado. **Veredas:** las del seed son de ejemplo.

## Si algo falla
| Síntoma | Causa probable |
|---|---|
| Estado **Exited** al desplegar | Estás usando `/docker-compose.yml` (desarrollo). Cambia a `/docker-compose.coolify.yml` y recarga. |
| No aparece el campo de dominio / no hay variables | Mismo motivo: recarga el compose después de cambiar la ubicación. |
| Falla diciendo que falta `ADMIN_PHONE`/`ADMIN_PASSWORD` | Son obligatorias: complétalas en Environment Variables. |
| «Bad Gateway» | Puerto distinto de `8000` o el contenedor no arrancó: mira **Logs**. |
| `database is locked` en los logs | Hay más de una réplica de la app, o dos procesos externos escribiendo. Deja solo 1. |
| Inicias sesión y te saca | Entras por `http://` o por IP:puerto: usa `https://` con el dominio. |
| No llegan los códigos por correo | `MAIL_*` incompleto. Con Gmail, usa una «contraseña de aplicación». |
| Los anuncios o las fotos desaparecen al desplegar | Falta el volumen `data` o `uploads` (paso 4). |
