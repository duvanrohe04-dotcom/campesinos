# Desplegar en Coolify

Coolify construye el `Dockerfile` del proyecto, le pone HTTPS (Let's Encrypt) y el dominio. **No uses** `docker-compose.prod.yml` ni Nginx aquí:
ese es el camino para un VPS sin Coolify (ver `DEPLOY.md`).

Resultado: 1 aplicación (web + tareas programadas) + 1 base de datos PostgreSQL que administra Coolify.

> Este flujo no se pudo ejecutar desde el equipo de desarrollo (aquí no hay Docker ni Coolify). La primera vez puede pedir algún ajuste menor.
> Lo que sí se verificó: las 300 pruebas, la configuración de Gunicorn y que las migraciones y el `seed` corren sobre una base vacía (en SQLite; **PostgreSQL no se probó**).

## 0. Antes de empezar
- Un servidor con Coolify instalado y un **dominio** apuntando a su IP (registro `A`). Sin dominio con HTTPS **no podrás iniciar sesión**: en producción las cookies son seguras y solo viajan por https.
- El código en GitHub (`github.com/duvanrohe04-dotcom/campesinos`, rama `main`). Desde tu terminal, en la carpeta del proyecto:
  ```
  git add .
  git commit -m "Listo para Coolify"
  git push origin main
  ```
  Si el repositorio es **privado**, en Coolify conecta GitHub (Sources → GitHub App) o usa una *Deploy key*.
- Una cuenta de correo para enviar códigos (Gmail con «contraseña de aplicación», Brevo, Mailjet o Zoho).

## 1. Crear la base de datos
1. En tu proyecto de Coolify: **+ New → Database → PostgreSQL** (versión 16).
2. Inícialo (**Start**) y copia la **Postgres URL (internal)**. La necesitas en el paso 3.

## 2. Crear la aplicación
1. **+ New → Application →** *Public Repository* (o *Private Repository (with GitHub App)*).
2. Repositorio `https://github.com/duvanrohe04-dotcom/campesinos`, rama `main`.
3. **Build Pack: `Dockerfile`** (no dejes Nixpacks).
4. **Ports Exposes: `8000`**.
5. **Domains:** `https://tu-dominio.com` (con `https://`).

## 3. Variables de entorno
En la aplicación → **Environment Variables → Developer view**: pega el contenido de `.env.coolify.example` y completa:
- `SECRET_KEY` (obligatoria: sin ella la app no arranca), `DATABASE_URL` (la del paso 1),
- `ADMIN_PHONE` y `ADMIN_PASSWORD` (tu usuario administrador),
- `MAIL_*` (para los códigos por correo) y `CONTACT_EMAIL` / `CONTACT_WHATSAPP`.

## 4. Guardar las fotos (importante)
En la aplicación → **Persistent Storage → + Add → Volume Mount**:
- Name: `campo-uploads`
- Destination Path: `/srv/app/static/uploads`

Sin este volumen, **las fotos se borran en cada despliegue**.

## 5. Chequeo de salud
En **Healthcheck** activa: método `GET`, ruta `/health`, puerto `8000`. La imagen ya trae `curl`. (El contenedor ya incluye su propio chequeo.)

## 6. Desplegar
Pulsa **Deploy**. Al arrancar, el contenedor solo:
1. espera a la base de datos y aplica las migraciones,
2. carga categorías, municipios y el administrador (sin datos de ejemplo),
3. inicia las tareas programadas (vence anuncios, alertas de búsquedas guardadas, precios),
4. inicia Gunicorn.

Activa **Auto Deploy** si quieres que cada `git push` a `main` se despliegue solo.

## 7. Probar que quedó bien
- `https://tu-dominio.com/health` → `{"database": true, "status": "ok"}`.
- Entra con `ADMIN_PHONE` / `ADMIN_PASSWORD` y revisa `/admin/`.
- Crea una cuenta con un correo real: debe llegar el código. Prueba «¿Olvidaste tu contraseña?».
- Publica un anuncio con foto, vuelve a desplegar y confirma que la foto sigue ahí (prueba del volumen).

## 8. Copias de seguridad
- **Base de datos:** en Coolify → tu PostgreSQL → **Backups**: programa copias diarias y configura un destino S3 (Backblaze B2, Cloudflare R2, etc.). Es lo más importante: sin destino externo, si se pierde el servidor se pierde todo.
- **Fotos:** Coolify no las respalda solo. Opciones: una copia periódica del volumen `campo-uploads`, o mover las fotos a un almacenamiento de objetos más adelante.
- Haz una **prueba de restauración** al menos una vez.

## 9. Cosas a tener presentes
- **Una sola réplica.** Las tareas programadas corren dentro del contenedor; con varias réplicas se duplicarían. Si escalas, pon `RUN_SCHEDULER=false` en todas menos una.
- **Límites de velocidad:** con `memory://` y varios procesos, cada uno cuenta por separado. Para compartirlos, agrega un servicio **Redis** en Coolify y pon su URL interna en `RATELIMIT_STORAGE_URI`.
- **Textos legales:** `terminos` y `privacidad` siguen siendo borrador pendiente de abogado.
- **Veredas:** las del seed son de ejemplo; el administrador debe cargar las reales.

## 10. Si algo falla
| Síntoma | Causa probable |
|---|---|
| «Bad Gateway» / no abre | *Ports Exposes* no es `8000`, o el contenedor no arrancó: mira **Logs**. |
| El contenedor se reinicia con `RuntimeError: Define SECRET_KEY` | Falta `SECRET_KEY` (o `ADMIN_PHONE` sin `ADMIN_PASSWORD`, o al revés). |
| Error de base de datos al arrancar | `DATABASE_URL` incorrecta: usa la URL **internal** de Coolify. |
| Inicias sesión y te saca | Estás entrando por `http://` o por IP:puerto: usa `https://` con el dominio. |
| No llegan los códigos por correo | `MAIL_*` incompleto. Con Gmail, usa una «contraseña de aplicación», no la de la cuenta. |
| Las fotos desaparecen al desplegar | Falta el volumen del paso 4. |
| Healthcheck en rojo y el sitio no se publica | Revisa que la ruta sea `/health` y el puerto `8000`. |
