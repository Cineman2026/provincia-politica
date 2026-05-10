# PROVINCIA POLÍTICA

> Agencia de noticias política digital especializada en Provincia de Buenos Aires.

**Director editorial:** Santiago
**Email:** provinciapolitica@outlook.com
**Web:** [provinciapolitica.com](https://provinciapolitica.com)
**X:** [@provincia29447](https://x.com/provincia29447)

---

## Qué es

Provincia Política es una agencia de noticias automatizada con redacción asistida por IA. El sistema scrapea portales bonaerenses, redacta notas con voz editorial propia, las publica en una web propia, y las distribuye en redes sociales.

**Posicionamiento editorial:** Cercano al gobierno de Kicillof con estética independiente. Tono directo, sin clickbait. Voz que combina rigor de Alconada Mon, ironía elegante de Asís, valentía de Navarro y capacidad de Lantos para meter al lector en la rosca.

**3 registros editoriales:**
- **R1** — Informativo/Institucional (declaraciones, anuncios, datos)
- **R2** — Análisis/Contexto (lectura política, escenarios, balance de poder)
- **R3** — Rosca/Trastienda (internas de despacho, peleas de poder)

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│   CRON-JOB.ORG (6 trabajos diarios con redundancia)     │
│   7:05 / 7:20 / 12:05 / 12:20 / 18:05 / 18:20 ARG       │
└────────────────────────┬────────────────────────────────┘
                         │ POST API
                         ▼
┌─────────────────────────────────────────────────────────┐
│         GITHUB ACTIONS (ubuntu-latest)                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. scraper.py (Playwright)                       │   │
│  │    → recorre letrap, latecla, infocielo          │   │
│  │    → extrae notas + og:image (hasta 21 noticias) │   │
│  │    → bloqueo de ads/trackers/fuentes             │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 2. agente_redactor.py                            │   │
│  │    → consulta notas recientes (anti-repetición)  │   │
│  │    → llama a Claude (sonnet-4-5) para redactar   │   │
│  │    → decide: nota completa / solo redes / descarta│  │
│  │    → carga en Notion                             │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              NOTION DATABASE (Noticias PP)              │
│  Santiago revisa → cambia Estado a "Publicada"          │
└────────────┬────────────────────────────┬───────────────┘
             │                            │
             ▼                            ▼
┌──────────────────────┐     ┌──────────────────────────┐
│ CLOUDFLARE WORKER    │     │ AGENTE SOCIAL            │
│ (notion-proxy)       │     │ (cada hora)              │
│ Filtra Solo Redes    │     │ → publica todas las notas│
│ ↓                    │     │   en X via Buffer GraphQL│
│ provinciapolitica.com│     └──────────────────────────┘
└──────────────────────┘
```

---

## Componentes principales

### Scraper (`scraper.py`)

- Construido con **Playwright** sobre Chromium headless
- Recorre **Letra P, La Tecla, Infocielo**
- Extrae hasta 7 notas por portal (titular, copete, URL, imagen)
- **Bloqueo de recursos pesados** (ads, trackers, fuentes web) — mejora ~50% en velocidad
- Filtro de relevancia por **~70 palabras clave** que incluyen: actores políticos provinciales y nacionales, intendentes del Conurbano e interior, sindicalistas, líderes docentes, términos legislativos
- Genera `scraper_output.json` con el material extraído

### Agente Redactor (`agente_redactor.py`)

- Usa **Claude Sonnet 4.5** via API de Anthropic
- Cadencia: 5 notas a la mañana, 3 al mediodía, 3 a la tarde
- **Anti-repetición:** consulta las últimas 30 notas publicadas en Notion antes de generar nuevas. Si un tema ya se cubrió y no hay novedad real, lo descarta
- **Tres opciones por tema:**
  1. Nota completa → va a la web y a X
  2. Post Solo Redes → actualización breve solo para X
  3. Descartar → si es lo mismo de ayer sin novedad
- Distribuye notas en categorías distintas (Ejecutivo, Legislatura, Internas PJ, Conurbano, Oposición, Economía, Última hora)
- Anti-duplicados por turno: verifica si ya corrió hoy antes de generar

### Agente Social (`agente_social.py`)

- Corre **cada hora** entre las 7am y 10pm ARG
- Publica notas en X via **Buffer GraphQL API**
- Filtro: notas con Estado=Publicada y En Redes=false
- 15 slots diarios configurados en Buffer (uno por hora)
- Instagram pendiente de implementación (requiere carruseles via API Canva)

### Sitio web (`index.html`)

- HTML/CSS/JS puro, hosting en GitHub Pages
- Lee Notion via Cloudflare Worker (proxy)
- **Archivo histórico automático:** notas con más de 10 días pasan al botón "Archivo" y desaparecen de portada
- Filtros por categoría
- Estética: negro #080808, bronce #B8860B/#D4A832, Fraunces + Inter + JetBrains Mono

---

## Notion como CMS

**Database "Noticias PP"** con las siguientes propiedades:

| Propiedad | Tipo | Función |
|-----------|------|---------|
| Nombre | title | Título de la nota |
| Copete | rich_text | Bajada |
| Cuerpo | rich_text | Cuerpo de la nota |
| Categoría | select | Una de 7 categorías |
| Estado | select | Borrador / Publicada |
| Destacada | checkbox | Aparece en portada destacada |
| Imagen | url | URL pública de la imagen |
| Fecha de publicación | date | Con timezone ARG |
| En Redes | checkbox | True después de publicar en X |
| Registro | select | R1 / R2 / R3 |
| Solo Redes | checkbox | True si va solo a X, no a la web |

---

## Infraestructura

### Scheduler externo: Cron-job.org

GitHub Actions tiene crons poco confiables — durante alta carga, los saltea sin notificación. Por eso usamos cron-job.org como scheduler externo que dispara el workflow via API. **6 trabajos configurados** con redundancia (primer intento + retry 15 min después) para cada turno.

### Cloudflare Worker (proxy a Notion)

- URL: `notion-proxy.provinciapolitica.workers.dev`
- Filtra Estado=Publicada y Solo Redes=false
- Ordena por fecha descendente
- Headers CORS abiertos
- Oculta el token de Notion del frontend

### Buffer (publicación X)

- Plan Free (10 posts simultáneos en cola)
- Personal Key como autenticación
- Mutación GraphQL `createPost` con `mode: addToQueue`
- 15 slots diarios configurados (1 por hora de 8 AM a 10 PM)

### GitHub Secrets requeridos

- `ANTHROPIC_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DB_ID`
- `BUFFER_TOKEN`
- `BUFFER_X_CHANNEL_ID`
- `BUFFER_INSTAGRAM_CHANNEL_ID`

---

## Banco de imágenes propio

Carpeta `/assets/banco/` con imágenes clasificadas por actor, lugar y tema. Cargado inicialmente desde las notas históricas de Notion (23 fotos) con el script de uso único `cargar_banco_historico.py`.

Estructura:

- `actores/`: kicillof, magario, bianco, maximo, cristina
- `lugares/`: casa-gobierno, legislatura, banco-provincia, cgt, pj, ucr, pro, lla
- `temas/`: economia, transporte, educacion, salud, agro, jubilados, trabajadores
- `sin-clasificar/`

Pendiente: conectar al agente redactor con un buscador inteligente que consulte el banco antes de usar imagen del portal fuente.

---

## Proceso editorial

1. **Generación automática:** el agente redactor genera notas como Borrador (o Solo Redes como Publicada directo)
2. **Revisión manual:** Santiago revisa, edita títulos/cuerpos si es necesario
3. **Imagen:** Santiago carga imagen manual si la del scraper no es óptima
4. **Publicación:** Santiago cambia Estado a Publicada
5. **Destacadas:** Santiago marca las más relevantes con checkbox "Destacada"
6. **Difusión:** Agente social toma todas las notas Publicadas y las publica en X

---

## Costos estimados

- Anthropic API (agente redactor + social + anti-repetición): ~$17-18 USD/mes
- GitHub Actions: gratis (dentro de los 2000 minutos/mes)
- Cron-job.org: gratis
- Cloudflare Workers: gratis
- Buffer: gratis (plan Free)
- GitHub Pages: gratis

---

## Decisiones legales

**Imágenes (Ley 11.723 Argentina):**

- Fuentes seguras: prensa.gba.gob.ar, AGLP, redes oficiales de funcionarios verificados, Wikimedia Commons
- Citar fuente reduce riesgo aunque no exime
- Evitar absolutamente: menores, redes personales, fotos íntimas, marcas de agua borradas
- CADRA representa fotógrafos desde dic 2023 — riesgo creciente

---

## Estado actual

### Sistema en producción

- ✅ Agente redactor con scraper Playwright funcionando
- ✅ Anti-repetición de temas (consulta últimas 30 notas)
- ✅ Flujo Solo Redes para actualizaciones breves
- ✅ Agente social publicando en X
- ✅ Web mostrando notas con archivo histórico (10 días)
- ✅ Cron externo en cron-job.org (más confiable que GitHub)
- ✅ Banco de imágenes cargado (23 fotos clasificadas)
- ✅ Panel de control editorial (panel-provincia-politica.html)
- ✅ Propiedad "Registro" en Notion para trazabilidad R1/R2/R3
- ✅ Scraper con bloqueo de recursos pesados (~50% más rápido)
- ✅ Palabras clave ampliadas (~70 términos: actores, intendentes, gremios, docentes)

### Pendientes

- ⬜ Carrusel Canva para Instagram + integración API Canva con agente social
- ⬜ Habilitar publicación en Instagram via Buffer
- ⬜ Verificar archivo histórico en producción (notas +10 días)
- ⬜ Probar el panel de control editorial funcionalmente
- ⬜ Optimizar scraper (puntos restantes): esperas inteligentes, selectores específicos por portal, HEAD request validación imagen
- ⬜ Editorial dominical (balance semanal, agente especial los domingos)
- ⬜ Plan evolución agente social Etapa 2 (hilos analíticos para R2/R3)
- ⬜ Plan evolución agente social Etapa 3 (quote-tweets, tendencias)
- ⬜ Buscador inteligente de imágenes (consulta banco propio antes que portal)

---

## Documentación interna

- `CLAUDE.md` — guía operativa para Claude (instancias que trabajen en el repo)
- `.claude/memory/` — memoria persistente por componente (scraping, agentes, notion-cms, publicación)
