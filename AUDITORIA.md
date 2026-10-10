# Auditoría integral — Campo Directo

Fecha: 2026-10-10 · Alcance: código, modelos, plantillas, configuración y despliegue del repo.
**Fase 1 solo diagnostica: no se cambió código por esta auditoría.** Espera tu aprobación para pasar a la Fase 2.

## 0. Cómo leer este documento

**Qué sí revisé de verdad:** rutas, permisos, modelos y llaves foráneas, búsqueda, verificación de celular, subida de imágenes,
administración, configuración, Docker/Nginx/backups y CI. Además, las 245 pruebas automáticas pasan (cobertura 96 %), un recorrido
automático de todas las rutas como anónimo/comprador no encontró errores, y probé a mano en el navegador el flujo de publicar.

**Qué NO está probado (sé que no lo sé):**
- **Experiencia con campesinos reales.** Los hallazgos de experiencia salen de leer el código y de usar la página en un navegador de
  escritorio; no se probó con un celular de gama baja ni con personas. Eso lo cubre el plan de pruebas de la Fase 4.
- **PostgreSQL en producción.** Localmente se usa SQLite, que se comporta distinto (ver H-02). El job de CI para PostgreSQL existe pero
  no bloquea nada y no sé si hoy pasa.
- **Alcance del recorrido automático:** se siguieron los enlaces como anónimo, comprador, vendedor y admin, con tope de 300 páginas por rol
  (los filtros generan combinaciones casi infinitas), sin los carteles PDF/imagen. Resultado: **0 errores 5xx**, 0 imágenes faltantes en esas páginas,
  los 112 archivos de fotos que están en la base existen en disco, y `flask db check` confirma que modelos y migraciones coinciden.
  Únicos 4xx: `/estilos` (403 para no admin, esperado) y el enlace roto L-09. Un recorrido por enlaces **no** envía formularios ni prueba cada rama de código.

**"Funciona al 100 %" no es algo que pueda afirmar.** Hoy puedo decir: *las pruebas existentes pasan y no encontré errores en las
rutas que recorrí*. Eso no demuestra ausencia de fallos, y esta auditoría lista varios que las pruebas no cubren.

## 1. Resumen

| Severidad | Cantidad | Idea central |
|---|---|---|
| Crítico | 2 | No hay forma real de verificar el celular ni de recuperar la contraseña. |
| Alto | 7 | Borrar anuncios falla en producción, publicación sin límites (spam/estafas), límites de velocidad débiles, respaldos en el mismo servidor, CI no protege PostgreSQL, celulares visibles a bots, sin eliminar/exportar datos. |
| Medio | 15 | Contadores manipulables, enlaces muertos de WhatsApp, errores sin recuperar datos, evidencia que se borra, etc. |
| Bajo | 9 | Restricciones, un enlace roto y detalles de datos. |

## 2. Estado de lo que pides construir (importante para planear)

Varias cosas de tu plan **no existen todavía**; no son "arreglos", son módulos nuevos:

| Pieza del plan | Estado real hoy |
|---|---|
| Chat entre comprador y vendedor | No existe. El contacto es WhatsApp / llamada (`listings/services.py:111`). |
| Encargos (pedidos) | No existe (ni modelo ni rutas). |
| Ofertas a una solicitud "Compro" | No existe: "Compro" es solo un tipo de anuncio (`constants.AD_TYPES`). |
| Recuperar contraseña | No existe. |
| Verificar celular | Existe, pero solo escribe el código en el log (ver C-01). |
| Eliminar / exportar cuenta | No existe. |
| Onboarding, botón de ayuda | No existen. |
| Herramientas de soporte en admin | Solo: buscar usuario, activar/desactivar, insignia. No hay fusionar, restablecer acceso ni ver actividad. |
| Favoritos, búsquedas guardadas y alertas, reportes, mapa, carteles | Existen. |

Consecuencia: el flujo 5 ("hacer y gestionar un encargo"), parte del flujo 3 ("chat") y varias funciones de la Fase 3 (respuestas
rápidas, "responde rápido", ofertas) requieren **construir primero** chat y/o encargos. Ver sección 7.

## 3. Hallazgos

Formato: **ID · Severidad · Qué pasa → Impacto → Dónde → Arreglo propuesto.**

### Críticos

**C-01 · Crítico · La verificación de celular no puede funcionar en producción.**
El único proveedor real es `ConsoleSender`, que escribe el código de 6 dígitos en el log del servidor
(`app/services/verification.py:30-34`) y es el valor por defecto (`:89`). Nadie recibe nada en su celular.
→ La insignia "Celular verificado" es inalcanzable, y además los códigos quedan en texto claro en los logs.
→ Arreglo: integrar un proveedor real (WhatsApp Cloud API o SMS) detrás de la interfaz `CodeSender` que ya existe, y no registrar el código.
**Esto tiene costo y requiere una cuenta con el proveedor: es una decisión tuya (ver sección 7).**

**C-02 · Crítico · No hay recuperación de contraseña.**
No existe ruta (`auth/routes.py`: solo registro, ingreso, verificar, salir). Quien olvida su clave pierde su cuenta, sus anuncios y su reputación;
con usuarios de baja alfabetización digital esto pasará seguido. Depende de C-01 (se recupera con un código al celular).

### Altos

**H-01 · Alto · Celulares visibles en el HTML (scraping).**
El número sale en el enlace `tel:` (`templates/components/buttons.html:21`), en el enlace `wa.me` (`listings/services.py:111-116`) y,
desde el cambio que hicimos hoy, escrito en la ficha del vendedor (`listings/detail.html`) y en el perfil público (`profiles/public.html`).
Cualquier bot recoge todos los números sin iniciar sesión. **Choca con el cambio que me pediste hoy** (mostrar el número):
la Fase 3 pide justo lo contrario. Propongo la solución intermedia de la sección 7.

**H-02 · Alto · Borrar un anuncio con avisos asociados falla en PostgreSQL.**
`Notification.listing_id` apunta a `listings.id` sin `ondelete` ni cascada (`models/alerts.py:39`), y el borrado
(`blueprints/profiles/services.py:148` y `blueprints/admin/services.py:93`) no las elimina.
En producción (PostgreSQL) da error 500 al borrar un anuncio por el que alguien recibió una alerta.
En local no se nota porque **SQLite no hace cumplir llaves foráneas** (no hay `PRAGMA foreign_keys=ON` en ningún lado de `app/`),
así que las pruebas pasan. Lo mismo aplica a `Notification.saved_search_id` (`:40`).

**H-03 · Alto · Publicar no tiene ningún límite.**
`/publicar` (`profiles/routes.py:29-31`) no tiene rate limit ni tope de anuncios activos por usuario, y no hay revisión de duplicados.
Una cuenta nueva puede inundar el sitio de anuncios y de fotos (disco). Es la puerta de entrada de las estafas y del spam.

**H-04 · Alto · Los límites de velocidad son débiles.**
Flask-Limiter usa `memory://` (`config.py:84`, `.env.production.example:45`) y Gunicorn corre 3 workers (`Dockerfile:22`):
cada worker cuenta por separado (el límite real es ~3×) y todo se reinicia al desplegar. Afecta login, registro, reportes y verificación.
Arreglo: almacenamiento compartido (Redis, o un almacenamiento en base de datos).

**H-05 · Alto · Los respaldos están en el mismo servidor.**
`deploy/backup.sh` hace `pg_dump` y `tar` a `./backups` del mismo VPS, conserva 14 días. Si el disco o el VPS se pierde, se pierde todo,
incluidos los respaldos. No hay alerta si el respaldo falla (`backup.sh:19-25` solo imprime) ni prueba de restauración.

**H-06 · Alto · CI no protege el comportamiento en PostgreSQL.**
El job `tests-postgres` tiene `continue-on-error: true` (`.github/workflows/ci.yml:50`) y el despliegue depende solo de `docker-build`
(`:76`, `:99`). Producción puede recibir código que rompe en PostgreSQL (como H-02) sin que nada lo detenga.

**H-07 · Alto · Sin eliminación ni exportación de datos (Ley 1581).**
No hay forma de que una persona pida borrar su cuenta ni descargar sus datos; los mensajes de contacto (`models/contact.py`)
guardan nombre y celular sin plazo de retención. Es un requisito legal para quien trata datos personales en Colombia
(los textos legales siguen siendo borrador pendiente de abogado).

### Medios

**M-01 · Medio · Los contadores de clics se pueden inflar.**
`track_click` está exento de CSRF, sin límite de velocidad y sin verificar el estado del anuncio (`listings/routes.py:126-134`);
la deduplicación depende de una cookie de sesión que un bot descarta en cada petición. Las estadísticas del vendedor no son confiables.

**M-02 · Medio · Cada visita de un bot escribe en la base de datos.**
`register_view` hace `commit` en cada GET de detalle (`listings/services.py:90-94`), sin deduplicar ni ignorar bots: contención de escritura y vistas infladas.

**M-03 · Medio · Un enlace de WhatsApp a un anuncio pausado/vencido muestra "No encontramos esa página".**
`can_view` solo deja ver activos y vendidos (`listings/services.py:79-83`) y la ruta responde 404 (`listings/routes.py:66-68`).
Los enlaces circulan por WhatsApp; el comprador no sabe si fue un error suyo. Debe decir "Este anuncio ya no está disponible" y ofrecer parecidos.

**M-04 · Medio · Cuenta bloqueada = mensaje engañoso.**
Un usuario desactivado ve "Celular o contraseña incorrectos" (`auth/routes.py:41-42`), sin saber que fue bloqueado ni cómo reclamar.

**M-05 · Medio · Sesión vencida o formulario viejo = pérdida de lo escrito.**
Un token CSRF inválido muestra una página genérica (`errors.py:19-21`) y no conserva lo escrito. Solo el asistente de publicar guarda un borrador
en el navegador (`static/js/publish.js`); perfil, reporte, calificación y contacto lo pierden.

**M-06 · Medio · La evidencia de reportes se borra con el anuncio.**
`Listing.reports` tiene `cascade="all, delete-orphan"` (`models/listing.py:56`): al eliminar un anuncio denunciado desaparece el rastro del reporte.
También hay moderación sin bitácora: no queda registro de quién retiró o restauró qué.

**M-07 · Medio · "Restaurar" un anuncio ignora el estado del dueño y del plazo.**
`moderate_listing` lo pone activo sin mirar si la cuenta está bloqueada o si ya venció (`admin/services.py:88-89`).
Desactivar una cuenta pausa sus anuncios (`:58-64`) pero reactivarla no los devuelve.

**M-08 · Medio · Subida de imágenes: memoria y disco.**
`Image.MAX_IMAGE_PIXELS = 40_000_000` (`services/images.py:19`) con hasta 6 fotos por petición y 3 workers puede agotar memoria
(una foto de 40 MP decodificada pesa ~160 MB). No hay cuota total por usuario y las fotos están en disco local.
Lo bueno: se re-codifica a WebP, lo que elimina el EXIF/GPS; los nombres son UUID; hay validación de tipo y tamaño.

**M-09 · Medio · El mapa en JSON no tiene límite de velocidad ni caché.**
`listings/routes.py:54-57` recalcula la búsqueda completa en cada petición (hasta `MAP_MAX_POINTS*2` filas, `listings/services.py:42`).

**M-10 · Medio · Búsqueda de texto y filtros JSON no escalan.**
`ILIKE '%palabra%'` sobre título y descripción (`services/search.py:62-70`) es un recorrido completo de la tabla; los filtros por atributo JSON
(`search.py:99-128`) no tienen índice. Bien hasta unos miles de anuncios; después se vuelve lento. Además, ordenar por precio trata
distinto los precios vacíos ("a convenir") en SQLite y PostgreSQL (`search.py:16-17`).

**M-11 · Medio · Generar carteles PDF/PNG ocupa un worker.**
`posters.build_poster_pdf` / `build_status_image` corren dentro de la petición (`listings/routes.py:108-123`); con 3 workers síncronos y límite de 60/hora por IP (por worker, ver H-04), unas pocas descargas simultáneas pueden dejar el sitio sin responder.

**M-12 · Medio · Las tareas programadas pueden fallar sin que nadie se entere.**
`expire-listings`, `check-saved-searches` y `update-prices` corren en un bucle de shell dentro de un contenedor (`deploy/scheduler.sh`);
si un comando falla solo imprime "ERROR" (`:10-16`); no hay señal de vida ni alerta.
Si se detienen, los anuncios no vencen y las alertas no salen. Tampoco hay monitoreo de errores (tipo Sentry) ni alerta de disco lleno;
`/health` (`main/routes.py:102`) solo prueba la base de datos.

**M-13 · Medio · El registro deja la sesión recordada siempre.**
`login_user(user, remember=True)` (`auth/routes.py:21`): en un celular compartido (común en el campo) la cuenta queda abierta un año.

**M-14 · Medio · SQLite en local no refleja producción.**
Además de las llaves foráneas (H-02), SQLite y PostgreSQL difieren en JSON, orden de nulos y mayúsculas. Los desarrolladores prueban en uno y el sitio corre en otro.

**M-15 · Medio · Reportes sin freno contra abuso.**
Cualquiera (incluso sin cuenta) puede reportar sin límite por anuncio y sin deduplicar (`listings/routes.py:153-162`); no hay umbral que oculte
automáticamente un anuncio muy denunciado ni forma de ver "reportes falsos" de una misma persona.

### Bajos

- **L-01** Favoritos acepta anuncios no públicos por id (`listings/routes.py:143-150`): solo revela que existen.
- **L-02** No hay `CHECK` en `price >= 0`, `status`, `ad_type` (`models/listing.py`); la validación vive solo en los formularios.
- **L-03** Faltan índices en `reports.reporter_id`, `ratings.rater_id`, `favorites.listing_id` (afecta borrados en cascada y consultas por dueño).
- **L-04** `uq_notification_once` (`models/alerts.py:29`) incluye columnas que aceptan NULL: en SQL los NULL no chocan, así que no evita duplicados cuando falta `listing_id` o `saved_search_id`.
- **L-05** La búsqueda de usuarios del admin no escapa `%` ni `_` (`admin/services.py:54`).
- **L-06** Fechas guardadas sin zona horaria (UTC "ingenuo"); los eventos usan hora local de Colombia (`models/content.py:16`). Funciona, pero es fácil equivocarse.
- **L-07** Aviso "Revisa los datos marcados en rojo" depende del color (`profiles/routes.py:12`): las personas daltónicas no distinguen el campo; conviene también texto/ícono por campo.
- **L-09** El botón "Perfil" de la lista de usuarios del admin (`templates/admin/users.html:14`) lleva a un 404 cuando el usuario es un admin,
  porque el perfil público no muestra cuentas admin (`blueprints/profiles/services.py`, `seller_page`). Es el único enlace roto que encontró el recorrido automático.
- **L-08** Las veredas del seed se repiten entre municipios con el mismo nombre (p. ej. "Buenavista"); en la lista aparecen como opciones iguales si se cambia de municipio rápido.

## 4. Lo que está bien (no tocar)

- Permisos de dueño centralizados (`decorators.py`): sin IDOR en editar/pausar/renovar/eliminar; el admin se protege solo con `@admin_required`.
- CSRF global, contraseñas con hash, bloqueo por intentos fallidos, `is_safe_next` contra redirecciones abiertas, cabeceras de seguridad.
- Imágenes re-codificadas (sin EXIF/GPS), nombres UUID, límite de tamaño.
- Respaldos automáticos diarios (falta sacarlos del servidor, H-05), `restart: unless-stopped`, healthchecks en Docker.
- Carga eficiente de listados (`card_query`), índices compuestos en anuncios (`models/listing.py:16-20`).
- Estados vacíos y "sin foto" ya manejados (icono de categoría).

## 5. Flujos que pides, y qué falta para que funcionen de punta a punta

| # | Flujo | Estado |
|---|---|---|
| 1 | Registro, verificar celular, completar perfil | Registro y perfil sí. **Verificar celular: no funciona (C-01).** |
| 2 | Publicar (cualquier tipo), editar, pausar, renovar, vendido | Sí funciona y tiene pruebas. Falta límite/anti-spam (H-03). |
| 3 | Buscar, filtrar, mapa, favorito, contactar por WhatsApp/llamada | Sí. **"Chat" no existe.** |
| 4 | Guardar búsqueda y recibir alerta | Existe (alertas en la app). Falta confirmar que corre el cron en producción (M-12). |
| 5 | Hacer y gestionar un encargo | **No existe.** |
| 6 | Reportar, moderar, bloquear | Existe. Falta bitácora y manejo de evidencia (M-06, M-07). |
| 7 | Recuperar contraseña por celular | **No existe (C-02).** |

## 6. Lo que necesito que decidas (antes de empezar la Fase 2)

1. **Proveedor de códigos (C-01/C-02):** ¿WhatsApp Cloud API (gratis hasta cierto volumen, requiere cuenta de Meta Business) o SMS (de pago por mensaje)?
   Sin esto, verificación y recuperación no pueden funcionar de verdad; puedo dejar todo listo detrás de la interfaz y probarlo con un proveedor simulado.
2. **Celular visible (H-01):** hoy lo muestra tal cual porque lo pediste. Mi recomendación:
   mostrar `310 ••• ••33` y revelar el número completo **al tocar** "Ver celular", solo para personas con sesión iniciada y con límite de revelaciones por hora;
   el botón de WhatsApp pasaría por una ruta nuestra en vez de llevar el número en el HTML. A cambio pierde un poco de comodidad para quien no tiene cuenta. ¿Lo aplico así, o prefieres dejarlo visible?
3. **Chat y encargos:** son módulos grandes. Mi recomendación es **no construir un chat propio ahora**: la gente del campo ya vive en WhatsApp, y un chat propio
   que nadie abre es peor que el que ya usan. Alternativa: "respuestas rápidas" como textos prellenados que se envían a WhatsApp, y un **encargo simple** (solicitud con cantidad/fecha/estado, sin pagos)
   que se gestiona desde el panel y avisa por notificación. "Responde rápido" se calcularía sobre el tiempo en que el vendedor **responde a encargos y ofertas**, porque el tiempo de respuesta en WhatsApp no se puede medir. ¿De acuerdo?
4. **Redis para límites y respaldos externos (H-04/H-05):** implican un servicio más y un destino de respaldo (almacenamiento tipo S3/Backblaze, centavos al mes). ¿Quieres que los prepare?

## 7. Plan propuesto para la Fase 2 (al aprobar)

Orden por impacto/riesgo, cada punto con su prueba:
1. **Integridad:** activar llaves foráneas en SQLite; `ondelete`/cascada correctos en notificaciones y reportes (migración); prueba que borre un anuncio con alertas. (H-02, M-06, L-02..L-04)
2. **Seguridad de la cuenta:** proveedor de códigos desacoplado, recuperación de contraseña, mensaje claro de cuenta bloqueada, "recordarme" opcional. (C-01, C-02, M-04, M-13)
3. **Anti-spam al publicar:** límite por hora y tope de activos por cuenta nueva, y marcado para revisión. (H-03, M-15)
4. **Límites compartidos y CI:** almacenamiento de límites compartido; hacer bloqueante el job de PostgreSQL. (H-04, H-06)
5. **Operación:** respaldos externos con alerta, señal de vida de las tareas programadas, `/health` ampliado. (H-05, M-12)
6. **Experiencia:** página "este anuncio ya no está disponible" con parecidos, formularios que conservan lo escrito al vencer la sesión. (M-03, M-05)
7. **Datos personales:** eliminar y exportar cuenta, retención de mensajes. (H-07)
8. **Pruebas de integración por flujo** (los 7 de tu lista; el 5 y parte del 3 según lo que decidas en 6.3).

## 9. Estado después de la Fase 2 (2026-10-10)

Decisiones que tomé (según el criterio que pediste): **correo** como canal de verificación y recuperación; celular **enmascarado** y revelado al tocar;
**sin chat propio**. Verificado: 295 pruebas en verde, cobertura 96 %, `ruff` y `black` limpios, y revisión manual en el navegador del celular enmascarado.

| ID | Estado | Qué se hizo / qué falta |
|---|---|---|
| C-01 | **Resuelto en código; falta configurar el correo real** | Códigos por correo (`services/mailer.py`, SMTP con TLS). Probado con un SMTP simulado; **no se probó con un proveedor real**: hay que llenar `MAIL_*` en producción. Con `MAIL_BACKEND=console` en producción no se envía nada y el código ya no se imprime en el log. |
| C-02 | **Resuelto** | `/recuperar` → código al correo verificado → contraseña nueva. No revela si el celular existe; el código se invalida tras 5 intentos; quita bloqueos. Quien no tiene correo verificado ve el botón de ayuda por WhatsApp/Contacto. **Limitación:** al cambiar la clave no se cierran las sesiones abiertas en otros aparatos. |
| H-01 | **Resuelto** | El celular no está en el HTML de anuncios ni perfiles; `Ver celular` y el botón de WhatsApp pasan por rutas con límite de velocidad (`CONTACT_REVEAL_RATE_LIMIT`), sin caché, sin indexar. Los carteles PDF/imagen (llevan el número) ahora solo los descarga su dueño. **Límite honesto:** frena a quien recolecta números a escala, no a una persona que los pida uno por uno desde muchas IP. |
| H-02 | **Resuelto** | Cascada de avisos al borrar anuncio/búsqueda. Las pruebas ahora corren con llaves foráneas activas en SQLite y una prueba de mutación confirma que el error existía y ya no. |
| H-03 | **Resuelto** | Límite de 20 publicaciones/hora, tope de 40 anuncios activos y de 5 en cuentas de menos de 24 h (configurables). No hay todavía detección de duplicados ni de precios sospechosos (Fase 3). |
| H-04 | **Sin resolver** | Los límites siguen en memoria (`memory://`). Requiere Redis u otro almacenamiento compartido; no lo agregué porque no puedo probar Docker aquí. |
| H-05 | **Sin resolver** | Respaldos siguen en el mismo servidor. Requiere decidir destino externo. |
| H-06 | **Sin resolver** | El job de PostgreSQL sigue sin bloquear: no puedo ejecutarlo localmente y no quise bloquear los despliegues a ciegas. Recomiendo correrlo una vez en GitHub y, si pasa, quitar `continue-on-error`. |
| H-07 | **Resuelto** | `/panel/cuenta`: descargar mis datos (JSON) y eliminar la cuenta (anonimiza, borra anuncios, fotos del disco, favoritos, búsquedas, avisos y mensajes). Falta la política de retención para mensajes de contacto de personas sin cuenta. |
| M-01 | **Resuelto** | Se eliminó el endpoint exento de CSRF; los contactos se cuentan al pasar por las rutas del servidor (una vez por sesión y anuncio). |
| M-03 | **Resuelto** | Anuncio pausado/vencido: página «ya no está disponible» con parecidos (410); retirado: 404. |
| M-04 | **Resuelto** | Cuenta suspendida muestra un mensaje claro (solo con la clave correcta). |
| M-05 | **Parcial** | Si se sabe de dónde venía, se vuelve a esa página con un aviso en vez de una pantalla muerta; **lo que escribieron en esos formularios no se conserva** (salvo el borrador del asistente de publicar). |
| M-13 | **Sin resolver** | El registro sigue recordando la sesión. |
| L-09 | **Resuelto** | El admin ya no muestra «Perfil» hacia cuentas admin; marca cuentas eliminadas. |
| M-02, M-06 a M-12, M-14, M-15, L-01 a L-08 | **Sin tocar** | (M-14 mejoró: las pruebas ya exigen llaves foráneas.) |

**Cosas nuevas que debes saber**
- **Migraciones nuevas** (`a1c4e8f20b73`, `b2d5f9a31c84`): agregan `users.email`, `email_verified_at`, `deleted_at`, y **reemplazan** la tabla de códigos (`phone_verifications` → `verification_codes`). Probadas en tu SQLite local; **no en PostgreSQL**. Haz respaldo antes de desplegar.
- **Cambio de comportamiento:** la insignia «Celular verificado» ahora es «Correo verificado». Las verificaciones de celular anteriores (que nunca pudieron enviarse) no se conservan.
- **Encargos y chat:** siguen sin existir; su flujo no tiene prueba. `AUDITORIA.md` §2 explica por qué recomiendo no construir un chat propio.
- Las pruebas de flujo están en `tests/integration/test_flows.py` (flujos 1, 2, 3, 4 y 6) y `test_password_recovery.py` (flujo 7).

## 8. Nota sobre el flujo de trabajo (ramas y commits)

Pides ramas por fase y commits convencionales. En esta máquina **`git` no está instalado/en el PATH** (existe la carpeta `.git`, pero no el ejecutable),
así que no puedo crear ramas ni commits. Opciones: instalar Git for Windows y avisarme, o yo dejo cada fase como un conjunto de cambios con los mensajes de commit sugeridos para que los apliques tú.
