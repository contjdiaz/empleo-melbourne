# buscador-empleo-melbourne

Busca ofertas de empleo nuevas en Melbourne para una mujer colombiana migrante
que estudia inglés y busca trabajo estable. Descarta limpieza y prioriza
jornada completa.

## Versión en la nube (la que usa tu hermana)

| Pieza | Dónde | Qué hace |
|---|---|---|
| Agente en Claude Managed Agents | `agents/melbourne-job-finder/` | Sonnet 5.5, tope USD 1,20 por conversación |
| Skill de búsqueda | `skills/melbourne-job-search/` | SEEK + LinkedIn + Vic Careers en un script |
| Web en Vercel | `web/` | Chat con tarjetas, EN/ES, búsqueda rápida gratis |
| IDs creados | `claude-lock.json` | Lo escribe `ant apply` |

Empieza por `agents/melbourne-job-finder/README.md` (la ficha completa) y
`web/README.md` (cómo desplegar y las variables de Vercel).

## Versión local (Agent SDK, la original)

Hecho con el [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk).

## Cómo correrlo

Dos comandos. El primero solo la primera vez.

```bash
uv sync
uv run agente.py
uv run agente.py "busca solo trabajos de administración de jornada completa"
```

Antes de la primera corrida, **diligencia tu perfil**:

```text
workspace/datos/perfil.md
```

Abre ese archivo, rellena la ficha (`visa`, `horas_disponibles`,
`certificaciones`…) y guarda. Para ver qué falta sin gastar tokens ni llamar al
modelo:

```bash
uv run python -m proveedores.perfil
```

## Qué hay aquí

| Archivo | Para qué |
|---|---|
| `agente.py` | El agente: system prompt, tools, límites y las nueve decisiones |
| `hooks.py` | El guardián: dominios permitidos y escritura solo en `entregas/` |
| `credenciales.py` | Lee `.env` y deja una sola credencial |
| `proveedores/seek.py` | Cliente de SEEK sin navegador ni dependencias |
| `proveedores/indeed.py` | Puente a un cliente de Indeed generado aparte |
| `proveedores/perfil.py` | Lee la ficha diligenciable y los filtros |
| `workspace/datos/perfil.md` | **Lo que tienes que diligenciar** |
| `workspace/datos/fuentes.md` | Los portales permitidos |
| `workspace/datos/filtros.json` | Palabras que excluyen títulos (limpieza, etc.) |
| `workspace/datos/visto.json` | Ofertas ya reportadas |
| `workspace/entregas/` | Donde el agente escribe el informe |
| `workspace/.claude/skills/buscar-empleos-melbourne/SKILL.md` | El procedimiento |
| `adaptadores/README.md` | Cómo habilitar Indeed con `reverse-api-engineer` |

## Cómo funciona

```text
tu perfil (datos/perfil.md)
    ↓
agente (Sonnet 5.5)
    ├── mcp__empleo__leer_perfil  → qué sabes y qué falta
    ├── mcp__empleo__buscar_seek  → SEEK por JSON, ya filtrado
    ├── mcp__empleo__buscar_indeed→ Indeed si hay cliente generado
    ├── WebSearch/WebFetch        → LinkedIn y portales oficiales
    ├── mcp__empleo__ya_visto     → ¿ya la reportamos?
    └── Write                     → solo dentro de entregas/
    ↓
workspace/entregas/novedades-<fecha>.md
```

### SEEK sin navegador

`proveedores/seek.py` usa el endpoint JSON que consume el buscador de
`au.seek.com`. No necesita clave ni cookies:

```bash
uv run python -m proveedores.seek "customer service" --jornada fulltime --paginas 2
```

Filtros de jornada: `fulltime`, `parttime`, `contract`, `casual`, `cualquiera`.

### Indeed: por qué no funciona directo

Indeed responde **403** a cualquier petición HTTP, incluso con User-Agent de
navegador. Hay que generar un cliente con una sesión de navegador real usando
`reverse-api-engineer`. Los pasos están en `adaptadores/README.md`. Mientras no
exista ese cliente, Indeed aparece como **no revisada**, no como si no hubiera
ofertas.

## Límites

- `max_turns=14`
- `max_budget_usd=0.30` por corrida
- Sin Bash, sin Edit, sin NotebookEdit.
- `WebFetch` solo a los dominios de `workspace/datos/fuentes.md`.
- `Write` solo dentro de `workspace/entregas/`.
- Las ofertas de limpieza se descartan por título, en código, no solo por
  criterio del modelo.

## La credencial

`credenciales.py` lee `.env` y usa **una sola** forma de pagar. En este
proyecto:

```env
AGENTE_AUTH=ant
ANTHROPIC_PROFILE=default
ANTHROPIC_CONFIG_DIR=C:\Users\LENOVO\AppData\Roaming\Anthropic
```

No edites `credenciales.py`; cambia `.env`.
