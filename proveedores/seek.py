"""Cliente de SEEK (Australia) sin dependencias externas.

Usa el mismo endpoint JSON que consume el buscador de au.seek.com. No necesita
clave, cookies ni navegador. Se apoya en la biblioteca estándar para que el
agente no tenga que instalar nada más.

Uso directo (sin LLM, útil para probar):

    python -m proveedores.seek "warehouse" --jornada fulltime --paginas 2

Aviso: es un endpoint público del sitio, no una API documentada. Puede cambiar
sin aviso. Si SEEK empieza a responder 403, hay que regenerar el cliente con
`reverse-api-engineer` (ver adaptadores/README.md) o usar un navegador.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://au.seek.com/api/jobsearch/v5/search"

# Sin User-Agent de navegador el endpoint responde 403.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)

# Códigos de jornada que entiende el endpoint (verificados el 2026-11-07).
JORNADAS = {
    "fulltime": "242",   # Full time
    "parttime": "243",   # Part time
    "contract": "244",   # Contract/Temp
    "casual": "245",     # Casual/Vacation
}

# Se comparan en minúsculas contra el título y la descripción corta.
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


def _pedir(url: str, timeout: int = 25, intentos: int = 2) -> dict[str, Any]:
    """GET con reintentos. Devuelve el JSON o lanza RuntimeError explicable."""
    ultimo_error = ""
    for intento in range(intentos):
        peticion = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-AU,en;q=0.9",
                "Referer": "https://au.seek.com/",
            },
        )
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            ultimo_error = f"HTTP {error.code}"
            if error.code in (429, 500, 502, 503):
                time.sleep(1.5 * (intento + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError) as error:
            ultimo_error = f"red: {error}"
            time.sleep(1.0 * (intento + 1))
        except json.JSONDecodeError:
            ultimo_error = "la respuesta no fue JSON"
            break
    raise RuntimeError(f"SEEK no respondió ({ultimo_error})")


def _texto(valor: Any) -> str:
    if isinstance(valor, dict):
        return str(valor.get("text") or valor.get("label") or "")
    return str(valor or "")


def _normalizar(oferta: dict[str, Any]) -> dict[str, Any]:
    ubicaciones = [str(u.get("label", "")) for u in oferta.get("locations") or []]
    jornadas = [_texto(x) for x in oferta.get("workTypes") or []]
    clasificaciones = [
        c.get("classification", {}).get("description", "")
        for c in oferta.get("classifications") or []
    ]
    return {
        "id": str(oferta.get("id", "")),
        "titulo": str(oferta.get("title", "")).strip(),
        "empresa": str(oferta.get("companyName") or "no especificada").strip(),
        "ubicacion": ", ".join(u for u in ubicaciones if u) or "no especificada",
        "jornada": ", ".join(j for j in jornadas if j) or "no especificada",
        "salario": str(oferta.get("salaryLabel") or "").strip() or "no especificado",
        "categoria": ", ".join(c for c in clasificaciones if c) or "no especificada",
        "publicada": str(oferta.get("listingDate", "")),
        "publicada_texto": str(oferta.get("listingDateDisplay", "")),
        "resumen": str(oferta.get("teaser", "")).strip(),
        "enlace": f"https://www.seek.com.au/job/{oferta.get('id', '')}",
        "fuente": "SEEK",
    }


def _coincide_exclusion(oferta: dict[str, Any], patrones: tuple[str, ...]) -> str | None:
    # Solo el título: buscar en el resumen descarta puestos de oficina que
    # mencionan «cleaning» de pasada (p. ej. «Office Manager ... cleaning rota»).
    titulo = oferta["titulo"].lower()
    for patron in patrones:
        if patron and patron.lower() in titulo:
            return patron
    return None


def buscar(
    keywords: str = "",
    where: str = "Melbourne VIC",
    jornada: str = "cualquiera",
    paginas: int = 1,
    pagesize: int = 50,
    excluir: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Busca ofertas en SEEK y devuelve un dict listo para el agente.

    jornada: fulltime | parttime | contract | casual | cualquiera
    Las ofertas de limpieza se descartan por defecto y se informan aparte, para
    que el agente pueda decir cuántas filtró sin volver a leerlas.
    """
    patrones = EXCLUIR_POR_DEFECTO if excluir is None else tuple(excluir)
    trabajo = JORNADAS.get(jornada.strip().lower())
    if jornada and jornada.lower() not in JORNADAS and jornada.lower() != "cualquiera":
        raise ValueError(
            f"jornada «{jornada}» no válida; usa fulltime, parttime, contract, casual o cualquiera"
        )

    paginas = max(1, min(int(paginas or 1), 5))
    pagesize = max(1, min(int(pagesize or 50), 100))

    ofertas: list[dict[str, Any]] = []
    excluidas: list[dict[str, str]] = []
    vistos: set[str] = set()
    total = 0

    for pagina in range(1, paginas + 1):
        parametros = {
            "siteKey": "AU-Main",
            "where": where,
            "page": str(pagina),
            "pagesize": str(pagesize),
            "sortmode": "ListedDate",
        }
        if keywords.strip():
            parametros["keywords"] = keywords.strip()
        if trabajo:
            parametros["worktype"] = trabajo

        datos = _pedir(f"{API}?{urllib.parse.urlencode(parametros)}")
        total = int(datos.get("totalCount") or 0)
        lote = datos.get("data") or []
        if not lote:
            break

        for cruda in lote:
            oferta = _normalizar(cruda)
            if not oferta["id"] or oferta["id"] in vistos:
                continue
            vistos.add(oferta["id"])
            motivo = _coincide_exclusion(oferta, patrones)
            if motivo:
                excluidas.append(
                    {"titulo": oferta["titulo"], "empresa": oferta["empresa"], "motivo": motivo}
                )
            else:
                ofertas.append(oferta)

    return {
        "fuente": "SEEK",
        "consulta": {
            "keywords": keywords,
            "where": where,
            "jornada": jornada or "cualquiera",
            "paginas": paginas,
        },
        "total_en_portal": total,
        "devueltas": len(ofertas),
        "excluidas_por_limpieza": excluidas,
        "ofertas": ofertas,
    }


if __name__ == "__main__":
    import argparse

    analizador = argparse.ArgumentParser(description="Prueba el cliente de SEEK")
    analizador.add_argument("keywords", nargs="?", default="")
    analizador.add_argument("--where", default="Melbourne VIC")
    analizador.add_argument("--jornada", default="fulltime")
    analizador.add_argument("--paginas", type=int, default=1)
    argumentos = analizador.parse_args()

    resultado = buscar(
        keywords=argumentos.keywords,
        where=argumentos.where,
        jornada=argumentos.jornada,
        paginas=argumentos.paginas,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
