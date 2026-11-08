# Melbourne Jobs · web

La interfaz que usa tu hermana. En inglés por defecto, con botón EN/ES. Sin frameworks ni build:
HTML + CSS + JS y cuatro funciones de Vercel.

```text
navegador ──► /api/chat    crea la Session del agente (tope USD 1,20) o envía una pregunta
          ──► /api/events  polling cada ~2 s: progreso, respuesta, estado y costo
          ──► /api/search  búsqueda rápida en SEEK, gratis, sin modelo
          ──► /api/health  ¿está configurado el chat? ¿el código es correcto?
                 │
                 └─ ANTHROPIC_API_KEY vive solo en Vercel; nunca llega al navegador
```

## Desplegar en Vercel

1. **Add New → Project → Import** el repositorio de GitHub.
2. **Root Directory:** `web` (o `buscador-empleo-melbourne/web` si el repo tiene la carpeta padre).
   Framework Preset: **Other**. Build y Output: vacíos.
3. **Settings → Environment Variables** (Production):

| Variable | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | una API key del workspace **"Prueba agentes"** (Console → API keys) |
| `AGENT_ID` | `agent_014bRzh9MwpUJM4C8pQbM1Ga` |
| `ENVIRONMENT_ID` | `env_01A7LShbxWTmD6oCJBgQR5o7` |
| `MEMORY_STORE_ID` | `memstore_01UvN1DoyRzLMDe1FmzjjEHa` |
| `ACCESS_CODE` | el código que le darás a tu hermana (largo, sin espacios) |
| `SESSION_BUDGET_CENTS` | opcional; `120` = USD 1,20 por conversación |

4. **Deploy** (o Redeploy después de cambiar variables).

Sin `ANTHROPIC_API_KEY` o sin `ACCESS_CODE`, el chat se apaga solo y la búsqueda rápida sigue
funcionando.

## Probar en tu máquina (sin API key)

```sh
# terminal 1: proxy local que usa tu login de `ant` (el token no sale del proceso)
uv run --script scripts/dev-proxy.py
# terminal 2: el mismo código de Vercel, servido localmente
ACCESS_CODE=local-test AGENT_ID=agent_... ENVIRONMENT_ID=env_... MEMORY_STORE_ID=memstore_... \
ANTHROPIC_API_KEY=local-proxy ANTHROPIC_BASE_URL=http://127.0.0.1:8788 node scripts/dev-web.js
# abre http://127.0.0.1:3000 y usa el código local-test
```

## Seguridad y costos

- Cada conversación tiene un tope duro de USD 1,20: al llegar, la Session se detiene
  (`budget_reached`) y la web ofrece un chat nuevo.
- Sin el código de acceso no se crea ninguna Session (respuesta 401, costo USD 0).
- Pon además un límite de gasto mensual al workspace en Console → Limits.
- El perfil vive en `localStorage`; viaja al agente solo en el primer mensaje de cada chat.

## La dedicatoria

El pie de página conserva la nota en español:

> Con mucho amor de **Jimy Díaz** para su hermana 💖 💕 💗 ❤️ 💓 💞 💘 💝
