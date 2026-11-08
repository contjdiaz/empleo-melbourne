/* GET /api/health — tells the page whether the AI chat is configured, and whether the
 * access code in the x-access-code header is right. It returns no secrets. */
const { send, configured, codeOk } = require("./_lib");

module.exports = function handler(req, res) {
  send(res, 200, {
    ok: true,
    ai: configured(),
    memory: Boolean(process.env.MEMORY_STORE_ID),
    code_ok: configured() && codeOk(req.headers["x-access-code"]),
  });
};
