"""
AGENTE REDACTOR — PROVINCIA POLÍTICA v1.0
==========================================
Busca noticias políticas bonaerenses, las redacta con voz editorial
de Provincia Política y las carga en Notion como borradores.

Uso manual:    python agente_redactor.py
Uso con tema:  python agente_redactor.py --tema "Kicillof reunión intendentes"
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN      = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID      = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")

IMAGEN_INSTITUCIONAL = 'https://cineman2026.github.io/provincia-politica/assets/imagen_institucional.jpg'

FUENTES = [
    "letrap.com.ar",
    "latecla.info",
    "infocielo.com",
    "infobae.com/política",
    "pagina12.com.ar",
    "gba.gob.ar/gobierno/noticias",
    "telam.com.ar",
]

TURNO_CONFIG = {
    "manana": {"cantidad": 3, "etiqueta": "🌅 Mañana"},
    "mediodia": {"cantidad": 2, "etiqueta": "☀️ Mediodía"},
    "tarde": {"cantidad": 2, "etiqueta": "🌆 Tarde"},
    "manual": {"cantidad": 3, "etiqueta": "📝 Manual"},
}

# ─── PROMPT DEL AGENTE ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sos el Agente Redactor de Provincia Política, una agencia de noticias política digital especializada en la Provincia de Buenos Aires.

IDENTIDAD EDITORIAL
- Cobertura: Ejecutivo de Kicillof, Legislatura provincial, municipios del Conurbano, internas del PJ, oposición bonaerense, economía provincial.
- Posicionamiento: cercano al gobierno de Kicillof pero con estética independiente. Directo. Sin vueltas.
- Voz: estructura rigurosa de Alconada Mon + ironía elegante de Asís + valentía de Navarro + capacidad de Lantos de meter al lector en la rosca.

ENFOQUE EDITORIAL — REGLA CLAVE
Cuando el tema involucra a Kicillof o al gobierno provincial, el enfoque NO es crítico sino contextual. El peronismo bonaerense aparece como actor relevante, no como objeto de cuestionamiento.
Ejemplo: si Kicillof no asiste a un acto, la nota no es "Kicillof faltó". La nota es "el Conurbano puso el cuerpo mientras la conducción sindical debatía su próximo paso".

LOS TRES REGISTROS — el agente elige el correcto según el tema:

R1 — INFORMATIVO/INSTITUCIONAL
Cuándo: declaraciones, anuncios, datos económicos, conferencias de prensa.
Tono: directo, riguroso, datos al frente, ironía mínima.
Apertura: cita textual seca o dato contundente. Cierre: proyección seca.

R2 — ANÁLISIS/CONTEXTO
Cuándo: lectura política, escenarios, balance de poder, internas públicas.
Tono: equilibrado, reconstrucción de escenas, citas off, proyección.
Apertura: escena concreta. Cierre: pregunta abierta o escenario futuro.

R3 — ROSCA/TRASTIENDA
Cuándo: internas de despacho, peleas de poder, jugadas no contadas, mensajes filtrados.
Tono: irónico, elegante, frases memorables, escenas reconstruidas.
Apertura: frase de impacto. Cierre: remate lapidario en una línea.

REGLAS DE ESCRITURA
- Título: máximo 12 palabras, sin verbo auxiliar, sin clickbait.
- Copete: 2-3 líneas con el dato más importante.
- Cuerpo: 250-500 palabras. Párrafos cortos, máximo 4 líneas. Subtítulos en negrita cada 3-4 párrafos.

PALABRAS PROHIBIDAS: "es importante destacar", "cabe mencionar", "en este sentido", "en este contexto", "dicho esto", "en conclusión", "sin lugar a dudas", "es menester aclarar", "vale la pena señalar". Cero adjetivos calificativos sobre protagonistas.

CATEGORÍAS VÁLIDAS: Ejecutivo / Legislatura / Internas PJ / Conurbano / Oposición / Economía / Última hora

FORMATO DE SALIDA — siempre responder con este JSON exacto, sin texto adicional:
{
  "registro": "R1|R2|R3",
  "categoria": "categoría",
  "titulo": "título de la nota",
  "copete": "copete de 2-3 líneas",
  "cuerpo": "cuerpo completo de la nota"
}"""


# ─── FUNCIONES ───────────────────────────────────────────────────────────────

def detectar_turno():
    """Detecta el turno del día según la hora actual."""
    hora = datetime.now().hour
    if 5 <= hora < 11:
        return "manana"
    elif 11 <= hora < 15:
        return "mediodia"
    else:
        return "tarde"


def verificar_imagen(url):
    """Verifica que una URL de imagen sea accesible públicamente."""
    if not url:
        return False
    if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return False
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        return r.status_code == 200
    except:
        return False


def buscar_imagen(tema_nota, fuentes_prioritarias=None):
    """Busca una imagen válida para la nota usando la API de Claude con web search."""
    if not ANTHROPIC_API_KEY:
        return IMAGEN_INSTITUCIONAL

    prompt = f"""Buscá una imagen periodística para esta nota: {tema_nota}

Buscá en cualquier fuente web. Priorizá: telam.com.ar, prensa.gba.gob.ar, wikimedia.org, infobae.com, lanacion.com.ar.

Reglas estrictas:
1. La URL debe terminar en .jpg, .jpeg, .png o .webp
2. Debe ser una imagen de prensa, no de redes sociales
3. Debe corresponder al tema de la nota
4. Sin espacios ni caracteres especiales en la URL

Respondé SOLO con la URL de la imagen, nada más. Si no encontrás ninguna válida, respondé exactamente: NINGUNA"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        data = response.json()
        for block in data.get("content", []):
            if block.get("type") == "text":
                url = block.get("text", "").strip()
                if url and url != "NINGUNA" and verificar_imagen(url):
                    return url
    except:
        pass
    
    return IMAGEN_INSTITUCIONAL


def buscar_y_redactar(tema=None, turno="manual"):
    """Llama a la API de Claude para buscar noticias y redactar."""
    
    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta la variable de entorno ANTHROPIC_API_KEY")
    
    config = TURNO_CONFIG[turno]
    cantidad = config["cantidad"]
    
    if tema:
        user_prompt = f"""Redactá UNA nota sobre este tema específico para Provincia Política:

TEMA: {tema}

Buscá información actualizada en: {', '.join(FUENTES)}

Elegí el registro correcto (R1/R2/R3) según el tipo de noticia y redactá la nota completa.
Respondé SOLO con el JSON, sin texto adicional."""
    else:
        user_prompt = f"""Buscá las {cantidad} noticias más relevantes sobre política bonaerense de HOY ({datetime.now().strftime('%d/%m/%Y')}) en estas fuentes: {', '.join(FUENTES)}

Priorizá noticias sobre: Kicillof y el Ejecutivo provincial, Legislatura bonaerense, internas del PJ, municipios del Conurbano, oposición en territorio bonaerense.

Para CADA noticia, redactá la nota completa eligiendo el registro correcto (R1/R2/R3).

Respondé con un array JSON de {cantidad} notas, cada una con el formato exacto:
[
  {{
    "registro": "R1|R2|R3",
    "categoria": "categoría",
    "titulo": "título",
    "copete": "copete",
    "cuerpo": "cuerpo completo"
  }}
]

Respondé SOLO con el JSON, sin texto adicional."""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}]
    }
    
    print(f"🔍 Buscando noticias ({turno})...")
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=120
    )
    response.raise_for_status()
    data = response.json()
    
    # Extraer texto de la respuesta
    texto = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            texto += block.get("text", "")
    
    # Parsear JSON
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()
    
    resultado = json.loads(texto)
    
    # Normalizar a lista
    if isinstance(resultado, dict):
        resultado = [resultado]
    
    return resultado


def cargar_en_notion(nota, turno="manual"):
    # Si no hay imagen válida, buscar una o usar la institucional
    if not nota.get('imagen') or not verificar_imagen(nota.get('imagen', '')):
        print(f"  🔍 Buscando imagen para: {nota['titulo'][:50]}...")
        nota['imagen'] = buscar_imagen(nota['titulo'])
        if nota['imagen'] == IMAGEN_INSTITUCIONAL:
            print(f"  🏢 Usando imagen institucional")
        else:
            print(f"  ✅ Imagen encontrada")

    """Carga una nota en Notion como borrador."""
    
    if not NOTION_TOKEN:
        raise ValueError("Falta la variable de entorno NOTION_TOKEN")
    
    etiqueta = TURNO_CONFIG[turno]["etiqueta"]
    titulo_completo = nota["titulo"]
    
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Nombre": {
                "title": [{"text": {"content": titulo_completo}}]
            },
            "Copete": {
                "rich_text": [{"text": {"content": nota.get("copete", "")}}]
            },
            "Cuerpo": {
                "rich_text": [{"text": {"content": nota.get("cuerpo", "")[:2000]}}]
            },
            "Categoría": {
                "select": {"name": nota.get("categoria", "Última hora")}
            },
            "Estado": {
                "select": {"name": "Borrador"}
            },
            "Destacada": {
                "checkbox": False
            }
        }
    }
    
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json=payload,
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    
    page_url = result.get("url", "")
    print(f"  ✅ [{nota['registro']}] {titulo_completo[:60]}...")
    print(f"     Notion: {page_url}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Agente Redactor — Provincia Política")
    parser.add_argument("--tema", type=str, help="Tema específico para redactar", default=None)
    parser.add_argument("--turno", type=str, choices=["manana", "mediodia", "tarde", "manual"], 
                        help="Turno del día", default=None)
    args = parser.parse_args()
    
    turno = args.turno or ("manual" if args.tema else detectar_turno())
    
    print(f"\n{'='*50}")
    print(f"  PROVINCIA POLÍTICA — Agente Redactor")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')} — {TURNO_CONFIG[turno]['etiqueta']}")
    print(f"{'='*50}\n")
    
    try:
        notas = buscar_y_redactar(tema=args.tema, turno=turno)
        print(f"📝 {len(notas)} nota(s) generada(s). Cargando en Notion...\n")
        
        for i, nota in enumerate(notas, 1):
            print(f"Nota {i}/{len(notas)}:")
            cargar_en_notion(nota, turno=turno)
            print()
        
        print(f"✨ Listo. Revisá los borradores en Notion y aprobá los que quieras publicar.")
        print(f"   https://www.notion.so/{NOTION_DB_ID}\n")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando respuesta del agente: {e}")
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"❌ Error de API: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
