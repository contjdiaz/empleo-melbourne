"""Servidor local que conecta el frontend con el agente real y sirve la interfaz web.

No usa frameworks: solo la biblioteca estándar, para que funcione con el mismo
`uv run` del proyecto y no agregue dependencias al despliegue.

    uv run python servidor/api.py

Endpoints:
    GET  /             → sirve la interfaz web (web/index.html)
    GET  /assets/...   → sirve estilos y scripts del frontend
    GET  /data/...     → sirve datos de respaldo
    GET  /salud        → comprobación rápida de estado
    POST /buscar       → búsqueda en vivo multicanal (SEEK + LinkedIn)
    POST /informe      → ejecuta agente.py y devuelve el informe en Markdown
"""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from proveedores import linkedin as proveedor_linkedin  # noqa: E402
from proveedores import perfil as proveedor_perfil  # noqa: E402
from proveedores import seek as proveedor_seek  # noqa: E402
from proveedores import vic_careers as proveedor_vic_careers  # noqa: E402

PUERTO = int(os.environ.get("PUERTO", "8787"))
INFORME_MAX_SEGUNDOS = 300
WEB_DIR = (RAIZ / "web").resolve()


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
    keywords = str(cuerpo.get("keywords") or "")
    jornada = str(cuerpo.get("jornada") or "fulltime")
    paginas = int(cuerpo.get("paginas") or 1)
    exclusiones = proveedor_perfil.exclusiones()

    # Fuente 1: SEEK
    try:
        res_seek = proveedor_seek.buscar(
            keywords=keywords,
            jornada=jornada,
            paginas=paginas,
            excluir=exclusiones,
        )
    except Exception as e:
        res_seek = {
            "fuente": "SEEK",
            "ofertas": [],
            "excluidas_por_limpieza": [],
            "aviso": str(e),
        }

    # Fuente 2: LinkedIn
    try:
        res_linkedin = proveedor_linkedin.buscar(
            keywords=keywords,
            jornada=jornada,
            paginas=1,
            excluir=exclusiones,
        )
    except Exception:
        res_linkedin = {"fuente": "LinkedIn", "ofertas": [], "excluidas_por_limpieza": []}

    ofertas_combinadas = res_seek.get("ofertas", []) + res_linkedin.get("ofertas", [])
    excluidas_total = (
        res_seek.get("excluidas_por_limpieza", [])
        + res_linkedin.get("excluidas_por_limpieza", [])
    )

    fuentes_activas = []
    if res_seek.get("ofertas"):
        fuentes_activas.append("SEEK")
    if res_linkedin.get("ofertas"):
        fuentes_activas.append("LinkedIn")

    return {
        "fuente": " + ".join(fuentes_activas) if fuentes_activas else "SEEK",
        "consulta": {
            "keywords": keywords,
            "where": "Melbourne VIC",
            "jornada": jornada,
            "paginas": paginas,
        },
        "total_en_portal": res_seek.get("total_en_portal", 0) + res_linkedin.get("total_en_portal", 0),
        "devueltas": len(ofertas_combinadas),
        "excluidas_por_limpieza": excluidas_total,
        "ofertas": ofertas_combinadas,
        "modo": "local",
        "permite_ia": True,
    }


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
        "entregas/. Usa mcp__empleo__buscar_seek y mcp__empleo__buscar_linkedin con jornada fulltime. "
        "Descarta limpieza y no inventes datos. "
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
    server_version = "MelbourneEmpleo/1.2"

    def log_message(self, formato: str, *args: Any) -> None:
        print(f"  {self.address_string()} · {formato % args}")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        ruta_limpia = self.path.split("?")[0].lstrip("/")
        if ruta_limpia == "salud":
            _json(self, 200, {"ok": True, "servicio": "melbourne-empleo", "fuentes": ["SEEK", "LinkedIn", "Victorian Government", "Indeed"]})
            return

        # Servir archivos estáticos de web/
        if not ruta_limpia:
            ruta_limpia = "index.html"

        archivo = (WEB_DIR / ruta_limpia).resolve()
        if not (archivo == WEB_DIR or WEB_DIR in archivo.parents) or not archivo.is_file():
            _json(self, 404, {"error": "archivo no encontrado"})
            return

        tipo, _ = mimetypes.guess_type(str(archivo))
        if not tipo:
            tipo = "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"

        try:
            contenido = archivo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(contenido)
        except Exception as error:
            _json(self, 500, {"error": f"Error al leer archivo: {error}"})

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
        except Exception as error:
            _json(self, 500, {"error": str(error)})


def main() -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"============================================================")
    print(f" Melbourne Empleo · Servidor en vivo")
    print(f"============================================================")
    print(f"  Web interactiva: http://127.0.0.1:{PUERTO}/")
    print(f"  Fuentes en vivo: SEEK, LinkedIn, Victorian Government, Indeed")
    print(f"  POST /buscar     Búsqueda en vivo (SEEK + LinkedIn)")
    print(f"  POST /informe    Ejecución del Agente IA (Claude Agent SDK)")
    print(f"  Ctrl+C para detener")
    print(f"============================================================")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
