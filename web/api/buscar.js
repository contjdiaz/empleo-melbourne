/* Función serverless de Vercel.
 *
 * Modos:
 *   1. AGENT_API_URL definido  → reenvía la búsqueda al agente local
 *      (servidor/api.py) y devuelve sus resultados.
 *   2. Sin AGENT_API_URL       → responde con las ofertas reales de SEEK
 *      incluidas en data/demo-ofertas.json (modo demostración).
 *
 * Así el frontend es desplegable en Vercel sin claves y, al mismo tiempo,
 * puede hablar con el agente real cuando lo tengas corriendo.
 */

const demo = require("../data/demo-ofertas.json");

const LIMPIEZA = [
  "cleaner",
  "cleaning",
  "housekeep",
  "janitor",
  "limpieza",
  "domestic clean",
  "commercial clean",
  "window clean",
  "laundry attendant",
];

const JORNADAS = {
  fulltime: "full",
  parttime: "part",
  casual: "casual",
  contract: "contract",
};

const normalizar = (texto) =>
  String(texto || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

function filtrarDemo({ keywords = "", jornada = "fulltime" }) {
  const terminos = normalizar(keywords).split(/\s+/).filter(Boolean);
  const esperado = JORNADAS[jornada] || "";

  const excluidas = [];
  const ofertas = (demo.ofertas || []).filter((oferta) => {
    const titulo = normalizar(oferta.titulo);
    const motivo = LIMPIEZA.find((palabra) => titulo.includes(palabra));
    if (motivo) {
      excluidas.push({ titulo: oferta.titulo, motivo });
      return false;
    }
    if (esperado && !normalizar(oferta.jornada).includes(esperado)) return false;
    if (terminos.length) {
      const heno = normalizar(
        `${oferta.titulo} ${oferta.empresa} ${oferta.categoria} ${oferta.resumen}`
      );
      if (!terminos.every((termino) => heno.includes(termino))) return false;
    }
    return true;
  });

  return {
    modo: "demo",
    fuente: "SEEK",
    total_en_portal: demo.total,
    devueltas: ofertas.length,
    excluidas_por_limpieza: excluidas,
    ofertas,
    permite_ia: false,
    nota: demo.nota,
  };
}

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Cache-Control", "no-store");

  if (req.method === "OPTIONS") return res.status(204).end();

  if (req.method === "GET") {
    return res.status(200).json({
      ok: true,
      modo: process.env.AGENT_API_URL ? "local" : "demo",
      ofertas_en_demo: demo.total,
    });
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Método no permitido" });
  }

  const cuerpo = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
  const { keywords = "", jornada = "fulltime", paginas = 1, perfil = {} } = cuerpo;

  const base = (process.env.AGENT_API_URL || "").replace(/\/+$/, "");
  if (base) {
    try {
      const respuesta = await fetch(`${base}/buscar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keywords, jornada, paginas, perfil }),
        signal: AbortSignal.timeout(25000),
      });
      const datos = await respuesta.json();
      return res.status(respuesta.ok ? 200 : 502).json({
        ...datos,
        modo: datos.modo || "local",
      });
    } catch (error) {
      const respaldo = filtrarDemo({ keywords, jornada });
      return res.status(200).json({
        ...respaldo,
        permite_ia: false,
        aviso: `No pude conectar con el agente local (${error.message}); te muestro la demo.`,
      });
    }
  }

  return res.status(200).json(filtrarDemo({ keywords, jornada }));
};
