# Adaptadores para portales que bloquean lectura directa

## Por qué existe esta carpeta

`reverse-api-engineer` (<https://github.com/kalil0321/reverse-api-engineer>) **no es una
fuente de datos**: es un generador de clientes. Abre un navegador real, graba el
tráfico (HAR) y un modelo escribe un cliente tipado para los endpoints que el
sitio usa de verdad. El cliente queda en disco y se ejecuta como código normal.

Eso resuelve exactamente nuestro problema con **Indeed** y con los portales que
solo cargan con JavaScript: no se puede leer con `WebFetch`, pero sí con una
sesión de navegador.

## Qué está integrado y qué no

| Portal | Estado | Cómo se lee |
|---|---|---|
| **SEEK** | ✅ listo, sin navegador | `proveedores/seek.py` usa el endpoint JSON público de `au.seek.com`. Verificado el 2026-11-07. |
| **Indeed** | ⚠️ requiere cliente generado | `proveedores/indeed.py` busca `adaptadores/indeed_client.py`. |
| LinkedIn | ✅ parcial | `WebFetch`/`WebSearch` (a veces responde 429). |
| Jobs Victoria / Workforce Australia | ⚠️ JavaScript | `WebFetch` devuelve poco; candidato a navegador. |

## Cómo generar el cliente de Indeed (una sola vez)

```bash
uv tool install reverse-api-engineer

reverse-api-engineer agent \
  --prompt "capture the public Indeed job search results for Melbourne" \
  --url "https://au.indeed.com/jobs?q=&l=Melbourne+VIC"
```

Se abre un navegador: haz una búsqueda de «full time» en Melbourne y ciérralo.
La herramienta deja el cliente en `./scripts/<nombre>/api_client.py`.

Cópialo a `adaptadores/indeed_client.py` y añádele una función `buscar` con este
contrato, para que `proveedores/indeed.py` lo pueda llamar:

```python
def buscar(keywords: str, where: str, paginas: int) -> dict:
    return {
        "fuente": "Indeed",
        "consulta": {...},
        "total_en_portal": 0,
        "devueltas": 0,
        "excluidas_por_limpieza": [],
        "ofertas": [
            {
                "id": "...",
                "titulo": "...",
                "empresa": "...",
                "ubicacion": "...",
                "jornada": "...",
                "salario": "...",
                "categoria": "...",
                "publicada": "...",
                "publicada_texto": "...",
                "resumen": "...",
                "enlace": "https://au.indeed.com/viewjob?jk=...",
                "fuente": "Indeed",
            }
        ],
    }
```

## Alternativa sin instalar nada

Si no quieres generar el cliente, el agente sigue funcionando con SEEK,
LinkedIn y los portales oficiales. Indeed aparecerá como **no revisada** en el
informe, no como si no hubiera ofertas.

## Nota legal

Ambos portales prohíben la extracción automatizada en sus términos de uso. Usa
esto para búsquedas personales y de bajo volumen, no para redistribuir datos ni
para alimentar un producto. Si necesitas volumen, pide acceso a su API oficial:
SEEK la ofrece a empleadores y partners; Indeed también.
