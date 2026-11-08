# hooks.py — el guardián del paso 9.
#
# Corre en TU proceso, antes que las reglas de permiso y antes del modo.
# Hace dos cosas:
#   1. WebFetch solo a los dominios de workspace/datos/fuentes.md.
#   2. Write/Edit solo dentro de workspace/entregas/.
#
# TRAMPA: las claves de un hook van en camelCase también en Python
# (hookSpecificOutput, permissionDecision, permissionDecisionReason).
# En snake_case se ignoran en silencio y el hook no hace nada.

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
ENTREGAS = (BASE / "workspace" / "entregas").resolve()

DOMINIOS = (
    "jobs.vic.gov.au",
    "careers.vic.gov.au",
    "workforceaustralia.gov.au",
    "jobsearch.gov.au",
    "fairwork.gov.au",
    "seek.com.au",
    "au.indeed.com",
    "linkedin.com",
)


def _dominio_permitido(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS)


def _dentro_de_entregas(ruta: str) -> bool:
    destino = Path(ruta)
    if not destino.is_absolute():
        destino = BASE / "workspace" / destino
    destino = destino.resolve()
    return destino == ENTREGAS or ENTREGAS in destino.parents


def _denegar(motivo_modelo: str, mensaje_persona: str) -> dict[str, Any]:
    return {
        "systemMessage": mensaje_persona,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo_modelo,
        },
    }


async def vigilar_fuentes(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    nombre = input_data.get("tool_name", "")
    datos = input_data.get("tool_input", {}) or {}

    if nombre == "WebFetch":
        url = datos.get("url", "")
        if not _dominio_permitido(url):
            return _denegar(
                "Solo puedes abrir dominios de workspace/datos/fuentes.md "
                "(jobs.vic.gov.au, careers.vic.gov.au, workforceaustralia.gov.au, "
                "jobsearch.gov.au, fairwork.gov.au, seek.com.au, au.indeed.com, "
                "linkedin.com). Usa una fuente de esa lista; si no encuentras la "
                "oferta ahí, no la reportes.",
                f"Hook bloqueó WebFetch fuera de la lista: {url}",
            )

    if nombre in ("Write", "Edit"):
        ruta = datos.get("file_path") or datos.get("path") or ""
        if not _dentro_de_entregas(ruta):
            return _denegar(
                "Solo puedes escribir dentro de entregas/. Para guardar una oferta "
                "en el estado usa la herramienta mcp__empleo__registrar_oferta.",
                f"Hook bloqueó una escritura fuera de entregas/: {ruta}",
            )

    # Objeto vacío = sin opinión; sigue el flujo normal de permisos.
    return {}
