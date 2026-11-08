"""Cliente para Victorian Government Careers (careers.vic.gov.au).

Consulta vacantes del sector público del estado de Victoria (Melbourne)
sin credenciales ni dependencias adicionales.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://careers.vic.gov.au/jobs"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
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


def buscar(
    keywords: str = "",
    where: str = "Melbourne",
    paginas: int = 1,
    excluir: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    patrones = EXCLUIR_POR_DEFECTO if excluir is None else tuple(excluir)
    params = {"keyword": keywords}
    url = f"{API}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Referer": "https://careers.vic.gov.au/",
        },
    )

    ofertas: list[dict[str, Any]] = []
    excluidas: list[dict[str, str]] = []

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Bloques de resultado
        bloques = re.findall(
            r'<div class="job-searchResult-header">(.+?)(?=<div class="job-searchResult-header"|</div>\s*</rpl-content>|$)',
            html,
            re.DOTALL,
        )

        for bloque in bloques:
            m_link = re.search(r'href="(/job/[^"]+)"[^>]*><h3>([^<]+)</h3>', bloque)
            if not m_link:
                continue
            enlace = "https://careers.vic.gov.au" + m_link.group(1).strip()
            titulo = m_link.group(2).strip()

            m_dept = re.search(r'<p[^>]*class="[^"]*rpl-type-p-small[^"]*"[^>]*>([^<]+)</p>', bloque)
            empresa = m_dept.group(1).strip() if m_dept else "Victorian Government"

            m_sal = re.search(r'(\$[\d,]+\s*[-–]\s*\$[\d,]+)', bloque)
            salario = m_sal.group(1).strip() if m_sal else "Salario acorde a convenio del Gobierno de Victoria"

            tit_lower = titulo.lower()
            motivo = next((p for p in patrones if p and p.lower() in tit_lower), None)
            if motivo:
                excluidas.append({"titulo": titulo, "motivo": motivo})
                continue

            m_id = re.search(r'-(\d+)$', enlace)
            id_oferta = m_id.group(1) if m_id else str(abs(hash(enlace)))[:10]

            ofertas.append(
                {
                    "id": id_oferta,
                    "titulo": titulo,
                    "empresa": empresa,
                    "ubicacion": "Melbourne / Victoria",
                    "jornada": "Full time",
                    "salario": salario,
                    "categoria": "Gobierno de Victoria / Empleo público",
                    "publicada": "",
                    "publicada_texto": "reciente",
                    "resumen": f"Puesto en {empresa}. Estabilidad y beneficios del sector público del estado de Victoria.",
                    "enlace": enlace,
                    "fuente": "Victorian Government Careers",
                }
            )
    except Exception:
        pass

    return {
        "fuente": "Victorian Government Careers",
        "consulta": {"keywords": keywords, "where": where, "paginas": paginas},
        "total_en_portal": len(ofertas) + len(excluidas),
        "devueltas": len(ofertas),
        "excluidas_por_limpieza": excluidas,
        "ofertas": ofertas,
    }


if __name__ == "__main__":
    res = buscar("administration")
    print(f"Victorian Careers: {res['devueltas']} ofertas devueltas.")
    for o in res["ofertas"][:3]:
        print(f" - {o['titulo']} ({o['empresa']}) -> {o['enlace']}")
