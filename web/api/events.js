/* GET /api/events?session=sesn_...&after=<ISO time>
 * Header: x-access-code
 *
 * The browser polls this every ~2 s while the agent works. It returns only what the
 * chat needs: progress steps, the agent's answers, the state of the Session and its cost.
 *
 * If the server's "auto" permission check pauses a call for approval (requires_action),
 * nobody is there to approve it, so this endpoint denies it with a short reason. The agent
 * then continues without that call, and the chat never hangs.
 */

const { anthropic, send, checkAccess } = require("./_lib");

const TYPES = [
  "user.message",
  "agent.message",
  "agent.tool_use",
  "session.status_running",
  "session.status_idle",
  "session.error",
  "session.usage",
];

function textOf(content) {
  return (content || [])
    .filter((block) => block && block.type === "text")
    .map((block) => block.text)
    .join("");
}

/* Turn a tool call into a progress step the person can understand. */
function step(event) {
  const input = event.input || {};
  if (event.name === "bash") {
    const command = String(input.command || "");
    if (command.includes("search.py search")) {
      const keywords = [...command.matchAll(/-k\s+"([^"]+)"/g)].map((m) => m[1]);
      const sources = (command.match(/--sources\s+([a-z,]+)/) || [])[1] || "seek,linkedin,vic,ethical";
      return { kind: "search", keywords, sources: sources.split(",") };
    }
    if (command.includes("search.py remember")) return { kind: "remember" };
    if (command.trim().startsWith("date")) return { kind: "date" };
    return { kind: "work" };
  }
  if (event.name === "web_fetch") {
    let host = "";
    try {
      host = new URL(String(input.url || "")).hostname;
    } catch {
      host = "";
    }
    return { kind: "fetch", host };
  }
  if (event.name === "read" && String(input.file_path || "").endsWith("SKILL.md")) return { kind: "skill" };
  return { kind: "work" };
}

async function listEvents(sessionId, after) {
  const params = new URLSearchParams({ limit: "100", order: "asc" });
  TYPES.forEach((type) => params.append("types[]", type));
  if (after) params.append("created_at[gte]", after);
  const all = [];
  let page = null;
  for (let i = 0; i < 5; i += 1) {
    if (page) params.set("page", page);
    const data = await anthropic(`/sessions/${sessionId}/events?${params.toString()}`);
    all.push(...(data.data || []));
    page = data.next_page;
    if (!page) break;
  }
  return all;
}

module.exports = async function handler(req, res) {
  if (req.method !== "GET") return send(res, 405, { error: "method_not_allowed" });
  if (!checkAccess(req, res)) return;

  const sessionId = String(req.query.session || "");
  if (!/^sesn_[A-Za-z0-9]+$/.test(sessionId)) return send(res, 400, { error: "bad_session" });
  const after = req.query.after ? String(req.query.after) : "";

  try {
    const [events, session] = await Promise.all([
      listEvents(sessionId, after),
      anthropic(`/sessions/${sessionId}`),
    ]);

    const out = [];
    let cursor = after;
    let lastIdle = null;
    const pendingAsk = [];

    for (const event of events) {
      if (event.processed_at) cursor = event.processed_at;
      switch (event.type) {
        case "user.message":
          out.push({ id: event.id, type: "user", text: textOf(event.content), at: event.processed_at });
          break;
        case "agent.message":
          out.push({ id: event.id, type: "agent", text: textOf(event.content), at: event.processed_at });
          break;
        case "agent.tool_use":
          if (event.evaluated_permission === "ask") pendingAsk.push(event.id);
          out.push({ id: event.id, type: "step", ...step(event), denied: event.evaluated_permission === "deny" });
          break;
        case "session.status_running":
          out.push({ id: event.id, type: "running" });
          break;
        case "session.status_idle":
          lastIdle = event.stop_reason || {};
          out.push({ id: event.id, type: "idle", reason: lastIdle.type || "end_turn" });
          break;
        case "session.error":
          out.push({ id: event.id, type: "error", text: (event.error && event.error.message) || "The agent had an error." });
          break;
        default:
          break;
      }
    }

    // Answer a paused permission check, so an unattended call never blocks the chat.
    if (lastIdle && lastIdle.type === "requires_action") {
      const ids = (lastIdle.event_ids || []).filter((id) => pendingAsk.includes(id) || pendingAsk.length === 0);
      if (ids.length) {
        await anthropic(`/sessions/${sessionId}/events`, {
          method: "POST",
          body: {
            events: ids.map((id) => ({
              type: "user.tool_confirmation",
              tool_use_id: id,
              result: "deny",
              deny_message:
                "Nobody can approve this call in the web chat. Continue without it, or tell the user what you could not do.",
            })),
          },
        }).catch(() => {});
      }
    }

    const usage = session.usage || {};
    const budget = (session.budget && session.budget.max_list_cost) || {};
    return send(res, 200, {
      status: session.status,
      events: out,
      cursor,
      cost_cents: Number((usage.list_cost && usage.list_cost.amount) || 0),
      budget_cents: Number(budget.amount || 0),
    });
  } catch (error) {
    return send(res, error.status === 404 ? 404 : 502, { error: "agent_error", detail: error.message });
  }
};
