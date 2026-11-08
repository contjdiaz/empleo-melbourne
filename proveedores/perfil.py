"""Lectura del perfil diligenciable y de los filtros del agente.

El perfil es un archivo Markdown con una sección de pares `clave: valor`.
Así la persona lo edita sin tocar código y el agente lo lee como datos.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent.parent
PERFIL = AQUI / "workspace" / "datos" / "perfil.md"
FILTROS = AQUI / "workspace" / "datos" / "filtros.json"

SECCION = "## Ficha para diligenciar"
LINEA = re.compile(r"^([a-z_]+):\s*(.*)$")

VACIOS = {"", "completar", "«completar»", "pendiente", "no especificado", "-"}


def leer_perfil(ruta: Path | None = None) -> dict[str, Any]:
    """Devuelve `{"campos": {...}, "faltantes": [...], "ruta": str}`."""
    destino = ruta or PERFIL
    campos: dict[str, str] = {}
    dentro = False
    for linea in destino.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("## "):
            dentro = linea.strip().startswith(SECCION)
            continue
        if not dentro:
            continue
        coincidencia = LINEA.match(linea.strip())
        if coincidencia:
            campos[coincidencia.group(1)] = coincidencia.group(2).strip()

    faltantes = [
        clave
        for clave, valor in campos.items()
        if clave != "nivel_de_ingles"
        and (valor.strip().lower() in VACIOS or "completar" in valor.lower())
    ]
    return {"campos": campos, "faltantes": faltantes, "ruta": str(destino)}


def leer_filtros(ruta: Path | None = None) -> dict[str, Any]:
    """Filtros editables por la persona. Si el archivo falta, usa vacíos."""
    destino = ruta or FILTROS
    if not destino.exists():
        return {"excluir_titulos": [], "excluir_empresas": []}
    datos = json.loads(destino.read_text(encoding="utf-8"))
    return {
        "excluir_titulos": [str(x) for x in datos.get("excluir_titulos", [])],
        "excluir_empresas": [str(x) for x in datos.get("excluir_empresas", [])],
    }


def exclusiones(ruta: Path | None = None) -> tuple[str, ...]:
    """Une las exclusiones por defecto con las que agregue la persona."""
    from . import seek

    filtros = leer_filtros(ruta)
    extra = tuple(filtros["excluir_titulos"])
    return tuple(dict.fromkeys(seek.EXCLUIR_POR_DEFECTO + extra))


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    informacion = leer_perfil()
    print(json.dumps(informacion, ensure_ascii=False, indent=2))
    if informacion["faltantes"]:
        faltan = ", ".join(informacion["faltantes"])
        print(f"\nFaltan datos por diligenciar: {faltan}")
        print(f"Edita {informacion['ruta']} y vuelve a correr.")
    else:
        print("\nPerfil completo.")
