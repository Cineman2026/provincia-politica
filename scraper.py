"""
SCRAPER — PROVINCIA POLÍTICA
=============================
Scrapea portales de noticias políticas bonaerenses y extrae
titulares, copetes e imágenes reales para el agente redactor.

Portales: letrap.com.ar, latecla.info, infocielo.com

Genera: scraper_output.json con las noticias encontradas
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TZ_ARG = timezone(timedelta(hours=-3))

PORTALES = [
    {
        "nombre": "Letra P",
        "url": "https://www.letrap.com.ar",
        "selectores": {
            "articulos": "article, .post, .entry, .news-item, h2 a, h3 a",
            "titulo": "h1, h2, h3",
            "copete": "p, .summary, .excerpt, .copete",
        }
    },
    {
        "nombre": "La Tecla",
        "url": "https://www.latecla.info",
        "selectores": {
            "articulos": "article, .post, .entry, h2 a, h3 a",
            "titulo": "h1, h2, h3",
            "copete": "p, .summary, .excerpt",
        }
    },
    {
        "nombre": "Infocielo",
        "url": "https://infocielo.com",
        "selectores": {
            "articulos": "article, .post, .entry, h2 a, h3 a",
            "titulo": "h1, h2, h3",
            "copete": "p, .summary, .excerpt",
        }
    },
]

PALABRAS_CLAVE = [
    # Política bonaerense general
    "kicillof", "provincia", "bonaerense", "pj", "kirchner", "milei",
    "gobernador", "buenos aires", "peronismo", "elecciones", "2027",
    "magario", "berni", "axel", "cristina", "conurbano", "intendente",
    # Legislatura — términos específicos
    "legislatura", "senado", "diputados", "senadores", "comisión",
    "proyecto de ley", "sesión", "vicegobernadora", "cámara",
    # Otros actores políticos nacionales/provinciales
    "bianco", "santilli", "bullrich", "máximo", "massa",
    # Intendentes del Conurbano (PJ)
    "espinoza", "insaurralde", "achával", "cascallares", "ferraresi",
    "mendoza", "mussi", "watson", "otermín", "nardini", "secco",
    # Intendentes del interior PBA
    "garro", "galli", "petrecca", "britos",
    # Sindicatos y líderes gremiales
    "sindicato", "gremio", "cgt", "cta", "moyano", "daer", "yasky",
    "godoy", "maturano", "aguiar", "sasia", "acuña",
    # Docentes
    "ctera", "feb", "suteba", "alesso", "petrocini", "docente"
]

def es_relevante(texto):
    """Verifica si el texto contiene palabras clave de política bonaerense."""
    texto_lower = texto.lower()
    return any(kw in texto_lower for kw in PALABRAS_CLAVE)

def extraer_og_image(page):
    """Extrae la imagen og:image de una página."""
    try:
        og = page.get_attribute('meta[property="og:image"]', 'content')
        if og and og.startswith('http'):
            return og
    except Exception:
        pass
    try:
        twitter = page.get_attribute('meta[name="twitter:image"]', 'content')
        if twitter and twitter.startswith('http'):
            return twitter
    except Exception:
        pass
    return ""

def scrape_portal(page, portal):
    """Scrapea un portal y devuelve lista de noticias."""
    noticias = []
    nombre = portal["nombre"]
    
    print(f"  → Scrapendo {nombre}...")
    
    try:
        page.goto(portal["url"], wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        
        # Extraer todos los links de artículos
        links = page.eval_on_selector_all(
            "a[href]",
            """elements => elements
                .map(e => ({href: e.href, text: e.innerText.trim()}))
                .filter(e => e.text.length > 20 && e.href.includes(window.location.hostname))
            """
        )
        
        # Filtrar por relevancia y deduplicar
        links_relevantes = []
        urls_vistas = set()
        for link in links:
            href = link.get("href", "")
            text = link.get("text", "")
            if href in urls_vistas:
                continue
            if len(text) < 20 or len(text) > 300:
                continue
            if not es_relevante(text):
                continue
            urls_vistas.add(href)
            links_relevantes.append({"url": href, "titulo": text})
        
        print(f"     {len(links_relevantes)} artículos relevantes encontrados")
        
        # Visitar hasta 5 artículos por portal para extraer contenido completo
        for item in links_relevantes[:7]:
            try:
                page.goto(item["url"], wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1500)
                
                # Título
                titulo = ""
                for sel in ["h1", ".titulo", ".headline", ".entry-title"]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            titulo = el.inner_text().strip()
                            if len(titulo) > 15:
                                break
                    except Exception:
                        pass
                
                if not titulo:
                    titulo = item["titulo"]
                
                # Copete / primer párrafo
                copete = ""
                for sel in [".copete", ".summary", ".excerpt", ".lead", "article p", "p"]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            copete = el.inner_text().strip()
                            if len(copete) > 30:
                                break
                    except Exception:
                        pass
                
                # Imagen
                imagen = extraer_og_image(page)
                if not imagen:
                    try:
                        img = page.query_selector("article img, .featured-image img, .post-thumbnail img")
                        if img:
                            src = img.get_attribute("src") or ""
                            if src.startswith("http"):
                                imagen = src
                    except Exception:
                        pass
                
                if titulo and es_relevante(titulo):
                    noticias.append({
                        "portal": nombre,
                        "url": item["url"],
                        "titulo": titulo[:300],
                        "copete": copete[:500],
                        "imagen": imagen,
                    })
                    print(f"     ✓ {titulo[:60]}...")
                    
            except PlaywrightTimeout:
                print(f"     ⏱ Timeout en {item['url'][:60]}")
                continue
            except Exception as e:
                print(f"     ⚠ Error: {e}")
                continue
                
    except Exception as e:
        print(f"     ❌ Error scrapeando {nombre}: {e}")
    
    return noticias

def main():
    print(f"\n{'='*52}")
    print(f"  PROVINCIA POLÍTICA — Scraper")
    print(f"  {datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')} ARG")
    print(f"{'='*52}\n")
    
    todas_las_noticias = []
    
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

        # ─── BLOQUEO DE RECURSOS PESADOS ──────────────────────────────────
        # No bloqueamos imágenes porque las necesitamos para extraer og:image.
        # Bloqueamos: fuentes web, hojas de estilo de terceros, ads y trackers.
        BLOQUEAR_DOMINIOS = [
            "googletagmanager.com", "google-analytics.com", "googlesyndication.com",
            "doubleclick.net", "facebook.net", "facebook.com/tr",
            "twitter.com/i/adsct", "ads-twitter.com",
            "scorecardresearch.com", "criteo.com", "taboola.com",
            "outbrain.com", "amazon-adsystem.com", "adsrvr.org",
            "tiktok.com/i18n/pixel", "snapchat.com",
        ]

        def manejador_ruta(route):
            request = route.request
            url = request.url.lower()
            tipo = request.resource_type
            # Bloquear fuentes web (no afectan extracción de texto/imagen)
            if tipo == "font":
                return route.abort()
            # Bloquear media (videos/audios) — no necesitamos
            if tipo == "media":
                return route.abort()
            # Bloquear dominios de ads/trackers conocidos
            if any(dominio in url for dominio in BLOQUEAR_DOMINIOS):
                return route.abort()
            return route.continue_()

        page.route("**/*", manejador_ruta)
        
        for portal in PORTALES:
            noticias = scrape_portal(page, portal)
            todas_las_noticias.extend(noticias)
            time.sleep(2)
        
        browser.close()
    
    # Guardar resultado
    output = {
        "fecha": datetime.now(TZ_ARG).isoformat(),
        "total": len(todas_las_noticias),
        "noticias": todas_las_noticias
    }
    
    with open("scraper_output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Scraper terminó. {len(todas_las_noticias)} noticias guardadas en scraper_output.json")
    
    if len(todas_las_noticias) == 0:
        print("⚠️  Sin noticias — el agente redactor usará web_search como fallback")
        sys.exit(0)  # No es error, el agente puede funcionar sin scraper

if __name__ == "__main__":
    main()
