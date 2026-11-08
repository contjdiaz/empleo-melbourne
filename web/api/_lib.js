/* Shared helpers for the Vercel functions. Files that start with "_" are not routes.
 *
 * Environment variables (Vercel → Settings → Environment Variables):
 *   ANTHROPIC_API_KEY   API key of the workspace that owns the agent (never sent to the browser)
 *   AGENT_ID            agent_...     from claude-lock.json
 *   ENVIRONMENT_ID      env_...       from claude-lock.json
 *   MEMORY_STORE_ID     memstore_...  from claude-lock.json (optional: without it, no NEW/SEEN)
 *   ACCESS_CODE         the code your sister types once; without it the AI chat stays off
 *   SESSION_BUDGET_CENTS optional, default "120" (USD 1.20 per conversation)
 */

const crypto = require("crypto");

// ANTHROPIC_BASE_URL only for local tests (scripts/dev-proxy.py); production uses the default.
const API = `${(process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com").replace(/\/+$/, "")}/v1`;
const HEADERS = {
  "anthropic-version": "2026-10-21",
  "anthropic-beta": "managed-agents-2026-04-01",
  "content-type": "application/json",
};

const BUDGET_CENTS = String(process.env.SESSION_BUDGET_CENTS || "120");
const MAX_TEXT = 2000;

function configured() {
  return Boolean(
    process.env.ANTHROPIC_API_KEY && process.env.AGENT_ID && process.env.ENVIRONMENT_ID && process.env.ACCESS_CODE
  );
}

function send(res, status, body) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.status(status).send(JSON.stringify(body));
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try {
    return JSON.parse(req.body || "{}");
  } catch {
    return {};
  }
}

/* Constant-time compare, so the code cannot be guessed byte by byte from response times. */
function codeOk(given) {
  const expected = process.env.ACCESS_CODE || "";
  const a = Buffer.from(String(given || ""));
  const b = Buffer.from(expected);
  return expected.length > 0 && a.length === b.length && crypto.timingSafeEqual(a, b);
}

function checkAccess(req, res) {
  if (!configured()) {
    send(res, 503, { error: "not_configured" });
    return false;
  }
  const given = req.headers["x-access-code"] || readBody(req).code;
  if (!codeOk(given)) {
    send(res, 401, { error: "bad_code" });
    return false;
  }
  return true;
}

async function anthropic(path, { method = "GET", body } = {}) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: { ...HEADERS, "x-api-key": process.env.ANTHROPIC_API_KEY },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(20000),
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!response.ok) {
    const message = (data.error && data.error.message) || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function clip(value, max) {
  return String(value == null ? "" : value).replace(/\s+/g, " ").trim().slice(0, max);
}

module.exports = { anthropic, send, readBody, checkAccess, configured, codeOk, clip, BUDGET_CENTS, MAX_TEXT };
