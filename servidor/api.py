"""Servidor local que conecta el frontend con el agente real.

No usa frameworks: solo la biblioteca estándar, para que funcione con el mismo
`uv run` del proyecto y no agregue dependencias al despliegue.

    uv run python servidor/api.py

Endpoints:
    GET  /salud     → comprobación rápida
    POST /buscar    → búsqueda en SEEK (rápida, sin IA)
    POST /informe   → ejecuta agente.py y devuelve el informe en Markdown

El frontend lo usa cuando `assets/config.js` tiene:
    window.CONFIG = { API_LOCAL: "http://127.0.0.1:8787" };
o cuando Vercel tiene la variable `AGENT_API_URL` apuntando aquí.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from proveedores import perfil as proveedor_perfil  # noqa: E402
from proveedores import seek as proveedor_seek  # noqa: E402

PUERTO = int(os.environ.get("PUERTO", "8787"))
INFORME_MAX_SEGUNDOS = 300


def _json(handler: BaseHTTPRequestHandler, codigo: int, datos: Any) -> None:
    cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    handler.send_response(codigo)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(cuerpo)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(cuerpo)


def _leer_cuerpo(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    largo = int(handler.headers.get("Content-Length") or 0)
    if largo <= 0:
        return {}
    crudo = handler.rfile.read(largo).decode("utf-8", errors="replace")
    try:
        return json.loads(crudo)
    except json.JSONDecodeError:
        return {}


def _buscar(cuerpo: dict[str, Any]) -> dict[str, Any]:
    resultado = proveedor_seek.buscar(
        keywords=str(cuerpo.get("keywords") or ""),
        jornada=str(cuerpo.get("jornada") or "fulltime"),
        paginas=int(cuerpo.get("paginas") or 1),
        excluir=proveedor_perfil.exclusiones(),
    )
    return {**resultado, "modo": "local", "permite_ia": True}


def _ultimo_informe() -> str:
    entregas = RAIZ / "workspace" / "entregas"
    informes = sorted(
        entregas.glob("novedades-*.md"), key=lambda ruta: ruta.stat().st_mtime
    )
    if not informes:
        return ""
    return informes[-1].read_text(encoding="utf-8")


def _informe(cuerpo: dict[str, Any]) -> dict[str, Any]:
    perfil = cuerpo.get("perfil") or {}
    resumen = ", ".join(
        f"{clave}={valor}"
        for clave, valor in perfil.items()
        if valor and "completar" not in str(valor).lower()
    )
    prompt = (
        "Busca ofertas de empleo nuevas en Melbourne y escribe el informe en "
        "entregas/. Usa mcp__empleo__buscar_seek con jornada fulltime y 2 o 3 "
        "palabras clave distintas. Descarta limpieza y no inventes datos. "
        f"Perfil declarado en la interfaz: {resumen or 'sin datos'}."
    )

    entorno = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    comando = [
        "uv",
        "run",
        "--project",
        str(RAIZ),
        "--directory",
        str(RAIZ),
        "python",
        "agente.py",
        prompt,
    ]
    proceso = subprocess.run(
        comando,
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=INFORME_MAX_SEGUNDOS,
        env=entorno,
    )
    informe = _ultimo_informe()
    if proceso.returncode != 0 and not informe:
        raise RuntimeError((proceso.stderr or proceso.stdout or "sin salida")[-800:])
    return {
        "modo": "ia",
        "informe": informe,
        "salida": (proceso.stdout or "")[-4000:],
    }


class Manejador(BaseHTTPRequestHandler):
    server_version = "MelbourneEmpleo/1.0"

    def log_message(self, formato: str, *args: Any) -> None:  # menos ruido en consola
        print(f"  {self.address_string()} · {formato % args}")

    def do_OPTIONS(self) -> None:  # noqa: N802 (API de http.server)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/salud", ""):
            _json(self, 200, {"ok": True, "servicio": "melbourne-empleo"})
        else:
            _json(self, 404, {"error": "ruta no encontrada"})

    def do_POST(self) -> None:  # noqa: N802
        ruta = self.path.rstrip("/")
        cuerpo = _leer_cuerpo(self)
        try:
            if ruta == "/buscar":
                _json(self, 200, _buscar(cuerpo))
            elif ruta == "/informe":
                _json(self, 200, _informe(cuerpo))
            else:
                _json(self, 404, {"error": "ruta no encontrada"})
        except subprocess.TimeoutExpired:
            _json(self, 504, {"error": "el agente tardó demasiado"})
        except Exception as error:  # devolvemos el motivo al frontend
            _json(self, 500, {"error": str(error)})


def main() -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"Melbourne Empleo · servidor local en http://127.0.0.1:{PUERTO}")
    print("  POST /buscar   búsqueda rápida en SEEK")
    print("  POST /informe  ejecuta el agente (IA)")
    print("  Ctrl+C para detener")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
