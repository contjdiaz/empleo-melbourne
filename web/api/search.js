/* POST /api/search — quick search on SEEK, without the AI model. Cost: USD 0.
 *
 * Body: { keywords, type: "fulltime"|"parttime"|"casual"|"contract"|"any", where? }
 * If SEEK does not answer from Vercel, it returns the bundled demo jobs with a notice.
 */

const demo = require("../data/demo-ofertas.json");
const { send, readBody, clip } = require("./_lib");

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36";
const SEEK_TYPES = { fulltime: "242", parttime: "243", contract: "244", casual: "245" };
const CLEANING = [
  "cleaner", "cleaning", "housekeep", "janitor", "limpieza",
  "domestic clean", "commercial clean", "window clean", "laundry attendant",
];
const NS = "not specified";

const norm = (text) =>
  String(text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const isCleaning = (title) => CLEANING.some((word) => norm(title).includes(word));
const label = (value) => (value && typeof value === "object" ? value.label || value.text || "" : String(value || ""));

async function seek({ keywords, type, where }) {
  const params = new URLSearchParams({
    siteKey: "AU-Main",
    where: where || "Melbourne VIC",
    page: "1",
    pagesize: "30",
    sortmode: "ListedDate",
  });
  if (keywords) params.set("keywords", keywords);
  if (SEEK_TYPES[type]) params.set("worktype", SEEK_TYPES[type]);

  const response = await fetch(`https://au.seek.com/api/jobsearch/v5/search?${params}`, {
    headers: {
      "User-Agent": UA,
      Accept: "application/json, text/plain, */*",
      "Accept-Language": "en-AU,en;q=0.9",
      Referer: "https://au.seek.com/",
    },
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) throw new Error(`SEEK HTTP ${response.status}`);
  const data = await response.json();

  let excluded = 0;
  const jobs = [];
  for (const job of data.data || []) {
    if (!job.id) continue;
    if (isCleaning(job.title)) {
      excluded += 1;
      continue;
    }
    jobs.push({
      title: clip(job.title, 160),
      company: clip(job.companyName, 120) || NS,
      location: (job.locations || []).map(label).filter(Boolean).join(", ") || NS,
      work_type: (job.workTypes || []).map(label).filter(Boolean).join(", ") || NS,
      salary: clip(job.salaryLabel, 120) || NS,
      posted: clip(job.listingDateDisplay, 40) || NS,
      summary: clip(job.teaser, 240),
      url: `https://www.seek.com.au/job/${job.id}`,
      source: "SEEK",
    });
  }
  return { mode: "live", total: Number(data.totalCount || 0), excluded, jobs };
}

function fromDemo({ keywords, type }) {
  const terms = norm(keywords).split(/\s+/).filter(Boolean);
  const wanted = { fulltime: "full", parttime: "part", casual: "casual", contract: "contract" }[type] || "";
  let excluded = 0;
  const jobs = [];
  for (const job of demo.ofertas || []) {
    if (isCleaning(job.titulo)) {
      excluded += 1;
      continue;
    }
    if (wanted && !norm(job.jornada).includes(wanted)) continue;
    const hay = norm(`${job.titulo} ${job.empresa} ${job.categoria} ${job.resumen}`);
    if (terms.length && !terms.every((term) => hay.includes(term))) continue;
    jobs.push({
      title: job.titulo,
      company: job.empresa || NS,
      location: job.ubicacion || NS,
      work_type: job.jornada || NS,
      salary: job.salario && !/no especificado/i.test(job.salario) ? job.salario : NS,
      posted: job.publicada_texto || NS,
      summary: job.resumen || "",
      url: job.enlace,
      source: "SEEK",
    });
  }
  return { mode: "demo", total: demo.total, excluded, jobs, generated: demo.generado };
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return send(res, 405, { error: "method_not_allowed" });
  const body = readBody(req);
  const query = {
    keywords: clip(body.keywords, 100),
    type: ["fulltime", "parttime", "casual", "contract", "any"].includes(body.type) ? body.type : "fulltime",
    where: clip(body.where, 60),
  };
  try {
    return send(res, 200, await seek(query));
  } catch (error) {
    return send(res, 200, { ...fromDemo(query), notice: error.message });
  }
};
