# CLAUDE.md

## Pendientes / Recordatorios

- **[2026-05-08] Skill code-chat sync (rama `claude/code-chat-sync-skill-UfiF6`):** el usuario está pensando si avanzar con una skill que sincronice avances del proyecto entre Claude Code, Claude.com y Claude Chrome. Recordatoria pedida para el 2026-05-09. Decisión pendiente:
  - Hub central: **Notion** (recomendado, ya hay MCP configurado) vs `PROGRESS.md` local.
  - Si avanza con Notion: el usuario crea la página y pasa la URL; entonces armamos skill `/sync-progress` + hook `Stop` en Claude Code que actualiza la página vía MCP, y conectores de Notion activados en .com y Chrome con instrucción de leer/actualizar al inicio y cierre de cada conversación.
  - Si avanza con `PROGRESS.md`: empezar simple en el repo y migrar a Notion más adelante.

  **Acción al ver esto:** preguntarle al usuario si ya decidió y retomar desde ahí.
