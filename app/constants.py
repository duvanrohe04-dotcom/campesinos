"""Constantes de la aplicación. Los valores visibles para el usuario están en español; las claves, en inglés/slug."""

# --- Roles ---
ROLE_SELLER = "seller"
ROLE_BUYER = "buyer"
ROLE_ADMIN = "admin"
# Todos los usuarios pueden comprar y vender; el rol solo distingue al administrador.
# «seller» y «buyer» se conservan por compatibilidad con cuentas ya creadas (se tratan igual).
ROLES = {ROLE_SELLER: "Usuario", ROLE_BUYER: "Usuario", ROLE_ADMIN: "Administrador"}

# --- Anuncios ---
AD_SELL, AD_BUY, AD_RENT = "vendo", "compro", "alquilo"
AD_TYPES = {AD_SELL: "Vendo", AD_BUY: "Compro / Busco", AD_RENT: "Alquilo / Ofrezco servicio"}
AD_TYPE_SHORT = {AD_SELL: "Vendo", AD_BUY: "Compro", AD_RENT: "Alquilo"}

STATUS_ACTIVE, STATUS_PAUSED, STATUS_SOLD = "active", "paused", "sold"
STATUS_EXPIRED, STATUS_REMOVED = "expired", "removed"
LISTING_STATUSES = {
    STATUS_ACTIVE: "Activa",
    STATUS_PAUSED: "Pausada",
    STATUS_SOLD: "Vendida",
    STATUS_EXPIRED: "Vencida",
    STATUS_REMOVED: "Retirada",
}
PUBLIC_STATUSES = (STATUS_ACTIVE, STATUS_SOLD)

PRICE_BY_AGREEMENT = "a convenir"
DEFAULT_PRICE_UNITS = ["unidad", "kilo", "lote"]

# --- Límites de validación ---
TITLE_MIN, TITLE_MAX = 5, 80
DESCRIPTION_MAX = 1000
QUANTITY_MAX = 1_000_000
PRICE_MAX = 10_000_000_000
BIO_MAX = 500
FARM_NAME_MAX = 120
NAME_MIN, NAME_MAX = 2, 120
PASSWORD_MIN, PASSWORD_MAX = 6, 72
SEARCH_TEXT_MAX = 80
REPORT_DETAIL_MAX = 500
CONTACT_MESSAGE_MIN, CONTACT_MESSAGE_MAX = 10, 2000
ATTR_TEXT_MAX = 120
AGE_MAX_MONTHS = 600

# --- Imágenes ---
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
VILLAGE_OTHER_ID = 0  # valor de la opción «Otra vereda» en el select (escriben el nombre aparte)
VILLAGE_OTHER_MAX = 80
OTHER_CHOICES = frozenset({"otra", "otro"})  # opciones de lista que piden escribir cuál es
CATEGORY_PHOTO_DIR = "img/categorias"  # dentro de static/; un archivo <slug>.webp por categoría raíz
IMAGE_MAX_SIDE = 1200
THUMB_MAX_SIDE = 480
IMAGE_QUALITY = 80
THUMB_QUALITY = 70

# --- Reportes y contacto ---
REPORT_REASONS = {
    "fraude": "Posible fraude o estafa",
    "animal_enfermo": "Animal enfermo",
    "info_falsa": "Información falsa",
    "otro": "Otro motivo",
}
REPORT_OPEN, REPORT_REVIEWED, REPORT_DISMISSED = "open", "reviewed", "dismissed"
CONTACT_SUBJECTS = {
    "ayuda": "Necesito ayuda con mi cuenta o un anuncio",
    "sugerencia": "Tengo una sugerencia",
    "denuncia": "Quiero denunciar un problema",
    "datos": "Datos personales (consulta o reclamo)",
    "otro": "Otro tema",
}
MESSAGE_NEW, MESSAGE_READ = "new", "read"

# --- Categorías y atributos ---
ATTR_TYPES = {
    "text": "Texto corto",
    "int": "Número entero",
    "decimal": "Número con decimales",
    "bool": "Sí / No",
    "choice": "Lista de opciones",
    "age": "Edad (se guarda en meses)",
}
CATEGORY_ICONS = [
    "vaca",
    "caballo",
    "cerdo",
    "gallina",
    "conejo",
    "fruta",
    "leche",
    "frasco",
    "costal",
    "herramienta",
    "sombrero",
    "campo",
]
HOME_SECTIONS = {"animales": "Animales", "mesa": "Del campo a tu mesa"}

# --- Clics de contacto ---
CLICK_WHATSAPP, CLICK_CALL = "whatsapp", "llamar"
CLICK_KINDS = (CLICK_WHATSAPP, CLICK_CALL)
CLICK_SESSION_MEMORY = 200

# --- Sitemap ---
SITEMAP_MAX_LISTINGS = 5000

# --- Confianza: verificación de correo, recuperación de clave y calificaciones ---
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_TTL_MINUTES = 10
VERIFICATION_MAX_ATTEMPTS = 5
VERIFICATION_RESEND_SECONDS = 60
PURPOSE_VERIFY_EMAIL, PURPOSE_RESET_PASSWORD = "verify_email", "reset_password"
EMAIL_MAX = 120
RESET_SESSION_KEY = "reset_phone"  # celular que pidió recuperar la clave (vive en la sesión, nunca en la URL)
RATING_MIN, RATING_MAX = 1, 5
RATING_COMMENT_MAX = 300
RATING_VISIBLE, RATING_HIDDEN = "visible", "hidden"

# --- Alertas y notificaciones ---
MAX_SAVED_SEARCHES = 20
MAX_NOTIFICATIONS_PER_SEARCH_RUN = 10
NOTIF_SEARCH_MATCH = "search_match"
SAVED_SEARCH_KEYS = ("cat", "sub", "q", "tipo", "mun", "ver", "pmin", "pmax")
SAVED_SEARCH_PREFIX = "a_"

# --- Precios de referencia ---
PRICE_WINDOW_DAYS = 30
PRICE_MIN_SAMPLE = 3
PRICE_OUTLIER_IQR = 1.5
PRICE_TREND_WEEKS = 12

# --- Mapa y ubicación aproximada ---
COORDINATE_DECIMALS = 2  # ~1,1 km: nunca se guarda la ubicación exacta de una finca
COLOMBIA_BOUNDS = (-4.3, 13.5, -79.1, -66.8)  # lat_min, lat_max, lng_min, lng_max
NEAR_RADIUS_OPTIONS = (5, 10, 25)
NEAR_DEFAULT_RADIUS = 10
MAP_MAX_POINTS = 300
NEAR_MAX_CANDIDATES = 3000
EARTH_RADIUS_KM = 6371.0

# --- Agenda del campo ---
EVENT_KINDS = {
    "feria": "Feria ganadera",
    "subasta": "Subasta",
    "mercado": "Mercado campesino",
    "vacunacion": "Jornada de vacunación",
    "capacitacion": "Capacitación",
    "otro": "Otro evento",
}
EVENTS_PER_PAGE = 10
ICS_LINE_LIMIT = 74

# --- Consejos del campo (blog) ---
ARTICLE_CATEGORIES = {
    "ganaderia": "Ganadería",
    "cultivos": "Cultivos",
    "aves": "Aves",
    "cerdos": "Cerdos",
    "ventas": "Ventas",
}
# Categoría de consejo → categoría raíz del marketplace (para enlazar a anuncios relacionados)
ARTICLE_LISTING_CATEGORY = {"ganaderia": "bovinos", "cultivos": "agricolas", "aves": "aves", "cerdos": "porcinos"}
ARTICLES_PER_PAGE = 9
READING_WORDS_PER_MINUTE = 180
ARTICLE_ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
    "div",
}
ARTICLE_TITLE_MAX = 120
ARTICLE_SUMMARY_MAX = 300
