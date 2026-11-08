"""Proveedor de Indeed mediante un cliente generado con reverse-api-engineer.

Indeed bloquea toda petición HTTP simple (403), incluso con User-Agent de
navegador. La única forma estable de leerlo es reutilizar una sesión de
navegador real. Eso es exactamente lo que hace `reverse-api-engineer`: graba el
tráfico de un navegador y genera un cliente tipado.

Este módulo no incluye ese cliente: lo busca en
`adaptadores/indeed_client.py`. Si no existe, devuelve instrucciones en vez de
fallar en silencio. Así el agente puede seguir con SEEK y las demás fuentes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent.parent
CLIENTE = AQUI / "adaptadores" / "indeed_client.py"

INSTRUCCIONES = f"""Indeed no tiene un cliente disponible todavía.

Indeed responde HTTP 403 a cualquier lectura directa, así que hay que generarle
un cliente con una sesión de navegador real:

  1. Instala la herramienta (una sola vez):
       uv tool install reverse-api-engineer

  2. Genera el cliente capturando una búsqueda tuya en Indeed:
       reverse-api-engineer agent \\
         --prompt "capture the public Indeed job search results for Melbourne" \\
         --url "https://au.indeed.com/jobs?q=&l=Melbourne+VIC"

     Se abre un navegador: busca «full time» en Melbourne y ciérralo.

  3. Copia el archivo generado a:
       {CLIENTE}

  4. Ese archivo debe exponer:
       def buscar(keywords: str, where: str, paginas: int) -> dict

     con la misma forma que devuelve proveedores.seek.buscar:
       {{"fuente", "consulta", "total_en_portal", "devueltas",
         "excluidas_por_limpieza", "ofertas": [...]}}

  Mientras no exista ese archivo, usa mcp__empleo__buscar_seek y WebFetch
  sobre LinkedIn; no inventes ofertas de Indeed.
"""


def disponible() -> bool:
    return CLIENTE.exists()


def buscar(
    keywords: str = "", where: str = "Melbourne VIC", paginas: int = 1
) -> dict[str, Any]:
    if not disponible():
        raise RuntimeError(INSTRUCCIONES)

    especificacion = importlib.util.spec_from_file_location("indeed_client", CLIENTE)
    if especificacion is None or especificacion.loader is None:
        raise RuntimeError(f"No pude cargar {CLIENTE}")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)

    if not hasattr(modulo, "buscar"):
        raise RuntimeError(
            f"{CLIENTE} no expone una función buscar(keywords, where, paginas)."
        )
    return modulo.buscar(keywords=keywords, where=where, paginas=paginas)
