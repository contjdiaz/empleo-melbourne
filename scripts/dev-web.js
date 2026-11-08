/* Local stand-in for Vercel: serves web/ and runs web/api/*.js with the same req/res shape.
 *
 *   ACCESS_CODE=test AGENT_ID=... ENVIRONMENT_ID=... MEMORY_STORE_ID=... ANTHROPIC_API_KEY=local \
 *   ANTHROPIC_BASE_URL=http://127.0.0.1:8788 node scripts/dev-web.js
 * Then open http://127.0.0.1:3000
 */
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "web");
const PORT = Number(process.env.PORT || 3000);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json" };

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname.startsWith("/api/")) {
    const name = url.pathname.slice(5).replace(/[^a-z]/g, "");
    const file = path.join(ROOT, "api", `${name}.js`);
    if (!name || name.startsWith("_") || !fs.existsSync(file)) {
      res.writeHead(404).end("not found");
      return;
    }
    let raw = "";
    for await (const chunk of req) raw += chunk;
    req.body = raw ? (() => { try { return JSON.parse(raw); } catch { return raw; } })() : {};
    req.query = Object.fromEntries(url.searchParams);
    res.status = (code) => { res.statusCode = code; return res; };
    res.send = (body) => res.end(body);
    res.json = (obj) => { res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(obj)); };
    try {
      await require(file)(req, res);
    } catch (error) {
      res.statusCode = 500;
      res.end(String(error.stack || error));
    }
    return;
  }
  const rel = url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname).replace(/^\/+/, "");
  const file = path.resolve(ROOT, rel);
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end("not found");
    return;
  }
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
}).listen(PORT, "127.0.0.1", () => console.log(`dev web on http://127.0.0.1:${PORT}`));
