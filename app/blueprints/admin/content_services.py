"""Guardado de eventos y artículos desde el admin (con imagen)."""

from ...extensions import db
from ...models import Article, Event, Municipality
from ...services import articles as article_service
from ...services import images


def _apply_image(current: str | None, upload, remove: bool) -> tuple[str | None, str | None]:
    """Devuelve (archivo_final, error). Reemplaza la imagen si hay nueva, la quita si se pidió."""
    if upload and upload.filename:
        try:
            new = images.save_upload(upload)
        except images.ImageError as error:
            return current, str(error)
        if current:
            images.delete_files(current)
        return new, None
    if remove and current:
        images.delete_files(current)
        return None, None
    return current, None


def save_event(form, event: Event | None, upload) -> tuple[Event | None, str | None]:
    """Crea o actualiza un evento. Devuelve (evento, error_de_imagen)."""
    target = event or Event()
    image, error = _apply_image(target.image, upload, form.remove_image.data)
    if error:
        return None, error
    target.title, target.kind = form.title.data.strip(), form.kind.data
    target.starts_at, target.ends_at = form.starts_at.data, form.ends_at.data
    target.place = (form.place.data or "").strip() or None
    target.municipality = db.session.get(Municipality, form.municipality_id.data) if form.municipality_id.data else None
    target.organizer = (form.organizer.data or "").strip() or None
    target.description = (form.description.data or "").strip() or None
    target.is_published, target.image = form.is_published.data, image
    db.session.add(target)
    db.session.commit()
    return target, None


def delete_event(event: Event) -> None:
    if event.image:
        images.delete_files(event.image)
    db.session.delete(event)
    db.session.commit()


def event_defaults(event: Event) -> dict:
    return {
        "title": event.title, "kind": event.kind, "starts_at": event.starts_at, "ends_at": event.ends_at,
        "place": event.place or "", "municipality_id": event.municipality_id or 0, "organizer": event.organizer or "",
        "description": event.description or "", "is_published": event.is_published,
    }  # fmt: skip


def save_article(form, article: Article | None, upload, author_id: int) -> tuple[Article | None, str | None]:
    cover, error = _apply_image(article.cover if article else None, upload, form.remove_cover.data)
    if error:
        return None, error
    saved = article_service.save_article(
        article, title=form.title.data, summary=form.summary.data, body=form.body.data, category=form.category.data,
        is_published=form.is_published.data, author_id=author_id,
    )  # fmt: skip
    saved.cover = cover
    db.session.commit()
    return saved, None


def delete_article(article: Article) -> None:
    if article.cover:
        images.delete_files(article.cover)
    db.session.delete(article)
    db.session.commit()


def article_defaults(article: Article) -> dict:
    return {
        "title": article.title, "category": article.category, "summary": article.summary,
        "body": article.body_html, "is_published": article.is_published,
    }  # fmt: skip
