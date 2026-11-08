# Melbourne Empleo · frontend

Interfaz para que una persona no técnica use el buscador de empleo sin tocar la
terminal: completa su perfil, busca ofertas reales de SEEK y abre cada aviso.

Sin frameworks. HTML + CSS + JavaScript, ~60 kB en total (incluida la demo).
Se despliega en Vercel tal cual, sin build.

## Estructura

```text
web/
├── index.html              la interfaz
├── assets/
│   ├── styles.css          estilos (~13 kB)
│   ├── app.js              lógica (~11 kB)
│   ├── config.js           URL del agente local (vacío en Vercel)
│   └── demo-data.js        60 ofertas reales para el modo demostración
├── api/
│   └── buscar.js           función serverless de Vercel
├── data/
│   └── demo-ofertas.json   datos completos de la demo
└── vercel.json
```

## Desplegar en Vercel

### Opción A · desde la web (sin terminal)

1. Sube esta carpeta a un repositorio de GitHub.
2. En Vercel: **Add New → Project → Import** el repositorio.
3. En **Root Directory** elige `buscador-empleo-melbourne/web`.
4. Framework Preset: **Other**. Build Command: vacío. Output Directory: vacío.
5. **Deploy**.

### Opción B · desde la terminal

```bash
cd buscador-empleo-melbourne/web
npx vercel
```

En producción, sin variables de entorno, funciona en **modo demostración** con
las 60 ofertas reales incluidas.

## Conectar el agente real

El agente corre en tu máquina (necesita `ant` y el SDK de Python). Vercel solo
aloja la interfaz y hace de puente.

```bash
# terminal 1
uv run python servidor/api.py

# terminal 2: expón el puerto con un túnel
npx localtunnel --port 8787
# o: cloudflared tunnel --url http://127.0.0.1:8787
```

En Vercel: **Settings → Environment Variables**

```text
AGENT_API_URL = https://tu-tunel.loca.lt
```

Vuelve a desplegar. Ahora `POST /api/buscar` reenvía al agente y devuelve datos
en vivo, y aparece el botón **«Pedir informe al agente (IA)»**.

### Sin Vercel ni túnel

Abre `web/assets/config.js` y pon:

```js
window.CONFIG = { API_LOCAL: "http://127.0.0.1:8787" };
```

Sirve la carpeta con cualquier servidor estático:

```bash
cd buscador-empleo-melbourne/web
python -m http.server 5500
```

## Modos

| Modo | Cuándo | Qué hace |
|---|---|---|
| `demo` | Sin `AGENT_API_URL` ni servidor local | Filtra las 60 ofertas reales incluidas |
| `local` | Con `AGENT_API_URL` o `API_LOCAL` | Consulta SEEK en vivo desde tu máquina |
| `ia` | Botón de informe con servidor local | Ejecuta `agente.py` y muestra el informe |

## Privacidad

El perfil se guarda **solo en `localStorage`** del navegador. No viaja a ningún
servidor salvo el `perfil` que se envía con cada búsqueda al agente local, para
que sepa qué datos faltan.

## La dedicatoria

El pie de página lleva la nota que pediste:

> Con mucho amor de **Jimy Díaz** para su hermana 💖 💕 💗 ❤️ 💓 💞 💘 💝

Está en `index.html`, bloque `<footer class="pie">`.
