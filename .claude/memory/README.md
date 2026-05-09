# .claude/memory

Esta carpeta es la memoria persistente del proyecto para Claude. No es documentación para humanos.

## Para qué sirve

El `CLAUDE.md` de la raíz tiene el contexto general del proyecto — línea editorial, hard nos, arquitectura, convenciones. Pero algunos aprendizajes son muy específicos de un componente y meterlos en el `CLAUDE.md` lo haría inmanejable.

Esta carpeta resuelve eso: un archivo por tema, donde cada uno guarda los aprendizajes acumulados, decisiones tomadas, bugs resueltos, y patrones específicos de ese componente.

## Estructura

```
.claude/memory/
├── README.md          ← este archivo
├── scraping/
│   ├── letrap.md      ← selectores y comportamiento específico de letrap.com.ar
│   ├── latecla.md     ← selectores y comportamiento específico de latecla.info
│   └── infocielo.md   ← selectores y comportamiento específico de infocielo.com
├── agentes/
│   ├── redactor.md    ← prompts, decisiones editoriales codificadas, bugs históricos
│   └── social-x.md    ← integración con Buffer, mutación GraphQL, límites
├── notion-cms.md      ← propiedades de la DB, queries, filtros, problemas conocidos
└── publicacion.md     ← flujo de publicación, archivado, render del sitio
```

## Reglas de uso

### Cuándo agregar algo

- **Bug nuevo descubierto y resuelto:** documentar el síntoma, la causa y la solución.
- **Decisión técnica con razón no obvia:** ej. "usamos endpoint X y no Y porque Y rechaza Personal Keys".
- **Patrón que se repite:** ej. "Notion devuelve `select: null` cuando la propiedad existe pero está vacía".
- **Selector CSS o configuración específica de un sitio externo:** todo lo del scraping va acá.

### Cuándo NO agregar algo

- Reglas que aplican al proyecto entero → van al `CLAUDE.md` raíz.
- Documentación para humanos → va al `README.md` raíz.
- Ideas o pendientes → van a la sección "Estado actual y pendientes vivos" del `CLAUDE.md`.
- Cosas obvias o que se entienden leyendo el código.

### Cómo escribir

- Un archivo, un tema. Si un archivo crece mucho, considerá dividirlo.
- Markdown plano, secciones claras.
- Privilegiá la causa sobre la solución. "Esto pasaba porque X" es más útil que "agregamos esta línea".
- Fecha aproximada cuando ayuda al contexto. No fechar todo, solo lo que importa.

### Cómo leer

Antes de tocar un componente, leé el archivo correspondiente. Si vas a modificar `scraper.py` y vas a tocar el portal Letra P, leé `scraping/letrap.md` primero. Te puede ahorrar reproducir bugs ya resueltos.

## Filosofía

Cada vez que un Claude futuro lea esta carpeta, tiene que poder evitar errores que ya cometimos. Si no podés explicar para qué sirve un aprendizaje en una línea, probablemente no valga la pena guardarlo.
