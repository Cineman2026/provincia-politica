# Agente Redactor

Aprendizajes acumulados sobre el agente que reescribe notas crudas con línea editorial y las sube a Notion.

---

## Modelo y configuración

**Modelo:** `claude-sonnet-4-5` — override con env var `ANTHROPIC_MODEL` si es necesario.

**No usar:** `claude-opus-4-6` (no existe — error histórico que apareció en versiones tempranas y rompió el agente hasta que lo arreglamos).

**`max_tokens`:** 8192. NO bajar — con 4096 las respuestas se truncan a la mitad del JSON y el parsing revienta con:

```
Error parseando respuesta del agente: Unterminated string starting at: line 43 column 15
```

## Pipeline general

1. Lee `scraper_output.json` generado por `scraper.py`.
2. Si existe material del scraper, lo pasa al modelo como contexto en el `user_prompt`.
3. Si no existe (fallback), le pide al modelo que use `web_search` directo.
4. El modelo devuelve un array JSON con N notas (cantidad según turno).
5. Cada nota se carga en Notion como "Borrador".

## Por qué se prefiere el scraper sobre web_search

`web_search` tiene dos problemas serios:

1. **URLs de imágenes inventadas:** el modelo "adivina" rutas basándose en patrones que vio en otras páginas. Termina generando URLs como `prensa.gba.gob.ar/upload/imagen/imagen_9583.jpg` que no existen y dan 404.

2. **Etiquetas `<cite>` en el cuerpo:** el modelo mete tags `<cite index="2-6,2-7">...</cite>` en el texto cuando usa web_search. Quedan visibles en la web hasta que la función `limpiar_citas` (regex) las saca antes de cargar en Notion.

El scraper con Playwright extrae imágenes reales (og:image del HTML) y resuelve los dos problemas.

## Cantidad de notas por turno

- **Mañana (7am ARG):** 5 notas
- **Mediodía (12pm ARG):** 3 notas
- **Tarde (6pm ARG):** 3 notas
- **Manual (workflow_dispatch):** 3 notas

## Anti-duplicados

Función `ya_se_ejecuto_turno_hoy(turno)`:

1. Define ventana horaria del turno (mañana 5-11, mediodía 11-15, tarde 15-23).
2. Consulta Notion por notas con `Fecha de publicación` en el día de hoy.
3. Si hay alguna nota dentro de la ventana del turno actual → ya corrió, sale sin hacer nada.

Esto previene que los crons redundantes (cron-job.org dispara dos veces por turno con 15 min de diferencia) generen notas duplicadas.

**Importante:** consulta Notion, NO estado local del proceso. Eso garantiza que funcione bien aunque los dos crons corran en runners distintos sin estado compartido.

## Destacadas

**El agente NO ejecuta `limpiar_destacadas()` al inicio de cada tanda.** Eso fue una decisión editorial: las destacadas se mantienen hasta que Santiago las desmarque manualmente. La función existe en el código pero no se llama en `main()`.

El modelo marca **una sola nota como destacada por tanda** (la más relevante).

## Reglas editoriales codificadas en el SYSTEM_PROMPT

Las reglas completas están en el `SYSTEM_PROMPT` de `agente_redactor.py`. Resumen:

- Posicionamiento: cercano a Kicillof, contextual con Senado/Magario, nunca crítico del peronismo bonaerense.
- Voz: Alconada Mon + Asís + Navarro + Lantos.
- 3 registros: R1 (informativo), R2 (análisis), R3 (rosca). El modelo elige según el tema.
- Categorías obligatorias distintas por tanda.
- Lista de palabras prohibidas (ver CLAUDE.md).
- Material de los últimos 2-3 días aceptado si no hay material relevante de hoy.

## Bugs históricos resueltos

### Modelo devolviendo texto plano

A veces el modelo respondía algo tipo *"No encontré material relevante para construir 5 notas..."* en lugar del array JSON. Eso rompía el parser.

**Solución:** instrucción explícita en el user_prompt: *"Tu respuesta DEBE ser SIEMPRE un array JSON válido. Si no encontrás N notas, devolvé las que sí pudiste hacer (mínimo 1). Nunca devuelvas texto plano explicando por qué no pudiste."*

### Comillas dobles sin escapar

El modelo metía citas textuales con comillas dobles dentro del JSON sin escapar:

```json
{"titulo": "Kicillof: \"Milei libra una guerra...\""}
```

A veces lo hacía mal y tiraba `Expecting ',' delimiter`.

**Solución:** instrucción en el system prompt para usar comillas simples o angulares «» dentro de los textos del JSON.

### Categoría con select null

Si Santiago crea una nota manualmente sin asignar categoría, Notion devuelve `Categoría: {"select": null}`. El chained `.get("select", {}).get("name", "")` revienta.

**Solución:** función helper `_get_select_seguro` que maneja el caso null.

### Etiquetas `<cite>` del web_search

Cuando el modelo usa la tool `web_search`, mete etiquetas `<cite index="2-6,2-7">...</cite>` en el cuerpo. Quedaban visibles en la web.

**Solución:** función `limpiar_citas` (regex) que las elimina antes de cargar en Notion.

### Bug del workflow: input de turno

La versión vieja del workflow tenía:

```yaml
run: |
  if [ -n "${{ github.event.inputs.tema }}" ]; then
    python agente_redactor.py --tema "${{ github.event.inputs.tema }}" --turno "${{ github.event.inputs.turno }}"
  else
    python agente_redactor.py
  fi
```

Cuando no había `tema`, `${{ }}` se sustituía como string vacío y el if quedaba como `if [ -n "" ]; then` literal. Caía al `else` y NO se pasaba `--turno`. El script auto-detectaba turno por hora UTC (no ARG) y a veces caía en el turno equivocado.

**Solución:** pasar inputs como variables de entorno (`TURNO_INPUT`, `TEMA_INPUT`) y chequear esas variables en el shell. Además resuelve riesgo de inyección si alguien metiera comillas en el `tema`.

## Validación de URL de imagen

Antes de cargar en Notion, la URL de imagen se valida con `validar_url_imagen()`:

- Debe empezar con `http://` o `https://`
- No puede tener espacios
- Debe terminar en `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`
- Si tiene caracteres no-ASCII, intenta encodear el path con `urllib.parse.quote`
- Si nada funciona, devuelve `""` y la nota se carga sin imagen

**Pendiente:** validar también con HEAD request que la URL sea accesible (no devuelva 404). Hoy solo se valida formato.
