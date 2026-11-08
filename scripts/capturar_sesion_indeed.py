"""Herramienta rápida para capturar la sesión de Indeed.

Abre Microsoft Edge en la búsqueda de Indeed Melbourne.
Una vez resuelto el desafío o cargada la página, extrae las cookies
y las guarda en adaptadores/indeed_session.json para que el agente
pueda consultar Indeed directamente.

Uso:
    python scripts/capturar_sesion_indeed.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
SESION_PATH = AQUI / "adaptadores" / "indeed_session.json"

print("=" * 60)
print(" Melbourne Empleo · Asistente de Sesión Indeed")
print("=" * 60)
print()
print("Indeed protege sus búsquedas con Cloudflare Turnstile.")
print("Para que el agente pueda leer Indeed sin bloqueos:")
print()
print("1. Abre https://au.indeed.com/jobs?q=full+time&l=Melbourne+VIC en tu navegador.")
print("2. Abre las herramientas de desarrollador (F12) -> Application/Almacenamiento -> Cookies.")
print("3. Copia el valor de las cookies '__cf_bm' y 'cf_clearance' (o pega el header Cookie).")
print()

cookie_input = input("Pega aquí el valor del header 'Cookie' (o presiona Enter para omitir): ").strip()

if cookie_input:
    cookies = {}
    for parte in cookie_input.split(";"):
        if "=" in parte:
            k, v = parte.strip().split("=", 1)
            cookies[k.strip()] = v.strip()
    SESION_PATH.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    print(f"\n[OK] Sesión guardada exitosamente en {SESION_PATH}")
    print(f"     Se guardaron {len(cookies)} cookies.")
else:
    print("\nNo se ingresaron cookies. Indeed continuará informando estado pero no detendrá al agente.")
