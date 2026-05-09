"""
SCRAPER BANCO DE IMÁGENES — PROVINCIA POLÍTICA
================================================
Recorre fuentes oficiales y descarga fotos para construir
un banco de imágenes propio que pueda usar el agente redactor.

Fuentes:
- prensa.gba.gob.ar (sitio oficial del gobierno PBA)
- legislaturapba.gob.ar (Legislatura)

Cadencia: martes y viernes a las 3 AM (configurado en cron-job.org)

Carpetas de salida:
- /assets/banco/actores/{kicillof,magario,bianco,maximo,cristina}/
- /assets/banco/lugares/{casa-gobierno,legislatura,...}/
- /assets/banco/sin-clasificar/
"""

import os
import sys
import json
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TZ_ARG = timezone(timedelta(hours=-3))

# ─── FUENTES ─────────────────────────────────────────────────────────────────
FUENTES = [
    {
        "nombre": "Prensa GBA",
        "url": "https://prensa.gba.gob.ar",
        "max_notas": 20,
    },
    {
        "nombre": "Legislatura PBA",
        "url": "https://www.legislaturapba.gob.ar",
        "max_notas": 10,
    },
]

# ─── CLASIFICACIÓN POR PALABRAS CLAVE ────────────────────────────────────────
# Si el título de la nota o el alt de la imagen contiene alguna palabra clave,
# se asigna a la carpeta correspondiente.
CLASIFICACION = {
    "actores/kicillof": ["kicillof", "axel", "gobernador"],
    "actores/magario": ["magario", "verónica", "vicegobernadora"],
    "actores/bianco": ["bianco", "carli"],
    "actores/maximo": ["máximo kirchner", "maximo kirchner"],
    "actores/cristina": ["cristina kirchner", "cfk", "cristina fernández"],
    "lugares/casa-gobierno": ["casa de gobierno", "casa rosada provincial"],
    "lugares/legislatura": ["legislatura", "diputados", "senado bonaerense"],
    "lugares/banco-provincia": ["banco provincia", "banco de la provincia"],
    "lugares/cgt": ["cgt"],
    "temas/educacion": ["educación", "escuela", "docente", "universidad"],
    "temas/salud": ["salud", "hospital", "médico", "sanitario"],
    "temas/economia": ["economía", "presupuesto", "deuda", "fondos"],
    "temas/transporte": ["transporte", "subte", "tren", "colectivo"],
    "temas/agro": ["agro", "rural", "campo", "cosecha"],
}

# ─── DESTINO DE CARPETAS ─────────────────────────────────────────────────────
BANCO_DIR = "assets/banco"
TODAS_CARPETAS = list(CLASIFICACION.keys()) + ["sin-clasificar"]


def crear_carpetas():
    """Crea la estructura de carpetas si no existe."""
    for sub in TODAS_CARPETAS:
        os.makedirs(os.path.join(BANCO_DIR, sub), exist_ok=True)


def clasificar_imagen(titulo, alt_text=""):
    """Devuelve la carpeta correspondiente según el contenido."""
    texto = f"{titulo} {alt_text}".lower()
    for carpeta, palabras in CLASIFICACION.items():
        if any(palabra in texto for palabra in palabras):
            return carpeta
    return "sin-clasificar"


def descargar_imagen(url, destino):
    """Descarga una imagen y la guarda en destino."""
    try:
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ProvinciaPoliticaBot/1.0)"
        })
        if r.status_code != 200:
            return False
        if len(r.content) < 5000:  # menos de 5KB probablemente es un placeholder
            return False
        with open(destino, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"     ⚠ Error descargando: {e}")
        return False


def hash_url(url):
    """Genera un hash corto para nombrar archivos sin colisiones."""
    return hashlib.md5(url.encode()).hexdigest()[:10]


def ya_existe(url):
    """Verifica si una imagen ya fue descargada anteriormente."""
    h = hash_url(url)
    for sub in TODAS_CARPETAS:
        carpeta = os.path.join(BANCO_DIR, sub)
        if not os.path.exists(carpeta):
            continue
        for archivo in os.listdir(carpeta):
            if h in archivo:
                return True
    return False


def scrape_prensa_gba(page):
    """Scrapea prensa.gba.gob.ar."""
    print("  → Scrapeando Prensa GBA...")
    descargadas = 0
    
    try:
        page.goto("https://prensa.gba.gob.ar", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        
        # Obtener links de notas
        links = page.eval_on_selector_all(
            "a[href]",
            """elements => elements
                .map(e => ({href: e.href, text: e.innerText.trim()}))
                .filter(e => e.text.length > 30 && e.href.includes('prensa.gba.gob.ar'))
                .slice(0, 20)
            """
        )
        
        # Visitar cada nota y extraer imagen
        urls_vistas = set()
        for link in links:
            if link["href"] in urls_vistas:
                continue
            urls_vistas.add(link["href"])
            
            try:
                page.goto(link["href"], wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1500)
                
                # Buscar imagen og:image
                img_url = None
                try:
                    og = page.get_attribute('meta[property="og:image"]', 'content')
                    if og and og.startswith("http"):
                        img_url = og
                except Exception:
                    pass
                
                if not img_url:
                    try:
                        img = page.query_selector("article img, .post img, .entry img")
                        if img:
                            src = img.get_attribute("src")
                            if src and src.startswith("http"):
                                img_url = src
                    except Exception:
                        pass
                
                if not img_url:
                    continue
                
                if ya_existe(img_url):
                    continue
                
                # Clasificar
                titulo = link["text"]
                alt = ""
                try:
                    img_el = page.query_selector("article img, .post img")
                    if img_el:
                        alt = img_el.get_attribute("alt") or ""
                except Exception:
                    pass
                
                carpeta = clasificar_imagen(titulo, alt)
                
                # Generar nombre y descargar
                fecha = datetime.now(TZ_ARG).strftime("%Y-%m-%d")
                h = hash_url(img_url)
                ext = img_url.split(".")[-1].split("?")[0][:4].lower()
                if ext not in ["jpg", "jpeg", "png", "webp"]:
                    ext = "jpg"
                nombre = f"prensa-gba-{fecha}-{h}.{ext}"
                destino = os.path.join(BANCO_DIR, carpeta, nombre)
                
                if descargar_imagen(img_url, destino):
                    descargadas += 1
                    print(f"     ✓ [{carpeta}] {titulo[:50]}...")
                
            except PlaywrightTimeout:
                continue
            except Exception as e:
                print(f"     ⚠ {e}")
                continue
    except Exception as e:
        print(f"     ❌ Error en Prensa GBA: {e}")
    
    return descargadas


def scrape_legislatura(page):
    """Scrapea legislaturapba.gob.ar."""
    print("  → Scrapeando Legislatura PBA...")
    descargadas = 0
    
    try:
        page.goto("https://www.legislaturapba.gob.ar", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        
        # Obtener todas las imágenes con alt no vacío
        imagenes = page.eval_on_selector_all(
            "img",
            """elements => elements
                .map(e => ({src: e.src, alt: e.alt || ''}))
                .filter(e => e.src && e.src.startsWith('http') && (e.alt.length > 5 || e.src.includes('upload')))
            """
        )
        
        for img in imagenes[:15]:
            src = img["src"]
            alt = img["alt"]
            
            if ya_existe(src):
                continue
            
            carpeta = clasificar_imagen("", alt)
            if carpeta == "sin-clasificar":
                # Forzar a lugares/legislatura porque viene del sitio
                carpeta = "lugares/legislatura"
            
            fecha = datetime.now(TZ_ARG).strftime("%Y-%m-%d")
            h = hash_url(src)
            ext = src.split(".")[-1].split("?")[0][:4].lower()
            if ext not in ["jpg", "jpeg", "png", "webp"]:
                ext = "jpg"
            nombre = f"legislatura-{fecha}-{h}.{ext}"
            destino = os.path.join(BANCO_DIR, carpeta, nombre)
            
            if descargar_imagen(src, destino):
                descargadas += 1
                print(f"     ✓ [{carpeta}] {alt[:50]}...")
    except Exception as e:
        print(f"     ❌ Error en Legislatura: {e}")
    
    return descargadas


def main():
    print(f"\n{'='*52}")
    print(f"  PROVINCIA POLÍTICA — Scraper Banco")
    print(f"  {datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')} ARG")
    print(f"{'='*52}\n")
    
    crear_carpetas()
    print(f"📁 Carpetas listas en {BANCO_DIR}/\n")
    
    total_descargadas = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        total_descargadas += scrape_prensa_gba(page)
        time.sleep(2)
        total_descargadas += scrape_legislatura(page)
        
        browser.close()
    
    print(f"\n✅ Banco actualizado. {total_descargadas} imágenes nuevas descargadas.")
    
    # Listar contenido del banco
    print(f"\n📊 Estado actual del banco:")
    for sub in TODAS_CARPETAS:
        carpeta = os.path.join(BANCO_DIR, sub)
        if os.path.exists(carpeta):
            cantidad = len([f for f in os.listdir(carpeta) if not f.startswith(".")])
            if cantidad > 0:
                print(f"   {sub}: {cantidad} fotos")

if __name__ == "__main__":
    main()
