"""Genera el conjunto de datos real que usa la demo del frontend.

Consulta SEEK varias veces, deduplica y deja solo ofertas de jornada completa
en Melbourne sin limpieza. El resultado es el JSON que se publica en Vercel,
para que la demo no dependa de una API ni de una clave.

    uv run python scripts/generar_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proveedores import perfil, seek  # noqa: E402

DESTINO = (
    Path(__file__).resolve().parent.parent / "web" / "data" / "demo-ofertas.json"
)

CONSULTAS = [
    "customer service",
    "warehouse",
    "administration",
    "retail",
    "receptionist",
    "driver",
    "sales",
    "office",
]


def main() -> None:
    exclusiones = perfil.exclusiones()
    vistas: dict[str, dict] = {}

    for palabras in CONSULTAS:
        try:
            resultado = seek.buscar(
                keywords=palabras,
                jornada="fulltime",
                paginas=2,
                pagesize=100,
                excluir=exclusiones,
            )
        except Exception as error:  # una consulta puede fallar y las demás no
            print(f"  ! {palabras}: {error}")
            continue
        for oferta in resultado["ofertas"]:
            if oferta["id"] not in vistas:
                vistas[oferta["id"]] = oferta
        print(f"  · {palabras}: {resultado['devueltas']} ofertas")

    ofertas = sorted(
        vistas.values(),
        key=lambda o: o.get("publicada", ""),
        reverse=True,
    )[:90]

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(
            {
                "generado": "2026-11-07",
                "fuente": "SEEK Australia (au.seek.com)",
                "nota": "Datos reales de una corrida de prueba. No son ofertas vigentes garantizadas.",
                "total": len(ofertas),
                "ofertas": ofertas,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nGuardadas {len(ofertas)} ofertas en {DESTINO}")


if __name__ == "__main__":
    main()
