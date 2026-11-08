/* Melbourne Jobs — front end. No dependencies.
 *
 * Talks to three Vercel functions:
 *   POST /api/chat    start a chat (a Managed Agents Session) or send a follow-up
 *   GET  /api/events  poll progress, answers, state and cost of the Session
 *   POST /api/search  free quick search on SEEK (no AI)
 */
(() => {
  "use strict";

  const KEYS = {
    lang: "mj:lang",
    profile: "melbourne-empleo:perfil:v1", // same key as before, so a saved profile survives
    code: "mj:code",
    session: "mj:session",
    saved: "mj:saved",
  };
  const PROFILE_FIELDS = [
    "visa", "derecho_a_trabajar", "horas_disponibles", "disponibilidad", "zona",
    "viaje_maximo_minutos", "certificaciones", "nivel_de_ingles", "experiencia", "salario_minimo",
  ];
  const IMPORTANT = ["visa", "derecho_a_trabajar", "horas_disponibles", "experiencia"];
  const POLL_MS = 1800;
  const POLL_LIMIT_MS = 5 * 60 * 1000;

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const store = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw == null ? fallback : JSON.parse(raw);
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        if (value == null) localStorage.removeItem(key);
        else localStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* private mode: keep going in memory */
      }
    },
  };

  const state = {
    lang: store.get(KEYS.lang, "en") === "es" ? "es" : "en",
    profile: { nivel_de_ingles: "intermediate", ...store.get(KEYS.profile, {}) },
    code: store.get(KEYS.code, ""),
    saved: store.get(KEYS.saved, []),
    ai: false,
    chat: null, // { id, cursor, seenIds:Set, busy, pending, startedAt }
    pollTimer: null,
  };

  /* ── i18n ─────────────────────────────────────────────────────── */

  function t(key, vars) {
    const dict = window.I18N[state.lang] || window.I18N.en;
    let text = dict[key] != null ? dict[key] : window.I18N.en[key] != null ? window.I18N.en[key] : key;
    Object.entries(vars || {}).forEach(([k, v]) => {
      text = text.split(`{${k}}`).join(String(v));
    });
    return text;
  }

  function applyLang() {
    document.documentElement.lang = state.lang;
    $$("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    $$("[data-i18n-placeholder]").forEach((node) => {
      node.placeholder = t(node.dataset.i18nPlaceholder);
    });
    $$(".lang [data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === state.lang)));
    renderSuggestions();
    renderQuickChips();
    renderProfileSummary();
    renderSaved();
    renderMeter();
  }

  /* ── Small helpers ───────────────────────────────────────────── */

  function esc(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function safeUrl(url) {
    try {
      const u = new URL(String(url));
      return u.protocol === "https:" || u.protocol === "http:" ? u.href : "#";
    } catch {
      return "#";
    }
  }

  function isEmpty(value) {
    const v = String(value || "").trim().toLowerCase();
    return !v || v === "completar" || v === "not set" || v === "no especificado" || v === "pendiente";
  }

  function ns(value) {
    return isEmpty(value) || /^not specified$/i.test(String(value)) ? t("card.ns") : value;
  }

  function toast(message) {
    const node = $("#toast");
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => (node.hidden = true), 3000);
  }

  async function api(path, { method = "GET", body } = {}) {
    const response = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "x-access-code": state.code || "" },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (!response.ok) {
      const error = new Error(data.detail || data.error || `HTTP ${response.status}`);
      error.status = response.status;
      error.code = data.error;
      throw error;
    }
    return data;
  }

  /* Minimal, safe Markdown: paragraphs, lists, bold, links. */
  function markdown(text) {
    const inline = (s) =>
      esc(s)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (m, label, url) =>
          `<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${label}</a>`)
        .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, (m, pre, url) =>
          `${pre}<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${url}</a>`);
    const out = [];
    let list = null;
    const close = () => {
      if (list) out.push(`</${list}>`);
      list = null;
    };
    String(text).split(/\r?\n/).forEach((line) => {
      const l = line.trim();
      if (!l) return close();
      const bullet = l.match(/^[-*•]\s+(.*)$/);
      const number = l.match(/^\d+[.)]\s+(.*)$/);
      const heading = l.match(/^#{1,4}\s+(.*)$/);
      if (bullet || number) {
        const kind = bullet ? "ul" : "ol";
        if (list !== kind) {
          close();
          out.push(`<${kind}>`);
          list = kind;
        }
        out.push(`<li>${inline((bullet || number)[1])}</li>`);
      } else if (heading) {
        close();
        out.push(`<h4>${inline(heading[1])}</h4>`);
      } else {
        close();
        out.push(`<p>${inline(l)}</p>`);
      }
    });
    close();
    return out.join("");
  }

  /* Split an agent message into text parts and ```jobs blocks. */
  function parseAgent(text) {
    const parts = [];
    const re = /```jobs\s*([\s\S]*?)```/g;
    let last = 0;
    let match;
    while ((match = re.exec(text))) {
      if (match.index > last) parts.push({ kind: "text", text: text.slice(last, match.index) });
      try {
        const jobs = JSON.parse(match[1]);
        parts.push({ kind: "jobs", jobs: Array.isArray(jobs) ? jobs : [] });
      } catch {
        parts.push({ kind: "text", text: match[0] });
      }
      last = re.lastIndex;
    }
    if (last < text.length) parts.push({ kind: "text", text: text.slice(last) });
    return parts;
  }

  /* ── Job cards (chat, quick search, saved) ───────────────────── */

  function isSaved(url) {
    return state.saved.some((job) => job.url === url);
  }

  function toggleSaved(job) {
    if (isSaved(job.url)) {
      state.saved = state.saved.filter((j) => j.url !== job.url);
      toast(t("saved.removed"));
    } else {
      state.saved = [{ ...job, saved_at: new Date().toISOString() }, ...state.saved].slice(0, 100);
      toast(t("saved.added"));
    }
    store.set(KEYS.saved, state.saved);
    $$(`[data-save-url="${CSS.escape(job.url)}"]`).forEach((b) => paintSave(b, job.url));
    renderSaved();
  }

  function paintSave(button, url) {
    const on = isSaved(url);
    button.setAttribute("aria-pressed", String(on));
    button.innerHTML = `<span aria-hidden="true">${on ? "♥" : "♡"}</span> ${esc(on ? t("card.saved") : t("card.save"))}`;
  }

  function workLabel(value) {
    const v = String(value || "").toLowerCase();
    if (v.includes("full")) return { text: t("type.fulltime"), cls: "full" };
    if (v.includes("part")) return { text: t("type.parttime"), cls: "part" };
    if (v.includes("casual")) return { text: t("type.casual"), cls: "part" };
    if (v.includes("contract")) return { text: t("type.contract"), cls: "part" };
    return null;
  }

  function card(job, { askable = false } = {}) {
    const el = document.createElement("article");
    el.className = "card";
    const url = safeUrl(job.url);
    const work = workLabel(job.work_type);
    const status = job.status === "new" ? `<span class="badge new">${esc(t("card.new"))}</span>`
      : job.status === "seen" ? `<span class="badge seen">${esc(t("card.seen"))}</span>` : "";
    el.innerHTML = `
      <div class="card-top">
        ${status}
        ${work ? `<span class="badge ${work.cls}">${esc(work.text)}</span>` : ""}
        <span class="badge src">${esc(job.source || "")}</span>
        <span class="card-date">${esc(isEmpty(job.posted) || /not specified/i.test(job.posted) ? "" : job.posted)}</span>
      </div>
      <h3><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(job.title)}</a></h3>
      <p class="company">${esc(ns(job.company))}</p>
      <ul class="details">
        <li><span aria-hidden="true">📍</span>${esc(ns(job.location))}</li>
        <li><span aria-hidden="true">💰</span>${esc(ns(job.salary))}</li>
      </ul>
      ${job.fit ? `<p class="fit">${esc(job.fit)}</p>` : job.summary ? `<p class="summary-text">${esc(job.summary)}</p>` : ""}
      ${job.check ? `<p class="check"><b>${esc(t("card.check"))}:</b> ${esc(job.check)}</p>` : ""}
      <div class="card-foot">
        <button type="button" class="btn btn-mini save" data-save-url="${esc(job.url)}"></button>
        ${askable ? `<button type="button" class="btn btn-mini ghost ask">${esc(t("chat.askAboutBtn"))}</button>` : ""}
        <a class="view" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(t("card.view"))} ↗</a>
      </div>`;
    const save = el.querySelector(".save");
    paintSave(save, job.url);
    save.addEventListener("click", () => toggleSaved(job));
    const ask = el.querySelector(".ask");
    if (ask) {
      ask.addEventListener("click", () => {
        $("#prompt").value = t("chat.askAbout", { title: job.title, company: ns(job.company), url: job.url });
        autosize();
        $("#assistant").scrollIntoView({ behavior: "smooth" });
        $("#prompt").focus();
      });
    }
    return el;
  }

  /* ── Profile ─────────────────────────────────────────────────── */

  function missing() {
    return IMPORTANT.filter((f) => isEmpty(state.profile[f]));
  }

  function renderProfileSummary() {
    const p = state.profile;
    $("#fact-visa").textContent = isEmpty(p.visa) ? t("fact.visaMissing") : p.visa;
    $("#fact-hours").textContent = isEmpty(p.horas_disponibles) ? t("fact.hoursMissing") : t("fact.hours", { n: p.horas_disponibles });
    const area = isEmpty(p.zona) ? t("fact.areaDefault") : p.zona;
    $("#fact-area").textContent = isEmpty(p.viaje_maximo_minutos) ? area : t("fact.area", { area, min: p.viaje_maximo_minutos });
    const miss = missing();
    $("#profile-dot").hidden = miss.length === 0;
    $("#profile-notice").hidden = miss.length === 0;
    $("#profile-notice-text").textContent = t("profile.missing", { fields: miss.map((f) => t(`field.${f}`)).join(", ") });
  }

  function openProfile() {
    const form = $("#profile-form");
    PROFILE_FIELDS.forEach((f) => {
      const control = form.elements.namedItem(f);
      if (control) control.value = state.profile[f] || (f === "nivel_de_ingles" ? "intermediate" : "");
    });
    $("#profile-dialog").showModal();
  }

  function bindProfile() {
    $("#open-profile").addEventListener("click", openProfile);
    document.addEventListener("click", (e) => {
      if (e.target.closest("[data-open-profile]")) openProfile();
    });
    $("#close-profile").addEventListener("click", () => $("#profile-dialog").close());
    $("#profile-dialog").addEventListener("click", (e) => {
      if (e.target === e.currentTarget) e.currentTarget.close();
    });
    $("#profile-form").addEventListener("submit", (e) => {
      e.preventDefault();
      PROFILE_FIELDS.forEach((f) => {
        const control = e.target.elements.namedItem(f);
        if (control) state.profile[f] = control.value.trim();
      });
      store.set(KEYS.profile, state.profile);
      $("#profile-dialog").close();
      renderProfileSummary();
      toast(t("profile.saved"));
    });
    $("#clear-profile").addEventListener("click", () => {
      if (!confirm(t("profile.confirmClear"))) return;
      state.profile = { nivel_de_ingles: "intermediate" };
      store.set(KEYS.profile, null);
      $("#profile-form").reset();
      renderProfileSummary();
      toast(t("profile.cleared"));
    });
  }

  /* ── Chat ────────────────────────────────────────────────────── */

  function renderSuggestions() {
    const box = $("#suggestions");
    box.innerHTML = "";
    [1, 2, 3, 4, 5].forEach((n) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = t(`suggest.${n}`);
      b.addEventListener("click", () => sendMessage(b.textContent));
      box.appendChild(b);
    });
  }

  function autosize() {
    const box = $("#prompt");
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, 160)}px`;
  }

  function scrollChat() {
    const box = $("#messages");
    box.scrollTop = box.scrollHeight;
  }

  function addBubble(role, html) {
    $("#empty-chat").hidden = true;
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.innerHTML = `<span class="who">${esc(role === "user" ? t("chat.you") : t("chat.assistant"))}</span><div class="body">${html}</div>`;
    $("#messages").appendChild(el);
    scrollChat();
    return el;
  }

  function addAgent(text) {
    const el = addBubble("agent", "");
    const body = el.querySelector(".body");
    parseAgent(text).forEach((part) => {
      if (part.kind === "text") {
        if (part.text.trim()) body.insertAdjacentHTML("beforeend", markdown(part.text));
      } else {
        const grid = document.createElement("div");
        grid.className = "grid chat-grid";
        part.jobs.forEach((job) => grid.appendChild(card(job)));
        body.appendChild(grid);
      }
    });
    scrollChat();
  }

  function stepText(step) {
    const sources = (step.sources || []).map((s) => t(`source.${s}`)).join(", ");
    const map = {
      skill: t("step.skill"),
      search: t("step.search", { sources, keywords: (step.keywords || []).join(" · ") }),
      remember: t("step.remember"),
      fetch: t("step.fetch", { host: step.host || "" }),
      date: t("step.date"),
    };
    return (map[step.kind] || t("step.work")) + (step.denied ? ` ${t("step.denied")}` : "");
  }

  function progressBubble() {
    if (state.chat.pending) return state.chat.pending;
    const el = document.createElement("div");
    el.className = "msg agent progress";
    el.innerHTML = `<span class="who">${esc(t("chat.assistant"))}</span>
      <div class="body"><p class="working"><span class="spinner" aria-hidden="true"></span>${esc(t("chat.working"))}</p><ol class="steps-live"></ol></div>`;
    $("#messages").appendChild(el);
    state.chat.pending = el;
    scrollChat();
    return el;
  }

  function finishProgress() {
    const el = state.chat && state.chat.pending;
    if (!el) return;
    const steps = el.querySelectorAll(".steps-live li").length;
    if (!steps) el.remove();
    else {
      el.classList.add("done");
      el.querySelector(".working").innerHTML = `✓ ${esc(t("chat.done"))}`;
      el.querySelector(".steps-live").hidden = true;
      el.addEventListener("click", () => {
        const list = el.querySelector(".steps-live");
        list.hidden = !list.hidden;
      });
    }
    state.chat.pending = null;
  }

  function setBusy(busy) {
    state.chat && (state.chat.busy = busy);
    $("#send").disabled = busy || !state.ai;
    $("#prompt").disabled = !state.ai;
    $$("#suggestions .chip").forEach((b) => (b.disabled = busy || !state.ai));
    $("#new-chat").hidden = !state.chat || !state.chat.id;
  }

  function renderMeter() {
    const c = state.chat;
    if (!c || !c.budget) {
      $("#meter").hidden = true;
      return;
    }
    $("#meter").hidden = false;
    const pct = Math.min(100, Math.round((c.cost / c.budget) * 100));
    $("#meter-fill").style.width = `${pct}%`;
    $("#meter").classList.toggle("high", pct >= 75);
    $("#meter-text").textContent = t("chat.budget", { cost: (c.cost / 100).toFixed(2), budget: (c.budget / 100).toFixed(2) });
  }

  /* Turn the stored first message back into what she typed. */
  function userText(raw) {
    const m = String(raw).match(/Request:\s*([\s\S]*?)(\n\nProfile \(|$)/);
    return m ? m[1].trim() : String(raw);
  }

  function handleEvents(data, { restoring }) {
    const c = state.chat;
    c.cost = data.cost_cents || 0;
    c.budget = data.budget_cents || c.budget;
    if (data.cursor) c.cursor = data.cursor;
    let finished = false;
    for (const ev of data.events || []) {
      if (c.seenIds.has(ev.id)) continue;
      c.seenIds.add(ev.id);
      if (ev.type === "user") {
        if (restoring) addBubble("user", markdown(userText(ev.text)));
      } else if (ev.type === "running") {
        c.sawRunning = true;
      } else if (ev.type === "step") {
        if (!restoring) {
          const li = document.createElement("li");
          li.textContent = stepText(ev);
          progressBubble().querySelector(".steps-live").appendChild(li);
          scrollChat();
        }
      } else if (ev.type === "agent") {
        if (!restoring) finishProgress();
        addAgent(ev.text);
        c.sawAgent = true;
      } else if (ev.type === "error") {
        addBubble("agent", `<p class="error">${esc(ev.text)}</p>`);
      } else if (ev.type === "idle") {
        if (restoring || c.sawRunning || c.sawAgent) finished = true;
        if (ev.reason === "budget_reached") {
          c.budgetReached = true;
          if (!restoring) addBubble("agent", `<p class="warn-text">${esc(t("chat.budgetReached"))}</p>`);
        }
      }
    }
    renderMeter();
    return finished || data.status === "terminated";
  }

  function stopPolling() {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  async function poll() {
    const c = state.chat;
    if (!c || !c.id) return;
    try {
      const data = await api(`/api/events?session=${encodeURIComponent(c.id)}&after=${encodeURIComponent(c.cursor || "")}`);
      const done = handleEvents(data, { restoring: false });
      if (done && data.status !== "running") {
        finishProgress();
        setBusy(false);
        if (c.budgetReached) $("#send").disabled = true;
        return;
      }
    } catch (error) {
      if (error.status === 401) return lock(true);
    }
    if (Date.now() - c.startedAt > POLL_LIMIT_MS) {
      finishProgress();
      addBubble("agent", `<p class="muted">${esc(t("chat.timeout"))}</p>`);
      setBusy(false);
      return;
    }
    state.pollTimer = setTimeout(poll, POLL_MS);
  }

  async function sendMessage(text) {
    text = String(text || "").trim();
    if (!text || !state.ai) return;
    if (!state.code) return lock(false);
    if (state.chat && state.chat.busy) return;
    if (state.chat && state.chat.budgetReached) newChat();

    const isNew = !state.chat || !state.chat.id;
    if (isNew) state.chat = { id: null, cursor: "", seenIds: new Set(), cost: 0, budget: 0 };
    const c = state.chat;
    c.sawRunning = false;
    c.sawAgent = false;
    addBubble("user", markdown(text));
    $("#prompt").value = "";
    autosize();
    setBusy(true);
    progressBubble();
    try {
      const data = await api("/api/chat", {
        method: "POST",
        body: { text, lang: state.lang, profile: isNew ? state.profile : undefined, session_id: c.id || undefined },
      });
      c.id = data.session_id;
      c.cursor = data.since;
      c.startedAt = Date.now();
      store.set(KEYS.session, c.id);
      setBusy(true);
      stopPolling();
      state.pollTimer = setTimeout(poll, 1200);
    } catch (error) {
      finishProgress();
      setBusy(false);
      if (error.status === 401) return lock(true);
      addBubble("agent", `<p class="error">${esc(t("chat.error", { detail: error.message }))}</p>`);
    }
  }

  function newChat() {
    stopPolling();
    state.chat = null;
    store.set(KEYS.session, null);
    $$("#messages .msg").forEach((m) => m.remove());
    $("#empty-chat").hidden = false;
    setBusy(false);
    renderMeter();
  }

  async function restoreChat() {
    const id = store.get(KEYS.session, null);
    if (!id || !state.code) return;
    state.chat = { id, cursor: "", seenIds: new Set(), cost: 0, budget: 0, startedAt: Date.now() };
    try {
      const data = await api(`/api/events?session=${encodeURIComponent(id)}`);
      handleEvents(data, { restoring: true });
      if (data.status === "running") {
        setBusy(true);
        progressBubble();
        poll();
      } else setBusy(false);
    } catch (error) {
      if (error.status === 401) return lock(true);
      newChat();
    }
  }

  function lock(bad) {
    state.code = "";
    store.set(KEYS.code, null);
    $("#unlock").hidden = false;
    $("#unlock-help").textContent = bad ? t("unlock.bad") : t("unlock.help");
    $("#unlock-help").classList.toggle("error", Boolean(bad));
    setBusy(false);
    $("#access-code").focus();
  }

  function bindChat() {
    $("#composer").addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage($("#prompt").value);
    });
    $("#prompt").addEventListener("input", autosize);
    $("#prompt").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        sendMessage($("#prompt").value);
      }
    });
    $("#new-chat").addEventListener("click", newChat);
    $("#unlock-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      state.code = $("#access-code").value.trim();
      try {
        const health = await api("/api/health");
        if (!health.code_ok) return lock(true);
      } catch {
        return lock(true);
      }
      store.set(KEYS.code, state.code);
      $("#unlock").hidden = true;
      $("#access-code").value = "";
      setBusy(false);
      const pending = $("#prompt").value.trim();
      if (pending) sendMessage(pending);
    });
  }

  /* ── Quick search ────────────────────────────────────────────── */

  function renderQuickChips() {
    const box = $("#quick-chips");
    box.innerHTML = "";
    ["customer service", "admin assistant", "warehouse", "retail", "receptionist", "barista"].forEach((q) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = q;
      b.addEventListener("click", () => {
        $("#q").value = q;
        quickSearch();
      });
      box.appendChild(b);
    });
  }

  async function quickSearch() {
    const btn = $("#search-btn");
    btn.disabled = true;
    $("#quick-summary").innerHTML = `<span class="spinner" aria-hidden="true"></span> ${esc(t("quick.searching"))}`;
    $("#quick-results").innerHTML = "";
    try {
      const data = await api("/api/search", { method: "POST", body: { keywords: $("#q").value.trim(), type: $("#type").value } });
      const parts = [`<b>${esc(t("quick.count", { n: data.jobs.length }))}</b>`];
      if (data.mode === "live" && data.total) parts.push(esc(t("quick.of", { total: Number(data.total).toLocaleString("en-AU") })));
      if (data.excluded) parts.push(`<span class="pill rose">${esc(t("quick.excluded", { n: data.excluded }))}</span>`);
      if (data.mode === "demo") parts.push(`<span class="pill sun">${esc(t("quick.demo", { date: data.generated || "" }))}</span>`);
      $("#quick-summary").innerHTML = parts.join(" · ");
      if (!data.jobs.length) $("#quick-summary").insertAdjacentHTML("beforeend", `<p class="muted">${esc(t("quick.none"))}</p>`);
      data.jobs.forEach((job) => $("#quick-results").appendChild(card(job, { askable: state.ai })));
    } catch (error) {
      $("#quick-summary").innerHTML = `<span class="error">${esc(t("chat.error", { detail: error.message }))}</span>`;
    } finally {
      btn.disabled = false;
    }
  }

  function bindQuick() {
    $("#search-form").addEventListener("submit", (e) => {
      e.preventDefault();
      quickSearch();
    });
    $("#type").addEventListener("change", quickSearch);
  }

  /* ── Saved ───────────────────────────────────────────────────── */

  function renderSaved() {
    const list = $("#saved-list");
    list.innerHTML = "";
    state.saved.forEach((job) => list.appendChild(card(job, { askable: state.ai })));
    $("#saved-empty").hidden = state.saved.length > 0;
    const count = $("#saved-count");
    count.hidden = state.saved.length === 0;
    count.textContent = state.saved.length;
  }

  /* ── Start ───────────────────────────────────────────────────── */

  async function start() {
    applyLang();
    bindProfile();
    bindChat();
    bindQuick();
    $$(".lang [data-lang]").forEach((b) =>
      b.addEventListener("click", () => {
        state.lang = b.dataset.lang;
        store.set(KEYS.lang, state.lang);
        applyLang();
      }));

    try {
      const health = await api("/api/health");
      state.ai = Boolean(health.ai);
    } catch {
      state.ai = false;
    }
    $("#ai-off").hidden = state.ai;
    $("#composer").hidden = !state.ai;
    if (state.ai && !state.code) lock(false);
    setBusy(false);
    if (state.ai) restoreChat();
    quickSearch();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
