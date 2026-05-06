"""
AGENTE SOCIAL — PROVINCIA POLÍTICA v1.0
=========================================
Lee las notas destacadas publicadas en Notion y genera contenido
para X e Instagram, publicándolo via Buffer.

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
import requests
from datetime import datetime, timezone, timedelta

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY")
NOTION_TOKEN          = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID          = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")
BUFFER_TOKEN          = os.environ.get("BUFFER_TOKEN")
BUFFER_INSTAGRAM_ID   = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
BUFFER_TWITTER_ID     = os.environ.get("BUFFER_X_CHANNEL_ID")

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
- Terminar con el link de la nota si se proporciona

FORMATO INSTAGRAM
- Entre 100 y 200 palabras
- Primer línea: frase de gancho fuerte (se ve antes del "ver más")
- Desarrollar el contexto de la nota en 2-3 párrafos cortos
- Cerrar con una pregunta o frase que invite a la reflexión
- Hashtags al final: entre 5 y 10, relevantes para política bonaerense
- Ejemplos de hashtags: #PolíticaBonaerense #BuenosAires #Kicillof #Legislatura #PJBonaerense #Conurbano #Argentina

REGLAS GENERALES
- Nunca inventar datos que no estén en la nota
- Nunca usar "es importante destacar", "cabe mencionar", "sin lugar a dudas"
- El tono de X es más cortante; el de Instagram más narrativo
- Nunca mencionar que el contenido fue generado por IA

FORMATO DE SALIDA — responder SOLO con este JSON, sin texto adicional:
{
  "x": "texto del post para X",
  "instagram": "texto del post para Instagram"
}"""

# ─── FUNCIONES NOTION ────────────────────────────────────────────────────────

def obtener_notas_para_publicar():
    """Obtiene notas con Estado=Publicada, Destacada=true y EnRedes=false."""
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

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

    response = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
        headers=headers,
        json=payload,
        timeout=30
    )
    response.raise_for_status()
    return response.json().get("results", [])


def marcar_como_publicada_en_redes(page_id):
    """Marca la nota con En Redes = true en Notion."""
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    response = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=headers,
        json={"properties": {"En Redes": {"checkbox": True}}},
        timeout=15
    )
    response.raise_for_status()


def extraer_datos_nota(page):
    """Extrae los campos relevantes de una página de Notion."""
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

# ─── GENERACIÓN DE POSTS CON CLAUDE ──────────────────────────────────────────

def generar_posts(nota):
    """Llama a Claude para generar los posts de X e Instagram."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta ANTHROPIC_API_KEY")

    user_prompt = f"""Generá los posts para X e Instagram basándote en esta nota:

TÍTULO: {nota['titulo']}
COPETE: {nota['copete']}
CUERPO: {nota['cuerpo'][:1500]}
CATEGORÍA: {nota['categoria']}

Respondé SOLO con el JSON."""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT_SOCIAL,
        "messages": [{"role": "user", "content": user_prompt}]
    }

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    data = response.json()

    texto = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            texto += block.get("text", "")

    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    return json.loads(texto)

# ─── PUBLICACIÓN EN BUFFER ────────────────────────────────────────────────────

def publicar_en_buffer(texto, channel_id, media_url=None):
    """Envía un post a Buffer via API GraphQL."""
    if not BUFFER_TOKEN:
        raise ValueError("Falta BUFFER_TOKEN")

    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }

    mutation = """
    mutation CreatePost {
      createPost(input: {
        text: "%s",
        channelId: "%s",
        schedulingType: automatic,
        mode: addToQueue
      }) {
        ... on PostActionSuccess {
          post {
            id
            text
            dueAt
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """ % (texto.replace('"', '\"').replace('\n', '\\n'), channel_id)

    payload = {"query": mutation}

    response = requests.post(
        "https://api.buffer.com",
        headers=headers,
        json=payload,
        timeout=30
    )
    response.raise_for_status()
    data = response.json()

    # Verificar errores GraphQL
    if "errors" in data:
        raise Exception(f"Error GraphQL: {data['errors']}")

    result = data.get("data", {}).get("createPost", {})
    if result.get("message"):
        raise Exception(f"Error Buffer: {result['message']}")

    return result

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"  PROVINCIA POLÍTICA — Agente Social")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')} — Revisando notas para publicar")
    print(f"{'='*50}\n")

    try:
        notas = obtener_notas_para_publicar()

        if not notas:
            print("✅ No hay notas nuevas para publicar en redes.")
            return

        print(f"📋 {len(notas)} nota(s) para publicar en redes.\n")

        for page in notas:
            nota = extraer_datos_nota(page)
            if not nota["titulo"]:
                continue

            print(f"📝 Generando posts para: {nota['titulo'][:60]}...")

            posts = generar_posts(nota)

            # Publicar en X
            if BUFFER_TWITTER_ID and posts.get("x"):
                publicar_en_buffer(posts["x"], BUFFER_TWITTER_ID)
                print(f"  ✅ X: {posts['x'][:80]}...")

            # Instagram deshabilitado temporalmente — requiere manejo de assets en GraphQL
            print(f"  ⏭️  Instagram: pendiente de implementación de assets")

            # Marcar como publicada en redes
            marcar_como_publicada_en_redes(nota["id"])
            print(f"  ✅ Marcada como publicada en Notion\n")

        print("✨ Listo. Posts publicados en Buffer.")

    except requests.HTTPError as e:
        print(f"❌ Error de API: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando respuesta: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
