"""
GENERAR TARJETA — PROVINCIA POLÍTICA
=====================================
Genera una tarjeta tipográfica 1080x1080 para acompañar posts en X / Instagram.
Estética idéntica a la plantilla de Canva DAHKUcfLMKA.

Fondo negro #080808, tipografía Fraunces (titular), Inter (bajada),
JetBrains Mono (categoría y marca). Líneas decorativas en dorado #D4A832.
"""

import os
import io
import textwrap
from PIL import Image, ImageDraw, ImageFont

# ─── COLORES (idéntica a Canva DAHKUcfLMKA) ──────────────────────────────────
BG_COLOR = (8, 8, 8)              # #080808
GOLD = (212, 168, 50)             # #D4A832
WHITE = (240, 232, 213)           # #f0e8d5 (ligeramente cálido)
GOLD_DIM = (138, 101, 16)         # bronce apagado

# ─── DIMENSIONES ─────────────────────────────────────────────────────────────
W, H = 1080, 1080
MARGIN_X = 80

# ─── PATHS DE FUENTES ────────────────────────────────────────────────────────
# El workflow descarga las fuentes a esta carpeta antes de ejecutar
FONT_DIR = os.environ.get("FONT_DIR", "fonts")

FONT_TITULAR = os.path.join(FONT_DIR, "Fraunces-Bold.ttf")
FONT_TITULAR_ITALIC = os.path.join(FONT_DIR, "Fraunces-BoldItalic.ttf")
FONT_BAJADA = os.path.join(FONT_DIR, "Inter-Regular.ttf")
FONT_MARCA = os.path.join(FONT_DIR, "Fraunces-Italic.ttf")
FONT_MONO = os.path.join(FONT_DIR, "JetBrainsMono-Regular.ttf")


def _load_font(path, size):
    """Carga una fuente. Si falla, usa una fallback del sistema."""
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        # Fallback a fuente default si no encuentra el archivo
        return ImageFont.load_default()


def _wrap_text(text, font, max_width, draw):
    """Divide el texto en líneas que caben en max_width."""
    if not text:
        return []
    palabras = text.split()
    lineas = []
    actual = ""
    for palabra in palabras:
        test = (actual + " " + palabra).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        ancho = bbox[2] - bbox[0]
        if ancho <= max_width:
            actual = test
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _font_size_for_titular(texto, draw, max_width, max_height):
    """Encuentra el tamaño de fuente óptimo para el titular para que entre bien."""
    # Empieza grande y baja hasta que entre
    for size in range(96, 44, -4):
        font = _load_font(FONT_TITULAR, size)
        lineas = _wrap_text(texto, font, max_width, draw)
        if len(lineas) > 5:  # demasiadas líneas, baja tamaño
            continue
        # Calcular altura total
        line_h = int(size * 1.1)
        total_h = line_h * len(lineas)
        if total_h <= max_height:
            return size, font, lineas
    # Último recurso
    size = 44
    font = _load_font(FONT_TITULAR, size)
    lineas = _wrap_text(texto, font, max_width, draw)
    return size, font, lineas


def generar_tarjeta(titulo, bajada="", categoria="", output_path="tarjeta.png"):
    """
    Genera una tarjeta 1080x1080 y la guarda en output_path.

    Args:
        titulo: texto principal del tuit (el titular grande)
        bajada: texto secundario / contexto breve (opcional)
        categoria: nombre de la categoría que aparece abajo a la izquierda
        output_path: dónde guardar el PNG
    """
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # ─── Línea dorada superior decorativa ────────────────────────────────────
    # Posición: top 74, left 80, width 200, height 5
    draw.rectangle([MARGIN_X, 74, MARGIN_X + 200, 74 + 5], fill=GOLD)

    # ─── Línea dorada chica encima del titular ───────────────────────────────
    # Posición: top 260, left 80, width 60, height 5
    draw.rectangle([MARGIN_X, 260, MARGIN_X + 60, 260 + 5], fill=GOLD)

    # ─── Titular del tuit ─────────────────────────────────────────────────────
    # Posición: top 280, dentro de un box de 1000x345
    max_width_titular = 920  # 1080 - 80*2
    max_height_titular = 460
    titular = titulo.strip() if titulo else ""
    size, font_titular, lineas = _font_size_for_titular(
        titular, draw, max_width_titular, max_height_titular
    )
    y = 280
    line_h = int(size * 1.1)
    for linea in lineas:
        draw.text((MARGIN_X, y), linea, font=font_titular, fill=WHITE)
        y += line_h

    # ─── Bajada / contexto breve ──────────────────────────────────────────────
    # Posición: top ~820, font Inter regular tamaño 24
    if bajada:
        font_bajada = _load_font(FONT_BAJADA, 24)
        lineas_bajada = _wrap_text(bajada.strip(), font_bajada, 920, draw)
        # Limitar a 3 líneas para que no choque con el footer
        lineas_bajada = lineas_bajada[:3]
        y_bajada = 820
        for linea in lineas_bajada:
            draw.text((MARGIN_X, y_bajada), linea, font=font_bajada, fill=WHITE)
            y_bajada += 32

    # ─── Footer: categoría a la izquierda ─────────────────────────────────────
    if categoria:
        font_cat = _load_font(FONT_MONO, 14)
        cat_text = categoria.upper()
        # Línea pequeña dorada al lado de la categoría
        draw.text((MARGIN_X + 11, 1018), cat_text, font=font_cat, fill=GOLD)

    # ─── Footer: "Provincia Política" a la derecha (marca) ────────────────────
    font_marca = _load_font(FONT_MARCA, 22)
    marca_text = "Provincia Política"
    bbox = draw.textbbox((0, 0), marca_text, font=font_marca)
    marca_w = bbox[2] - bbox[0]
    x_marca = W - MARGIN_X - marca_w
    draw.text((x_marca, 1013), marca_text, font=font_marca, fill=WHITE)

    # Guardar
    img.save(output_path, "PNG", optimize=True)
    return output_path


def generar_tarjeta_bytes(titulo, bajada="", categoria=""):
    """Genera la tarjeta y la devuelve como bytes (sin guardar a disco)."""
    buf = io.BytesIO()
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Líneas decorativas
    draw.rectangle([MARGIN_X, 74, MARGIN_X + 200, 74 + 5], fill=GOLD)
    draw.rectangle([MARGIN_X, 260, MARGIN_X + 60, 260 + 5], fill=GOLD)

    # Titular
    titular = titulo.strip() if titulo else ""
    size, font_titular, lineas = _font_size_for_titular(titular, draw, 920, 460)
    y = 280
    line_h = int(size * 1.1)
    for linea in lineas:
        draw.text((MARGIN_X, y), linea, font=font_titular, fill=WHITE)
        y += line_h

    # Bajada
    if bajada:
        font_bajada = _load_font(FONT_BAJADA, 24)
        lineas_bajada = _wrap_text(bajada.strip(), font_bajada, 920, draw)[:3]
        y_bajada = 820
        for linea in lineas_bajada:
            draw.text((MARGIN_X, y_bajada), linea, font=font_bajada, fill=WHITE)
            y_bajada += 32

    # Categoría
    if categoria:
        font_cat = _load_font(FONT_MONO, 14)
        draw.text((MARGIN_X + 11, 1018), categoria.upper(), font=font_cat, fill=GOLD)

    # Marca
    font_marca = _load_font(FONT_MARCA, 22)
    bbox = draw.textbbox((0, 0), "Provincia Política", font=font_marca)
    marca_w = bbox[2] - bbox[0]
    draw.text((W - MARGIN_X - marca_w, 1013), "Provincia Política", font=font_marca, fill=WHITE)

    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


if __name__ == "__main__":
    # Prueba rápida
    generar_tarjeta(
        titulo="Kicillof conduce el PJ bonaerense",
        bajada="Hoy asume la presidencia del PJ. El paso más concreto hacia 2027.",
        categoria="Internas PJ",
        output_path="tarjeta_test.png"
    )
    print("✓ Tarjeta generada en tarjeta_test.png")
