/* GlyphMark web UI.
   Framework-free logic + local CSS; Tailwind/Alpine/fonts come from CDN for polish.
   Every action calls the /api/* endpoints, whose shapes mirror the CLI flags. */

/* ---------------------------------------------------------------- helpers */
const $ = (id) => document.getElementById(id);
const val = (id) => ($(id) ? $(id).value : "");
const bytesOf = (s) => new TextEncoder().encode(s || "").length;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));
const debounced = (fn, ms = 140) => {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
};

async function api(path, body) {
  const res = await fetch("/api/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  let data = {};
  try { data = await res.json(); } catch (e) { data = { error: "HTTP " + res.status }; }
  if (!res.ok) {
    const err = new Error(data.error || ("HTTP " + res.status));
    err.code = data.exit_code;
    err.body = data;
    throw err;
  }
  return data;
}

function toast(msg, kind = "info", ms = 4200) {
  const box = $("toasts");
  if (!box) return;
  while (box.children.length > 3) box.firstChild.remove();
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.innerHTML = msg;
  el.title = "dismiss";
  el.addEventListener("click", () => el.remove());
  box.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function showErr(where, err) {
  toast("<b>" + where + ":</b> " + esc(err.message) +
    (err.code ? ` <span class="chip bad">exit ${err.code}</span>` : ""), "err", 9000);
}

function copy(text, label = "copied") {
  const done = () => toast(label, "ok", 2200);
  const fallback = () => {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { toast("copy blocked by browser", "err"); }
    ta.remove();
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done).catch(fallback);
  } else { fallback(); }
}

async function pasteInto(fieldId) {
  if (!navigator.clipboard || !navigator.clipboard.readText) {
    toast("the browser blocks clipboard reads — use <kbd>Ctrl</kbd>+<kbd>V</kbd> in the box", "info", 5000);
    return;
  }
  try {
    const text = await navigator.clipboard.readText();
    if (!text) { toast("clipboard is empty", "info", 2500); return; }
    $(fieldId).value = text;
    $(fieldId).dispatchEvent(new Event("input", { bubbles: true }));
    toast("pasted " + text.length + " characters", "ok", 2600);
  } catch (e) {
    toast("clipboard permission denied — paste manually", "err", 5000);
  }
}

function download(name, text, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/* ------------------------------------------------------------ text views */
function utf8Hex(text) {
  const out = [];
  for (const b of new TextEncoder().encode(text)) out.push(b.toString(16).padStart(2, "0").toUpperCase());
  const lines = [];
  for (let i = 0; i < out.length; i += 16) lines.push(out.slice(i, i + 16).join(" "));
  return lines.join("\n");
}

function escapedView(text) {
  let out = "";
  for (const ch of String(text)) {
    if (ch === "\n") out += "\n";
    else if (ch === "\t") out += "\\t";
    else {
      const cp = ch.codePointAt(0);
      if (cp < 0x7f) out += ch;
      else if (cp <= 0xffff) out += "\\u" + cp.toString(16).padStart(4, "0");
      else out += "\\u{" + cp.toString(16) + "}";   // astral: Plane-14 tags, VS17+
    }
  }
  return out;
}

const hex = (cp) => cp.toString(16).toUpperCase().padStart(4, "0");

function shortName(cp) {
  if (cp >= 0xe0020 && cp <= 0xe007f) return "TAG:" + String.fromCharCode(cp - 0xe0000);
  if (cp >= 0xfe00 && cp <= 0xfe0f) return "VS" + (cp - 0xfe00 + 1);
  if (cp >= 0xe0100 && cp <= 0xe01ef) return "VS" + (cp - 0xe0100 + 17);
  const named = {
    0x200b: "ZWSP", 0x200c: "ZWNJ", 0x200d: "ZWJ", 0x2060: "WJ", 0xfeff: "BOM",
    0x2061: "INVIS-APP", 0x2062: "INVIS-TIMES", 0x2063: "INVIS-SEP", 0x2064: "INVIS-PLUS",
    0x180e: "MVS", 0x3164: "HFILL", 0xffa0: "HFILL2", 0x200e: "LRM", 0x200f: "RLM",
    0x2066: "LRI", 0x2069: "PDI", 0xad: "SHY", 0xa0: "NBSP", 0x202f: "NNBSP",
    0x3000: "IDSP", 0x1680: "OGHAM", 0x061c: "ALM", 0x202e: "RLO", 0x202d: "LRO",
  };
  if (named[cp]) return named[cp];
  if (cp < 0x20) return "^" + String.fromCharCode(cp + 64);
  return "U+" + hex(cp);
}

function suspectByRange(cp) {
  if (cp === 0x09 || cp === 0x0a || cp === 0x0d || cp === 0x20) return false;
  if (cp < 0x20 || (cp >= 0x7f && cp <= 0x9f)) return true;
  if ((cp >= 0x200b && cp <= 0x200f) || (cp >= 0x202a && cp <= 0x202e) ||
      (cp >= 0x2060 && cp <= 0x2069) || cp === 0xfeff || cp === 0x180e ||
      cp === 0x00ad || cp === 0x061c) return true;
  if ((cp >= 0xfe00 && cp <= 0xfe0f) || (cp >= 0xe0000 && cp <= 0xe0fff)) return true;
  if (cp === 0x3164 || cp === 0xffa0) return true;
  if (cp >= 0xff01 && cp <= 0xff5e) return true;
  if (cp >= 0x0300 && cp <= 0x036f) return true;
  return [0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006,
          0x2007, 0x2008, 0x2009, 0x200a, 0x205f, 0x3000].includes(cp);
}

/* Fast client-side triage: the ranges above plus the exact code points channels use. */
const SUSPECT_CHARS = new Set();
function isSuspect(cp) { return SUSPECT_CHARS.has(cp) || suspectByRange(cp); }

function statsStrip(text) {
  let suspect = 0;
  for (const ch of text) if (isSuspect(ch.codePointAt(0))) suspect += 1;
  const chips = [
    `<span class="stat"><b>${text.length.toLocaleString()}</b> code points</span>`,
    `<span class="stat"><b>${bytesOf(text).toLocaleString()}</b> utf-8 bytes</span>`,
    `<span class="stat"><b>${(text.match(/\n/g) || []).length + (text ? 1 : 0)}</b> lines</span>`,
  ];
  if (suspect) {
    chips.push(`<span class="stat alarm"><b>${suspect}</b> anomalous code point${suspect > 1 ? "s" : ""}</span>`);
  }
  return chips.join("");
}

/* Render text with invisible / anomalous code points made visible. */
function annotate(text, info, markSwaps) {
  const rows = info && info.rows ? info.rows : null;
  let html = "";
  let i = 0;
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    if (ch === "\n") { html += "\n"; i += 1; continue; }
    const row = rows ? rows[i] : null;
    const bad = row ? row.suspect : isSuspect(cp);
    if (bad) {
      const kind = row && row.flags && row.flags.length ? row.flags[0] : "suspect";
      const cls = (kind === "confusable" || kind === "fullwidth-compat") ? "letter"
        : (kind === "space-variant" ? "zw" : "");
      html += `<span class="hidden-char ${cls}" title="${esc(kind)} · U+${hex(cp)}">` +
        esc(shortName(cp)) + "</span>";
    } else if (markSwaps && markSwaps.has(i)) {
      html += `<span class="swap" title="substituted code point: U+${hex(cp)}">${esc(ch)}</span>`;
    } else {
      html += esc(ch);
    }
    i += 1;
  }
  return html;
}

/* -------------------------------------------------------- what really changed */
function whatChanged(cover, out, scheme) {
  if (scheme.family === "insert") {
    const symbols = new Set([...(state.symbolsById[scheme.id] || [])]);
    const visible = [...out].filter((c) => !symbols.has(c)).join("");
    const positions = [];
    let idx = -1;
    for (const c of out) {
      idx += 1;
      if (symbols.has(c) && positions[positions.length - 1] !== idx) positions.push(idx);
    }
    return `
      <div class="card-h" style="margin-top:.9rem"><h2>What changed</h2>
        <div class="row-gap"><span class="chip ${visible === cover ? "ok" : "bad"}">
          visible text ${visible === cover ? "unchanged" : "ALTERED"}</span></div></div>
      <p class="hint"><b>${out.length - cover.length}</b> invisible symbols inserted at
        <b>${positions.length}</b> character boundaries. The cover text survives byte for byte
        underneath, which is why the recipient sees nothing — and deleting any single symbol breaks
        the CRC, so ordinary editing destroys the mark.
        First insertion offsets: ${positions.slice(0, 6).join(", ") || "—"}.</p>`;
  }
  const swaps = new Map();
  const marked = new Set();
  let changed = 0;
  for (let i = 0; i < Math.min(cover.length, out.length); i += 1) {
    if (cover[i] !== out[i]) {
      changed += 1;
      marked.add(i);
      const key = cover[i] + "→" + out[i];
      const cp = "U+" + hex(out.codePointAt(i));
      const prev = swaps.get(key) || { n: 0, cp };
      swaps.set(key, { n: prev.n + 1, cp });
    }
  }
  const sample = [...out].slice(0, 260).join("");
  return `
    <div class="card-h" style="margin-top:.9rem"><h2>What changed</h2>
      <div class="row-gap"><span class="chip">${changed} characters swapped</span>
        <span class="chip ok">same length · same words</span></div></div>
    <p class="hint">Nothing was inserted: ${changed} carrier characters were replaced by look-alikes
      from another script or block. That is why this channel survives copy-paste, JSON and social
      filters — and it is the same mechanism behind homograph phishing.</p>
    <div class="swaps">${[...swaps].slice(0, 24)
      .map(([k, v]) => `<span class="chip mono">${esc(k)} <b>${v.n}</b> <span class="dim">${v.cp}</span></span>`).join("")}</div>
    <div class="diffgrid" style="margin-top:.6rem">
      <div><p class="hint">cover</p><pre class="outtext">${esc([...cover].slice(0, 260).join(""))}</pre></div>
      <div><p class="hint">marked — swaps underlined</p><pre class="outtext annotated">${annotate(sample, null, marked)}</pre></div>
    </div>`;
}

/* -------------------------------------------------------------- output card */
function renderOutput(box, opts) {
  const el = $(box);
  if (!el) return;
  el.classList.remove("empty");
  state.views[box] = opts.text || "";
  const views = opts.views || [];
  const first = views[0];
  const initial = opts.html !== undefined ? opts.html
    : (first ? (first.html || esc(first.value || "")) : esc(opts.text || ""));
  const chips = (opts.chips || [])
    .map((c) => `<span class="chip ${c.kind || ""}">${c.label}</span>`).join("");
  const pre = box + "-pre";
  el.innerHTML = `
    <div class="card-h"><h2>${esc(opts.title)}</h2>
      <div class="row-gap"><button class="btn tiny ghost" data-act="copy-text">copy</button>
      ${opts.extraButtons || ""}</div></div>
    <div class="kv" data-role="chips">${chips}</div>
    ${views.length ? `<div class="viewtabs" role="tablist">${views.map((v, i) =>
      `<button class="viewtab ${i === 0 ? "active" : ""}" role="tab" aria-selected="${i === 0}"
        data-view="${v.id}">${esc(v.label)}</button>`).join("")}</div>` : ""}
    <pre class="outtext" id="${pre}">${initial}</pre>
    ${opts.body || ""}
    ${opts.cli ? `<div class="card-h" style="margin-top:.95rem"><h2>Same result from the CLI</h2>
        <div class="row-gap"><button class="btn tiny ghost" data-act="copy-cli">copy command</button></div>
      </div><pre class="cli">${esc(opts.cli)}</pre>` : ""}
    ${opts.note ? `<p class="hint" style="margin-top:.6rem">${opts.note}</p>` : ""}`;

  el.querySelectorAll("[data-view]").forEach((btn) => btn.addEventListener("click", () => {
    el.querySelectorAll("[data-view]").forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
    });
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    const v = views.find((x) => x.id === btn.dataset.view);
    const target = $(pre);
    if (v && v.html) target.innerHTML = v.html;
    else if (v) target.textContent = v.value;
  }));
  const copyText = el.querySelector('[data-act="copy-text"]');
  if (copyText) copyText.addEventListener("click", () => copy(state.views[box] || ""));
  const copyCli = el.querySelector('[data-act="copy-cli"]');
  if (copyCli) copyCli.addEventListener("click", () => copy(opts.cli || "", "command copied"));
  el.querySelectorAll("[data-copy]").forEach((n) => n.addEventListener("click", () => copy(n.dataset.copy)));
  if (opts.after) opts.after(el);
  if (window.innerWidth < 1060) el.scrollIntoView({ block: "nearest" });
}

const levelOf = (score) => (score >= 70 ? "high" : score >= 30 ? "suspicious" : "clean");

/* strip a channel's own symbols to recover what a reader actually sees */
function visibleOnly(text, scheme) {
  const symbols = state.symbolsById[scheme.id] || new Set();
  return [...text].filter((ch) => !symbols.has(ch.codePointAt(0))).join("");
}

function addChips(box, chips) {
  const slot = $(box) && $(box).querySelector('[data-role="chips"]');
  if (slot) slot.insertAdjacentHTML("beforeend",
    chips.map((c) => `<span class="chip ${c.kind || ""}">${c.label}</span>`).join(""));
}

function chipsForEncode(r) {
  return [
    { label: `channel <b>${esc(r.scheme)}</b>` },
    { label: `payload <b>${r.payload_len} B</b>` },
    { label: `units <b>${r.units_used}</b> of ${r.carrier_units.toLocaleString()}` },
    { label: `bits <b>${r.bits_used.toLocaleString()}</b>` },
    { label: `spare ≈ <b>${r.capacity_bytes} B</b>` },
    { label: r.keyed ? "keyed" : "unkeyed", kind: r.keyed ? "info" : "" },
    { label: r.verified ? "round-trip verified" : "NOT verified", kind: r.verified ? "ok" : "bad" },
  ];
}

function cliEncode(r, key, placement) {
  return ["glyphmark encode",
    "  --cover-file cover.txt",
    "  --payload-file payload.txt",
    "  --scheme " + r.scheme,
    "  --placement " + placement,
    key ? '  --key "$GLYPHMARK_KEY"' : null,
    "  -o marked.txt --report"].filter(Boolean).join(" \\\n");
}

function cliDecode(scheme, key) {
  return "glyphmark decode \\\n  --text-file marked.txt \\\n  --scheme " + scheme +
    (key ? ' \\\n  --key "$GLYPHMARK_KEY"' : "") + "\n  # exit 3 = nothing found · 4 = wrong key";
}

function attemptsTable(err) {
  const attempts = (err.body && err.body.attempts) || [];
  if (!attempts.length) return "";
  return `<details open style="margin-top:.6rem"><summary class="hint">
      channel sweep — ${attempts.length} channel(s) tried, none produced a valid frame</summary>
    <div class="table-wrap"><table>
      <thead><tr><th>channel tried</th><th>why it failed</th></tr></thead>
      <tbody>${attempts.map((a) => `<tr><td class="mono">${esc(a.scheme)}</td>
        <td>${esc(a.error)}</td></tr>`).join("")}</tbody></table></div></details>`;
}

function findingCard(f) {
  const chars = (f.characters || []).slice(0, 10).map((c) => {
    const ch = String.fromCodePoint(parseInt(c.codepoint.slice(2), 16));
    return `<span class="chip mono act" data-copy="${esc(ch)}"
      title="${esc(c.name)} · offset ${c.at} · UTF-8 ${esc(c.utf8)} — click to copy">
      ${esc(c.codepoint)}</span>`;
  }).join(" ");
  const tokens = (f.tokens || []).slice(0, 4)
    .map((t) => `<code>${esc(t.text)}</code> (${t.scripts.join("+")})`).join(" · ");
  const confirmed = f.kind === "frame_signature";
  return `<div class="finding ${f.severity} ${confirmed ? "confirmed" : ""}" data-sev="${f.severity}">
    <h4>${esc(f.title)}
      <span class="chip ${f.severity === "high" ? "bad" : (f.severity === "medium" ? "warn" : "info")}">${f.severity}</span>
      <span class="chip">${f.count} occurrence(s)</span>
      <span class="chip">remove with <b class="act" data-copy="${esc(f.remove_with || "")}">${esc(f.remove_with || "—")}</b></span>
    </h4>
    <p>${esc(f.why)}</p>
    ${chars ? `<p>${chars}</p>` : ""}
    ${f.payload_preview ? `<p><span class="chip bad">recovered payload</span> <code>${esc(f.payload_preview)}</code></p>` : ""}
    ${f.strength ? `<p class="hint">strength: ${esc(f.strength)}</p>` : ""}
    ${tokens ? `<p>mixed-script tokens: ${tokens}</p>` : ""}
  </div>`;
}

function stageTable(stages) {
  return `<table><thead><tr><th>stage</th><th>runs</th><th>kills channels</th></tr></thead>
    <tbody>${stages.map((s) => `<tr><td class="mono">${esc(s.id)}</td>
      <td>${s.default ? "default" : '<span class="chip warn">opt-in</span>'}</td>
      <td>${s.kills.map((k) => `<span class="chip">${esc(k)}</span>`).join(" ") || "—"}</td>
    </tr>`).join("")}</tbody></table>`;
}

const dots = (n) => "●".repeat(n) + "○".repeat(Math.max(0, 5 - n));

function schemeTable(rows) {
  return `<table>
    <thead><tr><th>channel</th><th>family</th><th class="num">bit/unit</th><th>stealth</th>
      <th>survival</th><th>carrier</th><th>detection vector</th><th></th></tr></thead>
    <tbody>${rows.map((s) => `<tr>
      <td><b class="mono">${esc(s.id)}</b><br><span class="dim">${esc(s.label)}</span></td>
      <td>${esc(s.family)}</td>
      <td class="num">${s.bits_per_unit}</td>
      <td title="stealth ${s.stealth}/5">${dots(s.stealth)}</td>
      <td title="survival ${s.survival}/5">${dots(s.survival)}</td>
      <td>${esc(s.carrier)}</td>
      <td>${esc(s.detection)}</td>
      <td><button class="btn tiny ghost" data-detail="${esc(s.id)}">detail</button></td>
    </tr>`).join("")}</tbody></table>`;
}

function detail(s) {
  return `<p class="hint">${esc(s.blurb)}</p>
    <div class="kv">
      <span class="chip">radix <b>${s.radix}</b></span>
      <span class="chip">density <b>${s.density_bytes_per_unit} B</b>/unit</span>
      <span class="chip">${s.anchor_required ? "anchor-bound" : "free placement"}</span>
      ${(s.tags || []).map((t) => `<span class="chip info">${esc(t)}</span>`).join("")}
    </div>
    <p class="hint">killed by: ${(s.killed_by || []).map((k) => `<code>${esc(k)}</code>`).join(", ")}</p>
    ${(s.notes || []).map((n) => `<p class="hint">• ${esc(n)}</p>`).join("")}
    <div class="table-wrap scroll" style="max-height:260px"><table>
      <thead><tr><th>digit</th><th>cp</th><th>cat</th><th>utf-8</th><th>render</th><th>name</th></tr></thead>
      <tbody>${(s.characters || []).slice(0, 60).map((c) => `<tr>
        <td class="mono">${esc(c.bit_value)}</td><td class="mono">${esc(c.codepoint)}</td>
        <td class="mono">${esc(c.category)}</td><td class="mono">${esc(c.utf8)}</td>
        <td>${esc(c.render)}</td><td>${esc(c.name)}</td></tr>`).join("")}</tbody>
    </table></div>`;
}

function buildCharTable(query) {
  const q = (query || "").toLowerCase();
  const rows = state.meta.characters.filter((c) => !q ||
    [c.codepoint, c.name, c.category, c.render, (c.schemes || []).join(" ")]
      .join(" ").toLowerCase().includes(q));
  $("charTable").innerHTML = `<table>
    <thead><tr><th>cp</th><th>cat</th><th>utf-8</th><th>how it renders</th>
      <th>unicode name</th><th>channels</th></tr></thead>
    <tbody>${rows.slice(0, 400).map((c) => `<tr class="click" data-char="${esc(c.char)}">
      <td class="mono">${esc(c.codepoint)}</td><td class="mono">${esc(c.category)}</td>
      <td class="mono">${esc(c.utf8)}</td><td>${esc(c.render)}</td>
      <td>${esc(c.name)}</td>
      <td>${(c.schemes || []).map((s) => `<span class="chip act" data-goto="${esc(s)}">${esc(s)}</span>`).join(" ")}</td>
    </tr>`).join("")}</tbody></table>`;
  document.querySelectorAll("#charTable [data-char]").forEach((tr) => tr.addEventListener("click", () => {
    copy(tr.dataset.char, "character copied — paste it into Detect");
  }));
}

function showDetail(id) {
  const s = state.schemesById[id];
  renderOutput("inspOut", { title: "Channel: " + id, text: s.blurb, html: detail(s) });
  UI.switchTab("inspect");
}

function setStageChecks(ids) {
  document.querySelectorAll("#stagePicker input").forEach((i) => {
    i.checked = ids.includes(i.value);
  });
}

function installVerifyButton() {
  const card = $("cliCard");
  const btn = document.createElement("button");
  btn.className = "btn tiny block";
  btn.style.marginTop = ".6rem";
  btn.textContent = "Self test every channel (glyphmark verify)";
  const out = document.createElement("div");
  out.setAttribute("aria-live", "polite");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> testing ' + state.meta.schemes.length + " channels…";
    try {
      const r = await api("verify", {});
      out.innerHTML = `<div class="kv" style="margin-top:.6rem"><span class="chip ${r.passed === r.total ? "ok" : "bad"}">
          ${r.passed}/${r.total} channels pass</span></div>
        <div class="table-wrap scroll" style="max-height:220px"><table>
        <thead><tr><th>channel</th><th>result</th><th class="num">bits</th><th class="num">carrier</th><th>detail</th></tr></thead>
        <tbody>${r.results.map((x) => `<tr><td class="mono">${esc(x.scheme)}</td>
          <td>${x.ok ? '<span class="chip ok">PASS</span>' : '<span class="chip bad">FAIL</span>'}</td>
          <td class="num">${x.bits_used}</td><td class="num">${x.carrier_units}</td>
          <td>${esc(x.error || "")}</td></tr>`).join("")}</tbody></table></div>`;
    } catch (err) { showErr("verify", err); }
    btn.disabled = false;
    btn.textContent = "Self test every channel (glyphmark verify)";
  });
  card.appendChild(btn);
  card.appendChild(out);
}

/* ------------------------------------------------------------ CLI cheat sheet */
const CLI_CHEAT = `# channel catalogue and per-channel character sets
glyphmark schemes
glyphmark scheme vs-bytes
glyphmark chars

# embed / extract  (flags, files and stdin all work; '-' = stdin)
glyphmark encode --cover-file cover.txt --payload-file tag.txt \\
                 --scheme tags --key "$SECRET" -o marked.txt --report
glyphmark decode --text-file marked.txt --scheme auto --key "$SECRET"
printf '%s' "$MARKED" | glyphmark decode -f json      # auto-sweep every channel

# defensive scanning and intake hygiene
glyphmark detect   --text-file marked.txt --json
glyphmark detect   --text-file marked.txt --fail-on-risk 60   # CI gate -> exit 6
glyphmark sanitize --list-stages
glyphmark sanitize --text-file marked.txt -o clean.txt
glyphmark sanitize --text-file in.txt --stage strip_tags --stage nfkc -e json

# forensics, self test, web UI
glyphmark inspect  --text-file marked.txt --only-suspect
glyphmark verify                              # encode+extract round trip, all channels
glyphmark verify --scheme homoglyph
glyphmark serve --host 127.0.0.1 --port 8123  # this UI`;

const PLACEMENT_LABELS = {
  spread: "Spread across the text (default, most natural)",
  interleave: "Interleaved through the first third",
  prefix: "Packed at the start",
  suffix: "Packed at the end",
};

const EXIT_CODES = [
  [0, "success"], [1, "error"], [2, "bad CLI arguments"], [3, "no watermark found"],
  [4, "corrupt frame or wrong key"], [5, "carrier text too small"], [6, "risk threshold reached"],
];

/* -------------------------------------------------------------------- state */
const STORE_KEY = "glyphmark-session-v1";
const SAMPLE = "The quick brown fox jumps over the lazy dog. Packing gives every wren a job; " +
  "sphinx of black quartz, judge my vow. Quick zephyrs blow, vexing daft Jim.";
const SAMPLE_PAYLOAD = "model=local-llm session=4F2A-91C7 rev=2026-07-08";

const STAT_BOX = {
  cover: "cover-stats", payload: "payload-stats", decText: "dec-stats",
  detText: "det-stats", sanText: "san-stats",
};

const state = {
  meta: null,
  schemesById: {},
  symbolsById: {},          // scheme id -> Set(code point) used by that channel
  altsById: {},             // scheme id -> Map(alt code point -> base char)
  defaultStages: [],
  alts: new Map(),          // union of all alternates -> base char
  scheme: "zw-octal",
  tab: "embed",
  busy: false,
  views: {},
  lastDetect: null,
  session: {},
};

/* Theme is the only thing Alpine owns; it mirrors onto [data-theme] for the CSS. */
function themeState() {
  return {
    dark: true,
    sync() {
      const saved = localStorage.getItem("gm-theme");
      if (saved) this.dark = saved === "dark";
      else this.dark = !(window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches);
      this.apply();
    },
    toggle() { this.dark = !this.dark; this.apply(); },
    apply() {
      document.documentElement.dataset.theme = this.dark ? "dark" : "light";
      document.body.dataset.theme = this.dark ? "dark" : "light";
      localStorage.setItem("gm-theme", this.dark ? "dark" : "light");
    },
  };
}

/* ------------------------------------------------------------------ UI logic */
const UI = {
  /* ---- capacity ------------------------------------------------------------ */
  carrierUnits(cover, scheme) {
    const symbols = state.symbolsById[scheme.id] || new Set();
    const alts = state.altsById[scheme.id] || new Map();
    if (scheme.family === "insert") {
      if (scheme.id === "ascii-ctrl") {
        return cover.split("\n").reduce(
          (n, line) => n + Math.max(0, line.trim().split(/\s+/).filter(Boolean).length), 0);
      }
      let n = 0;
      for (const ch of cover) { if (!symbols.has(ch.codePointAt(0))) n += 1; }
      return scheme.anchor_required ? n + 1 : Math.max(0, n - 1);
    }
    let usable = 0;
    for (const ch of cover) {
      const cp = ch.codePointAt(0);
      if (symbols.has(cp) || alts.has(cp)) usable += 1;
    }
    return usable;
  },

  capacityBytes(cover, scheme) {
    if (!cover) return { units: 0, bytes: 0, need: 0, fits: false };
    const units = this.carrierUnits(cover, scheme);
    const bytes = Math.floor((units * scheme.bits_per_unit) / 8);
    const need = bytesOf(val("payload"));
    return { units, bytes, need, fits: bytes >= need && need > 0 };
  },

  renderCapacity() {
    const box = $("capBox");
    if (!box) return;
    const scheme = state.schemesById[state.scheme];
    if (!scheme) { box.innerHTML = ""; return; }
    const cap = this.capacityBytes(val("cover"), scheme);
    if (!val("cover")) {
      box.innerHTML = '<span class="dim">Type or load cover text to see capacity.</span>';
      return;
    }
    const pct = Math.min(100, cap.need ? Math.round((cap.need / Math.max(1, cap.bytes)) * 100) : 100);
    box.innerHTML = `
      <div class="row-gap" style="justify-content:space-between">
        <span><b>${cap.units.toLocaleString()}</b> carrier units → up to <b>${cap.bytes} B</b> payload
          (${scheme.bits_per_unit} bit/unit)</span>
        <span class="${cap.bytes >= cap.need ? "" : "full"}">payload needs <b>${cap.need} B</b></span>
      </div>
      <div class="meter ${cap.bytes >= cap.need ? "" : "hot"}" style="margin-top:.3rem">
        <i style="width:${cap.bytes ? Math.min(100, Math.round((cap.need / cap.bytes) * 100)) : 0}%"></i></div>`;
    this.renderReco(cap);
  },

  /* Suggest channels that actually fit the current cover + payload. */
  renderReco(cap) {
    const reco = $("reco");
    if (!reco) return;
    const payload = val("payload");
    if (!val("cover") || !payload) { reco.innerHTML = ""; return; }
    const need = bytesOf(payload);
    const fits = state.meta.schemes
      .map((s) => ({ s, cap: this.capacityBytes(val("cover"), s) }))
      .filter((r) => r.cap.bytes >= need)
      .sort((a, b) => (b.s.survival - a.s.survival) || (b.s.stealth - a.s.stealth) ||
        (a.cap.bytes - b.cap.bytes));
    const chips = fits.slice(0, 3).map((r, i) => {
      const why = i === 0 ? "best fit" : (r.s.bits_per_unit >= 6 ? "high capacity" : "durable");
      return `<span class="chip reco act" data-scheme="${esc(r.s.id)}">
        <span class="tick">✓</span> ${esc(r.s.id)} · ${why} · ${r.cap.bytes} B free</span>`;
    });
    const mine = state.schemesById[state.scheme];
    const mineCap = this.capacityBytes(val("cover"), mine);
    if (!mineCap.bytes || mineCap.bytes < need) {
      chips.unshift(`<span class="chip warn">⚠ <b>${esc(state.scheme)}</b> cannot hold ${need} B here</span>`);
    }
    reco.innerHTML = chips.join("");
    reco.querySelectorAll("[data-scheme]").forEach((c) => c.addEventListener("click", () => {
      this.setScheme(c.dataset.scheme);
      toast("switched to <b>" + esc(c.dataset.scheme) + "</b>", "ok", 2600);
    }));
  },

  setScheme(id) {
    if (!state.schemesById[id]) return;
    state.scheme = id;
    const s = state.schemesById[id];
    if ($("pickerId")) $("pickerId").textContent = id;
    if ($("pickerLbl")) $("pickerLbl").textContent = s.label;
    const sel = $("decScheme");
    if (sel) sel.value = "auto";
    this.renderCapacity();
    saveState();
  },

  /* ---- channel combobox ---------------------------------------------------- */
  buildPicker() {
    const list = $("schemeOptions");
    const fill = (q) => {
      const query = (q || "").toLowerCase();
      const rows = state.meta.schemes.filter((s) => !query ||
        [s.id, s.label, s.family, (s.tags || []).join(" ")].join(" ").toLowerCase().includes(query));
      list.innerHTML = rows.map((s) => `
        <div class="pick ${s.id === state.scheme ? "sel" : ""}" role="option"
             aria-selected="${s.id === state.scheme}" tabindex="-1" data-pick="${esc(s.id)}">
          <b class="mono">${esc(s.id)}</b>
          <div>${esc(s.label)} <span class="dim">· ${s.bits_per_unit} bit/${esc(s.unit_name)} · ${esc(s.family)}</span></div>
          <span class="dim">stealth ${dots(s.stealth)} · survives ${dots(s.survival)}</span>
        </div>`).join("") || '<p class="hint" style="padding:.6rem">no channel matches</p>';
      list.querySelectorAll("[data-pick]").forEach((n) => n.addEventListener("click", () => {
        this.setScheme(n.dataset.pick);
        this.closePicker();
      }));
    };
    fill("");

    const btn = $("schemeBtn");
    const pop = $("schemePop");
    const filter = $("schemeFilter");
    const open = () => {
      pop.hidden = false;
      btn.setAttribute("aria-expanded", "true");
      filter.focus();
    };
    this.closePicker = () => { pop.hidden = true; btn.setAttribute("aria-expanded", "false"); };
    btn.addEventListener("click", () => (pop.hidden ? open() : this.closePicker()));
    filter.addEventListener("input", () => fill(filter.value));
    filter.addEventListener("keydown", (ev) => {
      const opts = [...list.querySelectorAll("[data-pick]")];
      let idx = opts.findIndex((o) => o.classList.contains("sel"));
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        idx = Math.max(0, Math.min(opts.length - 1, idx + (ev.key === "ArrowDown" ? 1 : -1)));
        opts.forEach((o, i) => { o.classList.toggle("hot", i === idx); o.scrollIntoView({ block: "nearest" }); });
      } else if (ev.key === "Enter") {
        ev.preventDefault();
        const pick = opts[idx] || opts[0];
        if (pick) { this.setScheme(pick.dataset.pick); this.closePicker(); btn.focus(); }
      } else if (ev.key === "Escape") { this.closePicker(); btn.focus(); }
    });
    document.addEventListener("click", (ev) => {
      if (!pop.hidden && !pop.contains(ev.target) && ev.target !== btn) this.closePicker();
    });
  },

  /* ---- tabs ---------------------------------------------------------------- */
  switchTab(id) {
    if (!$("panel-" + id)) return;
    state.tab = id;
    document.querySelectorAll(".tab").forEach((t) => {
      const on = t.dataset.tab === id;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".panel").forEach((p) => { p.hidden = p.id !== "panel-" + id; });
    if (id === "extract") $("decText").focus();
    if (id === "detect") $("detText").focus();
    if (id === "sanitize") $("sanText").focus();
    if (id === "inspect") $("inspText").focus();
    saveState();
  },

  /* ---- pipeline ribbon ------------------------------------------------------ */
  ribbon(patch) {
    Object.assign(state.session, patch || {});
    const s = state.session;
    const steps = [
      { key: "cover", label: "cover written", on: !!s.cover,
        hint: s.cover ? (s.cover.length + " chars") : "paste text" },
      { key: "marked", label: "watermarked", on: !!s.marked,
        hint: s.marked ? s.scheme + (s.keyed ? " · keyed" : "") : "no mark yet" },
      { key: "detected", label: "detected", on: !!s.detected,
        hint: s.detected ? (s.verdict + " · risk " + s.risk) : "unscanned" },
      { key: "clean", label: "sanitized", on: !!s.clean,
        hint: s.clean ? "verified clean" : "not cleaned" },
    ];
    $("ribbon").innerHTML = steps.map((st, i) => `
      <span class="step" data-state="${st.on ? "done" : "todo"}" data-step="${st.key}" role="button"
            tabindex="0" title="click to load this text into ${st.label}">
        <i class="dot"></i>${st.label} <b class="dim">${esc(st.hint)}</b></span>
      ${i < steps.length - 1 ? '<span class="arrow">→</span>' : ""}`).join("");
    $("ribbon").querySelectorAll("[data-step]").forEach((n) => {
      const go = () => UI.stepTarget(n.dataset.step);
      n.addEventListener("click", go);
      n.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } });
    });
  },

  stepTarget(key) {
    const s = state.session;
    if (key === "cover") { this.switchTab("embed"); $("cover").focus(); return; }
    if (key === "marked" && s.marked) { $("decText").value = s.marked; this.syncStats("decText", "dec-stats"); this.switchTab("extract"); return; }
    if (key === "detected") {
      if (s.marked) { $("detText").value = s.marked; this.syncStats("detText", "det-stats"); }
      this.switchTab("detect");
      return;
    }
    if (key === "clean" && s.clean) {
      $("sanText").value = s.cleanSource || "";
      this.syncStats("sanText", "san-stats");
      $("detText").value = s.clean;
      this.syncStats("detText", "det-stats");
      this.switchTab("sanitize");
      return;
    }
    toast("nothing there yet — run the previous step first", "info", 3000);
  },

  syncStats(fieldId, statId) {
    const el = $(statId);
    if (el) el.innerHTML = statsStrip($(fieldId).value);
  },

  /* ---- actions ------------------------------------------------------------- */
  async run(name, fn) {
    if (state.busy) return;
    state.busy = true;
    const spin = $("spin-" + name);
    if (spin) spin.hidden = false;
    const btns = document.querySelectorAll("[data-action]");
    btns.forEach((b) => { if (b.dataset.action === name) b.disabled = true; });
    try {
      await fn();
    } catch (err) {
      showErr(name, err);
      console.warn("[glyphmark]", err);
    } finally {
      state.busy = false;
      if (spin) spin.hidden = true;
      btns.forEach((b) => { if (b.dataset.action === name) b.disabled = false; });
    }
  },

  async encode() {
    const cover = val("cover");
    const payload = val("payload");
    if (!cover) { toast("cover text is required", "err"); return; }
    if (!payload) { toast("payload text is required", "err"); return; }
    await this.run("encode", async () => {
      const scheme = state.schemesById[state.scheme];
      const cap = this.capacityBytes(cover, scheme);
      if (cap.bytes < cap.need) {
        toast(`carrier too small: <b>${cap.bytes} B</b> free, payload needs <b>${cap.need} B</b>.
          <button class="btn tiny act" data-scheme-fix="1">pick a bigger channel</button>`, "err", 9000);
        const fix = document.querySelector("[data-scheme-fix]");
        if (fix) fix.addEventListener("click", () => {
          const best = [...state.meta.schemes].sort((a, b) => b.density_bytes_per_unit - a.density_bytes_per_unit)[0];
          this.setScheme(best.id);
        });
        return;
      }
      const key = val("encKey");
      const r = await api("encode", {
        cover, payload, scheme: state.scheme, key, placement: val("placement"),
      });
      state.session = {};
      this.ribbon({ cover: true, marked: true, scheme: r.scheme, keyed: !!key, detected: false, clean: false });
      state.lastDetect = null;
      renderOutput("encOut", {
        title: "Watermarked text",
        text: r.text,
        chips: chipsForEncode(r),
        views: [
          { id: "rendered", label: "as the recipient sees it", html: annotate(r.text, null, null) },
          { id: "visible", label: "visible text only", value: visibleOnly(r.text, scheme) },
          { id: "escaped", label: "escaped (what a JSON API sends)", value: escapedView(r.text) },
          { id: "bytes", label: "raw UTF-8 bytes", value: utf8Hex(r.text) },
        ],
        body: whatChanged(cover, r.text, scheme),
        cli: cliEncode(r, key, val("placement")),
        note: scheme.family === "insert"
          ? "Frame: magic <code>0x57</code> · version · channel id · flags · u16 length · payload · CRC32, LCG-spread across the carrier."
          : "Substitution channel: the decoder locates carriers by membership in the alternates set, so keying also hides <em>where</em> the data sits.",
      });
      state.session.marked = r.text;
      saveState();
      this.autoScan("encOut", r.text, "embed");
    });
  },

  /* Prove the mark survived, without being asked. */
  async autoScan(box, text, stage) {
    try {
      const r = await api("detect", { text, try_frames: true });
      const frames = r.frame_signatures || [];
      const verdict = r.verdict === "clean" ? "no anomaly" : esc(r.verdict);
      const good = frames.length > 0 || r.verdict === "clean";
      const chips = [{
        label: `auto re-scan: <b>${verdict}</b> · risk <b>${r.risk_score}</b>
          <button class="btn tiny act" data-open-scan="${esc(box)}">open report</button>`,
        kind: good ? "ok" : "warn",
      }];
      addChips(box, chips);
      const slot = $(box).querySelector("[data-open-scan]");
      if (slot) slot.addEventListener("click", () => {
        $("detText").value = text;
        this.syncStats("detText", "det-stats");
        this.switchTab("detect");
        state.lastDetect = r;
        this.showDetect(r);
      });
      this.ribbon({ detected: true, verdict: r.verdict, risk: r.risk_score });
      if (stage === "sanitize") this.ribbon({ clean: r.verdict === "clean" });
    } catch (err) { /* the manual scan still reports the reason */ }
  },

  async decode() {
    await this.run("decode", async () => {
      const text = val("decText");
      const key = val("decKey");
      try {
        const r = await api("decode", { text, key, scheme: val("decScheme") });
        const payload = r.payload_text ?? "";
        renderOutput("decOut", {
          title: "Recovered payload",
          text: payload,
          chips: [
            { label: `channel <b>${esc(r.scheme)}</b>`, kind: "ok" },
            { label: `payload <b>${r.payload_len} B</b>` },
            { label: `keyed <b>${r.keyed ? "yes" : "no"}</b>` },
            { label: `units read <b>${r.units_used}</b> of ${r.carrier_units.toLocaleString()}` },
            { label: `bits read <b>${r.bits_read.toLocaleString()}</b>` },
            { label: "magic + CRC32 valid", kind: "ok" },
          ],
          views: [
            { id: "payload", label: "payload (decoded text)", value: payload },
            { id: "hex", label: "payload as hex bytes", value: r.payload_hex || utf8Hex(payload) },
            { id: "b64", label: "payload as base64", value: r.payload_base64 || "" },
            { id: "escaped", label: "payload escaped", value: escapedView(payload) },
          ],
          cli: cliDecode(r.scheme, key),
          note: "The magic byte and CRC32 both validated — a positive identification, not a heuristic. " +
            "Wrong-key attempts surface as exit 4, never as silent garbage.",
        });
        copy(payload, "payload copied");
      } catch (err) {
        renderOutput("decOut", {
          title: "No valid frame",
          text: err.message,
          chips: [{ label: `exit <b>${err.code || 1}</b>`, kind: "bad" }],
          body: attemptsTable(err),
          cli: cliDecode(val("decScheme"), key),
          note: "exit 3 = nothing found · exit 4 = frame found but CRC failed (wrong key, or the carrier was edited).",
        });
      }
    });
  },

  async detect() {
    await this.run("detect", async () => {
      const text = val("detText");
      const r = await api("detect", { text, try_frames: true });
      state.lastDetect = r;
      if (text === val("decText") || text === state.session.marked) {
        this.ribbon({ detected: true, verdict: r.verdict, risk: r.risk_score });
      }
      this.showDetect(r);
    });
  },

  showDetect(r) {
    const level = levelOf(r.risk_score);
    const frames = r.frame_signatures || [];
    renderOutput("detOut", {
      title: "Detection report",
      text: val("detText"),
      extraButtons: '<button class="btn tiny ghost" data-act="dl-json">download JSON</button>',
      chips: [
        { label: `verdict <b>${esc(r.verdict)}</b>`, kind: level === "clean" ? "ok" : (level === "high" ? "bad" : "warn") },
        { label: `code points <b>${(r.codepoints || 0).toLocaleString()}</b>` },
        { label: `anomalous <b>${(r.suspect_total || 0).toLocaleString()}</b>` },
        { label: r.nfkc_equal ? "NFKC-stable" : "NFKC drift", kind: r.nfkc_equal ? "" : "warn" },
        { label: `frames <b>${frames.length}</b>`, kind: frames.length ? "bad" : "" },
      ],
      body: `
        <div class="gauge">
          <span class="num">${r.risk_score}</span>
          <span class="meter ${level === "high" ? "hot" : ""} track"><i style="width:${r.risk_score}%"></i></span>
          <span class="chip ${level === "clean" ? "ok" : (level === "high" ? "bad" : "warn")}">${esc(level)}</span>
        </div>
        <div class="bands"><span class="b0">clean 0–29</span><span class="b1">suspicious 30–69</span><span class="b2">high 70+</span></div>
        ${frames.length ? `<div class="finding high confirmed" data-sev="high">
            <h4>Recovered GlyphMark frames
              <span class="chip bad">high</span>
              <span class="chip">${frames.length} frame(s)</span></h4>
            ${frames.map((f) => `<p><span class="chip bad">${esc(f.scheme)}</span>
               <code>${esc(f.payload_preview)}</code> <span class="dim">${f.payload_len} B · ${esc(f.strength)}</span></p>`).join("")}
          </div>` : ""}
        ${r.tag_block_mirror ? `<div class="finding high" data-sev="high">
            <h4>Plane-14 tag block mirrored to ASCII <span class="chip bad">high</span></h4>
            <p>Tag characters decode back to real ASCII — this is how hidden-instruction injection shows up:</p>
            <code>${esc(r.tag_block_mirror)}</code></div>` : ""}
        ${r.recommendation ? `<p class="hint"><b>recommendation:</b> ${esc(r.recommendation)}
          <button class="btn tiny ghost" data-act="to-sanitize">open in sanitizer</button></p>` : ""}
        <div class="sevfilter" role="group" aria-label="Filter findings by severity">
          <button class="btn tiny ghost" data-sev="all" aria-pressed="true">all (${r.findings.length})</button>
          ${["high", "medium", "low", "info"].map((s) => `<button class="btn tiny ghost" data-sev="${s}" aria-pressed="false">${s}</button>`).join("")}
        </div>
        <div class="findings">${(r.findings || []).map(findingCard).join("") ||
          '<p class="hint">No findings — nothing anomalous in this text.</p>'}</div>`,
      note: "Only <b>watermark-confirmed</b> is a positive identification (magic byte + CRC32). Everything else is heuristic — treat it as “review this text”, not “attack detected”.",
    });
    const toSan = $("detOut").querySelector('[data-act="to-sanitize"]');
    if (toSan) toSan.addEventListener("click", () => {
      $("sanText").value = val("detText");
      UI.syncStats("sanText", STAT_BOX.sanText);
      UI.switchTab("sanitize");
    });
    const el = $("detOut");
    const dl = el.querySelector('[data-act="dl-json"]');
    if (dl) dl.addEventListener("click", () => download("glyphmark-detect.json", JSON.stringify(r, null, 2)));
    el.querySelectorAll(".sevfilter [data-sev]").forEach((b) => b.addEventListener("click", () => {
      const want = b.dataset.sev;
      el.querySelectorAll(".sevfilter [data-sev]").forEach((x) =>
        x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      el.querySelectorAll(".finding").forEach((f) => {
        f.style.display = (want === "all" || f.dataset.sev === want) ? "" : "none";
      });
    }));
  },

  async sanitize() {
    await this.run("sanitize", async () => {
      const text = val("sanText");
      const stages = [...document.querySelectorAll("#stagePicker input")]
        .filter((i) => i.checked).map((i) => i.value);
      const r = await api("sanitize", { text, stages });
      renderOutput("sanOut", {
        title: "Sanitized text",
        text: r.text,
        chips: [
          { label: `code points <b>${r.codepoints_before.toLocaleString()}</b> → <b>${r.codepoints_after.toLocaleString()}</b>` },
          { label: `removed <b>${r.removed_total.toLocaleString()}</b>`, kind: r.removed_total ? "warn" : "ok" },
          { label: r.identical ? "text unchanged" : "text changed", kind: r.identical ? "ok" : "warn" },
          { label: `channels targeted <b>${(r.channels_targeted || []).length}</b>` },
        ],
        views: [
          { id: "clean", label: "clean text", value: r.text },
          { id: "escaped", label: "clean text escaped", value: escapedView(r.text) },
          { id: "bytes", label: "clean text UTF-8 bytes", value: utf8Hex(r.text) },
        ],
        body: `<div class="card-h" style="margin-top:.9rem"><h2>Stage accounting</h2></div>
          <div class="table-wrap"><table>
            <thead><tr><th>stage</th><th class="num">removed</th><th class="num">length before</th><th class="num">length after</th></tr></thead>
            <tbody>${r.stages.map((x) => `<tr><td><b>${esc(x.label)}</b><br><span class="dim mono">${esc(x.id)}</span></td>
              <td class="num">${x.removed ? '<span class="chip warn">' + x.removed.toLocaleString() + "</span>" : "0"}</td>
              <td class="num">${x.before_len.toLocaleString()}</td>
              <td class="num">${x.after_len.toLocaleString()}</td></tr>`).join("")}</tbody>
          </table></div>`,
        cli: "glyphmark sanitize \\\n  --text-file suspect.txt \\\n  --stages " +
          (stages.join(",") || "(none)") + " \\\n  -o clean.txt   # --list-stages shows the pipeline",
        note: "Sanitizing reorders code points and can merge characters, so watermarks die — that is the point.",
      });
      state.session.clean = r.text;
      state.session.cleanSource = text;
      saveState();
      this.autoScan("sanOut", r.text, "sanitize");
    });
  },

  async inspect() {
    await this.run("inspect", async () => {
      const text = val("inspText");
      const only = $("onlySuspect").checked;
      const r = await api("inspect", { text, only_suspect: only, limit: 4000 });
      const flags = {};
      r.rows.forEach((x) => x.flags.forEach((f) => { flags[f] = (flags[f] || 0) + 1; }));
      const tiles = r.rows.slice(0, 900).map((x) =>
        `<i class="tile ${x.flags[0] || ""}" title="${esc(x.codepoint)} ${esc(x.name)}"></i>`).join("");
      const legend = Object.keys(flags).slice(0, 8).map((f) =>
        `<span><i class="tile ${f}" style="width:10px;height:10px;display:inline-block"></i>${esc(f)} ×${flags[f]}</span>`).join("");
      $("inspOut").innerHTML = `
        <div class="card-h"><h2>${r.codepoints.toLocaleString()} code points inspected
          ${only ? "(suspicious only)" : ""}</h2>
          <button class="btn tiny ghost" data-act="copy-json">copy JSON</button></div>
        <div class="kv">
          <span class="chip">shown <b>${r.rows.length.toLocaleString()}</b></span>
          <span class="chip ${r.suspect_count ? "warn" : "ok"}">anomalous <b>${r.suspect_count.toLocaleString()}</b></span>
          <span class="chip">visible-ish <b>${r.visible_guess.toLocaleString()}</b></span>
          <span class="chip">UTF-8 <b>${r.utf8_bytes.toLocaleString()} B</b></span>
          <span class="chip">UTF-16 <b>${r.utf16_units.toLocaleString()}</b> units</span>
          ${r.truncated ? '<span class="chip warn">truncated at 4000</span>' : ""}
        </div>
        <div class="tiles" aria-hidden="true">${tiles}</div>
        <div class="legend">${legend || '<span class="dim">nothing flagged — this text looks ordinary</span>'}</div>
        <div class="sevfilter" role="group" aria-label="Filter by flag">
          <button class="btn tiny ghost" data-flag="all" aria-pressed="true">all</button>
          ${Object.keys(flags).slice(0, 8).map((f) => `<button class="btn tiny ghost" data-flag="${esc(f)}" aria-pressed="false">${esc(f)}</button>`).join("")}
        </div>
        <div class="table-wrap scroll"><table>
          <thead><tr><th>index</th><th>cp</th><th>cat</th><th>script</th><th>name</th><th>renders</th><th>flags</th></tr></thead>
          <tbody id="inspBody">${r.rows.map((x) => `<tr data-flags="${esc(x.flags.join(" "))}">
            <td class="num">${x.index}</td><td class="mono">${esc(x.codepoint)}</td>
            <td class="mono">${esc(x.category)}</td><td class="mono">${esc(x.script)}</td>
            <td>${esc(x.name)}</td><td>${esc(x.display)}</td>
            <td>${x.flags.map((f) => `<span class="chip ${f === "confusable" ? "bad" : "warn"}">${esc(f)}</span>`).join("")}</td>
          </tr>`).join("")}</tbody></table></div>`;
      const box = $("inspOut");
      box.querySelector('[data-act="copy-json"]').addEventListener("click", () =>
        copy(JSON.stringify(r, null, 2), "inspect JSON copied"));
      box.querySelectorAll("[data-flag]").forEach((b) => b.addEventListener("click", () => {
        const want = b.dataset.flag;
        box.querySelectorAll("[data-flag]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
        box.querySelectorAll("#inspBody tr").forEach((tr) => {
          tr.style.display = (want === "all" || tr.dataset.flags.split(" ").includes(want)) ? "" : "none";
        });
      }));
    });
  },

  /* ---- help overlay -------------------------------------------------------- */
  help(open) {
    const el = $("help");
    if (!el) return;
    if (open) {
      this._lastFocus = document.activeElement;
      el.hidden = false;
      el.querySelector("[data-action='help-close']").focus();
    } else {
      el.hidden = true;
      if (this._lastFocus) this._lastFocus.focus();
    }
  },

  /* ---- persistence (text and settings only — never binding keys) ----------- */
  save() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        cover: val("cover"), payload: val("payload"), decText: val("decText"),
        detText: val("detText"), sanText: val("sanText"), inspText: val("inspText"),
        scheme: state.scheme, placement: val("placement"), tab: state.tab,
        marked: state.session.marked, clean: state.session.clean,
        cleanSource: state.session.cleanSource,
      }));
    } catch (e) { /* quota or private mode — silently skip */ }
  },

  restore() {
    let raw;
    try { raw = localStorage.getItem(STORE_KEY); } catch (e) { return; }
    if (!raw) return;
    let saved;
    try { saved = JSON.parse(raw); } catch (e) { return; }
    const map = { cover: "cover", payload: "payload", decText: "decText", detText: "detText", sanText: "sanText", inspText: "inspText" };
    let restored = false;
    for (const [key, id] of Object.entries(map)) {
      if (saved[key] && $(id)) { $(id).value = saved[key]; restored = true; }
    }
    if (saved.placement && $("placement")) $("placement").value = saved.placement;
    state.session.marked = saved.marked || "";
    state.session.clean = saved.clean || "";
    state.session.cleanSource = saved.cleanSource || "";
    if (saved.cover) this.ribbon({ cover: true });
    if (saved.marked) this.ribbon({ marked: true, scheme: saved.scheme || state.scheme });
    if (saved.clean) this.ribbon({ clean: true });
    if (restored) toast("restored your previous session — <button class='btn tiny act' data-clear-session>start fresh</button>", "info", 7000);
    const clr = document.querySelector("[data-clear-session]");
    if (clr) clr.addEventListener("click", () => {
      localStorage.removeItem(STORE_KEY);
      location.reload();
    });
    if (saved.tab) this.switchTab(saved.tab);
    if (saved.scheme) this.setScheme(saved.scheme);
  },
};

const saveState = debounced(() => UI.save(), 500);

/* ---------------------------------------------------------------------- boot */
async function boot() {
  state.meta = await (await fetch("/api/meta")).json();
  $("versionTag").textContent = state.meta.version;
  $("channelCount").textContent = state.meta.schemes.length;
  state.meta.schemes.forEach((s) => { state.schemesById[s.id] = s; });
  state.defaultStages = state.meta.sanitize_stages.filter((s) => s.default).map((s) => s.id);

  // code points that are invisible or non-standard, for instant client-side triage
  const SUSPECT_CATS = new Set(["Cc", "Cf", "Zs", "Mn", "Me", "Co", "Cs", "Cn"]);
  state.meta.characters.forEach((c) => {
    if (SUSPECT_CATS.has(c.category)) SUSPECT_CHARS.add(c.char.codePointAt(0));
  });

  // per-channel symbol sets, used for the live capacity estimate
  state.meta.schemes.forEach((s) => {
    const symbols = new Set();
    const alts = new Map();
    (s.characters || []).forEach((c) => {
      const cp = c.char.codePointAt(0);
      symbols.add(cp);
      if (c.base) { alts.set(cp, c.base); state.alts.set(cp, c.base); }
    });
    state.symbolsById[s.id] = symbols;
    state.altsById[s.id] = alts;
  });

  // selects
  $("placement").innerHTML = state.meta.placements.map((p) =>
    `<option value="${esc(p)}">${esc(PLACEMENT_LABELS[p] || p)}</option>`).join("");
  $("decScheme").innerHTML = '<option value="auto">auto — sweep all channels</option>' +
    state.meta.schemes.map((s) => `<option value="${esc(s.id)}">${esc(s.id)} — ${esc(s.label)}</option>`).join("");

  // stage checkboxes
  $("stagePicker").innerHTML = state.meta.sanitize_stages.map((s) => `
    <label class="${s.default ? "" : "opt"}" title="${esc(s.desc)}">
      <input type="checkbox" value="${esc(s.id)}" ${s.default ? "checked" : ""}>
      <span><span class="sid">${esc(s.label)}</span>
        <span class="dim mono">${esc(s.id)}</span>
        <span class="dim">· ${esc(s.description)}${s.kills.length ? " · kills " + esc(s.kills.join(", ")) : ""}</span></span>
    </label>`).join("");
  document.querySelectorAll("#stagePicker input").forEach((i) => i.addEventListener("change", saveState));

  // reference tables
  $("schemeTable").innerHTML = schemeTable(state.meta.schemes);
  $("stageTable").innerHTML = stageTable(state.meta.sanitize_stages);
  $("cliCheat").textContent = CLI_CHEAT;
  const codes = Object.entries(state.meta.exit_codes || Object.fromEntries(EXIT_CODES));
  $("codeTable").innerHTML = codes.map(([c, why]) =>
    `<tr><td class="mono">${esc(c)}</td><td>${esc(why)}</td></tr>`).join("");
  buildCharTable("");
  installVerifyButton();
  UI.buildPicker();
  UI.setScheme(state.scheme);
  UI.ribbon({});

  // channel row details, wired after the table exists
  document.querySelectorAll("[data-detail]").forEach((btn) =>
    btn.addEventListener("click", () => showDetail(btn.dataset.detail)));

  wire();
  UI.restore();
  UI.renderCapacity();
  Object.keys(STAT_BOX).forEach((id) => {
    const el = $(id);
    if (!el) return;
    if (el.value) UI.syncStats(id, STAT_BOX[id]);
    el.addEventListener("input", debounced(() => {
      UI.syncStats(id, STAT_BOX[id]);
      saveState();
    }, 120));
  });
  $("schemeSearch").addEventListener("input", debounced((e) => {
    $("schemeTable").innerHTML = schemeTable(state.meta.schemes.filter((s) =>
      [s.id, s.label, s.family, s.detection, (s.tags || []).join(" ")].join(" ")
        .toLowerCase().includes(e.target.value.toLowerCase())));
    document.querySelectorAll("[data-detail]").forEach((b) =>
      b.addEventListener("click", () => showDetail(b.dataset.detail)));
  }, 130));
  $("charSearch").addEventListener("input", debounced((e) => buildCharTable(e.target.value), 130));
  document.addEventListener("click", (ev) => {
    const goto = ev.target.closest && ev.target.closest("[data-goto]");
    if (goto) { UI.setScheme(goto.dataset.goto); UI.switchTab("embed"); }
  });
  toast("ready — <b>" + state.meta.schemes.length + "</b> channels loaded", "ok", 2800);
}

/* ------------------------------------------------------------------- wiring */
const TABS = ["embed", "extract", "detect", "sanitize", "inspect", "reference"];
const PANEL_ACTION = { embed: "encode", extract: "decode", detect: "detect", sanitize: "sanitize", inspect: "inspect" };

function runPanel(tab) {
  const action = PANEL_ACTION[tab];
  if (!action) { toast("reference has nothing to run — it is the catalogue", "info", 2600); return; }
  UI[action]();
}

const ACTIONS = {
  encode: () => UI.encode(),
  decode: () => UI.decode(),
  detect: () => UI.detect(),
  sanitize: () => UI.sanitize(),
  inspect: () => UI.inspect(),
  help: () => UI.help($("help").hidden),
  "help-close": () => UI.help(false),
  sample: (el) => {
    const field = $(el.dataset.field);
    const samples = (state.meta && state.meta.samples) || { cover: SAMPLE, payload: SAMPLE_PAYLOAD };
    field.value = el.dataset.field === "payload" ? samples.payload : samples.cover;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    UI.renderCapacity();
  },
  clear: (el) => {
    const field = $(el.dataset.field);
    field.value = "";
    field.dispatchEvent(new Event("input", { bubbles: true }));
    UI.renderCapacity();
    field.focus();
  },
  stages: (el) => {
    if (el.dataset.mode === "default") setStageChecks(state.defaultStages);
    else if (el.dataset.mode === "all") setStageChecks(state.meta.sanitize_stages.map((s) => s.id));
    else setStageChecks([]);
    saveState();
  },
  "copy-cli": () => copy(CLI_CHEAT, "CLI cheat sheet copied"),
  "toggle-key": (el) => {
    const input = $(el.dataset.target);
    input.type = input.type === "password" ? "text" : "password";
    el.textContent = input.type === "password" ? "show" : "hide";
    el.setAttribute("aria-pressed", input.type === "text" ? "true" : "false");
  },
  clipboard: (el) => pasteInto(el.dataset.target),
  "paste-last": (el) => {
    // each panel can pull in the most relevant text produced earlier in the session
    const sources = {
      extract: [state.session.marked, state.views.encOut],
      detect: [state.session.marked, state.views.encOut, state.session.clean],
      sanitize: [state.session.marked, state.views.encOut],
      inspect: [state.session.marked, state.session.clean, state.views.encOut],
    };
    const field = { extract: "decText", detect: "detText", sanitize: "sanText", inspect: "inspText" }[el.dataset.target];
    const text = (sources[el.dataset.target] || []).find(Boolean);
    if (!text) { toast("nothing generated yet in this session", "info", 3200); return; }
    $(field).value = text;
    if (STAT_BOX[field]) UI.syncStats(field, STAT_BOX[field]);
    saveState();
    toast("loaded the last generated text", "ok", 2500);
  },
};

function wire() {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => UI.switchTab(t.dataset.tab)));
  $("onlySuspect").addEventListener("change", () => { if (val("inspText")) UI.inspect(); });

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest && ev.target.closest("[data-action]");
    if (!el) return;
    const fn = ACTIONS[el.dataset.action];
    if (!fn) { console.warn("[glyphmark] unhandled action", el.dataset.action); return; }
    fn(el);
  });

  ["cover", "payload"].forEach((id) => $(id).addEventListener("input", debounced(() => UI.renderCapacity(), 130)));
  $("placement").addEventListener("change", saveState);

  document.addEventListener("keydown", (ev) => {
    const tag = (ev.target.tagName || "").toLowerCase();
    const typing = tag === "textarea" || tag === "input" || tag === "select";
    if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
      ev.preventDefault();
      runPanel(state.tab);
      return;
    }
    if (ev.altKey && !ev.ctrlKey && /^[1-6]$/.test(ev.key)) {
      ev.preventDefault();
      UI.switchTab(TABS[Number(ev.key) - 1]);
      return;
    }
    if (ev.key === "Escape") {
      if (!$("help").hidden) UI.help(false);
      else if ($("schemePop") && !$("schemePop").hidden) UI.closePicker();
      return;
    }
    if (typing) return;
    if (ev.key === "?") { ev.preventDefault(); UI.help(true); }
    if (ev.key === "/") {
      ev.preventDefault();
      if (state.tab === "reference") $("charSearch").focus();
      else if (state.tab === "embed") {
        if ($("schemePop").hidden) $("schemeBtn").click();
        $("schemeFilter").focus();
      }
    }
  });
}

function start() {
  boot().catch((err) => {
    console.error("[glyphmark] boot failed", err);
    toast("failed to load <code>/api/meta</code> — is the Flask server running?", "err", 12000);
  });
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
else start();
