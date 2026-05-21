"""
AGENTE SOCIAL â PROVINCIA POLÃTICA v2.0
=========================================
Lee las notas destacadas publicadas en Notion y genera contenido
para X e Instagram, publicÃ¡ndolo via Buffer GraphQL API.

LÃ³gica:
- Publica TODAS las notas con Estado = Publicada (independientemente de si estÃ¡n destacadas)
- Solo publica notas que NO hayan sido publicadas en redes todavÃ­a
- Marca cada nota como publicada en redes despuÃ©s de enviarla a Buffer
- Corre cada hora via GitHub Actions

Uso manual: python agente_social.py
"""

import os
import sys
import json
import base64

# Generador de tarjetas tipogrÃ¡ficas
from generar_tarjeta import generar_tarjeta_bytes
import time
import requests
import io
import boto3
from datetime import datetime, timezone, timedelta

# âââ CONFIGURACIÃN âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL       = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
NOTION_TOKEN          = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID          = os.environ.get("NOTION_DB_ID", "352e199864dd80e1af24f0b661dbd896")
BUFFER_TOKEN          = os.environ.get("BUFFER_TOKEN")
BUFFER_INSTAGRAM_ID   = os.environ.get("BUFFER_INSTAGRAM_CHANNEL_ID")
BUFFER_TWITTER_ID     = os.environ.get("BUFFER_X_CHANNEL_ID")
CF_ACCOUNT_ID      = os.environ.get("CF_ACCOUNT_ID")
CF_R2_ACCESS_KEY   = os.environ.get("CF_R2_ACCESS_KEY_ID")
CF_R2_SECRET_KEY   = os.environ.get("CF_R2_SECRET_ACCESS_KEY")
CF_R2_BUCKET       = os.environ.get("CF_R2_BUCKET_NAME", "provincia-tarjetas")
CF_R2_PUBLIC_URL   = os.environ.get("CF_R2_PUBLIC_URL", "").rstrip("/")

BUFFER_GRAPHQL_URL    = "https://api.buffer.com/"

TZ_ARG = timezone(timedelta(hours=-3))

# âââ SYSTEM PROMPT PARA GENERACIÃN DE POSTS ââââââââââââââââââââââââââââââââââ

SYSTEM_PROMPT_SOCIAL = """Sos el Agente Social de Provincia PolÃ­tica, una agencia de noticias polÃ­tica digital especializada en la Provincia de Buenos Aires.

Tu tarea es generar posts para X (Twitter) e Instagram a partir de notas periodÃ­sticas.

IDENTIDAD EDITORIAL
- Voz: directa, irÃ³nica, con personalidad. NO comunicado de prensa.
- Mirada: siempre hay lectura polÃ­tica. Contrastes, segundas intenciones, sobreentendidos.
- Posicionamiento: cercano al gobierno de Kicillof, contextual con el Senado y Magario, nunca crÃ­tico del peronismo bonaerense.
- Rigor: la informaciÃ³n que pongas debe estar en la nota. No inventes datos. La picante va en el Ã¡ngulo, no en hechos falsos.

TONO POR REGISTRO (ESENCIAL)
Cada nota viene con un registro: R1, R2 o R3. El tono del post DEBE ajustarse al registro:

**R1 â INFORMATIVO/INSTITUCIONAL** (declaraciones, anuncios, datos)
- Tuit factual pero con un pequeÃ±o remate al final
- El dato adelante, la lectura corta al cierre
- Ejemplo: "Kicillof anunciÃ³ obras para el segundo semestre. La lapicera dice presente."

**R2 â ANÃLISIS/CONTEXTO** (lectura polÃ­tica, escenarios, balance de poder)
- Tuit con interpretaciÃ³n polÃ­tica: contrastes, dobles mensajes, cuentas
- MostrÃ¡ lo que la nota implica, no solo lo que dice
- UsÃ¡ fÃ³rmulas como "Mensaje doble:", "Lectura en X:", "Los nÃºmeros:", "El gesto de..."
- Ejemplo: "Kicillof anuncia obras. Mensaje doble: a los intendentes que protestan y al kirchnerismo que mide los tiempos del armado."

**R3 â ROSCA/TRASTIENDA** (internas, peleas de poder, jugadas)
- Tuit con tono picante, frase memorable, Ã¡ngulo de trastienda
- SugerÃ­ mÃ¡s de lo que afirmÃ¡s: usÃ¡ preguntas implÃ­citas, contrastes silenciosos, sobreentendidos
- Funcionan bien: "a quiÃ©nes incluyÃ³ / a quiÃ©nes dejÃ³ afuera", "lo que nadie dice", "la foto que no hubo"
- Ejemplo: "Kicillof anunciÃ³ obras. En el conurbano leyeron tres cosas: a quiÃ©nes incluyÃ³, a quiÃ©nes dejÃ³ afuera, y por quÃ© Magario no estuvo en la foto."

REGLAS DE LA PIMIENTA (NO PASAR LA RAYA)
- Lo picante va en ÃNGULO Y LECTURA, no en insultos ni adjetivos personales
- NO descalificar a personas (ni siquiera a opositores). La crÃ­tica va a movimientos, decisiones, contradicciones
- NO usar ironÃ­a sobre temas sensibles: causas judiciales, denuncias, situaciones de violencia, fallecimientos
- NO mentir ni inventar. La informaciÃ³n debe estar en la nota
- NO usar adjetivos calificativos fuertes ("ridÃ­culo", "patÃ©tico", "vergonzoso")
- SÃ usar observaciones afiladas: contrastes, omisiones notables, cuentas que no cierran
- En notas sobre Kicillof o el peronismo bonaerense: mirada CONTEXTUAL, no crÃ­tica. La picante mira hacia afuera.

FORMATO X (Twitter)
- MÃ¡ximo 260 caracteres
- Frase de impacto que enganche en las primeras palabras
- NO usar hashtags
- NO usar emojis a menos que sean muy pertinentes
- NO cerrar con "MÃ¡s info en el link" ni similares

FORMATO INSTAGRAM
- Entre 100 y 200 palabras
- Primer lÃ­nea: frase de gancho fuerte (se ve antes del "ver mÃ¡s")
- Desarrollar el contexto en 2-3 pÃ¡rrafos cortos manteniendo el tono del registro
- Cerrar con una observaciÃ³n filosa o pregunta que abra el debate
- Hashtags al final: entre 5 y 10, relevantes para polÃ­tica bonaerense

REGLAS GENERALES
- Nunca inventar datos que no estÃ©n en la nota
- Nunca usar "es importante destacar", "cabe mencionar", "sin lugar a dudas", "en este contexto"
- Nunca mencionar que el contenido fue generado por IA
- En el JSON, NO uses comillas dobles dentro de los textos. UsÃ¡ comillas simples o angulares Â«Â» si necesitÃ¡s citar algo.

FORMATO DE SALIDA â responder SOLO con JSON puro, sin texto antes ni despuÃ©s, sin fences markdown:
{
  "x": "texto del post para X",
  "instagram": "texto del post para Instagram"
}"""

# âââ UTILIDADES ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def post_with_retry(url, headers, payload, timeout=60, max_retries=3):
    """POST con backoff exponencial para 429/5xx. EnvÃ­a body como UTF-8 bytes explÃ­citamente."""
    delay = 2
    r = None
    # Serializar a UTF-8 bytes para evitar errores de encoding latin-1 con caracteres unicode
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    # Limpiar headers a ASCII puro (HTTP/1.1 no permite unicode en headers)
    headers_clean = {}
    for k, v in headers.items():
        v_str = str(v)
        try:
            v_str.encode("ascii")
            headers_clean[k] = v_str
        except UnicodeEncodeError:
            print(f"  â ï¸  Header '{k}' tiene caracteres no-ASCII, sanitizando...")
            headers_clean[k] = v_str.encode("ascii", "ignore").decode("ascii").strip()
    headers = {**headers_clean, "Content-Type": "application/json; charset=utf-8"}
    for intento in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=body_bytes, timeout=timeout)
        except requests.RequestException as e:
            if intento == max_retries:
                raise
            print(f"  â³ Error de red ({e}); reintento {intento}/{max_retries} en {delay}s")
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504) and intento < max_retries:
            print(f"  â³ HTTP {r.status_code}; reintento {intento}/{max_retries} en {delay}s")
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
    """Extrae JSON puro del texto, ignorando fences y texto antes/despuÃ©s."""
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


# âââ NOTION ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def _notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def obtener_notas_para_publicar():
    """Obtiene notas con Estado=Publicada y EnRedes=false (independientemente de si son destacadas)."""
    payload = {
        "filter": {
            "and": [
                {"property": "Estado", "select": {"equals": "Publicada"}},
                {"property": "En Redes", "checkbox": {"equals": False}}
            ]
        },
        "sorts": [{"property": "Fecha de publicaciÃ³n", "direction": "descending"}]
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


def _get_select_seguro(prop):
    """Extrae el nombre de un select de Notion manejando None correctamente."""
    if not prop:
        return ""
    select = prop.get("select")
    if not select:
        return ""
    return select.get("name", "")


def extraer_datos_nota(page):
    """Extrae los campos relevantes de una pÃ¡gina de Notion."""
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
        "categoria": _get_select_seguro(props.get("CategorÃ­a") or props.get("Categoria")),
        "registro": _get_select_seguro(props.get("Registro")) or "R1",
        "imagen": get_url(props.get("Imagen")),
    }


# âââ ANTHROPIC âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def generar_posts(nota):
    """Llama a Claude para generar los posts de X e Instagram."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Falta ANTHROPIC_API_KEY")

    user_prompt = f"""GenerÃ¡ los posts para X e Instagram basÃ¡ndote en esta nota:

TÃTULO: {nota['titulo']}
COPETE: {nota['copete']}
CUERPO: {nota['cuerpo'][:1500]}
CATEGORÃA: {nota['categoria']}
REGISTRO: {nota['registro']}

IMPORTANTE: ajustÃ¡ el tono segÃºn el REGISTRO de la nota (R1 = informativo con remate, R2 = anÃ¡lisis con lectura polÃ­tica, R3 = rosca con tono picante). Ver instrucciones de cada registro en el system prompt.

RespondÃ© SOLO con el JSON. No uses comillas dobles dentro de los textos."""

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
        print(f"  â Anthropic HTTP {r.status_code}: {r.text[:500]}")
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
        print(f"  â JSON invÃ¡lido del modelo. Primeros 500 chars:\n{texto[:500]}")
        raise


# âââ BUFFER GRAPHQL ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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


def subir_imagen_a_r2(image_bytes, filename=None):
    """Sube image_bytes (PNG) a Cloudflare R2 y devuelve la URL publica."""
    if not (CF_R2_ACCESS_KEY and CF_R2_SECRET_KEY and CF_R2_BUCKET):
        raise ValueError("Faltan credenciales de Cloudflare R2")
    if filename is None:
        import uuid
        filename = "{}".format(__import__("uuid").uuid4().hex) + ".png"
    endpoint = "https://{}.r2.cloudflarestorage.com".format(CF_ACCOUNT_ID)
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=CF_R2_ACCESS_KEY,
        aws_secret_access_key=CF_R2_SECRET_KEY,
        region_name="auto",
    )
    s3.put_object(
        Bucket=CF_R2_BUCKET,
        Key=filename,
        Body=image_bytes,
        ContentType="image/png",
    )
    public_url = "{}/{}".format(CF_R2_PUBLIC_URL, filename)
    print("  Imagen subida a R2: {}".format(public_url))
    return public_url


def publicar_en_buffer(texto, channel_id, image_url=None):
    """Publica un post en Buffer via GraphQL â modo addToQueue.

    Si se pasa image_bytes (PNG), lo adjunta como media al post.
    """
    if not BUFFER_TOKEN:
        raise ValueError("Falta BUFFER_TOKEN")

    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }

    input_data = {
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "text": texto
    }
    if image_url:
        input_data["media"] = {"photo": image_url}

    payload = {
        "query": CREATE_POST_MUTATION,
        "variables": {
            "input": input_data
        }
    }

    r = post_with_retry(BUFFER_GRAPHQL_URL, headers=headers, payload=payload, timeout=30)

    if r.status_code >= 400:
        print(f"  â Buffer HTTP {r.status_code}: {r.text[:500]}")
    r.raise_for_status()

    data = r.json()

    if "errors" in data:
        raise Exception(f"Error GraphQL Buffer: {data['errors']}")

    result = data.get("data", {}).get("createPost", {})
    if result.get("message"):
        raise Exception(f"Error Buffer: {result['message']}")

    return result


# âââ MAIN âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def main():
    print(f"\n{'='*52}")
    print(f"  PROVINCIA POLÃTICA â Agente Social v2.0")
    print(f"  {datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')} ARG")
    print(f"{'='*52}\n")

    publicadas = 0
    errores = 0

    try:
        notas = obtener_notas_para_publicar()

        if not notas:
            print("â No hay notas nuevas para publicar en redes.")
            return

        print(f"ð {len(notas)} nota(s) para publicar.\n")

        for page in notas:
            nota = extraer_datos_nota(page)
            if not nota["titulo"]:
                continue

            print(f"ð Generando posts para: {nota['titulo'][:60]}...")

            try:
                posts = generar_posts(nota)

                # Publicar en X (sin imagen â pendiente resolver upload a Buffer)
                if BUFFER_TWITTER_ID and posts.get("x"):
                    publicar_en_buffer(posts["x"], BUFFER_TWITTER_ID)
                    print(f"  â X: {posts['x'][:80]}...")

                # Publicar en Instagram con tarjeta tipografica
                if BUFFER_INSTAGRAM_ID and posts.get("instagram"):
                    try:
                        image_bytes = generar_tarjeta_bytes(
                            titulo=nota["titulo"],
                            bajada=nota.get("bajada", ""),
                            categoria=nota.get("categoria", ""),
                        )
                        image_url_ig = subir_imagen_a_r2(image_bytes)
                        publicar_en_buffer(posts["instagram"], BUFFER_INSTAGRAM_ID, image_url=image_url_ig)
                        print("  Instagram OK")
                    except Exception as e_ig:
                        print("  Instagram fallo: {}".format(e_ig))

                # Marcar como publicada en redes
                marcar_como_publicada_en_redes(nota["id"])
                print(f"  â Marcada como publicada en Notion\n")
                publicadas += 1

            except Exception as e:
                errores += 1
                import traceback
                print(f"  â FallÃ³ esta nota: {e}")
                print(f"  TRACEBACK:")
                traceback.print_exc()
                print()

        print(f"â¨ Listo. {publicadas} publicada(s), {errores} con error.")

        if publicadas == 0 and errores > 0:
            sys.exit(1)

    except requests.HTTPError as e:
        print(f"â Error HTTP: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"â Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
