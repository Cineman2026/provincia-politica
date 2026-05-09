# Publicación

Aprendizajes acumulados sobre el flujo de publicación: del Notion al sitio web y a redes.

---

## Flujo completo

```
Borrador (Notion)
    ↓ Santiago revisa, edita si hace falta, opcionalmente sube imagen propia
Publicada (Notion)
    ↓ Worker la expone via JSON
Sitio web (provinciapolitica.com)
    ↓ Aparece en portada si tiene <10 días, en archivo si tiene >10 días
Agente social (cada hora)
    ↓ Si Estado=Publicada y En Redes=false → genera post X y publica via Buffer
Marcada como En Redes=true
```

## Sitio web

**Hosting:** GitHub Pages
**Dominio:** provinciapolitica.com (DNS en Cloudflare)
**Tecnología:** HTML/CSS/JS puro, sin frameworks

### Cómo lee Notion

```javascript
fetchFromNotion() → llama al Cloudflare Worker → recibe JSON → mapea al formato interno
```

El Worker filtra `Estado = "Publicada"` y ordena por fecha desc. El frontend NO filtra por estado (asume que el Worker ya lo hizo).

### Filtros en frontend

- `currentFilter === 'archivo'` → muestra solo notas con `esVieja: true` (más de 10 días).
- `currentFilter === 'Todo'` → muestra solo notas con `esVieja: false` (últimos 10 días).
- Categoría específica → notas recientes de esa categoría.

```javascript
function filterNoticias(noticias) {
  if (currentFilter === 'archivo') return noticias.filter(n => n.esVieja);
  const recientes = noticias.filter(n => !n.esVieja);
  if (currentFilter === 'Todo') return recientes;
  return recientes.filter(n => n.categoria === currentFilter);
}
```

### Lead-grid (destacadas en portada)

Muestra hasta 3 notas destacadas (`featured: true`):
- 1 grande (la primera destacada)
- 2 secundarias (las siguientes destacadas)
- Si hay menos de 3 destacadas, completa con placeholders

**Bug histórico:** la versión vieja calculaba `feedItems = featured ? rest.slice(2) : rest.slice(0)` saltándose 2 notas asumiendo que las secundarias salían de `rest`. Pero las secundarias salen de `otrasDestacadas`, no de `rest`. Resultado: las 2 primeras notas no destacadas desaparecían del feed cuando había 1 sola destacada. **Arreglado:** ahora siempre `feedItems = rest.slice(0)`.

### Filtro de notas viejas

```javascript
esVieja: (function() {
  const fechaNota = new Date(props['Fecha de publicación']?.date?.start || page.created_time);
  const ahora = new Date();
  const diasDiferencia = (ahora - fechaNota) / (1000 * 60 * 60 * 24);
  return diasDiferencia > 10;
})()
```

10 días es el umbral acordado con Santiago. Si quiere cambiarlo, modificar este número.

## Bugs históricos del sitio

### `data-cat="PJ"` no matcheaba

El botón "Internas PJ" del menú tenía `data-cat="PJ"` pero las notas tienen `categoria: "Internas PJ"`. El filtro nunca matcheaba. **Arreglado:** ahora `data-cat="Internas PJ"`.

### SEED_NOTICIAS hardcodeadas

Había 5 notas dummy en el JS (`n001` a `n005`) que se mezclaban con las de Notion. Aparecían siempre en el feed aunque las borraras de Notion. **Arreglado:** eliminadas del código.

### Cache del navegador

Después de cambios en `index.html`, los refrescos normales muestran versión cacheada. Hay que hacer `Ctrl+F5` (o Cmd+Shift+R en Mac) para ver los cambios.

## Buffer (publicación X)

### Cola y horarios

Buffer publica los posts según los horarios configurados en la cuenta de Buffer (no en nuestro código). El agente social los manda con `mode: addToQueue` y Buffer los programa en el próximo slot disponible.

**Plan Free:** límite de 10 posts en cola simultáneos. Cuando se llena, los nuevos posts fallan con `Scheduled posts limit reached`. No es bug, es comportamiento esperado.

A medida que Buffer va publicando los posts en cola, se libera espacio y el agente social (que corre cada hora) va metiendo los pendientes.

### Verificar si un post se publicó

1. Mirar la cola en `publish.buffer.com` (sección Schedule).
2. Mirar en X directamente: https://x.com/provincia29447

A veces el agente marca como "En Redes" en Notion pero el post nunca llegó a publicarse en X (errores de Buffer durante la publicación). En esos casos:

1. Desmarcar "En Redes" en Notion.
2. El agente lo va a reintentar en la próxima corrida.

## Archivado

**Cómo funciona:**
- Las notas con más de 10 días automáticamente pasan al botón "Archivo" del menú.
- Desaparecen de la portada (sección "Últimas noticias" y lead-grid).
- Siguen accesibles desde el botón "Archivo".

**No requiere intervención manual.** El cálculo se hace en frontend en cada carga de la página.

**Pendiente verificar (desde 7/5/2026):** que el flujo funcione correctamente cuando las primeras notas cumplan 10 días.

## Calidad editorial

### Imágenes idénticas a la fuente

Si el scraper extrae la `og:image` del portal y la nota se publica con esa imagen, queda la **MISMA imagen** que el portal original. Eso te delata como secundario.

**Solución pendiente:** buscador inteligente de imágenes que consulte el banco propio (`assets/banco/`) antes de usar la imagen del portal. Si hay match con el actor o tema de la nota, usar la del banco. Si no, usar la del portal como fallback.

### Distribución por registros R1/R2/R3

Pendiente analizar el balance real de registros que produce el agente. Para eso se agregó la propiedad `Registro` en Notion (mayo 2026). Después de unos días de datos se podrá ver si hay desbalance (ej: todo informativo, poco análisis).

Si hay desbalance, ajustar el SYSTEM_PROMPT del agente para que prefiera más R2 o R3 según la necesidad editorial.

### Distribución por categorías

Bug detectado al inicio: el agente concentraba notas en Ejecutivo. **Arreglado:** se agregó una directiva explícita en el SYSTEM_PROMPT: *"Las N notas DEBEN ser de categorías DISTINTAS. No concentrar la cobertura en Ejecutivo."*

## Notas y links útiles

- **Cuenta X:** @provincia29447
- **Cuenta Buffer:** provincia_politica (Instagram, deshabilitado), provincia29447 (X)
- **Diseño Canva carrusel:** DAHI5hGI7E0 (5 plantillas base ya armadas, pendiente integrar via API)
