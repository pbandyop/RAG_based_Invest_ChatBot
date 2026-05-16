/**
 * Phase 5 UI — Stitch layout + POST /query (Phase 6). Multi-session chat with localStorage.
 */

const PAN_LIKE = /\b[A-Z]{5}[0-9]{4}[A-Z]\b/i;
const AADHAAR_LIKE = /\b\d{4}\s?\d{4}\s?\d{4}\b/;

const SESSIONS_STORAGE_KEY = "nextleap_groww_chat_sessions_v1";
const ACTIVE_SESSION_STORAGE_KEY = "nextleap_groww_chat_active_v1";

const SVG_BOT = `<svg class="h-5 w-5 text-primary-fixed-dim" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>`;

const SVG_USER = `<svg class="h-5 w-5 text-primary-fixed-dim" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>`;

function apiUrl(path) {
  return new URL(path, window.location.origin).toString();
}

/** Best-effort message from FastAPI / proxy JSON error bodies */
function formatApiErrorPayload(data, status, rawText) {
  if (data && typeof data === "object") {
    const d = data.detail;
    if (typeof d === "string" && d.trim()) return d;
    if (Array.isArray(d) && d.length) {
      const parts = d.map((x) =>
        typeof x === "object" && x !== null && "msg" in x ? String(x.msg) : JSON.stringify(x),
      );
      return parts.join("; ");
    }
    if (data.message && String(data.message).trim()) return String(data.message);
    if (data.error && String(data.error).trim()) return String(data.error);
  }
  const snippet = (rawText || "").trim().slice(0, 400);
  if (snippet) return `Request failed (${status}): ${snippet}`;
  return `Request failed (${status})`;
}

function setStatus(el, text, isError) {
  el.textContent = text;
  el.classList.toggle("error", Boolean(isError));
}

function autoResizeTextarea(el) {
  if (!el) return;
  el.style.height = "auto";
  const max = 160;
  el.style.height = `${Math.min(el.scrollHeight, max)}px`;
}

function newSessionId() {
  return `s_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function formatSessionTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function loadSessionsFromStorage() {
  try {
    const raw = localStorage.getItem(SESSIONS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveSessionsToStorage(sessions) {
  try {
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
  } catch (e) {
    console.warn("Chat sessions could not be saved (quota or private mode).", e);
  }
}

function persistActiveId(activeSessionId) {
  try {
    if (activeSessionId) localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, activeSessionId);
  } catch (e) {
    console.warn("Active session id could not be saved.", e);
  }
}

function deriveTitleFromThread(threadEl) {
  if (!threadEl) return "Conversation";
  const u = threadEl.querySelector('[data-message-role="user"]');
  if (u) {
    const p = u.querySelector("p");
    const t = (p?.textContent || "").trim();
    if (t) return t.length > 52 ? `${t.slice(0, 49)}…` : t;
  }
  if (threadEl.querySelector("#chat-welcome")) return "Getting started";
  return "Conversation";
}

function scrollChatToBottom() {
  const outer = document.getElementById("chat-thread");
  if (!outer) return;
  requestAnimationFrame(() => {
    outer.scrollTop = outer.scrollHeight;
  });
}

function removeWelcomeIfPresent() {
  const w = document.getElementById("chat-welcome");
  if (w && w.parentNode) w.parentNode.removeChild(w);
}

function humanizeGeneratorRoute(route) {
  const r = route || "";
  if (r.startsWith("groq")) {
    if (r === "groq_fallback") return "Sources + language model (fallback).";
    if (r.startsWith("groq_grounding")) return "Sources + language model (citation check).";
    if (r === "groq_retry") return "Sources + language model (policy pass).";
    return "Sources + language model.";
  }
  if (r === "extractive_fallback") return "Sources only (model unavailable after retrieval).";
  if (r === "extractive") return "Sources only — add GROQ_API_KEY for full chat replies.";
  return `${r || "unknown"}`;
}

function elAssistantAvatar() {
  const wrap = document.createElement("div");
  wrap.className =
    "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-outline-variant bg-surface-container-high shadow-sm";
  wrap.setAttribute("aria-hidden", "true");
  wrap.innerHTML = SVG_BOT;
  return wrap;
}

function elUserAvatar() {
  const wrap = document.createElement("div");
  wrap.className =
    "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary-container/30 bg-primary-container/20";
  wrap.setAttribute("aria-hidden", "true");
  wrap.innerHTML = SVG_USER;
  return wrap;
}

function appendUserBubble(thread, text) {
  const row = document.createElement("div");
  row.className = "flex animate-fade-in items-start justify-end gap-4";
  row.setAttribute("data-message-role", "user");
  const bubble = document.createElement("div");
  bubble.className = "max-w-[80%] rounded-2xl border border-outline-variant/50 bg-surface-bright p-4 shadow-md";
  const p = document.createElement("p");
  p.className = "body-md m-0 whitespace-pre-wrap leading-relaxed text-on-surface";
  p.textContent = text;
  bubble.appendChild(p);
  row.appendChild(bubble);
  row.appendChild(elUserAvatar());
  thread.appendChild(row);
}

function appendLoadingBubble(thread) {
  const row = document.createElement("div");
  row.className = "flex animate-fade-in items-start gap-4";
  row.setAttribute("data-message-role", "assistant");
  row.setAttribute("data-loading", "true");
  const bubble = document.createElement("div");
  bubble.className = "assistant-bubble-shell flex-1 rounded-2xl border border-outline-variant bg-surface-container-lowest p-4 shadow-xl";
  const span = document.createElement("span");
  span.className = "typing-label";
  span.textContent = "Thinking…";
  bubble.appendChild(span);
  row.appendChild(elAssistantAvatar());
  row.appendChild(bubble);
  thread.appendChild(row);
  return row;
}

function removeNode(node) {
  if (node && node.parentNode) node.parentNode.removeChild(node);
}

function appendEvidence(container, rows) {
  if (!rows || !rows.length) return;

  const details = document.createElement("details");
  details.className = "evidence-block";
  details.open = false;

  const summary = document.createElement("summary");
  const left = document.createElement("span");
  left.style.display = "flex";
  left.style.alignItems = "center";
  left.style.gap = "0.5rem";
  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined evidence-source-icon";
  icon.style.fontSize = "18px";
  icon.textContent = "layers";
  const title = document.createElement("span");
  title.textContent = `Retrieved passages (${rows.length})`;
  left.appendChild(icon);
  left.appendChild(title);
  const chevron = document.createElement("span");
  chevron.className = "material-symbols-outlined evidence-summary-chevron";
  chevron.textContent = "expand_more";
  summary.appendChild(left);
  summary.appendChild(chevron);
  details.appendChild(summary);

  details.addEventListener("toggle", () => {
    chevron.textContent = details.open ? "expand_less" : "expand_more";
  });

  const list = document.createElement("div");
  list.className = "evidence-list";

  const maxShow = 8;
  for (let i = 0; i < rows.length && i < maxShow; i += 1) {
    const row = rows[i];
    const article = document.createElement("article");
    article.className = "evidence-snippet";
    const header = document.createElement("header");
    const cid = document.createElement("span");
    cid.textContent = row.chunk_id || "(chunk)";
    const sm = document.createElement("span");
    sm.className = "snippet-meta";
    const parts = [];
    if (typeof row.score === "number") parts.push(`score ${row.score.toFixed(4)}`);
    if (row.fetched_at) parts.push(String(row.fetched_at));
    sm.textContent = parts.join(" · ");
    header.appendChild(cid);
    header.appendChild(sm);
    article.appendChild(header);
    const urlP = document.createElement("p");
    if (row.source_url) {
      urlP.textContent = row.source_url;
    } else {
      urlP.textContent = "No source URL on record.";
    }
    article.appendChild(urlP);
    list.appendChild(article);
  }

  details.appendChild(list);
  container.appendChild(details);
}

function appendParagraph(parent, text) {
  const p = document.createElement("p");
  p.className = "body-md text-on-surface";
  p.textContent = text;
  parent.appendChild(p);
}

function wrapAssistantShell(card) {
  const shell = document.createElement("div");
  shell.className =
    "assistant-bubble-shell flex-1 rounded-2xl border border-outline-variant bg-surface-container-lowest p-6 shadow-xl";
  shell.appendChild(card);
  return shell;
}

function appendAssistantResponse(thread, data) {
  const row = document.createElement("div");
  row.className = "flex animate-fade-in items-start gap-4";
  row.setAttribute("data-message-role", "assistant");

  const card = document.createElement("div");
  card.className = "result-card chat-embedded-card";

  const inner = document.createElement("div");
  inner.className = "result-card-inner";

  if (data.client_error) {
    card.classList.add("refusal");
    const badge = document.createElement("div");
    badge.className = "refusal-badge refusal-badge--system";
    badge.textContent = "Couldn’t complete request";
    inner.appendChild(badge);
    appendParagraph(inner, data.answer || "Something went wrong.");
    card.appendChild(inner);
    row.appendChild(elAssistantAvatar());
    row.appendChild(wrapAssistantShell(card));
    thread.appendChild(row);
    return;
  }

  if (data.refusal) {
    card.classList.add("refusal");
    const badge = document.createElement("div");
    badge.className = "refusal-badge";
    badge.textContent = "Information only";
    inner.appendChild(badge);
    appendParagraph(inner, data.answer || "");
    if (data.educational_url) {
      const meta = document.createElement("div");
      meta.className = "result-meta-row";
      const p = document.createElement("p");
      const a = document.createElement("a");
      a.href = data.educational_url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = data.educational_label || data.educational_url;
      p.appendChild(document.createTextNode("Learn more: "));
      p.appendChild(a);
      meta.appendChild(p);
      inner.appendChild(meta);
    }
    card.appendChild(inner);
    row.appendChild(elAssistantAvatar());
    row.appendChild(wrapAssistantShell(card));
    thread.appendChild(row);
    return;
  }

  if (data.needs_scheme_clarification) {
    card.classList.add("refusal");
    appendParagraph(inner, data.answer || data.clarification_message || "Please name a pilot fund in your message.");
    card.appendChild(inner);
    row.appendChild(elAssistantAvatar());
    row.appendChild(wrapAssistantShell(card));
    thread.appendChild(row);
    return;
  }

  const route = data.generator_route;
  if (route) {
    const syn = document.createElement("p");
    syn.className = "synthesis-route" + (String(route).startsWith("groq") ? " llm-on" : "");
    syn.textContent = humanizeGeneratorRoute(route);
    inner.appendChild(syn);
  }

  appendParagraph(inner, data.answer || "");

  const meta = document.createElement("div");
  meta.className = "result-meta-row";

  if (data.citation_url) {
    const a = document.createElement("a");
    a.href = data.citation_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    const linkIcon = document.createElement("span");
    linkIcon.className = "material-symbols-outlined";
    linkIcon.style.fontSize = "18px";
    linkIcon.textContent = "open_in_new";
    a.appendChild(linkIcon);
    a.appendChild(document.createTextNode(" Open on Groww"));
    meta.appendChild(a);
  }

  if (data.footer_line) {
    const span = document.createElement("span");
    span.className = "result-meta-muted";
    span.textContent = data.footer_line;
    meta.appendChild(span);
  }

  if (data.last_updated && !data.footer_line) {
    const lu = document.createElement("span");
    lu.className = "result-meta-muted";
    lu.textContent = `Source date: ${data.last_updated}`;
    meta.appendChild(lu);
  }

  if (meta.childNodes.length) inner.appendChild(meta);

  card.appendChild(inner);
  appendEvidence(card, data.evidence);
  row.appendChild(elAssistantAvatar());
  row.appendChild(wrapAssistantShell(card));
  thread.appendChild(row);
}

async function loadDisclaimer() {
  const el = document.getElementById("disclaimer-text");
  if (!el) return;
  try {
    const r = await fetch(apiUrl("/meta/disclaimer"));
    if (!r.ok) throw new Error(String(r.status));
    const j = await r.json();
    el.textContent = j.text || "Facts-only. No investment advice.";
  } catch {
    el.textContent = "Facts-only. No investment advice.";
  }
}

function appendCorpusFundRow(ul, scheme, onPick) {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className =
    "w-full rounded-md px-2 py-2.5 text-left text-xs leading-snug text-on-surface transition-colors hover:bg-secondary-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";
  const cat = scheme.category ? String(scheme.category) : "";
  btn.textContent = cat ? `${scheme.display_name} · ${cat}` : String(scheme.display_name);
  btn.addEventListener("click", () => onPick(scheme));
  li.appendChild(btn);
  ul.appendChild(li);
}

async function loadCorpusFunds(onPick) {
  const r = await fetch(apiUrl("/meta/schemes"));
  if (!r.ok) throw new Error("Could not load schemes");
  const j = await r.json();
  const schemes = j.schemes || [];
  const desktop = document.getElementById("corpus-fund-list");
  const mobile = document.getElementById("corpus-fund-list-mobile");
  if (desktop) {
    while (desktop.firstChild) desktop.removeChild(desktop.firstChild);
    for (const s of schemes) appendCorpusFundRow(desktop, s, onPick);
  }
  if (mobile) {
    while (mobile.firstChild) mobile.removeChild(mobile.firstChild);
    for (const s of schemes) appendCorpusFundRow(mobile, s, onPick);
  }
}

function wireExamples(textarea) {
  document.querySelectorAll(".btn-example").forEach((btn) => {
    btn.addEventListener("click", () => {
      textarea.value = btn.getAttribute("data-query") || "";
      autoResizeTextarea(textarea);
      textarea.focus();
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("query-form");
  const textarea = document.getElementById("question-input");
  const status = document.getElementById("status");
  const submitBtn = document.getElementById("submit-btn");
  const thread = document.getElementById("chat-thread-messages");
  const welcomeTemplate = document.getElementById("chat-welcome-template");
  const composer = document.getElementById("chat-composer");

  const sidebar = document.getElementById("sidebar");
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  const sidebarOpenBtn = document.getElementById("sidebar-open-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const clearChatBtn = document.getElementById("clear-chat-btn");
  const sessionsListEl = document.getElementById("chat-sessions-list");

  const corpusToggle = document.getElementById("corpus-nav-toggle");
  const corpusPanel = document.getElementById("corpus-nav-panel");
  const corpusChevron = corpusToggle?.querySelector(".corpus-chevron");

  const mobileOpen = document.getElementById("corpus-mobile-open");
  const mobileClose = document.getElementById("corpus-mobile-close");
  const mobileBackdrop = document.getElementById("corpus-mobile-backdrop");
  const mobileSheet = document.getElementById("corpus-mobile-sheet");

  let sessions = [];
  let activeSessionId = null;

  function persistCurrentSession() {
    if (!thread || !activeSessionId) return;
    const html = thread.innerHTML;
    const title = deriveTitleFromThread(thread);
    const updatedAt = Date.now();
    const idx = sessions.findIndex((s) => s.id === activeSessionId);
    const payload = { id: activeSessionId, title, updatedAt, html };
    if (idx >= 0) sessions[idx] = payload;
    else sessions.push(payload);
    saveSessionsToStorage(sessions);
    persistActiveId(activeSessionId);
    renderSessionList();
  }

  function renderSessionList() {
    if (!sessionsListEl) return;
    sessionsListEl.innerHTML = "";
    const sorted = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);
    for (const s of sorted) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.sessionId = s.id;
      const isActive = s.id === activeSessionId;
      btn.className = [
        "chat-session-btn flex w-full flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors",
        isActive
          ? "border-primary-fixed-dim/60 bg-surface-bright text-on-surface"
          : "border-transparent text-on-surface-variant hover:border-outline-variant/30 hover:bg-surface-container-high hover:text-on-surface",
      ].join(" ");
      if (isActive) btn.setAttribute("aria-current", "true");
      const titleEl = document.createElement("span");
      titleEl.className = "w-full truncate text-left text-xs font-medium";
      titleEl.textContent = s.title || "Conversation";
      const meta = document.createElement("span");
      meta.className = "text-[10px] text-outline";
      meta.textContent = formatSessionTime(s.updatedAt);
      btn.appendChild(titleEl);
      btn.appendChild(meta);
      btn.addEventListener("click", () => {
        if (s.id === activeSessionId) {
          closeSidebarMobile();
          return;
        }
        persistCurrentSession();
        activeSessionId = s.id;
        thread.innerHTML = s.html || "";
        persistActiveId(activeSessionId);
        renderSessionList();
        scrollChatToBottom();
        closeSidebarMobile();
      });
      li.appendChild(btn);
      sessionsListEl.appendChild(li);
    }
  }

  function resetToWelcomeOnly() {
    if (!thread) return;
    thread.replaceChildren();
    if (welcomeTemplate?.content) thread.appendChild(welcomeTemplate.content.cloneNode(true));
  }

  function initSessionsFromStorage() {
    sessions = loadSessionsFromStorage();
    activeSessionId = localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY) || "";

    if (sessions.length === 0) {
      activeSessionId = newSessionId();
      sessions.push({
        id: activeSessionId,
        title: deriveTitleFromThread(thread),
        updatedAt: Date.now(),
        html: thread.innerHTML,
      });
      saveSessionsToStorage(sessions);
      persistActiveId(activeSessionId);
    } else {
      if (!activeSessionId || !sessions.some((x) => x.id === activeSessionId)) {
        activeSessionId = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)[0].id;
      }
      const cur = sessions.find((x) => x.id === activeSessionId);
      if (cur?.html) thread.innerHTML = cur.html;
      persistActiveId(activeSessionId);
    }
    renderSessionList();
  }

  function startNewChat() {
    persistCurrentSession();
    activeSessionId = newSessionId();
    resetToWelcomeOnly();
    sessions.push({
      id: activeSessionId,
      title: "New conversation",
      updatedAt: Date.now(),
      html: thread.innerHTML,
    });
    saveSessionsToStorage(sessions);
    persistActiveId(activeSessionId);
    renderSessionList();
    closeSidebarMobile();
    scrollChatToBottom();
    textarea.value = "";
    autoResizeTextarea(textarea);
    textarea.focus();
  }

  function deleteActiveSessionOnly() {
    if (!activeSessionId || !thread) return;
    const currentTitle = sessions.find((s) => s.id === activeSessionId)?.title || "this chat";
    if (!window.confirm(`Delete “${currentTitle}”? Other saved conversations will stay on this device.`)) return;

    sessions = sessions.filter((s) => s.id !== activeSessionId);
    saveSessionsToStorage(sessions);

    if (sessions.length > 0) {
      const next = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)[0];
      activeSessionId = next.id;
      thread.innerHTML = next.html || "";
    } else {
      activeSessionId = newSessionId();
      resetToWelcomeOnly();
      sessions.push({
        id: activeSessionId,
        title: "Getting started",
        updatedAt: Date.now(),
        html: thread.innerHTML,
      });
      saveSessionsToStorage(sessions);
    }

    persistActiveId(activeSessionId);
    renderSessionList();
    closeSidebarMobile();
    scrollChatToBottom();
    textarea.value = "";
    autoResizeTextarea(textarea);
  }

  function closeSidebarMobile() {
    if (!sidebar || !sidebarOverlay) return;
    sidebar.classList.add("-translate-x-full");
    sidebarOverlay.classList.add("hidden");
  }

  function openSidebarMobile() {
    if (!sidebar || !sidebarOverlay) return;
    sidebar.classList.remove("-translate-x-full");
    sidebarOverlay.classList.remove("hidden");
  }

  function closeMobileCorpus() {
    if (!mobileSheet || !mobileBackdrop) return;
    mobileSheet.hidden = true;
    mobileBackdrop.classList.add("hidden");
    mobileOpen?.setAttribute("aria-expanded", "false");
  }

  function openMobileCorpus() {
    if (!mobileSheet || !mobileBackdrop) return;
    mobileSheet.hidden = false;
    mobileBackdrop.classList.remove("hidden");
    mobileOpen?.setAttribute("aria-expanded", "true");
    mobileClose?.focus();
  }

  function onFundPick(scheme) {
    const name = scheme.display_name || "";
    textarea.value = name ? `What is the NAV for ${name}?` : "";
    autoResizeTextarea(textarea);
    textarea.focus();
    closeMobileCorpus();
    closeSidebarMobile();
    composer?.scrollIntoView({ behavior: "smooth", block: "end" });
    scrollChatToBottom();
  }

  initSessionsFromStorage();

  sidebarOpenBtn?.addEventListener("click", openSidebarMobile);
  sidebarOverlay?.addEventListener("click", closeSidebarMobile);
  newChatBtn?.addEventListener("click", startNewChat);
  clearChatBtn?.addEventListener("click", deleteActiveSessionOnly);

  if (corpusToggle && corpusPanel) {
    corpusToggle.addEventListener("click", () => {
      corpusPanel.classList.toggle("hidden");
      const expanded = !corpusPanel.classList.contains("hidden");
      corpusToggle.setAttribute("aria-expanded", String(expanded));
      corpusChevron?.classList.toggle("rotate-180", expanded);
    });
  }

  mobileOpen?.addEventListener("click", openMobileCorpus);
  mobileClose?.addEventListener("click", closeMobileCorpus);
  mobileBackdrop?.addEventListener("click", closeMobileCorpus);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && mobileSheet && !mobileSheet.hidden) closeMobileCorpus();
  });

  textarea?.addEventListener("input", () => autoResizeTextarea(textarea));

  loadDisclaimer();
  loadCorpusFunds(onFundPick).catch(() => {
    setStatus(status, "Could not load fund list.", true);
  });
  wireExamples(textarea);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = (textarea.value || "").trim();
    if (!q) {
      setStatus(status, "Enter a message.", true);
      return;
    }
    if (PAN_LIKE.test(q) || AADHAAR_LIKE.test(q)) {
      setStatus(status, "Remove PAN/Aadhaar-like numbers before sending.", true);
      return;
    }

    removeWelcomeIfPresent();

    setStatus(status, "", false);
    submitBtn.disabled = true;

    appendUserBubble(thread, q);
    textarea.value = "";
    autoResizeTextarea(textarea);
    const loadingEl = appendLoadingBubble(thread);
    scrollChatToBottom();

    const body = { query: q };

    try {
      const r = await fetch(apiUrl("/query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const text = await r.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("Invalid response from server.");
      }
      removeNode(loadingEl);
      if (!r.ok) {
        throw new Error(formatApiErrorPayload(data, r.status, text));
      }
      appendAssistantResponse(thread, data);
      scrollChatToBottom();
    } catch (err) {
      removeNode(loadingEl);
      appendAssistantResponse(thread, {
        client_error: true,
        answer: err.message || "Network error — check that the server is running and try again.",
      });
      scrollChatToBottom();
      setStatus(status, "Something went wrong.", true);
    } finally {
      persistCurrentSession();
      submitBtn.disabled = false;
      textarea.focus();
    }
  });
});
