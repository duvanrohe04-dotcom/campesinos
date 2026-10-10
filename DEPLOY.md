# Despliegue a producción (VPS propio)

> **¿Usas Coolify?** Entonces no sigas esta guía: ve a [DEPLOY-COOLIFY.md](DEPLOY-COOLIFY.md). Esta es para un VPS con Docker Compose, Nginx y certbot.

Arquitectura: **Nginx** (HTTPS, archivos estáticos y fotos) → **Gunicorn/Flask** → **PostgreSQL**, todo con Docker Compose
(`docker-compose.prod.yml`). Incluye renovación automática del certificado, copias de seguridad diarias y tareas programadas.

> **Aviso:** este paso a paso no se pudo probar de punta a punta en el equipo de desarrollo (no tiene Docker).
> Haz la primera instalación con calma y revisa cada comando. Los textos legales siguen siendo borrador: que los revise un abogado antes de publicar.

## 0. Qué necesitas
- Un VPS con Ubuntu 22.04/24.04 (mínimo 1 vCPU, 2 GB de RAM, 20 GB de disco).
- Un dominio (por ejemplo `campodirecto.com`) y acceso para editar su DNS.
- Un correo real para los avisos de Let's Encrypt.

## 1. Preparar el servidor
```bash
ssh root@IP_DEL_VPS
adduser deploy && usermod -aG sudo deploy         # usuario normal para trabajar
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh              # instala Docker + Compose
usermod -aG docker deploy
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable   # firewall
```
Cierra la sesión y entra como `deploy` (`ssh deploy@IP_DEL_VPS`).

## 2. Apuntar el dominio
En el DNS del dominio crea dos registros **A** hacia la IP del VPS: `@` (campodirecto.com) y `www`.
Espera unos minutos y comprueba con `ping campodirecto.com`.

## 3. Descargar el proyecto y configurar
```bash
git clone <URL_DEL_REPOSITORIO> campo && cd campo
cp .env.production.example .env
nano .env        # completa DOMAIN, LETSENCRYPT_EMAIL, SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD, CONTACT_EMAIL…
```
Genera la `SECRET_KEY` con: `python3 -c "import secrets; print(secrets.token_hex(32))"`.
El archivo `.env` **nunca** se sube a git (ya está en `.gitignore`).

## 4. Primer arranque con HTTPS
```bash
chmod +x deploy/*.sh entrypoint.sh
./deploy/init-letsencrypt.sh
```
El script crea un certificado temporal, levanta la app, pide el certificado real a Let's Encrypt y recarga Nginx.
Al terminar abre `https://TU_DOMINIO`. El contenedor `app` aplica las migraciones y carga las categorías, atributos y municipios al iniciar.

Si algo falla: `docker compose -f docker-compose.prod.yml logs -f nginx app`.

## 5. Crear el administrador
El usuario administrador se crea solo con `ADMIN_PHONE` y `ADMIN_PASSWORD` del `.env`. Ingresa y **cambia esa clave**. Para crear otro:
```bash
docker compose -f docker-compose.prod.yml exec app flask create-admin 3001234567
```
Entra a **Admin → Municipios** y completa las veredas reales de cada municipio.

## 6. Qué corre automáticamente
| Servicio | Qué hace |
|---|---|
| `scheduler` | Cada hora vence anuncios (`flask expire-listings`); cada 30 min revisa búsquedas guardadas (`flask check-saved-searches`). |
| `certbot` | Renueva el certificado HTTPS cada 12 h si hace falta. |
| `backup` | Cada día a las `BACKUP_HOUR` (3 a. m.) guarda la base (`db-*.dump`) y las fotos (`uploads-*.tar.gz`) en `./backups`, y borra las de más de `BACKUP_RETENTION_DAYS` días. |

Si prefieres el cron del servidor en vez del contenedor `scheduler`:
```cron
0 * * * *   cd /home/deploy/campo && docker compose -f docker-compose.prod.yml exec -T app flask expire-listings
*/30 * * * * cd /home/deploy/campo && docker compose -f docker-compose.prod.yml exec -T app flask check-saved-searches
```

## 7. Copias de seguridad: guardarlas fuera del VPS
`./backups` está en el mismo servidor. Copia esa carpeta a otro lugar con regularidad, por ejemplo desde tu computador:
```bash
rsync -avz deploy@IP_DEL_VPS:~/campo/backups/ ./copias-campo/
```

### Restaurar
```bash
# Base de datos (reemplaza el contenido actual)
docker compose -f docker-compose.prod.yml exec -T db pg_restore -U campo -d campo --clean --if-exists < backups/db-AAAAMMDD-HHMM.dump
# Fotos
docker run --rm -v campo_uploads:/data/uploads -v $PWD/backups:/backups alpine \
  tar -xzf /backups/uploads-AAAAMMDD-HHMM.tar.gz -C /data
```
(el nombre del volumen es `<carpeta-del-proyecto>_uploads`; compruébalo con `docker volume ls`).
**Prueba una restauración en un servidor de prueba antes de necesitarla de verdad.**

## 8. Actualizar a una versión nueva
```bash
cd ~/campo && git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
Las migraciones se aplican solas al reiniciar el contenedor `app`. Antes de actualizar, revisa que haya una copia reciente en `./backups`.

## 9. Logs y revisión
- Todos los servicios: `docker compose -f docker-compose.prod.yml logs -f --tail=100`.
- La aplicación también escribe en archivo con rotación (2 MB × 5) dentro del volumen `applogs` (`/srv/instance/logs/app.log`).
- Los logs de Docker rotan solos (10 MB × 5 por servicio).
- Estado de salud: `https://TU_DOMINIO/health` debe responder `{"status":"ok","database":true}`.
- Páginas de error 404/403/500 propias, con el diseño de la app.

## 10. Integración continua y despliegue automático (GitHub Actions)

El archivo `.github/workflows/ci.yml` hace lo siguiente:

| Cuándo | Qué corre |
|---|---|
| Cada *push* y *pull request* | `ruff`, `black --check`, pruebas con cobertura (falla si baja de 80 %) y pruebas contra PostgreSQL. |
| Si lo anterior pasa | Construye las imágenes Docker de la app y de Nginx (sin publicarlas). |
| *Push*/merge a `main` | Entra al VPS por SSH, hace `git reset --hard origin/main`, reconstruye, reinicia (las migraciones corren al iniciar `app`) y comprueba `/health`. |

**Secrets que debes crear** en GitHub → *Settings → Secrets and variables → Actions → New repository secret*:

| Secret | Valor |
|---|---|
| `SSH_HOST` | IP o dominio del VPS |
| `SSH_USER` | usuario de despliegue (p. ej. `deploy`) |
| `SSH_PORT` | opcional, 22 por defecto |
| `SSH_PRIVATE_KEY` | clave privada SSH **solo para despliegue** (genérala con `ssh-keygen -t ed25519 -f deploy_key`; la pública va en `~/.ssh/authorized_keys` del VPS) |
| `DEPLOY_PATH` | carpeta del proyecto en el VPS (p. ej. `/home/deploy/campo`) |
| `DEPLOY_DOMAIN` | dominio público, sin `https://` (para el chequeo de salud) |

Además crea un *Environment* llamado `production` (*Settings → Environments*); allí puedes exigir aprobación manual antes de desplegar.

**Bloquear el merge a `main` si algo falla:** *Settings → Branches → Add rule* para `main` → marca *Require a pull request before merging* y *Require status checks to pass*, y elige `Calidad (ruff + black)`, `Pruebas (SQLite)` e `Imagen Docker`.
(El job `Pruebas (PostgreSQL)` está como no bloqueante hasta confirmar que pasa una vez en tu repositorio; luego quítale `continue-on-error`.)

> Este flujo no se pudo ejecutar desde el equipo de desarrollo (no hay GitHub ni Docker aquí): la primera ejecución puede pedir ajustes menores.

## 11. Lista de verificación antes de abrir al público
- [ ] `DEBUG` apagado (`FLASK_ENV=production`) y `SECRET_KEY` propia.
- [ ] Clave del administrador cambiada.
- [ ] Textos legales revisados por un abogado y datos entre corchetes completados (`[NIT]`, `[FECHA]`…).
- [ ] `CONTACT_EMAIL` real y, si aplica, WhatsApp/redes en `.env`.
- [ ] Veredas reales cargadas; categorías revisadas.
- [ ] Copia de seguridad restaurada con éxito en una prueba.
- [ ] **Correo (`MAIL_*`) configurado** y probado: crea una cuenta con tu correo y confirma que llega el código de verificación,
      y que «¿Olvidaste tu contraseña?» envía el código. Con `MAIL_BACKEND=console` no se envía nada y la app lo avisa en el log.
- [ ] Migraciones nuevas aplicadas (`flask db upgrade`; el contenedor `app` las aplica al iniciar). Haz un respaldo antes: reemplazan la tabla
      de códigos de verificación (sus datos no servían: nunca se enviaron) y agregan columnas a `users` y `listings`.
- [ ] Límites de velocidad compartidos entre procesos: con `RATELIMIT_STORAGE_URI=memory://` y 3 procesos de Gunicorn el límite real es ~3 veces mayor.
