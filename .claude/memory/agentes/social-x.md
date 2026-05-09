# Agente Social (X)

Aprendizajes acumulados sobre el agente que publica en X via Buffer.

---

## Endpoint de Buffer correcto

**Usar:** `https://api.buffer.com/`

**No usar:**
- `https://graph.buffer.com/` — no existe DNS, falla con error de red.
- `https://api.bufferapp.com/` — endpoint de la API REST v1 deprecada. Rechaza Personal Keys con error OIDC: *"OIDC tokens are not accepted for direct API access"*.

Buffer mismo nos confirma esto: cuando le pegás a `graph.buffer.com` con una Personal Key, responde con HTTP 401 y body `{"errors":[{"message":"Please use api.buffer.com",...}]}`. La pista está literalmente en el mensaje de error.

## Tipo de autenticación

Buffer descontinuó los Access Tokens clásicos (los del flujo OAuth de developers.buffer.com). Solo se pueden generar **Personal Keys** desde Settings → API. Estas Personal Keys solo funcionan contra la API GraphQL nueva, no contra REST v1.

**Plan Free:** máximo 1 Personal Key activa simultánea. Para regenerar sin perder el slot, usar el botón "Regenerate" del menú de la key (no "Revoke + crear nueva").

**Cuidado:** una Personal Key expuesta en chat o logs hay que rotarla. La key actual (al momento de escribir esto) termina en `…v6uV` y vence el 5/5/2027.

## Mutación GraphQL

```graphql
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
```

**Tipo de input:** `CreatePostInput` (NO `PostCreateInput` — ese fue un error que tiramos al comienzo y Buffer respondió `Unknown type "PostCreateInput"`).

**Campos requeridos:**
- `channelId` — el ID del canal (uno por red social)
- `schedulingType` — usar `automatic`
- `mode` — `addToQueue` (próximo slot), `shareNow`, `customScheduled` (con `dueAt`), `shareNext`, `recommendedTime`
- `text` — el contenido

**Modo usado:** `addToQueue` — Buffer lo programa en el próximo slot disponible según la cola configurada.

## Límite del plan Free

Máximo **10 posts en cola** simultáneos por canal. Cuando se llega al tope:

```
Error Buffer: Scheduled posts limit reached. You have 10 scheduled posts out of 10 allowed.
```

No es un bug. El agente social corre cada hora y va metiendo notas a medida que Buffer libera espacio publicando las que tiene en cola. Si querés evitar el error, marcar manualmente como "En Redes" las notas viejas que no quieras compartir.

## Filtro de notas para publicar

El agente trae notas con:
- `Estado = "Publicada"`
- `En Redes = false`

(Antes era además `Destacada = true`, pero se cambió en mayo 2026 para postear todas las notas, no solo destacadas. Ver "Estado actual y pendientes vivos" en CLAUDE.md.)

Después de publicar, marca `En Redes = true` para no duplicar en la próxima corrida.

## Bugs históricos resueltos

### Latin-1 en headers HTTP

`http.client.putheader` codifica todo header en latin-1 por estándar HTTP/1.1. Si un header tiene caracteres no-ASCII (incluso un token con un caracter raro), revienta con:

```
UnicodeEncodeError: 'latin-1' codec can't encode character '\u2192' in position 49
```

**Solución:** sanitizar headers a ASCII puro antes del POST. La función `post_with_retry` ya lo hace.

### Encoding del body

`requests` por defecto serializa con `json=` y a veces falla con caracteres unicode. **Solución:** serializar manual con `json.dumps(payload, ensure_ascii=False).encode("utf-8")` y mandar con `data=`.

### `Categoría` con select null

Si una nota se crea sin categoría asignada, Notion devuelve la propiedad con `select: null` (no la propiedad ausente). El chained `.get("select", {}).get("name", "")` revienta con `AttributeError: 'NoneType' object has no attribute 'get'`.

**Solución:** helper `_get_select_seguro` que maneja el caso null antes del segundo `.get()`.

### Comillas dobles dentro del JSON del modelo

El modelo a veces no escapa bien las comillas dobles cuando hay citas textuales en el cuerpo. Resultado: JSON inválido al parsear.

**Solución:** instrucción explícita en el system prompt para usar comillas simples o angulares «» dentro de los textos.

## Instagram

Deshabilitado actualmente. La mutación de `createPost` para Instagram requiere `assets` (imagen subida a Buffer como asset, no URL). Ese flujo no está implementado.

**Pendiente:** habilitar via API de Canva — generar carrusel desde plantilla `DAHI5hGI7E0`, exportar slides como assets, subirlas a Buffer y publicar.
