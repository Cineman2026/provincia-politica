"""
AGENTE REDACTOR — PROVINCIA POLÍTICA v1.3
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
    "manana":   {"cantidad": 3, "etiqueta": "🌅 Mañana"},
    "mediodia": {"cantidad": 2, "etiqueta": "☀️ Mediodía"},
    "tarde":    {"cantidad": 2, "etiqueta": "🌆 Tarde"},
    "manual":   {"cantidad": 3, "etiqueta": "📝 Manual"},
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

DESTACADA: En cada tanda, marcá exactamente UNA nota como "destacada": true — la más importante o de mayor impacto político del día. El resto llevan "destacada": false.

FORMATO DE SALIDA — siempre responder con este JSON exacto, sin texto adicional:
{
  "registro": "R1|R2|R3",
  "categoria": "categoría",
  "titulo": "título de la nota",
  "copete": "copete de 2-3 líneas",
  "cuerpo": "cuerpo completo de la nota",
  "destacada": true|false
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


def extraer_texto_respuesta(content):
    """Extrae todo el texto de los bloques de contenido de la API."""
    texto = ""
    for block in content:
        tipo = block.get("type", "")
        if tipo == "text":
            texto += block.get("text", "")
        elif tipo == "tool_result":
            # Para web_search server-side, el resultado puede venir aquí
            inner = block.get("content", [])
            if isinstance(inner, list):
                for inner_block in inner:
                    if inner_block.get("type") == "text":
                        texto += inner_block.get("text", "")
            elif isinstance(inner, str):
                texto += inner
    return texto


def llamar_api(messages, tools=None):
    """Realiza una llamada a la API de Anthropic y devuelve la data JSON."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "web-search-2025-03-05"
    }

    payload = {
        "model": "claude-opus-4-5",
        "max_tokens": 8000,
        "system": SYSTEM_PROMPT,
        "messages": messages
    }

    if tools:
        payload["tools"] = tools

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=120
    )

    # Loguear status y respuesta para debug
    print(f"   [API] status={response.status_code}")
    if not response.ok:
        print(f"   [API] error body: {response.text[:500]}")
        response.raise_for_status()

    data = response.json()
    print(f"   [API] stop_reason={data.get('stop_reason')} blocks={[b.get('type') for b in data.get('content', [])]}")
    return data


def buscar_y_redactar(tema=None, turno="manual"):
    """Llama a la API de Claude para buscar noticias y redactar."""

    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta la variable de entorno ANTHROPIC_API_KEY")

    config   = TURNO_CONFIG[turno]
    cantidad = config["cantidad"]

    if tema:
        user_prompt = f"""Redactá UNA nota sobre este tema específico para Provincia Política:

TEMA: {tema}

Usá tu conocimiento sobre política bonaerense y la información disponible para redactar la nota.

Elegí el registro correcto (R1/R2/R3) según el tipo de noticia y redactá la nota completa.
Marcá "destacada": true si es la nota más importante, false si no.
Respondé SOLO con el JSON, sin texto adicional."""
    else:
        user_prompt = f"""Redactá {cantidad} notas sobre las noticias más relevantes de política bonaerense de HOY ({datetime.now().strftime('%d/%m/%Y')}).

Priorizá temas sobre: Kicillof y el Ejecutivo provincial, Legislatura bonaerense, internas del PJ, municipios del Conurbano, oposición en territorio bonaerense.

Para CADA nota, elegí el registro correcto (R1/R2/R3).

Marcá "destacada": true SOLO en la nota más importante de esta tanda. El resto llevan "destacada": false.

Respondé con un array JSON de {cantidad} notas, cada una con el formato exacto:
[
  {{
    "registro": "R1|R2|R3",
    "categoria": "categoría",
    "titulo": "título",
    "copete": "copete",
    "cuerpo": "cuerpo completo",
    "destacada": true|false
  }}
]

Respondé SOLO con el JSON, sin texto adicional."""

    print(f"🔍 Buscando noticias ({turno})...")

    # Intentar primero con web_search (server-side tool)
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    messages = [{"role": "user", "content": user_prompt}]

    texto = ""
    try:
        data = llamar_api(messages, tools=tools)
        stop_reason = data.get("stop_reason", "")
        content = data.get("content", [])

        if stop_reason == "end_turn":
            texto = extraer_texto_respuesta(content)
        elif stop_reason == "tool_use":
            # Si la API pide ejecutar tool_use manualmente (no debería con web_search server-side)
            # Continuar el ciclo
            messages.append({"role": "assistant", "content": content})
            tool_results = []
            for block in content:
                if block.get("type") == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.get("id"),
                        "content": "No se pudo ejecutar la búsqueda web."
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
                data2 = llamar_api(messages, tools=tools)
                texto = extraer_texto_respuesta(data2.get("content", []))

        print(f"   [DEBUG] texto extraído (primeros 200 chars): {repr(texto[:200])}")

    except requests.HTTPError as e:
        print(f"   [WARN] web_search falló con HTTP error: {e}. Intentando sin tools...")
        texto = ""

    # Si no obtuvimos texto, intentar sin herramienta web_search
    if not texto.strip():
        print("   [WARN] Sin texto con web_search. Reintentando sin tools...")
        messages_simple = [{"role": "user", "content": user_prompt}]
        data_simple = llamar_api(messages_simple, tools=None)
        texto = extraer_texto_respuesta(data_simple.get("content", []))
        print(f"   [DEBUG] texto sin tools (primeros 200 chars): {repr(texto[:200])}")

    if not texto.strip():
        raise ValueError("La API no devolvió texto en ningún intento")

    # Parsear JSON
    texto = texto.strip()
    # Remover bloques de código markdown si los hay
    if "```" in texto:
        partes = texto.split("```")
        # Tomar el contenido dentro del primer bloque
        if len(partes) >= 2:
            texto = partes[1]
            if texto.startswith("json"):
                texto = texto[4:]
            texto = texto.strip()

    resultado = json.loads(texto)

    # Normalizar a lista
    if isinstance(resultado, dict):
        resultado = [resultado]

    return resultado


def limpiar_destacadas():
    """Desmarca todas las noticias destacadas en Notion antes de cargar las nuevas."""
    if not NOTION_TOKEN:
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "filter": {"property": "Destacada", "checkbox": {"equals": True}}
    }
    response = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
        headers=headers,
        json=payload,
        timeout=30
    )
    if not response.ok:
        print("⚠️ No se pudieron limpiar destacadas anteriores")
        return

    pages = response.json().get("results", [])
    for page in pages:
        requests.patch(
            f"https://api.notion.com/v1/pages/{page['id']}",
            headers=headers,
            json={"properties": {"Destacada": {"checkbox": False}}},
            timeout=15
        )
    print(f"🧹 {len(pages)} destacada(s) anterior(es) limpiada(s)")


def cargar_en_notion(nota, turno="manual"):
    """Carga una nota en Notion como borrador."""

    if not NOTION_TOKEN:
        raise ValueError("Falta la variable de entorno NOTION_TOKEN")

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
                "rich_text": [{"text": {"content": nota.get("copete", "")[:1999]}}]
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
                "checkbox": nota.get("destacada", False)
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

    page_url      = result.get("url", "")
    destacada_str = "⭐" if nota.get("destacada") else " "
    print(f"  ✅ {destacada_str} [{nota['registro']}] {titulo_completo[:60]}...")
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
        limpiar_destacadas()

        notas = buscar_y_redactar(tema=args.tema, turno=turno)
        print(f"📝 {len(notas)} nota(s) generada(s). Cargando en Notion...\n")

        for i, nota in enumerate(notas, 1):
            print(f"Nota {i}/{len(notas)}:")
            cargar_en_notion(nota, turno=turno)
            print()

        print(f"✨ Listo. Revisá los borradores en Notion.")
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
