"""
AGENTE SOCIAL — PROVINCIA POLITICA v1.3
=========================================
Lee las notas destacadas publicadas en Notion y genera contenido para X e
Instagram, publicandolo via Buffer (REST API v1).

Logica:
- Solo publica notas con Estado = Publicada y Destacada = true
- Solo publica notas que NO hayan sido publicadas en redes todavia
- Marca cada nota como publicada en redes despues de enviarla a Buffer
- Corre cada hora via GitHub Actions

Uso manual:
    python agente_social.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta

# ─── CONFIGURACION ─────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")
BUFFER_TOKEN = os.environ.get("BUFFER_TOKEN")
BUFFER_INSTAGRAM_ID = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
BUFFER_TWITTER_ID = os.environ.get("BUFFER_X_CHANNEL_ID")

# Modelo Anthropic (override con env var ANTHROPIC_MODEL si queres cambiarlo).
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# Endpoint del API REST v1 de Buffer.
# Las "channel IDs" que tenemos en realidad son IDs de profile en la API v1.
BUFFER_REST_URL = "https://api.bufferapp.com/1/updates/create.json"

# ─── SYSTEM PROMPT PARA GENERACION DE POSTS ────────────────────────
SYSTEM_PROMPT_SOCIAL = """Sos el Agente Social de Provincia Politica, una agencia de noticias politica digital especializada en la Provincia de Buenos Aires.
Tu tarea es generar posts para X (Twitter) e Instagram a partir de notas periodisticas.

IDENTIDAD EDITORIAL
- Voz: directa, ironica cuando corresponde, sin clickbait, sin adjetivos innecesarios.
- Posicionamiento: cercano al gobierno de Kicillof, contextual con el Senado y Magario, nunca critico del peronismo bonaerense.

FORMATO X (Twitter)
- Maximo 260 caracteres
- Frase de impacto que enganche en las primeras palabras
- Puede incluir ironia elegante si el tema lo permite
- NO usar hashtags en exceso — maximo 2, solo si agregan valor
- NO usar emojis a menos que sean muy pertinentes
- Terminar con el link de la nota si se proporciona

FORMATO INSTAGRAM
- Entre 100 y 200 palabras
- Primer linea: frase de gancho fuerte (se ve antes del "ver mas")
- Desarrollar el contexto de la nota en 2-3 parrafos cortos
- Cerrar con una pregunta o frase que invite a la reflexion
- Hashtags al final: entre 5 y 10, relevantes para politica bonaerense
- Ejemplos de hashtags: #PoliticaBonaerense #BuenosAires #Kicillof #Legislatura #PJBonaerense #Conurbano #Argentina

REGLAS GENERALES
- Nunca inventar datos que no esten en la nota
- Nunca usar "es importante destacar", "cabe mencionar", "sin lugar a dudas"
- El tono de X es mas cortante; el de Instagram mas narrativo
- Nunca mencionar que el contenido fue generado por IA

FORMATO DE SALIDA — responder SOLO con este JSON, sin texto adicional:
{
  "x": "texto del post para X",
  "instagram": "texto del post para Instagram"
}"""

# ─── HTTP CON RETRY/BACKOFF ────────────────────────────────
def post_with_retry(url, headers=None, payload=None, data=None, timeout=30, max_retries=3, label=""):
    """POST con backoff exponencial para 429/5xx y errores de red.

    - Si se pasa `payload`, se envia como JSON.
    - Si se pasa `data`, se envia como x-www-form-urlencoded.
    """
    delay = 2
    r = None
    for intento in range(1, max_retries + 1):
        try:
            if data is not None:
                r = requests.post(url, headers=headers, data=data, timeout=timeout)
            else:
                r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            if intento == max_retries:
                raise
            print(f"    ⏳ {label} error de red ({e}); reintento {intento}/{max_retries} en {delay}s")
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504) and intento < max_retries:
            print(f"    ⏳ {label} HTTP {r.status_code}; reintento {intento}/{max_retries} en {delay}s")
            try:
                print(f"       body: {r.text[:500]}")
            except Exception:
                pass
            time.sleep(delay)
            delay *= 2
            continue
        return r
    return r

# ─── LIMPIEZA DE JSON DEVUELTO POR CLAUDE ────────────────────────
def _extraer_json(texto):
    """Devuelve el primer objeto/array JSON encontrado en el texto,
    tolerando fences markdown y texto antes/despues."""
    t = (texto or "").strip()
    if not t:
        return t
    if "```" in t:
        partes = t.split("```")
        for p in partes[1:]:
            p = p.lstrip()
            if p.startswith("json"):
                p = p[4:].lstrip()
            if p.startswith("{") or p.startswith("["):
                end = p.rfind("```")
                if end != -1:
                    p = p[:end]
                return p.strip()
    for i, ch in enumerate(t):
        if ch in "{[":
            return t[i:].strip()
    return t

# ─── FUNCIONES NOTION ─────────────────────────────────────
def _notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

def obtener_notas_para_publicar():
    """Obtiene notas con Estado=Publicada, Destacada=true y En Redes=false."""
    payload = {
        "filter": {
            "and": [
                {"property": "Estado", "select": {"equals": "Publicada"}},
                {"property": "Destacada", "checkbox": {"equals": True}},
                {"property": "En Redes", "checkbox": {"equals": False}},
            ]
        },
        "sorts": [{"property": "Fecha de publicación", "direction": "descending"}],
    }
    r = post_with_retry(
        f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
        headers=_notion_headers(),
        payload=payload,
        timeout=30,
        label="Notion query",
    )
    if r.status_code >= 400:
        print(f"❌ Notion query HTTP {r.status_code}: {r.text[:1000]}")
        r.raise_for_status()
    return r.json().get("results", [])

def marcar_como_publicada_en_redes(page_id):
    """Marca la nota con En Redes = true en Notion."""
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_notion_headers(),
        json={"properties": {"En Redes": {"checkbox": True}}},
        timeout=15,
    )
    if r.status_code >= 400:
        print(f"    ⚠️ Notion patch HTTP {r.status_code}: {r.text[:500]}")
        r.raise_for_status()

def extraer_datos_nota(page):
    """Extrae los campos relevantes de una pagina de Notion."""
    props = page.get("properties", {})
    def get_title(p):
        return p.get("title", [{}])[0].get("plain_text", "") if p else ""
    def get_text(p):
        return p.get("rich_text", [{}])[0].get("plain_text", "") if p else ""
    def get_url(p):
        return p.get("url", "") if p else ""
    return {
        "id": page["id"],
        "titulo": get_title(props.get("Nombre") or props.get("Name")),
        "copete": get_text(props.get("Copete")),
        "cuerpo": get_text(props.get("Cuerpo")),
        "categoria": (props.get("Categoría") or props.get("Categoria") or {}).get("select", {}).get("name", ""),
        "imagen": get_url(props.get("Imagen")),
    }

# ─── GENERACION DE POSTS CON CLAUDE ───────────────────────────────
def generar_posts(nota):
    """Llama a Claude para generar los posts de X e Instagram."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta ANTHROPIC_API_KEY")

    user_prompt = f"""Genera los posts para X e Instagram basandote en esta nota:

TITULO: {nota['titulo']}
COPETE: {nota['copete']}
CUERPO: {nota['cuerpo'][:1500]}
CATEGORIA: {nota['categoria']}

Responde SOLO con el JSON."""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT_SOCIAL,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    r = post_with_retry(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        payload=payload,
        timeout=60,
        label="Anthropic",
    )
    if r.status_code >= 400:
        print(f"    ❌ Anthropic HTTP {r.status_code}: {r.text[:1000]}")
        r.raise_for_status()
    data = r.json()
    texto = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            texto += block.get("text", "")
    json_str = _extraer_json(texto)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print(f"    ❌ JSON invalido de Claude. Primeros 600 chars:\n{json_str[:600]}")
        raise

# ─── PUBLICACION EN BUFFER (REST API v1) ──────────────────────────
def publicar_en_buffer(texto, profile_id):
    """Envia un post a Buffer via REST API v1.

    Doc: https://buffer.com/developers/api/updates#updatescreate
    Endpoint: POST https://api.bufferapp.com/1/updates/create.json
    Auth: Authorization: Bearer <BUFFER_TOKEN>  (o access_token=... en form)
    Form fields: text, profile_ids[] (uno o mas).
    """
    if not BUFFER_TOKEN:
        raise ValueError("Falta BUFFER_TOKEN")
    if not profile_id:
        raise ValueError("Falta profile_id de Buffer")

    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    # `profile_ids[]` debe ir como repeticion de campo en form-encoded.
    form = [
        ("text", texto),
        ("profile_ids[]", profile_id),
    ]
    r = post_with_retry(
        BUFFER_REST_URL,
        headers=headers,
        data=form,
        timeout=30,
        label="Buffer",
    )
    if r.status_code >= 400:
        print(f"    ❌ Buffer HTTP {r.status_code}: {r.text[:1000]}")
        r.raise_for_status()
    try:
        data = r.json()
    except ValueError:
        raise Exception(f"Respuesta no-JSON de Buffer: {r.text[:500]}")
    if not data.get("success", True):
        raise Exception(f"Error Buffer: {data}")
    return data

# ─── MAIN ─────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f" PROVINCIA POLITICA — Agente Social")
    print(f" {datetime.now().strftime('%d/%m/%Y %H:%M')} — Revisando notas para publicar")
    print(f"{'='*50}\n")

    try:
        notas = obtener_notas_para_publicar()
    except Exception as e:
        print(f"❌ Error consultando Notion: {e}")
        sys.exit(1)

    if not notas:
        print("✅ No hay notas nuevas para publicar en redes.")
        return

    print(f"📋 {len(notas)} nota(s) para publicar en redes.\n")

    publicadas = 0
    errores = 0

    for page in notas:
        try:
            nota = extraer_datos_nota(page)
            if not nota["titulo"]:
                print("    ⏭️ Nota sin titulo, salteada.\n")
                continue

            print(f"📝 Generando posts para: {nota['titulo'][:60]}...")
            posts = generar_posts(nota)

            # Publicar en X
            if BUFFER_TWITTER_ID and posts.get("x"):
                publicar_en_buffer(posts["x"], BUFFER_TWITTER_ID)
                print(f"    ✅ X: {posts['x'][:80]}...")
            else:
                print("    ⏭️ X: sin BUFFER_X_CHANNEL_ID o sin texto generado")

            # Instagram en REST v1 requiere subir media aparte; lo dejamos pendiente.
            print("    ⏭️ Instagram: pendiente (requiere subida de imagen)")

            marcar_como_publicada_en_redes(nota["id"])
            print("    ✅ Marcada como publicada en Notion\n")
            publicadas += 1

        except Exception as e:
            errores += 1
            print(f"    ❌ Fallo esta nota: {e}\n")
            continue

    print(f"✨ Listo. {publicadas} publicada(s), {errores} con error.")
    if publicadas == 0 and errores > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
