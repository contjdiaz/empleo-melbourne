/* POST /api/chat — start a conversation (one Managed Agents Session) or continue it.
 *
 * Body: { text, lang: "en"|"es", profile: {...}, session_id?: "sesn_..." }
 * Header: x-access-code
 *
 * New conversation → creates a Session with a USD budget and the first message.
 * Follow-up        → sends one user.message to the same Session.
 * Returns { session_id, since } — "since" is the time to poll /api/events from.
 */

const { anthropic, send, readBody, checkAccess, clip, BUDGET_CENTS, MAX_TEXT } = require("./_lib");

const PROFILE_FIELDS = [
  ["visa", "visa"],
  ["derecho_a_trabajar", "right to work"],
  ["horas_disponibles", "hours available per week"],
  ["disponibilidad", "availability"],
  ["certificaciones", "certifications"],
  ["nivel_de_ingles", "English level"],
  ["experiencia", "experience"],
  ["salario_minimo", "minimum pay"],
  ["zona", "suburb or area"],
  ["viaje_maximo_minutos", "max travel (minutes)"],
];

function profileBlock(profile) {
  const lines = PROFILE_FIELDS.map(([key, label]) => {
    const value = clip(profile && profile[key], 200);
    return `- ${label}: ${value || "not set"}`;
  });
  return `Profile (from the profile form):\n${lines.join("\n")}`;
}

function language(lang) {
  return lang === "es" ? "Spanish" : "English";
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return send(res, 405, { error: "method_not_allowed" });
  if (!checkAccess(req, res)) return;

  const body = readBody(req);
  const text = String(body.text || "").trim().slice(0, MAX_TEXT);
  if (!text) return send(res, 400, { error: "empty_message" });

  const since = new Date(Date.now() - 1000).toISOString();
  const head = `Reply language: ${language(body.lang)}\n\nRequest: ${text}`;

  try {
    if (body.session_id) {
      const sessionId = String(body.session_id);
      if (!/^sesn_[A-Za-z0-9]+$/.test(sessionId)) return send(res, 400, { error: "bad_session" });
      await anthropic(`/sessions/${sessionId}/events`, {
        method: "POST",
        body: { events: [{ type: "user.message", content: [{ type: "text", text: head }] }] },
      });
      return send(res, 200, { session_id: sessionId, since });
    }

    const resources = [];
    if (process.env.MEMORY_STORE_ID) {
      resources.push({
        type: "memory_store",
        memory_store_id: process.env.MEMORY_STORE_ID,
        access: "read_write",
      });
    }
    const session = await anthropic("/sessions", {
      method: "POST",
      body: {
        agent: process.env.AGENT_ID,
        environment_id: process.env.ENVIRONMENT_ID,
        title: `Web chat: ${clip(text, 60)}`,
        budget: { type: "limit", max_list_cost: { amount: BUDGET_CENTS, currency: "USD" } },
        resources,
        initial_events: [
          {
            type: "user.message",
            content: [{ type: "text", text: `${head}\n\n${profileBlock(body.profile || {})}` }],
          },
        ],
      },
    });
    return send(res, 200, { session_id: session.id, since });
  } catch (error) {
    // A session at its budget rejects nothing, but it will not run: the events endpoint reports it.
    return send(res, error.status === 404 ? 404 : 502, { error: "agent_error", detail: error.message });
  }
};
