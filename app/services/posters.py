"""Carteles imprimibles (PDF tamaño carta con QR) e imagen cuadrada 1080×1080 para estados de WhatsApp/Facebook."""

import os
from io import BytesIO

import qrcode
import reportlab
from flask import current_app
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from ..constants import AD_TYPES, PRICE_BY_AGREEMENT
from ..models import Listing
from ..utils import cop, format_phone

# Paleta del sistema de diseño (tailwind.config.js)
GREEN, GREEN_DARK = "#2E5D22", "#1F3D1B"
TERRACOTTA, SUN, CREAM, INK, MUTED = "#B64A24", "#F8BE2B", "#FAF8F5", "#241F19", "#6B6054"
STATUS_SIZE = 1080


def price_text(listing: Listing) -> tuple[str, str]:
    """(precio grande, unidad): «$ 3.200.000», «por cabeza»."""
    if listing.price is None:
        return "Precio a convenir", ""
    unit = listing.price_unit if listing.price_unit and listing.price_unit != PRICE_BY_AGREEMENT else ""
    return cop(listing.price), f"por {unit}" if unit else ""


def qr_image(url: str, box_size: int = 10) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color=GREEN_DARK, back_color="white").convert("RGB")


def _main_photo(listing: Listing) -> Image.Image | None:
    image = listing.main_image
    if not image:
        return None
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], image.filename)
    try:
        return Image.open(path).convert("RGB")
    except OSError:
        return None


def _cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Recorta y escala para llenar width×height sin deformar."""
    scale = max(width / img.width, height / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (resized.width - width) // 2, (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


# ---------------------------------------------------------------- PDF carta
def build_poster_pdf(listing: Listing, url: str) -> bytes:
    site = current_app.config["SITE_NAME"]
    width, height = LETTER
    margin = 36
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    pdf.setTitle(f"Cartel: {listing.title}")
    pdf.setAuthor(site)

    # Banda superior
    pdf.setFillColor(HexColor(GREEN))
    pdf.rect(0, height - 70, width, 70, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(margin, height - 46, site)
    pdf.setFillColor(HexColor(SUN))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawRightString(width - margin, height - 44, AD_TYPES.get(listing.ad_type, "").upper())

    # Foto principal o recuadro con la categoría
    photo_h, y = 300, height - 70 - 20
    photo = _main_photo(listing)
    box_w = width - 2 * margin
    if photo:
        pdf.drawImage(ImageReader(_cover(photo, box_w * 2, photo_h * 2)), margin, y - photo_h, box_w, photo_h)
    else:
        pdf.setFillColor(HexColor("#DDEFD5"))
        pdf.roundRect(margin, y - photo_h, box_w, photo_h, 12, stroke=0, fill=1)
        pdf.setFillColor(HexColor(GREEN))
        pdf.setFont("Helvetica-Bold", 30)
        pdf.drawCentredString(width / 2, y - photo_h / 2, listing.category.root.name)
    y -= photo_h + 34

    # Título
    pdf.setFillColor(HexColor(INK))
    pdf.setFont("Helvetica-Bold", 30)
    for line in simpleSplit(listing.title, "Helvetica-Bold", 30, box_w)[:3]:
        pdf.drawString(margin, y, line)
        y -= 34

    # Precio
    big, unit = price_text(listing)
    pdf.setFillColor(HexColor(GREEN))
    pdf.setFont("Helvetica-Bold", 46)
    pdf.drawString(margin, y - 14, big)
    if unit:
        offset = pdf.stringWidth(big, "Helvetica-Bold", 46) + 10
        pdf.setFillColor(HexColor(MUTED))
        pdf.setFont("Helvetica", 20)
        pdf.drawString(margin + offset, y - 14, unit)
    if listing.negotiable:
        pdf.setFillColor(HexColor(MUTED))
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, y - 36, "Precio negociable")
    y -= 62

    # Lugar
    pdf.setFillColor(HexColor(INK))
    pdf.setFont("Helvetica", 18)
    pdf.drawString(margin, y, listing.location_text)

    # Franja inferior: contacto + QR
    band_h = 190
    pdf.setFillColor(HexColor(CREAM))
    pdf.rect(0, 0, width, band_h, stroke=0, fill=1)
    pdf.setStrokeColor(HexColor(TERRACOTTA))
    pdf.setLineWidth(4)
    pdf.line(0, band_h, width, band_h)

    qr_size = 130
    pdf.drawImage(ImageReader(qr_image(url)), width - margin - qr_size, 30, qr_size, qr_size)
    pdf.setFillColor(HexColor(MUTED))
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width - margin - qr_size / 2, 16, "Escanea para ver más fotos")

    pdf.setFillColor(HexColor(INK))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, 140, "Escríbeme por WhatsApp o llama:")
    pdf.setFillColor(HexColor(TERRACOTTA))
    pdf.setFont("Helvetica-Bold", 40)
    pdf.drawString(margin, 92, format_phone(listing.user.phone))
    pdf.setFillColor(HexColor(INK))
    pdf.setFont("Helvetica", 14)
    pdf.drawString(margin, 62, f"{listing.user.farm_name or listing.user.name}")
    pdf.setFillColor(HexColor(MUTED))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, 30, url)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


# ----------------------------------------------------------- imagen 1080×1080
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Fuente Vera (viene con ReportLab, licencia libre y con tildes/ñ). Si faltara, usa la de Pillow."""
    path = os.path.join(os.path.dirname(reportlab.__file__), "fonts", "VeraBd.ttf" if bold else "Vera.ttf")
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,; ")[: max(len(lines[-1]) - 1, 1)] + "…"
    return lines


def _bold(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill: str, anchor: str = "la") -> None:
    draw.text(xy, text, font=_font(int(getattr(font, "size", 40)), bold=True), fill=fill, anchor=anchor)


def build_status_image(listing: Listing, url: str) -> bytes:
    """PNG cuadrado con foto, título, precio, lugar, celular y QR, listo para compartir como estado."""
    site = current_app.config["SITE_NAME"]
    size, pad = STATUS_SIZE, 48
    canvas_img = Image.new("RGB", (size, size), CREAM)
    draw = ImageDraw.Draw(canvas_img)

    # Cabecera
    draw.rectangle((0, 0, size, 96), fill=GREEN)
    _bold(draw, (pad, 48), site, _font(46), "white", "lm")
    _bold(draw, (size - pad, 48), AD_TYPES.get(listing.ad_type, "").upper(), _font(30), SUN, "rm")

    # Foto
    photo_box = (pad, 120, size - pad, 520)
    photo = _main_photo(listing)
    if photo:
        canvas_img.paste(_cover(photo, photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]), photo_box[:2])
    else:
        draw.rounded_rectangle(photo_box, radius=24, fill="#DDEFD5")
        _bold(draw, ((photo_box[0] + photo_box[2]) // 2, (photo_box[1] + photo_box[3]) // 2),
              listing.category.root.name, _font(54), GREEN, "mm")  # fmt: skip

    # Título
    y = 548
    for line in _wrap(draw, listing.title, _font(58), size - 2 * pad, 2):
        _bold(draw, (pad, y), line, _font(58), INK)
        y += 66

    # Precio
    big, unit = price_text(listing)
    _bold(draw, (pad, y + 6), big, _font(84), GREEN)
    if unit:
        width = int(draw.textlength(big, font=_font(84, bold=True)))
        draw.text((pad + width + 16, y + 52), unit, font=_font(34), fill=MUTED)
    draw.text((pad, y + 106), listing.location_text, font=_font(34), fill=INK)

    # Franja inferior
    draw.rectangle((0, 842, size, size), fill="white")
    draw.rectangle((0, 842, size, 848), fill=TERRACOTTA)
    qr = qr_image(url, box_size=8).resize((190, 190))
    canvas_img.paste(qr, (size - pad - 190, 862))
    draw.text((pad, 870), "WhatsApp o llamada:", font=_font(30), fill=MUTED)
    _bold(draw, (pad, 910), format_phone(listing.user.phone), _font(76), TERRACOTTA)
    draw.text((pad, 1000), listing.user.farm_name or listing.user.name, font=_font(30), fill=INK)

    buffer = BytesIO()
    canvas_img.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()
