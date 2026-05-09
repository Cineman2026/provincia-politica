"""
CARGAR BANCO HISTÓRICO — PROVINCIA POLÍTICA
=============================================
Script de uso único: descarga las imágenes de todas las notas publicadas
en Notion y las clasifica en el banco de imágenes según su contenido.

Uso: python cargar_banco_historico.py
"""

import os
import sys
import time
import hashlib
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")

# ─── CLASIFICACIÓN ───────────────────────────────────────────────────────────
CLASIFICACION = {
    "actores/kicillof": ["kicillof", "axel", "gobernador"],
    "actores/magario": ["magario", "verónica", "vicegobernadora"],
    "actores/bianco": ["bianco", "carli"],
    "actores/maximo": ["máximo kirchner", "maximo kirchner"],
    "actores/cristina": ["cristina kirchner", "cfk", "cristina fernández"],
    "lugares/casa-gobierno": ["casa de gobierno"],
    "lugares/legislatura": ["legislatura", "diputados", "senado"],
    "lugares/banco-provincia": ["banco provincia", "banco de la provincia"],
    "lugares/cgt": ["cgt"],
    "lugares/pj": ["pj ", "peronismo", "partido justicialista"],
    "lugares/ucr": ["ucr ", "radical"],
    "lugares/pro": ["pro ", "macri", "santilli"],
    "lugares/lla": ["la libertad avanza", "milei", "lla "],
    "temas/educacion": ["educación", "escuela", "docente", "universidad"],
    "temas/salud": ["salud", "hospital", "médico", "sanitario"],
    "temas/economia": ["economía", "presupuesto", "deuda", "fondos", "fiscal"],
    "temas/transporte": ["transporte", "subte", "tren", "colectivo"],
    "temas/agro": ["agro", "rural", "campo", "cosecha"],
    "temas/jubilados": ["jubilad", "anses"],
    "temas/trabajadores": ["trabajadores", "sindicato", "gremio"],
}

CATEGORIA_A_CARPETA = {
    "Ejecutivo": "actores/kicillof",
    "Legislatura": "lugares/legislatura",
    "Internas PJ": "lugares/pj",
    "Conurbano": "sin-clasificar",
    "Oposición": "sin-clasificar",
    "Economía": "temas/economia",
    "Última hora": "sin-clasificar",
}

BANCO_DIR = "assets/banco"
TODAS_CARPETAS = list(set(list(CLASIFICACION.keys()) + list(CATEGORIA_A_CARPETA.values()) + ["sin-clasificar"]))


def crear_carpetas():
    for sub in TODAS_CARPETAS:
        os.makedirs(os.path.join(BANCO_DIR, sub), exist_ok=True)


def clasificar(titulo, categoria):
    """Clasifica una imagen según título y categoría."""
    texto = titulo.lower()
    for carpeta, palabras in CLASIFICACION.items():
        if any(p in texto for p in palabras):
            return carpeta
    if categoria in CATEGORIA_A_CARPETA:
        return CATEGORIA_A_CARPETA[categoria]
    return "sin-clasificar"


def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]


def ya_existe(url):
    h = hash_url(url)
    for sub in TODAS_CARPETAS:
        carpeta = os.path.join(BANCO_DIR, sub)
        if not os.path.exists(carpeta):
            continue
        for archivo in os.listdir(carpeta):
            if h in archivo:
                return True
    return False


def descargar(url, destino):
    try:
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ProvinciaPoliticaBot/1.0)"
        })
        if r.status_code != 200 or len(r.content) < 5000:
            return False
        with open(destino, "wb") as f:
            f.write(r.content)
        return True
    except Exception:
        return False


def obtener_notas_publicadas():
    """Trae todas las notas con Estado=Publicada de Notion."""
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    notas = []
    cursor = None
    while True:
        body = {
            "filter": {"property": "Estado", "select": {"equals": "Publicada"}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
            headers=headers, json=body, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        notas.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return notas


def main():
    print("=" * 52)
    print("  CARGAR BANCO HISTÓRICO — Provincia Política")
    print("=" * 52)
    print()
    
    if not NOTION_TOKEN:
        print("❌ Falta NOTION_TOKEN")
        sys.exit(1)
    
    crear_carpetas()
    print("📁 Carpetas listas\n")
    
    print("📥 Trayendo notas publicadas de Notion...")
    notas = obtener_notas_publicadas()
    print(f"   {len(notas)} notas encontradas\n")
    
    descargadas = 0
    sin_imagen = 0
    duplicadas = 0
    errores = 0
    
    for nota in notas:
        props = nota.get("properties", {})
        titulo_data = props.get("Nombre", {}).get("title", [])
        titulo = titulo_data[0].get("plain_text", "") if titulo_data else ""
        imagen = (props.get("Imagen") or {}).get("url", "") or ""
        cat_prop = props.get("Categoría") or props.get("Categoria") or {}
        cat_select = cat_prop.get("select") if cat_prop else None
        categoria = cat_select.get("name", "") if cat_select else ""
        
        if not imagen:
            sin_imagen += 1
            continue
        
        if ya_existe(imagen):
            duplicadas += 1
            continue
        
        carpeta = clasificar(titulo, categoria)
        h = hash_url(imagen)
        ext = imagen.split(".")[-1].split("?")[0][:4].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            ext = "jpg"
        nombre = f"notion-{h}.{ext}"
        destino = os.path.join(BANCO_DIR, carpeta, nombre)
        
        if descargar(imagen, destino):
            descargadas += 1
            print(f"   ✓ [{carpeta}] {titulo[:55]}")
        else:
            errores += 1
            print(f"   ✗ {titulo[:55]} (fallo descarga)")
        
        time.sleep(0.5)  # no atorar las fuentes
    
    print()
    print("=" * 52)
    print(f"  ✅ Descargadas: {descargadas}")
    print(f"  ⏭️  Sin imagen: {sin_imagen}")
    print(f"  ♻️  Duplicadas: {duplicadas}")
    print(f"  ❌ Errores: {errores}")
    print("=" * 52)
    
    print("\n📊 Estado del banco:")
    for sub in sorted(TODAS_CARPETAS):
        carpeta = os.path.join(BANCO_DIR, sub)
        if os.path.exists(carpeta):
            cantidad = len([f for f in os.listdir(carpeta) if not f.startswith(".")])
            if cantidad > 0:
                print(f"   {sub}: {cantidad} fotos")


if __name__ == "__main__":
    main()
