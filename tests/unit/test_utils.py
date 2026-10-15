import pytest

from app.utils import cop, is_safe_next, normalize_phone, parse_int, slugify, whatsapp_url


def test_normalize_phone():
    assert normalize_phone("310 123 4567") == "3101234567"
    assert normalize_phone("+57 310 123 4567") == "3101234567"
    assert normalize_phone("2101234567") is None
    assert normalize_phone("31012") is None
    assert normalize_phone(None) is None


def test_cop_format():
    assert cop(3200000) == "$ 3.200.000"
    assert cop(0) == "$ 0"
    assert cop(None) == ""


def test_slugify_removes_accents_and_symbols():
    assert slugify("Novillo cebú de 18 meses — Vélez!") == "novillo-cebu-de-18-meses-velez"
    assert slugify("???") == "anuncio"


def test_parse_int_accepts_thousand_separators_and_rejects_text():
    assert parse_int("$ 1.200.000") == 1200000
    assert parse_int("1,500") == 1500
    with pytest.raises(ValueError):
        parse_int("abc")
    with pytest.raises(ValueError):
        parse_int("5", minimum=10)


def test_is_safe_next_blocks_external_redirects():
    assert is_safe_next("/panel")
    assert not is_safe_next("//evil.com")
    assert not is_safe_next("https://evil.com")
    assert not is_safe_next("")


def test_is_safe_next_blocks_backslash_and_control_characters():
    # Los navegadores leen «/\evil.com» como «//evil.com»
    assert not is_safe_next("/\\evil.com")
    assert not is_safe_next("/panel\\..\\x")
    assert not is_safe_next("/\t/evil.com")
    assert not is_safe_next("/panel\r\nSet-Cookie: x=1")


def test_parse_int_rejects_non_ascii_digits():
    for raw in ("²", "١٢٣", "１２３"):
        with pytest.raises(ValueError, match="solo números"):
            parse_int(raw)


def test_whatsapp_url_prefills_message():
    url = whatsapp_url("3101234567", "Hola, ¿sigue disponible?")
    assert url.startswith("https://wa.me/573101234567?text=") and "Hola" in url
    assert whatsapp_url("", "x").startswith("https://wa.me/?text=")
