/* GlyphMark web UI.
   Vanilla JS core + Alpine for shell state + Tailwind/fonts from CDN.
   Every action calls the same /api/* endpoints, whose payloads mirror the CLI flags. */

/* ---------------------------------------------------------------- helpers */
const $ = (id) => document.getElementById(id);
const val = (id) => ($(id) ? $(id).value : "");
const bytesOf = (s) => new TextEncoder().encode(s || "").length;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

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
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.innerHTML = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function showErr(where, err) {
  toast("<b>" + where + ":</b> " + esc(err.message), "err", 8000);
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
      else out += "\\u{" + cp.toString(16) + "}";   // astral: Plane 14 tags, VS17+
    }
  }
  return out;
}

function hex(cp) { return cp.toString(16).toUpperCase().padStart(4, "0"); }

function shortName(cp) {
  if (cp >= 0xe0020 && cp <= 0xe007f) return "TAG:" + String.fromCharCode(cp - 0xe0000);
  if (cp >= 0xfe00 && cp <= 0xfe0f) return "VS" + (cp - 0xfe00 + 1);
  if (cp >= 0xe0100 && cp <= 0xe01ef) return "VS" + (cp - 0xe0100 + 17);
  const named = {
    0x200b: "ZWSP", 0x200c: "ZWNJ", 0x200d: "ZWJ", 0x2060: "WJ", 0xfeff: "BOM",
    0x2061: "INVIS-APP", 0x2062: "INVIS-TIMES", 0x2063: "INVIS-SEP", 0x2064: "INVIS-PLUS",
    0x180e: "MVS", 0x3164: "HFILL", 0xffa0: "HFILL2", 0x200e: "LRM", 0x200f: "RLM",
    0x2066: "LRI", 0x2069: "PDI", 0xad: "SHY", 0xa0: "NBSP", 0x202f: "NNBSP",
    0x3000: "IDSP", 0x1680: "OGHAM", 0x061c: "ALM",
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

/* Render text with invisible / anomalous code points made visible. */
function annotate(text, info) {
  const rows = info && info.rows ? info.rows : null;
  let html = "";
  let i = 0;
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    if (ch === "\n") { html += "\n"; i += 1; continue; }
    const row = rows ? rows[i] : null;
    const bad = row ? row.suspect : suspectByRange(cp);
    if (bad) {
      const kind = row && row.flags.length ? row.flags[0] : "suspect";
      const cls = (kind === "confusable" || kind === "fullwidth-compat") ? "letter"
        : (kind === "space-variant" ? "zw" : "");
      html += '<span class="hidden-char ' + cls + '" title="' + esc(kind) + " · U+" + hex(cp) + '">' +
        esc(shortName(cp)) + "</span>";
    } else {
      html += esc(ch);
    }
    i += 1;
  }
  return html;
}

/* ------------------------------------------------------------- output card */
function renderOutput(box, opts) {
  const el = $(box);
  if (!el) return;
  el.classList.remove("empty");
  state.views[box] = opts.text || "";
  const chips = (opts.chips || [])
    .map((c) => '<span class="chip ' + (c.kind || "") + '">' + c.label + "</span>").join("");
  const views = opts.views || [];
  const first = views[0];
  const initial = opts.html !== undefined ? opts.html
    : (first ? (first.html || esc(first.value ?? "")) : esc(opts.text || ""));
  const pre = box + "-pre";
  el.innerHTML = `
    <div class="card-h"><h2>${esc(opts.title)}</h2>
      <div class="row-gap">
        <button class="btn tiny ghost" data-act="copy-text">copy</button>
        ${opts.extraButtons || ""}
      </div>
    </div>
    <div class="kv">${chips}</div>
    ${views.length ? `<div class="viewtabs">${views.map((v, i) =>
      `<button class="viewtab ${i === 0 ? "active" : ""}" data-view="${v.id}">${esc(v.label)}</button>`
    ).join("")}</div>` : ""}
    <pre class="outtext" id="${pre}">${initial}</pre>
    ${opts.body || ""}
    ${opts.cli ? `<div class="card-h" style="margin-top:.95rem">
        <h2>Same result from the CLI</h2>
        <div class="row-gap"><button class="btn tiny ghost" data-act="copy-cli">copy command</button></div>
      </div><pre class="cli">${esc(opts.cli)}</pre>` : ""}
    ${opts.note ? `<p class="hint" style="margin-top:.6rem">${opts.note}</p>` : ""}`;

  el.querySelectorAll("[data-view]").forEach((btn) => btn.addEventListener("click", () => {
    el.querySelectorAll("[data-view]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const v = views.find((x) => x.id === btn.dataset.view);
    const target = $(pre);
    if (v && v.html) target.innerHTML = v.html;
    else target.textContent = v ? v.value : "";
  }));
  const copyText = el.querySelector('[data-act="copy-text"]');
  if (copyText) copyText.addEventListener("click", () => copy(state.views[box] || ""));
  const copyCli = el.querySelector('[data-act="copy-cli"]');
  if (copyCli) copyCli.addEventListener("click", () => copy(opts.cli || "", "command copied"));
  if (opts.after) opts.after(el);
}

function chipsForEncode(r) {
  return [
    { label: `channel <b>${esc(r.scheme)}</b>` },
    { label: `payload <b>${r.payload_len} B</b>` },
    { label: `units <b>${r.units_used}</b> of ${r.carrier_units}` },
    { label: `bits <b>${r.bits_used}</b>` },
    { label: `spare ≈ <b>${r.capacity_bytes} B</b>` },
    { label: r.keyed ? "keyed" : "unkeyed", kind: r.keyed ? "info" : "" },
    { label: r.verified ? "round-trip verified" : "NOT verified", kind: r.verified ? "ok" : "bad" },
  ];
}

function cliEncode(r, key, placement) {
  const parts = ["glyphmark encode",
    "  --cover-file cover.txt",
    "  --payload-file payload.txt",
    "  --scheme " + r.scheme,
    "  --placement " + placement];
  if (key) parts.push('  --key "$GLYPHMARK_KEY"');
  parts.push("  -o marked.txt --report");
  return parts.join(" \\\n");
}

function cliDecode(scheme, key) {
  return "glyphmark decode \\\n  --text-file marked.txt \\\n  --scheme " + scheme +
    (key ? ' \\\n  --key "$GLYPHMARK_KEY"' : "") + "\n  # exit 3 = nothing found, 4 = wrong key";
}

function attemptsTable(err) {
  const attempts = (err.body && err.body.attempts) || [];
  if (!attempts.length) return "";
  return `<div class="table-wrap" style="margin-top:.6rem"><table>
    <thead><tr><th>channel tried</th><th>why it failed</th></tr></thead>
    <tbody>${attempts.map((a) => `<tr><td class="mono">${esc(a.scheme)}</td>
      <td>${esc(a.error)}</td></tr>`).join("")}</tbody></table></div>`;
}

function findingCard(f) {
  const chars = (f.characters || []).slice(0, 8)
    .map((c) => `<span class="chip mono">${esc(c.codepoint)}</span>`).join(" ");
  const tokens = (f.tokens || []).slice(0, 4)
    .map((t) => `<code>${esc(t.text)}</code> (${t.scripts.join("+")})`).join(" · ");
  return `<div class="finding ${f.severity}">
    <h4>${esc(f.title)} <span class="chip ${f.severity === "high" ? "bad" :
      (f.severity === "medium" ? "warn" : "info")}">${f.severity}</span>
      <span class="chip">${f.count} occurrence(s)</span>
      <span class="chip">remove with <b>${esc(f.remove_with || "—")}</b></span></h4>
    <p>${esc(f.why)}</p>
    ${chars ? `<p>${chars}</p>` : ""}
    ${f.payload_preview ? `<p><span class="chip bad">recovered payload</span> <code>${esc(f.payload_preview)}</code></p>` : ""}
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

function dots(n) { return "●".repeat(n) + "○".repeat(Math.max(0, 5 - n)); }

function schemeTable(rows) {
  return `<table>
    <thead><tr><th>channel</th><th>family</th><th>bit/unit</th><th>stealth</th>
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
      <td>${(c.schemes || []).map((s) => `<span class="chip">${esc(s)}</span>`).join(" ")}</td>
    </tr>`).join("")}</tbody></table>`;
  document.querySelectorAll("#charTable [data-char]").forEach((tr) => tr.addEventListener("click", () => {
    copy(tr.dataset.char, "character copied — paste it into Detect");
  }));
}

function setStageChecks(ids) {
  document.querySelectorAll("#stagePicker input").forEach((i) => {
    i.checked = ids.includes(i.value);
  });
}

function installVerifyButton() {
  const card = $("cliCheat").closest(".card");
  const btn = document.createElement("button");
  btn.className = "btn tiny block";
  btn.style.marginTop = ".6rem";
  btn.textContent = "Run self test for all channels (glyphmark verify)";
  const out = document.createElement("div");
  out.id = "verifyOut";
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> testing 13 channels…';
    try {
      const r = await api("verify", {});
      out.innerHTML = `<div class="kv"><span class="chip ${r.passed === r.total ? "ok" : "bad"}">
          ${r.passed}/${r.total} channels pass</span></div>
        <div class="table-wrap scroll" style="max-height:220px"><table>
        <thead><tr><th>channel</th><th>result</th><th>bits</th><th>carrier</th><th>detail</th></tr></thead>
        <tbody>${r.results.map((x) => `<tr><td class="mono">${esc(x.scheme)}</td>
          <td>${x.ok ? '<span class="chip ok">PASS</span>' : '<span class="chip bad">FAIL</span>'}</td>
          <td class="num">${x.bits_used}</td><td class="num">${x.carrier_units}</td>
          <td>${esc(x.error || "")}</td></tr>`).join("")}</tbody></table></div>`;
    } catch (err) { showErr("verify", err); }
    btn.disabled = false;
    btn.textContent = "Run self test for all channels (glyphmark verify)";
  });
  card.appendChild(btn);
  card.appendChild(out);
}

/* ------------------------------------------------------------ CLI cheat */
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
glyphmark verify                            # encode+extract round trip, all channels
glyphmark verify --scheme homoglyph --json
glyphmark serve --port 8000                 # this page + the JSON API under /api/*`;

/* ------------------------------------------------------ capacity arithmetic */
function carrierUnits(text, scheme) {
  const chars = [...text];
  if (scheme.family === "insert") {
    if (scheme.anchor_required) {
      const set = new Set((scheme.characters || []).map((c) => c.char));
      return chars.filter((ch) => !set.has(ch)).length;
    }
    return chars.length + 1;
  }
  const bases = new Set((scheme.characters || []).map((c) => c.base).filter(Boolean));
  return chars.filter((ch) => bases.has(ch)).length;
}

function capacityBytes(units, scheme) {
  // insert: 6B header + 4B crc ; substitute: 10B phase-A + 4B payload crc
  const overhead = scheme.family === "insert" ? (6 + 4) * 8 : (10 + 4) * 8;
  return Math.max(0, Math.floor((units * scheme.bits_per_unit - overhead) / 8));
}

/* =========================================================== UI controller
   Deliberately framework-free: Alpine in this page only decorates the theme
   toggle, so the lab still works if a CDN is blocked. */

const state = { views: {}, meta: null, last: "", tab: "embed", showKey: false };

const TAB_ACTION = { embed: "encode", extract: "decode", detect: "detect",
                     sanitize: "sanitize", inspect: "inspect" };
const FIELD = { cover: "cover", payload: "payload", decText: "decText",
                detText: "detText", sanText: "sanText", inspText: "inspText" };
const PASTE_TARGET = { extract: "decText", detect: "detText", sanitize: "sanText",
                       inspect: "inspText" };

function themeState() {
  const saved = (localStorage.getItem("gm-theme") || "dark") === "dark";
  return {
    dark: saved,
    sync() { UI.applyTheme(this.dark); },
    toggle() { this.dark = !this.dark; UI.applyTheme(this.dark); },
  };
}

const UI = {
  /* ------------------------------------------------------------- shell */
  boot() {
    UI.applyTheme((localStorage.getItem("gm-theme") || "dark") === "dark");
    UI.wire();
    UI.setTab("embed");
    UI.fetchMeta();
  },

  applyTheme(dark) {
    document.body.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("gm-theme", dark ? "dark" : "light");
  },

  setTab(id) {
    state.tab = id;
    document.querySelectorAll(".tab").forEach((b) =>
      b.classList.toggle("active", b.dataset.tab === id));
    document.querySelectorAll(".panel").forEach((p) => {
      p.hidden = p.id !== "panel-" + id;
    });
  },

  async fetchMeta() {
    try {
      const res = await fetch("/api/meta");
      state.meta = await res.json();
      $("channelCount").textContent = state.meta.schemes.length;
      $("versionTag").textContent = state.meta.version;
      UI.buildSelects();
      UI.buildStagePicker();
      UI.buildReference();
      $("cover").value = state.meta.samples.cover;
      $("payload").value = JSON.stringify(state.meta.samples.payload_json);
      UI.capacity();
    } catch (err) {
      toast("could not reach <b>/api/meta</b>: " + esc(err.message), "err", 9000);
    }
  },

  wire() {
    document.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-tab]");
      if (tab) { UI.setTab(tab.dataset.tab); return; }
      const act = event.target.closest("[data-action]");
      if (!act) return;
      const name = act.dataset.action;
      if (name === "sample") { UI.fillSample(act.dataset.field); return; }
      if (name === "clear") { UI.clear(act.dataset.field); return; }
      if (name === "paste-last") { UI.pasteLast(act.dataset.target); return; }
      if (name === "toggle-key") { UI.toggleKey(); return; }
      if (name === "stages") { UI.setStages(act.dataset.mode); return; }
      if (UI[name]) UI[name]();
    });
    document.addEventListener("input", (event) => {
      if (event.target.dataset.event === "capacity") UI.capacity();
      if (event.target.id === "schemeSearch") UI.filterSchemes(event.target.value);
    });
    document.addEventListener("change", (event) => {
      if (event.target.dataset.event === "capacity") UI.capacity();
      if (event.target.id === "onlySuspect") UI.inspect();
    });
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        const action = TAB_ACTION[state.tab];
        if (action) UI[action]();
      }
    });
  },

  busy(name, on) {
    const spin = $("spin-" + name);
    if (spin) spin.hidden = !on;
    const btn = document.querySelector('[data-action="' + name + '"]');
    if (btn) btn.disabled = on;
  },

  /* ------------------------------------------------------------- inputs */
  fillSample(field) {
    if (!state.meta) return;
    $(FIELD[field]).value = field === "cover"
      ? state.meta.samples.cover
      : JSON.stringify(state.meta.samples.payload_json);
    UI.capacity();
  },

  clear(field) {
    const el = $(FIELD[field]);
    if (el) el.value = "";
    UI.capacity();
  },

  pasteLast(target) {
    if (!state.last) { toast("nothing embedded yet — embed a watermark first", "info"); return; }
    const el = $(PASTE_TARGET[target]);
    if (!el) return;
    el.value = state.last;
    toast("loaded the last watermarked output", "ok", 2600);
  },

  toggleKey() {
    state.showKey = !state.showKey;
    const input = $("encKey");
    input.type = state.showKey ? "text" : "password";
    const btn = document.querySelector('[data-action="toggle-key"]');
    if (btn) btn.textContent = state.showKey ? "hide" : "show";
    input.focus();
  },

  buildSelects() {
    const options = state.meta.schemes
      .map((s) => `<option value="${esc(s.id)}">${esc(s.id)} — ${esc(s.label)}</option>`).join("");
    $("encScheme").innerHTML = options;
    $("decScheme").innerHTML = '<option value="auto">auto — sweep all channels</option>' + options;
    $("placement").innerHTML = state.meta.placements
      .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
  },

  buildStagePicker() {
    $("stagePicker").innerHTML = state.meta.sanitize_stages.map((s) => `
      <label class="${s.default ? "" : "opt"}" title="${esc(s.description)}">
        <input type="checkbox" value="${esc(s.id)}" ${s.default ? "checked" : ""}>
        <span><span class="sid">${esc(s.id)}</span><br>${esc(s.label)}</span>
      </label>`).join("");
    $("stageTable").innerHTML = stageTable(state.meta.sanitize_stages);
    $("cliCheat").textContent = CLI_CHEAT;
    installVerifyButton();
  },

  buildReference() {
    buildCharTable("");
    UI.filterSchemes("");
  },

  setStages(mode) {
    if (mode === "default") setStageChecks(state.meta.default_pipeline);
    else if (mode === "all") setStageChecks(state.meta.sanitize_stages.map((s) => s.id));
    else setStageChecks([]);
  },

  filterSchemes(query) {
    if (!state.meta) return;
    const q = (query || "").toLowerCase();
    const rows = state.meta.schemes.filter((s) => !q ||
      [s.id, s.label, s.family, s.carrier, s.detection, (s.tags || []).join(" ")]
        .join(" ").toLowerCase().includes(q));
    $("schemeTable").innerHTML = schemeTable(rows);
    document.querySelectorAll("[data-detail]").forEach((btn) => btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const row = btn.closest("tr");
      const next = row.nextElementSibling;
      if (next && next.dataset.detailof === btn.dataset.detail) {
        next.remove();
        btn.textContent = "detail";
        return;
      }
      const scheme = state.meta.schemes.find((x) => x.id === btn.dataset.detail);
      const tr = document.createElement("tr");
      tr.dataset.detailof = scheme.id;
      tr.innerHTML = '<td colspan="8">' + detail(scheme) + "</td>";
      row.after(tr);
      btn.textContent = "hide";
    }));
  },

  capacity() {
    const box = $("capBox");
    if (!box || !state.meta) return;
    const scheme = state.meta.schemes.find((s) => s.id === val("encScheme"));
    if (!scheme) { box.innerHTML = ""; return; }
    const units = carrierUnits(val("cover"), scheme);
    const cap = capacityBytes(units, scheme);
    const need = bytesOf(val("payload"));
    const pct = cap ? Math.min(100, Math.round((need / cap) * 100)) : (need ? 100 : 0);
    box.innerHTML = `
      <div>${scheme.bits_per_unit} bit/unit · <b>${units.toLocaleString()}</b> carrier units in
        this cover · capacity ≈ <b>${cap} B</b> · payload <b>${need} B</b></div>
      <div class="meter ${need > cap ? "hot" : ""}" style="margin-top:.35rem">
        <i style="width:${pct}%"></i></div>
      ${need > cap ? `<div class="full" style="margin-top:.3rem">Payload exceeds this channel.
        Use a longer cover or a denser channel (<code>vs-bytes</code>, <code>tags</code>).</div>` : ""}`;
  },

  /* ------------------------------------------------------------ actions */
  async encode() {
    UI.busy("encode", true);
    try {
      const r = await api("encode", {
        cover: val("cover"), payload: val("payload"), scheme: val("encScheme"),
        key: val("encKey"), placement: val("placement"),
      });
      state.last = r.text;
      const info = await api("inspect", { text: r.text, limit: 20000 });
      renderOutput("encOut", {
        title: "Watermarked text",
        chips: chipsForEncode(r),
        text: r.text,
        views: [
          { id: "annot", label: "annotated (visual aid)",
            html: '<span class="annotated">' + annotate(r.text, info) + "</span>" },
          { id: "raw", label: "raw text", value: r.text },
          { id: "esc", label: "\\u escapes", value: escapedView(r.text) },
          { id: "hex", label: "utf-8 hex", value: utf8Hex(r.text) },
        ],
        cli: cliEncode(r, val("encKey"), val("placement")),
        note: "Copy <b>raw text</b> to paste it elsewhere — the annotated view only exists so you " +
          "can see what was written. " + r.units_used + " watermark units were emitted.",
        extraButtons: '<button class="btn tiny ghost" data-act="send">→ scan it</button>',
        after: (el) => {
          const btn = el.querySelector('[data-act="send"]');
          if (btn) btn.addEventListener("click", () => {
            $("detText").value = r.text;
            UI.setTab("detect");
            UI.detect();
          });
        },
      });
      toast("watermark embedded and round-trip verified", "ok");
    } catch (err) { showErr("embed", err); }
    UI.busy("encode", false);
  },

  async decode() {
    UI.busy("decode", true);
    try {
      const r = await api("decode", { text: val("decText"), scheme: val("decScheme"),
                                      key: val("decKey") });
      renderOutput("decOut", {
        title: "Recovered payload",
        chips: [
          { label: `channel <b>${esc(r.scheme)}</b>` },
          { label: `<b>${r.payload_len} B</b> payload` },
          { label: `bits read <b>${r.bits_read}</b>` },
          { label: r.keyed ? "keyed frame" : "unkeyed frame", kind: "info" },
          { label: "magic + CRC32 valid", kind: "ok" },
        ],
        text: r.payload_text === null ? r.payload_hex : r.payload_text,
        views: [
          { id: "text", label: "text",
            value: r.payload_text === null ? "(binary — see hex/base64)" : r.payload_text },
          { id: "hex", label: "hex", value: r.payload_hex },
          { id: "b64", label: "base64", value: r.payload_base64 },
        ],
        cli: cliDecode(r.scheme, val("decKey")),
        note: "A valid magic byte and CRC32 make this a positive identification, not a heuristic.",
      });
      toast("payload recovered", "ok");
    } catch (err) {
      renderOutput("decOut", {
        title: "No payload recovered",
        chips: [{ label: "extraction failed", kind: "bad" },
                { label: `exit <b>${err.code || 1}</b>`, kind: "bad" }],
        text: "",
        body: '<p class="hint">' + esc(err.message) + "</p>" + attemptsTable(err),
        cli: cliDecode(val("decScheme"), val("decKey")),
        note: "Usual causes: the text went through a normalizer or sanitizer, a different channel " +
          "was used, or the frame is keyed and the key is missing.",
      });
      showErr("extract", err);
    }
    UI.busy("decode", false);
  },

  async detect() {
    UI.busy("detect", true);
    try {
      const r = await api("detect", { text: val("detText") });
      const kind = r.verdict === "clean" ? "ok" : (r.risk_score >= 60 ? "bad" : "warn");
      const stages = [...new Set(r.findings.map((f) => f.remove_with).filter(Boolean))];
      renderOutput("detOut", {
        title: "Covert-channel analysis",
        chips: [
          { label: `verdict <b>${esc(r.verdict)}</b>`, kind },
          { label: `suspect <b>${r.suspect_total}</b> / ${r.codepoints} code points` },
          { label: `NFKC identical: <b>${r.nfkc_equal ? "yes" : "no"}</b>` },
          { label: `frame signatures <b>${r.frame_signatures.length}</b>`,
            kind: r.frame_signatures.length ? "bad" : "" },
        ],
        text: val("detText"),
        body: `
          <div class="gauge">
            <div class="num">${r.risk_score}</div>
            <div class="meter track ${r.risk_score >= 60 ? "hot" : ""}">
              <i style="width:${r.risk_score}%"></i></div>
            <div class="chip">${r.findings.length} finding(s)</div>
          </div>
          ${r.tag_block_mirror ? `<p class="chip bad">Plane-14 tags decode to
            <code>${esc(r.tag_block_mirror.slice(0, 160))}</code></p>` : ""}
          <div class="stack">${r.findings.map(findingCard).join("") ||
            '<p class="hint">Nothing anomalous. Keep normalizing untrusted text (NFKC) before it ' +
            'reaches a model, template or database.</p>'}</div>
          <p class="hint">${esc(r.recommendation)}</p>`,
        cli: "glyphmark detect --text-file suspect.txt --fail-on-risk 60",
        extraButtons: stages.length
          ? '<button class="btn tiny" data-act="clean">sanitize with these stages</button>' : "",
        after: (el) => {
          const btn = el.querySelector('[data-act="clean"]');
          if (btn) btn.addEventListener("click", () => {
            $("sanText").value = val("detText");
            setStageChecks(stages);
            UI.setTab("sanitize");
            UI.sanitize();
          });
        },
      });
    } catch (err) { showErr("detect", err); }
    UI.busy("detect", false);
  },

  async sanitize() {
    UI.busy("sanitize", true);
    try {
      const stages = [...document.querySelectorAll("#stagePicker input:checked")].map((i) => i.value);
      if (!stages.length) { toast("select at least one stage", "err"); UI.busy("sanitize", false); return; }
      const r = await api("sanitize", { text: val("sanText"), stages });
      renderOutput("sanOut", {
        title: "Sanitized text",
        chips: [
          { label: `<b>${r.codepoints_before} → ${r.codepoints_after}</b> code points` },
          { label: `<b>${r.removed_total}</b> removed / rewritten` },
          { label: r.identical ? "nothing to remove" : "text modified",
            kind: r.identical ? "ok" : "warn" },
          { label: `channels targeted <b>${r.channels_targeted.length}</b>` },
        ],
        text: r.text,
        views: [
          { id: "clean", label: "clean text", value: r.text },
          { id: "esc", label: "\\u escapes", value: escapedView(r.text) },
        ],
        body: `<div class="table-wrap scroll" style="margin-top:.8rem;max-height:200px"><table>
            <thead><tr><th>stage</th><th class="num">removed</th><th class="num">length</th></tr></thead>
            <tbody>${r.stages.map((s) => `<tr><td class="mono">${esc(s.id)}</td>
              <td class="num">${s.removed}</td>
              <td class="num">${s.before_len}→${s.after_len}</td></tr>`).join("")}</tbody>
          </table></div>`,
        cli: "glyphmark sanitize --text-file in.txt -o clean.txt" +
          stages.map((s) => " --stage " + s).join(""),
        note: "Prove it worked: press <b>re-detect</b> — the clean output should come back clean.",
        extraButtons: '<button class="btn tiny ghost" data-act="redetect">re-detect</button>',
        after: (el) => {
          const btn = el.querySelector('[data-act="redetect"]');
          if (btn) btn.addEventListener("click", () => {
            $("detText").value = r.text;
            UI.setTab("detect");
            UI.detect();
          });
        },
      });
      toast("sanitized", "ok");
    } catch (err) { showErr("sanitize", err); }
    UI.busy("sanitize", false);
  },

  async inspect() {
    UI.busy("inspect", true);
    try {
      const only = $("onlySuspect").checked;
      const text = val("inspText");
      const r = await api("inspect", { text });
      const rows = r.rows.filter((x) => !only || x.suspect);
      $("inspOut").innerHTML = `
        <div class="kv">
          <span class="chip"><b>${r.codepoints}</b> code points</span>
          <span class="chip"><b>${r.utf8_bytes}</b> utf-8 bytes</span>
          <span class="chip"><b>${r.utf16_units}</b> utf-16 units</span>
          <span class="chip ${r.suspect_count ? "bad" : "ok"}"><b>${r.suspect_count}</b> suspicious</span>
          ${r.truncated ? '<span class="chip warn">table truncated</span>' : ""}
        </div>
        <span class="annotated" style="display:block;margin-bottom:.9rem">
          ${annotate(text, r)}</span>
        <div class="table-wrap scroll"><table>
          <thead><tr><th>#</th><th>cp</th><th>cat</th><th>script</th><th>utf-8</th>
            <th>name</th><th>flags</th></tr></thead>
          <tbody>${rows.slice(0, 800).map((x) => `<tr>
            <td class="num">${x.index}</td><td class="mono">${x.codepoint}</td>
            <td class="mono">${x.category}</td><td>${x.script}</td>
            <td class="mono">${x.utf8}</td><td>${esc(x.name)}</td>
            <td>${x.flags.map((f) => `<span class="chip ${x.suspect ? "warn" : ""}">${f}</span>`)
              .join(" ") || "—"}</td></tr>`).join("")}</tbody></table></div>`;
    } catch (err) { showErr("inspect", err); }
    UI.busy("inspect", false);
  },
};

window.GlyphMarkUI = UI;
window.themeState = themeState;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", UI.boot);
} else {
  UI.boot();
}
