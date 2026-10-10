"""Subida segura de imágenes: valida tipo y tamaño, redimensiona a 1200px y guarda en WebP."""

import os
import uuid
from io import BytesIO

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

from ..constants import (
    ALLOWED_IMAGE_EXTENSIONS,
    IMAGE_MAX_SIDE,
    IMAGE_QUALITY,
    THUMB_MAX_SIDE,
    THUMB_QUALITY,
)

Image.MAX_IMAGE_PIXELS = 40_000_000


class ImageError(ValueError):
    """Foto inválida; el mensaje está en español y se puede mostrar al usuario."""


def _prepare(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    return img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")


def _read_and_validate(file_storage: FileStorage) -> Image.Image:
    name = file_storage.filename or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ImageError("Solo se aceptan fotos JPG, PNG o WebP.")
    max_bytes = current_app.config["MAX_IMAGE_BYTES"]
    data = file_storage.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ImageError("La foto pesa demasiado (máximo 10 MB).")
    try:
        Image.open(BytesIO(data)).verify()
        return _prepare(Image.open(BytesIO(data)))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageError("No pudimos leer esa foto. Prueba con otra.") from None


def _save_webp(img: Image.Image, path: str, side: int, quality: int) -> None:
    resized = img.copy()
    resized.thumbnail((side, side))
    resized.save(path, "WEBP", quality=quality, method=4)


def _store(img: Image.Image) -> str:
    folder = current_app.config["UPLOAD_FOLDER"]
    base = uuid.uuid4().hex
    _save_webp(img, os.path.join(folder, f"{base}.webp"), IMAGE_MAX_SIDE, IMAGE_QUALITY)
    _save_webp(img, os.path.join(folder, f"{base}_t.webp"), THUMB_MAX_SIDE, THUMB_QUALITY)
    return f"{base}.webp"


def save_upload(file_storage: FileStorage) -> str:
    """Guarda la foto (uuid.webp) y su miniatura (uuid_t.webp). Devuelve el nombre del archivo grande."""
    return _store(_read_and_validate(file_storage))


def save_from_path(path: str) -> str:
    """Igual que save_upload pero desde un archivo del disco (lo usa el seed de demostración)."""
    try:
        return _store(_prepare(Image.open(path)))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageError(f"No se pudo leer la foto {path}") from None


def delete_files(filename: str) -> None:
    folder = current_app.config["UPLOAD_FOLDER"]
    for name in (filename, filename.replace(".webp", "_t.webp")):
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            current_app.logger.debug("No se pudo borrar %s", name)
