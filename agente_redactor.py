"""
AGENTE REDACTOR — PROVINCIA POLÍTICA v1.4
==========================================
Busca noticias políticas bonaerenses, las redacta con voz editorial
de Provincia Política y las carga en Notion como borradores.

Uso manual:    python agente_redactor.py
Uso con tema:  python agente_redactor.py --tema "Kicillof reunión intendentes"
"""

import os
import sys
import json
import time
import argparse
import urllib.parse
import requests
import re
from datetime import datetime, timezone, timedelta

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")

# Modelo Anthropic. Override con la env var ANTHROPIC_MODEL si querés cambiarlo.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# Si está en "1", se desactiva la tool web_search (útil si la cuenta no la tiene).
DISABLE_WEB_SEARCH = os.environ.get("DISABLE_WEB_SEARCH", "0") == "1"

TZ_ARG = timezone(timedelta(hours=-3))

FUENTES = [
    "letrap.com.ar",
    "latecla.info",
    "infocielo.com",
    "infobae.com/política",
    "pagina12.com.ar",
    "gba.gob.ar/gobierno/noticias",
    "telam.com.ar",
]

def limpiar_citas(texto):
    """Elimina etiquetas <cite index="..."> y </cite> del texto."""
    if not texto:
        return texto
    # Quitar etiquetas de apertura <cite index="...">
    texto = re.sub(r'<cite\s+index="[^"]*">', '', texto)
    # Quitar etiquetas de cierre </cite>
    texto = re.sub(r'</cite>', '', texto)
    return texto


TURNO_CONFIG = {
    "manana":   {"cantidad": 5, "etiqueta": "🌅 Mañana"},
    "mediodia": {"cantidad": 3, "etiqueta": "☀️ Mediodía"},
    "tarde":    {"cantidad": 3, "etiqueta": "🌆 Tarde"},
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

Cuando el tema involucra al Senado bonaerense o a Verónica Magario, el enfoque es contextual, no crítico. La gestión del Senado aparece como dato político, no como objeto de cuestionamiento. No señalar parálisis legislativa, demoras ni ausencias salvo directiva explícita del director editorial.

Cuando Kicillof aparece como receptor de una situación (declaraciones de terceros, conflictos, presiones), el enfoque es neutro. No redactar frases que lo muestren superado, sorprendido o en posición débil. Ejemplo: no escribir "tuvo que leer en los portales" sino "la declaración llegó primero a los portales".

Las interpretaciones sobre la relación Kicillof-Cristina o sobre las internas del PJ deben atribuirse siempre a fuentes ("desde el entorno de...", "según dirigentes del PJ", "la lectura en Gobernación es que..."). Nunca afirmarlas como hechos verificados.

Las comillas se usan SOLO para citas textuales verificables y atribuidas explícitamente a una persona. No usar comillas para parafrasear, interpretar o resumir la posición de un dirigente. Si no es textual, va sin comillas y con verbo de atribución ("sostuvo", "advirtió", "señaló").

DISTRIBUCIÓN POR CATEGORÍAS — REGLA CLAVE
Cuando se generan varias notas en una misma tanda, las notas DEBEN cubrir categorías DISTINTAS. No concentrar la cobertura en Ejecutivo. Distribuir activamente entre las 7 categorías disponibles: Ejecutivo, Legislatura, Internas PJ, Conurbano, Oposición, Economía, Última hora.
Si en una tanda hay 3 notas, deben ser de 3 categorías distintas.
Si hay 5 notas, deben ser de 5 categorías distintas.
Excepción: solo se puede repetir categoría si no hay material relevante en otras categorías ese día, lo cual debe ser raro.

LOS TRES REGISTROS — el agente elige el correcto según el tema:

R1 — INFORMATIVO/INSTITUCIONAL
Cuándo: declaraciones, anuncios, datos económicos, conferencias de prensa.
Tono: directo, riguroso, datos al frente, ironía mínima.
Apertura: cita textual seca o dato contundente.
Cierre: proyección seca.

R2 — ANÁLISIS/CONTEXTO
Cuándo: lectura política, escenarios, balance de poder, internas públicas.
Tono: equilibrado, reconstrucción de escenas, citas off, proyección.
Apertura: escena concreta.
Cierre: pregunta abierta o escenario futuro.

R3 — ROSCA/TRASTIENDA
Cuándo: internas de despacho, peleas de poder, jugadas no contadas, mensajes filtrados.
Tono: irónico, elegante, frases memorables, escenas reconstruidas.
Apertura: frase de impacto.
Cierre: remate lapidario en una línea.

REGLAS DE ESCRITURA
- Título: máximo 12 palabras, sin verbo auxiliar, sin clickbait.
- Copete: 2-3 líneas con el dato más importante.
- Cuerpo: 250-500 palabras. Párrafos cortos, máximo 4 líneas. Subtítulos en negrita cada 3-4 párrafos.

PALABRAS PROHIBIDAS: "es importante destacar", "cabe mencionar", "en este sentido", "en este contexto", "dicho esto", "en conclusión", "sin lugar a dudas", "es menester aclarar", "vale la pena señalar". Cero adjetivos calificativos sobre protagonistas.

CATEGORÍAS VÁLIDAS: Ejecutivo / Legislatura / Internas PJ / Conurbano / Oposición / Economía / Última hora

DESTACADA: En cada tanda, marcá exactamente UNA nota como "destacada": true — la más importante o de mayor impacto político del día. El resto llevan "destacada": false.

CRITERIOS DE IMAGEN — buscar siempre una URL de imagen para cada nota:
Fuentes permitidas (en orden de preferencia):
1. Prensa oficial del gobierno provincial: prensa.gba.gob.ar, redes de ministerios, AGLP
2. Redes sociales oficiales de funcionarios públicos verificados
3. Portales: letrap.com.ar, latecla.info, infocielo.com, infobae.com, pagina12.com.ar
4. Télam y agencias de noticias

Reglas de selección:
- Solo figuras públicas en ejercicio de su función (acto oficial, conferencia, sesión, marcha)
- Preferir fotos recientes (2024-2026)
- La URL debe terminar en .jpg, .jpeg, .png o .webp y cargar directamente
- No menores, no íntimas, no privadas
- No URLs con espacios

Si no encontrás una URL válida, dejá "imagen" como cadena vacía "".

FORMATO DE SALIDA — SIEMPRE responder con JSON puro, sin texto antes ni después, sin fences markdown.
- Para una sola nota: un objeto JSON.
- Para varias notas: un array JSON.
Cada nota tiene EXACTAMENTE estas claves:
{
  "registro": "R1|R2|R3",
  "categoria": "Ejecutivo|Legislatura|Internas PJ|Conurbano|Oposición|Economía|Última hora",
  "titulo": "título de la nota",
  "copete": "copete de 2-3 líneas",
  "cuerpo": "cuerpo completo de la nota",
  "imagen": "URL directa de la imagen o cadena vacía",
  "destacada": true|false
}"""

# ─── UTILIDADES ──────────────────────────────────────────────────────────────
def detectar_turno():
    """Detecta el turno del día según la hora ARGENTINA (no UTC)."""
    hora = datetime.now(TZ_ARG).hour
    if 5 <= hora < 11:
        return "manana"
    elif 11 <= hora < 15:
        return "mediodia"
    else:
        return "tarde"

def validar_url_imagen(url):
    """Valida y normaliza la URL de imagen para Notion. Devuelve la URL o ''."""
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return ""
    if " " in url:
        return ""
    url_path = url.split("?")[0].split("#")[0].lower()
    extensiones_validas = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    if not any(url_path.endswith(ext) for ext in extensiones_validas):
        return ""
    try:
        url.encode("ascii")
        return url
    except UnicodeEncodeError:
        try:
            partes = urllib.parse.urlsplit(url)
            path_q = urllib.parse.quote(partes.path, safe="/%")
            query = urllib.parse.quote(partes.query, safe="=&%")
            return urllib.parse.urlunsplit((partes.scheme, partes.netloc, path_q, query, ""))
        except Exception:
            return ""

def chunk_rich_text(texto, limite=1900):
    """Divide texto en bloques rich_text de hasta limite chars (Notion exige <=2000)."""
    if not texto:
        return [{"text": {"content": ""}}]
    bloques = []
    while texto:
        bloques.append({"text": {"content": texto[:limite]}})
        texto = texto[limite:]
    return bloques

def post_with_retry(url, headers, payload, timeout=120, max_retries=3):
    """POST con backoff exponencial para 429/5xx y errores de red."""
    delay = 2
    r = None
    for intento in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            if intento == max_retries:
                raise
            print(f"  ⏳ Error de red ({e}); reintento {intento}/{max_retries} en {delay}s")
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504) and intento < max_retries:
            print(f"  ⏳ HTTP {r.status_code}; reintento {intento}/{max_retries} en {delay}s")
            try:
                print(f"     body: {r.text[:500]}")
            except Exception:
                pass
            time.sleep(delay)
            delay *= 2
            continue
        return r
    return r

# ─── ANTHROPIC ───────────────────────────────────────────────────────────────
def _extraer_texto(content_blocks):
    return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

def _limpiar_fences(texto):
    """Elimina fences markdown y texto antes/después del primer bloque JSON."""
    t = texto.strip()
    if "```" in t:
        partes = t.split("```")
        for p in partes[1:]:
            p = p.lstrip()
            if p.startswith("json"):
                p = p[4:].lstrip()
            if p.startswith("{") or p.startswith("["):
                return p.strip().rstrip("`").strip()
    for i, ch in enumerate(t):
        if ch in "{[":
            return t[i:].strip()
    return t

def obtener_notas_recientes(dias=5, limit=30):
    """Obtiene los títulos de las notas publicadas en los últimos N días para evitar repeticiones."""
    if not NOTION_TOKEN:
        return []
    headers = _notion_headers()
    desde = (datetime.now(TZ_ARG) - timedelta(days=dias)).date().isoformat()
    body = {
        "filter": {
            "and": [
                {"property": "Estado", "select": {"equals": "Publicada"}},
                {"property": "Fecha de publicación", "date": {"on_or_after": desde}}
            ]
        },
        "sorts": [{"property": "Fecha de publicación", "direction": "descending"}],
        "page_size": limit,
    }
    try:
        r = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
            headers=headers, json=body, timeout=30
        )
        if not r.ok:
            print(f"⚠️  No se pudieron consultar notas recientes (HTTP {r.status_code})")
            return []
        data = r.json()
        notas = []
        for page in data.get("results", []):
            props = page.get("properties", {})
            titulo_data = props.get("Nombre", {}).get("title", [])
            titulo = titulo_data[0].get("plain_text", "") if titulo_data else ""
            copete_data = props.get("Copete", {}).get("rich_text", [])
            copete = copete_data[0].get("plain_text", "")[:200] if copete_data else ""
            fecha = props.get("Fecha de publicación", {}).get("date", {}).get("start", "")
            if titulo:
                notas.append({"titulo": titulo, "copete": copete, "fecha": fecha[:10]})
        return notas
    except Exception as e:
        print(f"⚠️  Error consultando notas recientes: {e}")
        return []


def leer_scraper_output():
    """Lee el output del scraper si existe. Devuelve lista de noticias o None."""
    import os
    try:
        if not os.path.exists("scraper_output.json"):
            return None
        with open("scraper_output.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        noticias = data.get("noticias", [])
        if not noticias:
            return None
        print(f"📰 Scraper encontró {len(noticias)} noticias para procesar")
        return noticias
    except Exception as e:
        print(f"⚠️  No se pudo leer scraper_output.json: {e}")
        return None


def buscar_y_redactar(tema=None, turno="manual"):
    """Llama a la API de Claude para buscar noticias y redactar."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta la variable de entorno ANTHROPIC_API_KEY")

    config = TURNO_CONFIG[turno]
    cantidad = config["cantidad"]

    if tema:
        user_prompt = f"""Redactá UNA nota sobre este tema específico para Provincia Política.

TEMA: {tema}

Buscá información actualizada en: {', '.join(FUENTES)}

Elegí el registro correcto (R1/R2/R3) y redactá la nota completa.
Marcá "destacada": true si es la más importante, false si no.
Incluí "imagen" siguiendo los criterios del system prompt.
Respondé SOLO con un objeto JSON válido (sin fences, sin texto adicional)."""
    else:
        # Intentar usar material del scraper si está disponible
        material_scraper = leer_scraper_output()

        if material_scraper:
            material_texto = ""
            for i, n in enumerate(material_scraper[:15], 1):
                material_texto += f"""
{i}. [{n['portal']}] {n['titulo']}
   Copete: {n['copete'][:200] if n['copete'] else '(sin copete)'}
   URL imagen: {n['imagen'] or '(sin imagen)'}
   Fuente: {n['url']}
"""
            # Traer notas ya publicadas para evitar repeticiones
            notas_recientes = obtener_notas_recientes(dias=5, limit=30)
            recientes_texto = ""
            if notas_recientes:
                print(f"📚 {len(notas_recientes)} nota(s) publicada(s) en los últimos 5 días para chequear repeticiones")
                recientes_texto = "\n\nNOTAS QUE YA PUBLICAMOS EN LOS ÚLTIMOS DÍAS (NO repetir estos temas a menos que haya novedad real):\n"
                for i, n in enumerate(notas_recientes, 1):
                    recientes_texto += f"- [{n['fecha']}] {n['titulo']}\n"

            user_prompt = f"""Tenés el siguiente material periodístico extraído HOY ({datetime.now(TZ_ARG).strftime('%d/%m/%Y')}) de portales bonaerenses:

{material_texto}
{recientes_texto}

Con ese material, redactá hasta {cantidad} notas para Provincia Política.

REGLA CLAVE — ANTI-REPETICIÓN Y POSTS DE ACTUALIZACIÓN:
Si el material nuevo cubre temas que ya cubrimos en los últimos días (lista de arriba), tenés 3 opciones según el tipo de novedad:

1. **NOTA COMPLETA** ("solo_redes": false) → SI hay un dato nuevo importante, declaración fuerte, giro narrativo o actor nuevo que amerite cobertura propia. Esta nota va a la web y a redes.

2. **POST DE ACTUALIZACIÓN** ("solo_redes": true) → SI hay una actualización menor (un detalle nuevo, una reacción, una declaración secundaria) que no amerita nota larga pero sí vale postear en X para mantener continuidad. En este caso, redactá el "cuerpo" como un texto BREVE de máximo 250 caracteres (apto para tweet), y el "copete" como un titular corto. NO se mostrará en la web, solo en redes sociales.

3. **DESCARTAR** → SI es "lo mismo de ayer con otras palabras" sin novedad real. No generes nada para ese tema.

Es preferible devolver menos notas que generar contenido repetido.

OTRAS REGLAS:
- Las notas que sí generés deben ser de categorías DISTINTAS: Ejecutivo, Legislatura, Internas PJ, Conurbano, Oposición, Economía, Última hora
- Para la imagen, usá la URL imagen que viene con cada nota (si existe). Si no existe, dejá "imagen" como cadena vacía ""
- Redactá cada nota con voz editorial propia, no copies el texto de las fuentes
- Elegí el registro correcto (R1/R2/R3) para cada nota

REGLA CRÍTICA: Respondé SOLO con un array JSON válido, sin texto antes ni después, sin fences markdown. Mínimo 1 nota, máximo {cantidad}.

Cada nota con estas claves exactas:
(registro, categoria, titulo, copete, cuerpo, imagen, destacada, solo_redes)

Donde "solo_redes" es booleano: true para posts breves de actualización (solo van a X), false para notas completas que van a la web."""
        else:
            user_prompt = f"""Buscá las noticias más relevantes sobre política bonaerense de HOY ({datetime.now(TZ_ARG).strftime('%d/%m/%Y')}) en estas fuentes:
{', '.join(FUENTES)}

OBJETIVO: generar {cantidad} notas. Si no hay suficiente material del día de hoy, podés usar material de los últimos 2-3 días que siga siendo relevante.

IMPORTANTE: Si lográs varias notas, deben ser de categorías DISTINTAS. Distribuir entre: Ejecutivo, Legislatura, Internas PJ, Conurbano, Oposición, Economía, Última hora.
No concentrar la cobertura en Ejecutivo — buscar activamente material en las otras categorías.

REGLA CRÍTICA: Tu respuesta DEBE ser SIEMPRE un array JSON válido, sin texto antes ni después, sin fences markdown, sin explicaciones. Si no encontrás {cantidad} notas, devolvé las que sí pudiste hacer (mínimo 1). Nunca devuelvas texto plano explicando por qué no pudiste.

Para CADA noticia, redactá la nota completa eligiendo R1/R2/R3.
Marcá "destacada": true SOLO en una nota (la más importante). El resto false.
Incluí "imagen" en cada nota siguiendo los criterios del system prompt.

Respondé SOLO con un array JSON, con TODAS las claves definidas
(registro, categoria, titulo, copete, cuerpo, imagen, destacada)."""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if not DISABLE_WEB_SEARCH:
        payload["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }]

    print(f"🔍 Buscando noticias ({turno}) con modelo {ANTHROPIC_MODEL}"
          f"{' [sin web_search]' if DISABLE_WEB_SEARCH else ''}...")
    r = post_with_retry("https://api.anthropic.com/v1/messages",
                        headers=headers, payload=payload, timeout=180)

    if r.status_code >= 400:
        print(f"❌ Anthropic respondió HTTP {r.status_code}")
        try:
            print(f"   body: {r.text[:2000]}")
        except Exception:
            pass
        if not DISABLE_WEB_SEARCH and "tool" in r.text.lower():
            print("   Reintentando sin web_search...")
            payload.pop("tools", None)
            r = post_with_retry("https://api.anthropic.com/v1/messages",
                                headers=headers, payload=payload, timeout=180)
            if r.status_code >= 400:
                print(f"   body 2: {r.text[:2000]}")

    r.raise_for_status()
    data = r.json()
    content = data.get("content", [])
    tipos = [b.get("type") for b in content]
    if "tool_use" in tipos and "text" not in tipos:
        print(f"⚠️ Claude devolvió tool_use sin texto final. stop_reason={data.get('stop_reason')}")

    texto = _extraer_texto(content).strip()
    if not texto:
        raise ValueError(f"Respuesta vacía de Anthropic. stop_reason={data.get('stop_reason')}, "
                         f"tipos_bloques={tipos}")

    texto = _limpiar_fences(texto)

    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError:
        print(f"❌ JSON inválido. Primeros 1000 chars:\n{texto[:1000]}")
        raise

    if isinstance(resultado, dict):
        resultado = [resultado]
    return resultado

# ─── NOTION ──────────────────────────────────────────────────────────────────
def _notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

def limpiar_destacadas():
    """Desmarca todas las páginas con Destacada=true. Pagina y tolera errores."""
    if not NOTION_TOKEN:
        return
    headers = _notion_headers()
    cursor = None
    total = 0
    while True:
        body = {
            "filter": {"property": "Destacada", "checkbox": {"equals": True}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        try:
            r = requests.post(
                f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
                headers=headers, json=body, timeout=30)
        except requests.RequestException as e:
            print(f"⚠️ No se pudo consultar destacadas: {e}")
            return
        if not r.ok:
            print(f"⚠️ No se pudieron limpiar destacadas (HTTP {r.status_code}): {r.text[:300]}")
            return
        data = r.json()
        for page in data.get("results", []):
            try:
                requests.patch(
                    f"https://api.notion.com/v1/pages/{page['id']}",
                    headers=headers,
                    json={"properties": {"Destacada": {"checkbox": False}}},
                    timeout=15)
                total += 1
            except requests.RequestException as e:
                print(f"  ⚠️ Error desmarcando {page.get('id')}: {e}")
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    if total:
        print(f"🧹 {total} destacada(s) anterior(es) limpiada(s)")

def cargar_en_notion(nota, turno="manual"):
    """Carga una nota en Notion como borrador."""
    if not NOTION_TOKEN:
        raise ValueError("Falta la variable de entorno NOTION_TOKEN")

    titulo = (nota.get("titulo") or "Sin título").strip()
    copete = limpiar_citas(nota.get("copete") or "")
    cuerpo = limpiar_citas(nota.get("cuerpo") or "")
    categoria = nota.get("categoria") or "Última hora"
    destacada = bool(nota.get("destacada", False))
    solo_redes = bool(nota.get("solo_redes", False))
    ahora = datetime.now(TZ_ARG).strftime("%Y-%m-%dT%H:%M:%S-03:00")

    # Validar registro: solo R1, R2 o R3
    registro_val = nota.get("registro", "").strip().upper()
    if registro_val not in ("R1", "R2", "R3"):
        registro_val = "R1"  # default si el modelo no devolvió uno válido

    # Si es Solo Redes, marcarla automáticamente como Publicada (no requiere revisión manual)
    estado_val = "Publicada" if solo_redes else "Borrador"

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Nombre": {"title": [{"text": {"content": titulo[:1900]}}]},
            "Copete": {"rich_text": chunk_rich_text(copete)},
            "Cuerpo": {"rich_text": chunk_rich_text(cuerpo)},
            "Categoría": {"select": {"name": categoria}},
            "Estado": {"select": {"name": estado_val}},
            "Destacada": {"checkbox": destacada},
            "Solo Redes": {"checkbox": solo_redes},
            "Registro": {"select": {"name": registro_val}},
            "Fecha de publicación": {"date": {"start": ahora}},
        },
    }

    imagen_url = validar_url_imagen(nota.get("imagen", ""))
    if imagen_url:
        payload["properties"]["Imagen"] = {"url": imagen_url}

    r = post_with_retry("https://api.notion.com/v1/pages",
                        headers=_notion_headers(), payload=payload, timeout=30)
    if r.status_code >= 400:
        print(f"  ❌ Notion HTTP {r.status_code}: {r.text[:1000]}")
        r.raise_for_status()

    result = r.json()
    page_url = result.get("url", "")
    star = "⭐" if destacada else "  "
    registro = nota.get("registro", "?")
    print(f"  ✅ {star} [{registro}] {titulo[:60]}")
    if page_url:
        print(f"     {page_url}")
    return result

# ─── MAIN ────────────────────────────────────────────────────────────────────
def ya_se_ejecuto_turno_hoy(turno):
    """Verifica si ya hay notas creadas hoy para evitar duplicados."""
    if not NOTION_TOKEN or turno == "manual":
        return False
    hoy_arg = datetime.now(TZ_ARG).date()
    # Definir ventana horaria del turno
    rangos = {
        "manana": (5, 11),
        "mediodia": (11, 15),
        "tarde": (15, 23),
    }
    if turno not in rangos:
        return False
    hora_inicio, hora_fin = rangos[turno]
    try:
        body = {
            "filter": {
                "and": [
                    {"property": "Fecha de publicación", "date": {"on_or_after": hoy_arg.isoformat()}},
                ]
            },
            "page_size": 100,
        }
        r = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
            headers=_notion_headers(), json=body, timeout=30)
        if not r.ok:
            print(f"⚠️ No se pudo verificar duplicados: {r.status_code}")
            return False
        data = r.json()
        for page in data.get("results", []):
            fecha_str = page.get("properties", {}).get("Fecha de publicación", {}).get("date", {}).get("start", "")
            if not fecha_str:
                continue
            try:
                fecha_pub = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).astimezone(TZ_ARG)
            except ValueError:
                continue
            if fecha_pub.date() == hoy_arg and hora_inicio <= fecha_pub.hour < hora_fin:
                return True
        return False
    except requests.RequestException as e:
        print(f"⚠️ Error verificando duplicados: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Agente Redactor — Provincia Política")
    parser.add_argument("--tema", type=str, default=None, help="Tema específico para redactar")
    parser.add_argument("--turno", type=str, default=None,
                        choices=["manana", "mediodia", "tarde", "manual"],
                        help="Turno del día")
    args = parser.parse_args()

    turno = args.turno or ("manual" if args.tema else detectar_turno())

    print(f"\n{'='*52}")
    print(f"  PROVINCIA POLÍTICA — Agente Redactor")
    print(f"  {datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')} ARG — {TURNO_CONFIG[turno]['etiqueta']}")
    print(f"{'='*52}\n")

    errores = 0
    cargadas = 0
    try:
        # Anti-duplicados: si ya corrió este turno hoy, salir sin hacer nada
        if ya_se_ejecuto_turno_hoy(turno):
            print(f"✅ Ya se ejecutó el turno '{turno}' hoy. Saliendo sin duplicar.\n")
            return
        # NOTA: Ya no limpiamos destacadas anteriores. Las destacadas se mantienen
        # hasta que el director editorial las desmarque manualmente. El agente solo
        # agrega una nueva destacada por tanda.
        notas = buscar_y_redactar(tema=args.tema, turno=turno)
        print(f"📝 {len(notas)} nota(s) generada(s). Cargando en Notion...\n")
        for i, nota in enumerate(notas, 1):
            print(f"Nota {i}/{len(notas)}:")
            try:
                cargar_en_notion(nota, turno=turno)
                cargadas += 1
            except Exception as e:
                errores += 1
                print(f"  ❌ Falló esta nota: {e}")
            print()

        print(f"✨ Listo. {cargadas} cargada(s), {errores} con error.")
        print(f"   https://www.notion.so/{NOTION_DB_ID}\n")

        if cargadas == 0 and errores > 0:
            sys.exit(1)
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
