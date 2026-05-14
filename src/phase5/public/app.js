/**
 * Phase 5 UI — calls same-origin POST /query (Phase 6).
 * Renders assistant output as plain text / safe DOM (no innerHTML on model text).
 */

const PAN_LIKE = /\b[A-Z]{5}[0-9]{4}[A-Z]\b/i;
const AADHAAR_LIKE = /\b\d{4}\s?\d{4}\s?\d{4}\b/;

function apiUrl(path) {
  return new URL(path, window.location.origin).toString();
}

function setStatus(el, text, isError) {
  el.textContent = text;
  el.classList.toggle("error", Boolean(isError));
}

function clearResult(container) {
  while (container.firstChild) container.removeChild(container.firstChild);
}

function appendParagraph(parent, text) {
  const p = document.createElement("p");
  p.textContent = text;
  parent.appendChild(p);
}

function renderResponse(data, container) {
  clearResult(container);

  if (data.refusal) {
    const badge = document.createElement("div");
    badge.className = "refusal-badge";
    badge.textContent = "Information only";
    container.appendChild(badge);
    appendParagraph(container, data.answer || "");
    if (data.educational_url) {
      const meta = document.createElement("div");
      meta.className = "result-meta";
      const p = document.createElement("p");
      const a = document.createElement("a");
      a.href = data.educational_url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = data.educational_label || data.educational_url;
      p.appendChild(document.createTextNode("Educational link: "));
      p.appendChild(a);
      meta.appendChild(p);
      container.appendChild(meta);
    }
    return;
  }

  if (data.needs_scheme_clarification) {
    appendParagraph(container, data.answer || data.clarification_message || "Please choose a scheme.");
    return;
  }

  appendParagraph(container, data.answer || "");

  const meta = document.createElement("div");
  meta.className = "result-meta";

  if (data.citation_url) {
    const p = document.createElement("p");
    const a = document.createElement("a");
    a.href = data.citation_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "View scheme page on Groww (opens in new tab)";
    p.appendChild(a);
    meta.appendChild(p);
  }

  if (data.footer_line) {
    const f = document.createElement("p");
    f.textContent = data.footer_line;
    meta.appendChild(f);
  }

  if (data.last_updated) {
    const lu = document.createElement("p");
    lu.textContent = `Source fetch window (metadata): ${data.last_updated}`;
    meta.appendChild(lu);
  }

  if (meta.childNodes.length) container.appendChild(meta);
}

async function loadDisclaimer() {
  const el = document.getElementById("disclaimer-text");
  try {
    const r = await fetch(apiUrl("/meta/disclaimer"));
    if (!r.ok) throw new Error(String(r.status));
    const j = await r.json();
    el.textContent = j.text || "Facts-only. No investment advice.";
  } catch {
    el.textContent = "Facts-only. No investment advice.";
  }
}

async function loadSchemes(select) {
  const r = await fetch(apiUrl("/meta/schemes"));
  if (!r.ok) throw new Error("Could not load schemes");
  const j = await r.json();
  const schemes = j.schemes || [];
  for (const s of schemes) {
    const opt = document.createElement("option");
    opt.value = s.scheme_id;
    opt.textContent = `${s.display_name} (${s.category || "scheme"})`;
    select.appendChild(opt);
  }
}

function wireExamples(select, textarea) {
  document.querySelectorAll(".btn-example").forEach((btn) => {
    btn.addEventListener("click", () => {
      textarea.value = btn.getAttribute("data-query") || "";
      const sid = btn.getAttribute("data-scheme");
      if (sid) select.value = sid;
      textarea.focus();
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("query-form");
  const select = document.getElementById("scheme-select");
  const textarea = document.getElementById("question-input");
  const status = document.getElementById("status");
  const submitBtn = document.getElementById("submit-btn");
  const resultSection = document.getElementById("result-section");
  const resultBody = document.getElementById("result-body");

  loadDisclaimer();
  loadSchemes(select).catch(() => {
    setStatus(status, "Could not load scheme list — refresh the page.", true);
  });
  wireExamples(select, textarea);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = (textarea.value || "").trim();
    if (!q) {
      setStatus(status, "Enter a question.", true);
      return;
    }
    if (PAN_LIKE.test(q) || AADHAAR_LIKE.test(q)) {
      setStatus(status, "Remove PAN/Aadhaar-like numbers before sending.", true);
      return;
    }

    setStatus(status, "…");
    submitBtn.disabled = true;
    resultSection.hidden = true;

    const schemeId = (select.value || "").trim() || null;
    const body = { query: q, scheme_id: schemeId };

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
      if (!r.ok) {
        throw new Error(data.detail || data.message || `Request failed (${r.status})`);
      }
      renderResponse(data, resultBody);
      resultSection.hidden = false;
      setStatus(status, "", false);
    } catch (err) {
      clearResult(resultBody);
      appendParagraph(resultBody, err.message || "Network error — check the API server and try again.");
      resultSection.hidden = false;
      setStatus(status, "Request failed.", true);
    } finally {
      submitBtn.disabled = false;
    }
  });
});
