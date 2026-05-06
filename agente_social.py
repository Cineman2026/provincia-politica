"""
AGENTE SOCIAL — PROVINCIA POLÍTICA v2.0
=========================================
Lee las notas destacadas publicadas en Notion y genera contenido
para X e Instagram, publicándolo via Buffer GraphQL API.

Lógica:
- Solo publica notas con Estado = Publicada y Destacada = true
- Solo publica notas que NO hayan sido publicadas en redes todavía
- Marca cada nota como publicada en redes después de enviarla a Buffer
- Corre cada hora via GitHub Actions

Uso manual: python agente_social.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL       = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
NOTION_TOKEN          = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID          = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")
BUFFER_TOKEN          = os.environ.get("BUFFER_TOKEN")
BUFFER_INSTAGRAM_ID   = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
BUFFER_TWITTER_ID     = os.environ.get("BUFFER_X_CHANNEL_ID")

BUFFER_GRAPHQL_URL    = "https://graph.buffer.com/"

TZ_ARG = timezone(timedelta(hours=-3))

# ─── SYSTEM PROMPT PARA GENERACIÓN DE POSTS ──────────────────────────────────

SYSTEM_PROMPT_SOCIAL = """Sos el Agente Social de Provincia Política, una agencia de noticias política digital especializada en la Provincia de Buenos Aires.

Tu tarea es generar posts para X (Twitter) e Instagram a partir de notas periodísticas.

IDENTIDAD EDITORIAL
- Voz: directa, irónica cuando corresponde, sin clickbait, sin adjetivos innecesarios.
- Posicionamiento: cercano al gobierno de Kicillof, contextual con el Senado y Magario, nunca crítico del peronismo bonaerense.

FORMATO X (Twitter)
- Máximo 260 caracteres
- Frase de impacto que enganche en las primeras palabras
- Puede incluir ironía elegante si el tema lo permite
- NO usar hashtags en exceso — máximo 2, solo si agregan valor
- NO usar emojis a menos que sean muy pertinentes

FORMATO INSTAGRAM
- Entre 100 y 200 palabras
- Primer línea: frase de gancho fuerte (se ve antes del "ver más")
- Desarrollar el contexto de la nota en 2-3 párrafos cortos
- Cerrar con una pregunta o frase que invite a la reflexión
- Hashtags al final: entre 5 y 10, relevantes para política bonaerense

REGLAS GENERALES
- Nunca inventar datos que no estén en la nota
- Nunca usar "es importante destacar", "cabe mencionar", "sin lugar a dudas"
- El tono de X es más cortante; el de Instagram más narrativo
- Nunca mencionar que el contenido fue generado por IA
- En el JSON, NO uses comillas dobles dentro de los textos. Usá comillas simples o angulares «» si necesitás citar algo.

FORMATO DE SALIDA — responder SOLO con JSON puro, sin texto antes ni después, sin fences markdown:
{
  "x": "texto del post para X",
  "instagram": "texto del post para Instagram"
}"""

# ─── UTILIDADES ──────────────────────────────────────────────────────────────

def post_with_retry(url, headers, payload, timeout=60, max_retries=3):
    """POST con backoff exponencial para 429/5xx."""
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
                print(f"     body: {r.text[:300]}")
            except Exception:
                pass
            time.sleep(delay)
            delay *= 2
            continue
        return r
    return r


def _limpiar_json(texto):
    """Extrae JSON puro del texto, ignorando fences y texto antes/después."""
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


# ─── NOTION ──────────────────────────────────────────────────────────────────

def _notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def obtener_notas_para_publicar():
    """Obtiene notas con Estado=Publicada, Destacada=true y EnRedes=false."""
    payload = {
        "filter": {
            "and": [
                {"property": "Estado", "select": {"equals": "Publicada"}},
                {"property": "Destacada", "checkbox": {"equals": True}},
                {"property": "En Redes", "checkbox": {"equals": False}}
            ]
        },
        "sorts": [{"property": "Fecha de publicación", "direction": "descending"}]
    }

    r = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
        headers=_notion_headers(),
        json=payload,
        timeout=30
    )
    r.raise_for_status()
    return r.json().get("results", [])


def marcar_como_publicada_en_redes(page_id):
    """Marca la nota con En Redes = true en Notion."""
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_notion_headers(),
        json={"properties": {"En Redes": {"checkbox": True}}},
        timeout=15
    )
    r.raise_for_status()


def extraer_datos_nota(page):
    """Extrae los campos relevantes de una página de Notion."""
    props = page.get("properties", {})

    def get_title(p):
        if not p:
            return ""
        items = p.get("title", [])
        return items[0].get("plain_text", "") if items else ""

    def get_text(p):
        if not p:
            return ""
        items = p.get("rich_text", [])
        return items[0].get("plain_text", "") if items else ""

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


# ─── ANTHROPIC ───────────────────────────────────────────────────────────────

def generar_posts(nota):
    """Llama a Claude para generar los posts de X e Instagram."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta ANTHROPIC_API_KEY")

    user_prompt = f"""Generá los posts para X e Instagram basándote en esta nota:

TÍTULO: {nota['titulo']}
COPETE: {nota['copete']}
CUERPO: {nota['cuerpo'][:1500]}
CATEGORÍA: {nota['categoria']}

Respondé SOLO con el JSON. No uses comillas dobles dentro de los textos."""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT_SOCIAL,
        "messages": [{"role": "user", "content": user_prompt}]
    }

    r = post_with_retry("https://api.anthropic.com/v1/messages",
                        headers=headers, payload=payload, timeout=60)

    if r.status_code >= 400:
        print(f"  ❌ Anthropic HTTP {r.status_code}: {r.text[:500]}")
    r.raise_for_status()

    data = r.json()
    texto = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            texto += block.get("text", "")

    texto = _limpiar_json(texto.strip())

    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON inválido del modelo. Primeros 500 chars:\n{texto[:500]}")
        raise


# ─── BUFFER GRAPHQL ──────────────────────────────────────────────────────────

CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post { id }
    }
    ... on MutationError {
      message
    }
  }
}
"""


def publicar_en_buffer(texto, channel_id):
    """Publica un post en Buffer via GraphQL — modo addToQueue."""
    if not BUFFER_TOKEN:
        raise ValueError("Falta BUFFER_TOKEN")

    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": CREATE_POST_MUTATION,
        "variables": {
            "input": {
                "channelId": channel_id,
                "schedulingType": "automatic",
                "mode": "addToQueue",
                "text": texto
            }
        }
    }

    r = post_with_retry(BUFFER_GRAPHQL_URL, headers=headers, payload=payload, timeout=30)

    if r.status_code >= 400:
        print(f"  ❌ Buffer HTTP {r.status_code}: {r.text[:500]}")
    r.raise_for_status()

    data = r.json()

    if "errors" in data:
        raise Exception(f"Error GraphQL Buffer: {data['errors']}")

    result = data.get("data", {}).get("createPost", {})
    if result.get("message"):
        raise Exception(f"Error Buffer: {result['message']}")

    return result


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*52}")
    print(f"  PROVINCIA POLÍTICA — Agente Social v2.0")
    print(f"  {datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')} ARG")
    print(f"{'='*52}\n")

    publicadas = 0
    errores = 0

    try:
        notas = obtener_notas_para_publicar()

        if not notas:
            print("✅ No hay notas nuevas para publicar en redes.")
            return

        print(f"📋 {len(notas)} nota(s) para publicar.\n")

        for page in notas:
            nota = extraer_datos_nota(page)
            if not nota["titulo"]:
                continue

            print(f"📝 Generando posts para: {nota['titulo'][:60]}...")

            try:
                posts = generar_posts(nota)

                # Publicar en X
                if BUFFER_TWITTER_ID and posts.get("x"):
                    publicar_en_buffer(posts["x"], BUFFER_TWITTER_ID)
                    print(f"  ✅ X: {posts['x'][:80]}...")

                # Instagram deshabilitado temporalmente — requiere assets
                print(f"  ⏭️  Instagram: pendiente de implementación de assets")

                # Marcar como publicada en redes
                marcar_como_publicada_en_redes(nota["id"])
                print(f"  ✅ Marcada como publicada en Notion\n")
                publicadas += 1

            except Exception as e:
                errores += 1
                print(f"  ❌ Falló esta nota: {e}\n")

        print(f"✨ Listo. {publicadas} publicada(s), {errores} con error.")

        if publicadas == 0 and errores > 0:
            sys.exit(1)

    except requests.HTTPError as e:
        print(f"❌ Error HTTP: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
