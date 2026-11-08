# melbourne-job-finder

Asistente de búsqueda de empleo que corre en **Claude Managed Agents** (la nube de Anthropic).
Tu hermana conversa con él desde la web en Vercel: busca ofertas reales en SEEK, LinkedIn y
Victorian Government Careers y Ethical Jobs, prioriza trabajos que usan su formación de abogada en derechos humanos, descarta la limpieza, marca NEW/SEEN y explica qué encaja con su
perfil. Nunca postula ni inventa datos.

- **Costo medido:** USD 0,06 – 0,10 por búsqueda (perfil de abogada: USD 0,08); USD 0,01 por pregunta de seguimiento (2026-11-08).
- **Tope:** USD 1,20 por conversación (`budget.max_list_cost.amount = "120"`, en `web/api/chat.js`).

## Ficha

```
FICHA DEL AGENTE  melbourne-job-finder   (archivos en agents/melbourne-job-finder/)

Modelo        claude-sonnet-5-5 · effort low                          model.yaml
              por qué: correr un script, filtrar y explicar; low deja muchas
              preguntas por chat dentro de USD 1,20 (medido: USD 0,06-0,10)
Disparador    una persona: tu hermana desde la web (POST /api/chat)
Entrega       user.message por pregunta; el "listo" vive en el Goal del prompt
Tope de costo USD 1,20 por conversación (amount "120")                web/api/chat.js
              al llegar: idle budget_reached → la web ofrece "New chat"
System prompt system_prompt.md
Tools         read/glob/grep/web_fetch: always_allow · bash/write/edit: auto
              web_search: apagada (las fuentes están en la skill)        tools.yaml
              si auto pide permiso, /api/events lo niega para no colgar el chat
MCP           no usa
Skills        melbourne-job-search: SEEK, LinkedIn, Vic Careers, Ethical Jobs  skills.yaml
Subagentes    ninguno
Environment   cloud · networking limited                              environment.yaml
              hosts: au.seek.com, www.seek.com.au, www.linkedin.com,
              www.careers.vic.gov.au, www.ethicaljobs.com.au, www.fairwork.gov.au
Memoria       job-finder-memory → /mnt/memory/job-finder-memory/seen.json
              read_write · solo URLs vistas (máx. 1.000), nunca el perfil
Credenciales  agente: ninguna · web: variables de entorno en Vercel
Compuerta     el agente solo busca y explica; ella postula desde el enlace
Perfil fijo   abogada colombiana, DD. HH.; nunca la presenta como "lawyer":
              la admisión la decide el Victorian Legal Admissions Board
Fuera         Indeed (bloquea bots) · Deployment programado (se puede agregar)
```

## Archivos

| Archivo | Qué es |
|---|---|
| `model.yaml` | Nombre, descripción, modelo y effort |
| `system_prompt.md` | El system prompt, en Simplified Technical English |
| `tools.yaml` | Tools del sandbox y sus permisos |
| `skills.yaml` | La skill propia `../../skills/melbourne-job-search` |
| `environment.yaml` | El contenedor: red limitada a 5 hosts |
| `memory_store-memoria.yaml` | La memoria `seen.json` entre conversaciones |
| `tests/` | Casos de prueba para `scripts/probar.py` |
| `agent.md` | Generado por `scripts/ensamblar.py`. No lo edites a mano |

## Cambiar algo

```sh
uv run --script scripts/ensamblar.py agents/melbourne-job-finder
sed -i 's/\r$//' agents/melbourne-job-finder/agent.md     # Windows: quita \r del archivo generado
F=(agents/melbourne-job-finder/agent.md agents/melbourne-job-finder/environment.yaml agents/melbourne-job-finder/memory_store-memoria.yaml skills/melbourne-job-search)
ant apply --dry-run -v "${F[@]}"
ant apply --yes "${F[@]}"     # solo después de leer el plan
```

Las conversaciones nuevas usan la última versión del Agent; las que ya existen siguen con la suya.

## Probar y depurar

```sh
uv run --script scripts/probar.py agents/melbourne-job-finder/tests/basico.json
uv run --script scripts/trazas.py <session_id>        # la traza explicada
uv run --script scripts/inspeccionar.py <session_id>  # si algo falló
```

Cada chat de la web es una Session con título `Web chat: …` en
platform.claude.com → Sessions.

## IDs (workspace "Prueba agentes")

| Recurso | ID |
|---|---|
| Agent `melbourne-job-finder` (v5) | `agent_014bRzh9MwpUJM4C8pQbM1Ga` |
| Environment | `env_01A7LShbxWTmD6oCJBgQR5o7` |
| Memory store `job-finder-memory` | `memstore_01UvN1DoyRzLMDe1FmzjjEHa` |
| Skill `melbourne-job-search` | `skill_01PdyjD6J5WctYHKGWKcEUAn` |
