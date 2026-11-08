# Decisiones de buscador-empleo-melbourne

La credencial y las nueve respuestas del wizard, la opción exacta del SDK que
produjo cada una, y dónde leer más. Generado el 2026-11-07.

Versiones contra las que se probó: **Python SDK 0.2.176** (empaca Claude Code
2.1.316).

| # | Pregunta | Tu respuesta | Código exacto | Dónde leer más |
|---|---|---|---|---|
| 0 | ¿Con qué pagas? | Login con `ant` | `AGENTE_AUTH=ant`, `ANTHROPIC_PROFILE=default` en `.env` | [ant CLI](https://platform.claude.com/docs/en/api/sdks/cli) |
| 1 | ¿En qué lenguaje? | Python | `agente.py` + `pyproject.toml` | [quickstart](https://code.claude.com/docs/en/agent-sdk/quickstart.md) |
| 2 | ¿Qué tiene que lograr? | Buscar ofertas y usar funciones propias | `query()` en `main()` | [agent-loop](https://code.claude.com/docs/en/agent-sdk/agent-loop.md) |
| 3 | ¿Qué modelo? | Sonnet 5.5 | `model="claude-sonnet-5-5"` | [modelos](https://platform.claude.com/docs/en/about-claude/models/overview.md) |
| 4 | ¿Qué reglas fijas? | Mínimo + reglas de la idea | `SYSTEM_PROMPT` | [system prompt](https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts.md) |
| 5 | ¿Qué puede hacer? | Leer, escribir, web y funciones propias | `allowed_tools=[...]`, `mcp_servers={"empleo": empleo}` | [custom-tools](https://code.claude.com/docs/en/agent-sdk/custom-tools.md) |
| 6 | ¿Un procedimiento tuyo? | Sí, skill nueva | `setting_sources=["project"]`, `skills=["buscar-empleos-melbourne"]` | [skills](https://code.claude.com/docs/en/skills.md) |
| 7 | ¿Repartir la tarea? | No, un solo agente | sin `agents=` | [subagents](https://code.claude.com/docs/en/agent-sdk/subagents.md) |
| 8 | ¿Quién autoriza? | Solo lo listado | `permission_mode="default"`, `allowed_tools`, `disallowed_tools=["Bash","Edit","NotebookEdit"]` | [permissions](https://code.claude.com/docs/en/agent-sdk/permissions.md) |
| 9 | ¿Un vigilante? | El guardián de la idea | `hooks={"PreToolUse": [...]}` → `hooks.py` | [hooks](https://code.claude.com/docs/en/agent-sdk/hooks.md) |

## Funciones propias (paso 5)

| Herramienta | Qué hace | Por qué |
|---|---|---|
| `mcp__empleo__leer_perfil` | Devuelve la ficha y los campos en `COMPLETAR` | Para no inventar visa ni horas |
| `mcp__empleo__buscar_seek` | Busca en SEEK por su endpoint JSON | `WebFetch` recibe 403; el JSON sí responde |
| `mcp__empleo__buscar_indeed` | Usa `adaptadores/indeed_client.py` si existe | Indeed exige sesión de navegador |
| `mcp__empleo__ya_visto` | Deduplicación por título o enlace | No repetir ofertas entre corridas |
| `mcp__empleo__registrar_oferta` | Guarda la oferta reportada | Estado persistente |

## Límites

- `max_turns=14`
- `max_budget_usd=0.30`
- Sin Bash, sin Edit, sin NotebookEdit.
- WebFetch solo a los dominios de `workspace/datos/fuentes.md`.
- Write solo dentro de `workspace/entregas/`.
- Limpieza: se descarta en código por título (`proveedores/seek.py`) y se puede
  ampliar en `workspace/datos/filtros.json`.

## Qué cambiar primero

| Si quieres… | Cambia |
|---|---|
| completar visa, horas o certificaciones | `workspace/datos/perfil.md` |
| excluir más tipos de empleo | `workspace/datos/filtros.json` |
| más fuentes | `workspace/datos/fuentes.md` |
| habilitar Indeed | genera `adaptadores/indeed_client.py` (ver `adaptadores/README.md`) |
| más presupuesto por corrida | `max_budget_usd` en `agente.py` |
| otro modelo | `model=` en `agente.py` |
| permitir otra web | `DOMINIOS` en `hooks.py` y `datos/fuentes.md` |
