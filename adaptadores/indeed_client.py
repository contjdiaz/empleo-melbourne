"""Cliente de Indeed (Australia) para Melbourne Empleo.

Cumple con el contrato exigido por adaptadores/README.md y proveedores/indeed.py:
    def buscar(keywords: str, where: str, paginas: int) -> dict:

Estrategias implementadas:
  1. Si existe adaptadores/indeed_session.json con cookies de sesión,
     realiza la petición autenticada directamente sin abrir navegador.
  2. Si no hay sesión o Cloudflare bloquea la petición directa (HTTP 403),
     intenta consultar mediante Microsoft Edge con el perfil de usuario.
  3. Si la protección de Cloudflare exige resolución manual de CAPTCHA,
     no rompe la ejecución del agente ni lanza excepciones no controladas:
     devuelve un objeto estructurado informando el estado y cómo desbloquearlo
     en un clic con scripts/capturar_sesion_indeed.py.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
SESION_PATH = AQUI / "indeed_session.json"
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
)

EXCLUIR_POR_DEFECTO = (
    "cleaner",
    "cleaning",
    "housekeep",
    "janitor",
    "limpieza",
    "domestic clean",
    "commercial clean",
    "window clean",
    "laundry attendant",
)


def _obtener_edge_path() -> str | None:
    for ruta in EDGE_PATHS:
        if os.path.exists(ruta):
            return ruta
    return None


def _cargar_cookies_sesion() -> dict[str, str]:
    if not SESION_PATH.exists():
        return {}
    try:
        datos = json.loads(SESION_PATH.read_text(encoding="utf-8"))
        if isinstance(datos, dict):
            return {str(k): str(v) for k, v in datos.items()}
    except Exception:
        pass
    return {}


def _peticion_http(url: str, cookies: dict[str, str]) -> tuple[int, str]:
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Cookie": cookie_header,
            "Referer": "https://au.indeed.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, ""
    except Exception:
        return 0, ""


def _parsear_html_indeed(html: str, keywords: str, where: str) -> list[dict[str, Any]]:
    """Extrae ofertas de trabajo del HTML de Indeed."""
    ofertas: list[dict[str, Any]] = []

    # Estrategia A: window.mosaic.providerData["mosaic-provider-jobcards"]
    patron_mosaic = re.search(
        r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*({.+?});\s*window',
        html,
    )
    if patron_mosaic:
        try:
            datos_mosaic = json.loads(patron_mosaic.group(1))
            resultados = (
                datos_mosaic.get("metaData", {})
                .get("mosaicProviderJobCardsModel", {})
                .get("results", [])
            )
            for res in resultados:
                jk = res.get("jobkey") or res.get("jobKey")
                if not jk:
                    continue
                titulo = res.get("title") or res.get("displayTitle") or ""
                empresa = res.get("company") or res.get("companyName") or "no especificada"
                ubicacion = (
                    res.get("formattedLocation")
                    or res.get("location")
                    or where
                )
                salario = (
                    res.get("estimatedSalary", {}).get("formatted")
                    or res.get("salarySnippet", {}).get("text")
                    or "no especificado"
                )
                resumen = (
                    res.get("snippet")
                    or res.get("jobCardSnippet")
                    or ""
                )
                pub = res.get("formattedRelativeTime") or ""
                jornadas = res.get("jobTypes") or ["Full time"]
                ofertas.append(
                    {
                        "id": str(jk),
                        "titulo": str(titulo).strip(),
                        "empresa": str(empresa).strip(),
                        "ubicacion": str(ubicacion).strip(),
                        "jornada": ", ".join(jornadas) if isinstance(jornadas, list) else str(jornadas),
                        "salario": str(salario).strip(),
                        "categoria": "General",
                        "publicada": "",
                        "publicada_texto": str(pub).strip(),
                        "resumen": re.sub(r"<[^>]+>", "", str(resumen)).strip(),
                        "enlace": f"https://au.indeed.com/viewjob?jk={jk}",
                        "fuente": "Indeed",
                    }
                )
            if ofertas:
                return ofertas
        except Exception:
            pass

    # Estrategia B: Regex sobre tarjetas DOM
    bloques = re.findall(r'<div[^>]*class="[^"]*job_seen_beacon[^"]*"[^>]*>(.+?)</div>\s*</td>', html, re.DOTALL)
    for bloque in bloques:
        m_jk = re.search(r'data-jk="([a-zA-Z0-9]+)"', bloque)
        m_tit = re.search(r'<span[^>]*id="jobTitle-[^"]*"[^>]*>([^<]+)</span>', bloque)
        m_emp = re.search(r'data-testid="company-name"[^>]*>([^<]+)<', bloque)
        m_ubi = re.search(r'data-testid="text-location"[^>]*>([^<]+)<', bloque)
        m_sal = re.search(r'<div[^>]*class="[^"]*salary-snippet-container[^"]*"[^>]*>([^<]+)<', bloque)
        m_res = re.search(r'<ul[^>]*>(.+?)</ul>', bloque, re.DOTALL)

        if m_jk and m_tit:
            jk = m_jk.group(1)
            titulo = m_tit.group(1).strip()
            empresa = m_emp.group(1).strip() if m_emp else "no especificada"
            ubicacion = m_ubi.group(1).strip() if m_ubi else where
            salario = m_sal.group(1).strip() if m_sal else "no especificado"
            resumen = re.sub(r"<[^>]+>", " ", m_res.group(1)).strip() if m_res else ""
            ofertas.append(
                {
                    "id": jk,
                    "titulo": titulo,
                    "empresa": empresa,
                    "ubicacion": ubicacion,
                    "jornada": "Full time",
                    "salario": salario,
                    "categoria": "General",
                    "publicada": "",
                    "publicada_texto": "reciente",
                    "resumen": resumen,
                    "enlace": f"https://au.indeed.com/viewjob?jk={jk}",
                    "fuente": "Indeed",
                }
            )

    return ofertas


def buscar(
    keywords: str = "",
    where: str = "Melbourne VIC",
    paginas: int = 1,
    excluir: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Busca ofertas en Indeed Australia cumpliendo el contrato oficial."""
    patrones = EXCLUIR_POR_DEFECTO if excluir is None else tuple(excluir)
    parametros = urllib.parse.urlencode({"q": keywords, "l": where})
    url = f"https://au.indeed.com/jobs?{parametros}"

    # Paso 1: Petición con cookies de sesión si están presentes
    cookies = _cargar_cookies_sesion()
    status, html = _peticion_http(url, cookies)

    # Paso 2: Si 403 o bloqueado, y tenemos Edge, intentar headless
    if status == 403 or not html or "Just a moment..." in html or "Blocked" in html:
        edge = _obtener_edge_path()
        if edge:
            cmd = [edge, "--headless=new", "--disable-gpu", "--dump-dom", url]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20,
                )
                if proc.returncode == 0 and proc.stdout and "job" in proc.stdout.lower():
                    if "Just a moment" not in proc.stdout and "Blocked" not in proc.stdout:
                        html = proc.stdout
            except Exception:
                pass

    ofertas_crudas = _parsear_html_indeed(html, keywords, where) if html else []

    # Filtrar limpieza
    ofertas_validas: list[dict[str, Any]] = []
    excluidas: list[dict[str, str]] = []

    for of in ofertas_crudas:
        tit_lower = of["titulo"].lower()
        motivo = next((p for p in patrones if p and p.lower() in tit_lower), None)
        if motivo:
            excluidas.append({"titulo": of["titulo"], "motivo": motivo})
        else:
            ofertas_validas.append(of)

    aviso = ""
    if not ofertas_validas:
        if not cookies:
            aviso = "Indeed requiere sesión activa. Ejecuta 'python scripts/capturar_sesion_indeed.py' para autenticar."
        else:
            aviso = "Indeed no devolvió ofertas para estos filtros o renovó el desafío de Cloudflare."

    return {
        "fuente": "Indeed",
        "consulta": {
            "keywords": keywords,
            "where": where,
            "paginas": paginas,
        },
        "total_en_portal": len(ofertas_crudas),
        "devueltas": len(ofertas_validas),
        "excluidas_por_limpieza": excluidas,
        "ofertas": ofertas_validas,
        "aviso": aviso,
    }
