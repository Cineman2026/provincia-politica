# Notion CMS

Aprendizajes acumulados sobre la integración con Notion como CMS del proyecto.

---

## Database "Noticias PP"

**Database ID:** `352e199864dd80e1af24f0b661dbd896`

**API version usada:** `2022-06-28`

## Propiedades

| Propiedad | Tipo | Quién la setea | Notas |
|-----------|------|----------------|-------|
| Nombre | title | agente redactor | Título de la nota. Max 1900 chars |
| Copete | rich_text | agente redactor | Bajada de 2-3 líneas |
| Cuerpo | rich_text | agente redactor | Cuerpo de la nota. Chunked en bloques de 1900 chars |
| Categoría | select | agente redactor | Una de 7 categorías predefinidas |
| Estado | select | Santiago manualmente | Borrador / Publicada |
| Destacada | checkbox | agente redactor + Santiago | El agente marca 1 por tanda. Santiago las maneja manualmente después |
| Imagen | url | agente redactor | URL pública. Tipo URL, NO Files & media |
| Fecha de publicación | date | agente redactor | Con timezone ARG (-03:00) |
| En Redes | checkbox | agente social | true después de publicar en X |
| Registro | select | agente redactor | R1 / R2 / R3 (registros editoriales) |

### Categorías válidas

- Ejecutivo
- Legislatura
- Internas PJ
- Conurbano
- Oposición
- Economía
- Última hora

## Por qué Imagen es URL y no Files & media

Notion no renderiza una propiedad URL como imagen — solo la muestra como texto enlazable. Para que renderice como miniatura habría que usar tipo "Files & media".

**Pero:** el sitio web (no Notion) es el que muestra la imagen con un `<img src="...">` leyendo la URL. El frontend ya lo hace correctamente. **No hace falta cambiar el tipo a Files & media** — eso traería complicaciones (Notion vacía los valores al cambiar de tipo, habría que repoblar todo, los agentes tendrían que subir archivos en lugar de pasar URLs).

## Worker como proxy

El sitio web NO consulta Notion directamente. Pasa por el Cloudflare Worker:

```
https://notion-proxy.provinciapolitica.workers.dev
```

El Worker:

- Filtra `Estado = "Publicada"` (esto es importante: las notas en "Borrador" no aparecen en la web aunque tengan todo cargado).
- Ordena por `Fecha de publicación` descendente.
- Tiene CORS abierto (`access-control-allow-origin: *`).
- Oculta el token de Notion del frontend.

**El código fuente del Worker NO está en este repo.** Vive solo en el dashboard de Cloudflare.

Para ver qué filtros aplica el Worker sin acceder al código:

```bash
curl -s https://notion-proxy.provinciapolitica.workers.dev/ > out.json
jq '[.results[].properties.Estado.select.name] | group_by(.) | map({estado: .[0], n: length})' out.json
```

## Bugs históricos resueltos

### Categoría con select null

Cuando Santiago crea una nota manualmente sin asignar categoría, Notion devuelve la propiedad presente pero con `select: null`. El chained access falla:

```python
# REVIENTA con AttributeError: 'NoneType' object has no attribute 'get'
categoria = props.get("Categoría").get("select").get("name", "")
```

**Solución:** helper `_get_select_seguro` que valida null en cada paso:

```python
def _get_select_seguro(prop):
    if not prop:
        return ""
    select = prop.get("select")
    if not select:
        return ""
    return select.get("name", "")
```

Aplicado en `agente_social.py` y `cargar_banco_historico.py`.

### Chunking de rich_text

Notion exige bloques de rich_text con máximo 2000 caracteres. Si el cuerpo es más largo, falla con HTTP 400.

**Solución:** función `chunk_rich_text(texto, limite=1900)` que divide en bloques de 1900 chars (margen de seguridad).

```python
def chunk_rich_text(texto, limite=1900):
    if not texto:
        return [{"text": {"content": ""}}]
    bloques = []
    while texto:
        bloques.append({"text": {"content": texto[:limite]}})
        texto = texto[limite:]
    return bloques
```

## Filtros para queries

### Notas para publicar en redes (agente social)

```python
{
    "filter": {
        "and": [
            {"property": "Estado", "select": {"equals": "Publicada"}},
            {"property": "En Redes", "checkbox": {"equals": False}}
        ]
    },
    "sorts": [{"property": "Fecha de publicación", "direction": "descending"}]
}
```

(Antes incluía `Destacada = true`, eliminado en mayo 2026 — ahora se publican todas las notas, no solo destacadas.)

### Anti-duplicados (agente redactor)

```python
{
    "filter": {
        "and": [
            {"property": "Fecha de publicación", "date": {"on_or_after": hoy_arg.isoformat()}}
        ]
    },
    "page_size": 100
}
```

Después se filtra en Python por ventana horaria del turno.

## Lecturas masivas

Algunas operaciones (limpiar destacadas, traer todas las notas publicadas) requieren paginación. Notion devuelve max 100 resultados por query.

```python
cursor = None
while True:
    body = {...}
    if cursor:
        body["start_cursor"] = cursor
    r = requests.post(...)
    data = r.json()
    # procesar data["results"]
    if not data.get("has_more"):
        break
    cursor = data.get("next_cursor")
```

## Cuidado con cambios de tipo de propiedad

Si en algún momento se piensa cambiar el tipo de una propiedad existente (ej: Imagen de URL a Files & media), Notion **vacía los valores** en el cambio. Hay que repoblar todo manualmente. Mejor evitar.
