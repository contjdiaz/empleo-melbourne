# Fuentes permitidas

El agente solo puede abrir con `WebFetch` los dominios de esta lista; el hook
`vigilar_fuentes` deniega cualquier otro y le explica al modelo por qué.

## Portales oficiales y de empleo

| Fuente | URL base | Cómo la usa el agente |
|---|---|---|
| SEEK | https://www.seek.com.au | **`mcp__empleo__buscar_seek`** (endpoint JSON, sin bloqueo). `WebFetch` no sirve: responde 403. |
| Indeed Australia | https://au.indeed.com | **`mcp__empleo__buscar_indeed`**, solo si existe `adaptadores/indeed_client.py`. Sin ese cliente, queda como *no revisada*. |
| LinkedIn Jobs | https://www.linkedin.com/jobs | `WebSearch` + `WebFetch` (a veces responde 429). |
| Jobs Victoria | https://jobs.vic.gov.au | `WebFetch`; carga con JavaScript, puede devolver poco. |
| Victorian Government Careers | https://careers.vic.gov.au | `WebFetch`; vacantes del gobierno estatal. |
| Workforce Australia | https://www.workforceaustralia.gov.au | `WebFetch`; búsqueda oficial del gobierno federal. |
| JobSearch | https://www.jobsearch.gov.au | `WebFetch`; ofertas del gobierno australiano. |
| Fair Work Ombudsman | https://www.fairwork.gov.au | Consulta de derechos y salarios mínimos. No publica ofertas. |

## Reglas de fuentes

- No agregues fuentes nuevas sin que la usuaria lo pida.
- No uses agregadores desconocidos, grupos de Facebook, Telegram ni sitios de
  «trabajos desde casa» que piden dinero.
- Si una fuente falla o bloquea la lectura, anótala como **no revisada** y sigue.
- Para habilitar Indeed, sigue `adaptadores/README.md`.
