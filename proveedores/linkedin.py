"""Cliente de LinkedIn Jobs sin credenciales ni navegador.

Consume el endpoint público de búsqueda para invitados de LinkedIn:
    https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

No requiere sesión, cookies ni JavaScript.
Devuelve ofertas normalizadas con el mismo formato que proveedores.seek.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)

# Mapeo de jornadas a filtros de LinkedIn
JORNADAS_LINKEDIN = {
    "fulltime": "F",   # Full-time
    "parttime": "P",   # Part-time
    "contract": "C",   # Contract
    "casual": "T",     # Temporary
}

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


def _pedir_html(url: str, timeout: int = 15, intentos: int = 2) -> str:
    ultimo_error = ""
    for intento in range(intentos):
        peticion = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-AU,en;q=0.9",
                "Referer": "https://www.linkedin.com/jobs",
            },
        )
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            ultimo_error = f"HTTP {error.code}"
            if error.code in (429, 500, 502, 503):
                time.sleep(1.5 * (intento + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError) as error:
            ultimo_error = f"red: {error}"
            time.sleep(1.0 * (intento + 1))
    raise RuntimeError(f"LinkedIn no respondió ({ultimo_error})")


def _extraer_ofertas(html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    bloques = re.findall(r'<li[^>]*>(.+?)</li>', html, re.DOTALL)
    for bloque in bloques:
        m_link = re.search(r'base-card__full-link[^>]*href="([^"]+)"', bloque)
        m_tit = re.search(r'base-search-card__title[^>]*>[\s\r\n]*([^<]+)', bloque)
        if not m_link or not m_tit:
            continue

        enlace_crudo = m_link.group(1).strip()
        enlace = enlace_crudo.split("?")[0]
        titulo = m_tit.group(1).strip()

        m_emp = re.search(r'base-search-card__subtitle[^>]*>[\s\r\n]*(?:<a[^>]*>)?[\s\r\n]*([^<\n\r]+)', bloque)
        empresa = m_emp.group(1).strip() if m_emp else "no especificada"

        m_ubi = re.search(r'job-search-card__location[^>]*>[\s\r\n]*([^<\n\r]+)', bloque)
        ubicacion = m_ubi.group(1).strip() if m_ubi else "Melbourne, VIC"

        m_tiempo = re.search(r'<time[^>]*datetime="([^"]*)"[^>]*>[\s\r\n]*([^<]+)', bloque)
        publicada_iso = m_tiempo.group(1).strip() if m_tiempo else ""
        publicada_texto = m_tiempo.group(2).strip() if m_tiempo else "reciente"

        # Extraer ID numérico si existe
        m_id = re.search(r'-(\d+)(?:\?|$)', enlace)
        id_oferta = m_id.group(1) if m_id else str(abs(hash(enlace)))[:10]

        items.append(
            {
                "id": id_oferta,
                "titulo": titulo,
                "empresa": empresa,
                "ubicacion": ubicacion,
                "jornada": "Full time",
                "salario": "no especificado",
                "categoria": "Atención al cliente / Oficina",
                "publicada": publicada_iso,
                "publicada_texto": publicada_texto,
                "resumen": f"Vacante en {empresa} ubicada en {ubicacion}.",
                "enlace": enlace,
                "fuente": "LinkedIn",
            }
        )
    return items


def buscar(
    keywords: str = "",
    where: str = "Melbourne, Victoria, Australia",
    jornada: str = "fulltime",
    paginas: int = 1,
    excluir: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Busca ofertas en LinkedIn y las devuelve con la misma firma de SEEK."""
    patrones = EXCLUIR_POR_DEFECTO if excluir is None else tuple(excluir)
    paginas = max(1, min(int(paginas or 1), 3))

    ofertas: list[dict[str, Any]] = []
    excluidas: list[dict[str, str]] = []
    vistos_enlaces: set[str] = set()

    codigo_jornada = JORNADAS_LINKEDIN.get(jornada.strip().lower(), "")

    for pagina in range(paginas):
        params: dict[str, Any] = {
            "keywords": keywords,
            "location": where,
            "start": pagina * 25,
        }
        if codigo_jornada:
            params["f_JT"] = codigo_jornada

        url = f"{API}?{urllib.parse.urlencode(params)}"
        try:
            html = _pedir_html(url)
            encontradas = _extraer_ofertas(html)
            if not encontradas:
                break
            for of in encontradas:
                if of["enlace"] in vistos_enlaces:
                    continue
                vistos_enlaces.add(of["enlace"])

                tit_lower = of["titulo"].lower()
                motivo = next((p for p in patrones if p and p.lower() in tit_lower), None)
                if motivo:
                    excluidas.append({"titulo": of["titulo"], "motivo": motivo})
                else:
                    ofertas.append(of)
        except Exception:
            break

    return {
        "fuente": "LinkedIn",
        "consulta": {
            "keywords": keywords,
            "where": where,
            "jornada": jornada,
            "paginas": paginas,
        },
        "total_en_portal": len(ofertas) + len(excluidas),
        "devueltas": len(ofertas),
        "excluidas_por_limpieza": excluidas,
        "ofertas": ofertas,
    }


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "customer service"
    res = buscar(kw)
    print(f"LinkedIn: {res['devueltas']} ofertas devueltas, {len(res['excluidas_por_limpieza'])} excluidas.")
    for o in res["ofertas"][:3]:
        print(f" - {o['titulo']} ({o['empresa']}) -> {o['enlace']}")
