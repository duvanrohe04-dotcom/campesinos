"""Modelos de la aplicación. Se exportan aquí para `from app.models import ...`."""

from .alerts import Notification, SavedSearch
from .category import AttributeDef, Category
from .contact import ContactMessage
from .content import Article, Event
from .favorite import Favorite
from .geo import Municipality, Village
from .listing import Listing, ListingImage
from .prices import PriceSnapshot
from .report import Report
from .stats import DailyStat
from .trust import Rating, VerificationCode
from .user import User

__all__ = [
    "Article",
    "AttributeDef",
    "Category",
    "ContactMessage",
    "DailyStat",
    "Event",
    "Favorite",
    "Listing",
    "ListingImage",
    "Municipality",
    "Notification",
    "VerificationCode",
    "PriceSnapshot",
    "Rating",
    "Report",
    "SavedSearch",
    "User",
    "Village",
]
