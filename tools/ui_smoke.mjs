/**
 * Headless DOM smoke test for the GlyphMark web UI.
 *   node tools/ui_smoke.mjs                 # expects http://127.0.0.1:8123
 *   GM_BASE=http://host:port node tools/ui_smoke.mjs
 *
 * Loads the real index.html + app.js into jsdom, stubs the CDN assets, and drives the
 * full flow: embed -> auto re-scan -> extract -> detect (+ severity filter) ->
 * sanitize (+ verified clean) -> inspect -> reference, plus the UX layer: keyboard
 * shortcuts, help overlay, pipeline ribbon, channel picker, recommendations, persistence.
 * Needs a running server plus the dev-only jsdom dependency:
 *   uv run glyphmark serve --port 8123 &
 *   npm install && node tools/ui_smoke.mjs
 */
import { JSDOM, VirtualConsole } from "jsdom";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const APP_JS = fileURLToPath(new URL("../src/glyphmark/web/static/app.js", import.meta.url));

const BASE = process.env.GM_BASE || "http://127.0.0.1:8123";
const fails = [];
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
  if (!ok) fails.push(name);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => {
  if (!/Could not parse CSS|not implemented/i.test(String(e))) console.error("[jsdom]", e.message);
});
vc.on("error", (...a) => console.error("[console.error]", ...a));
vc.on("warn", (...a) => console.error("[console.warn]", ...a));
vc.on("log", (...a) => { if (/glyphmark/.test(a.map(String).join(" "))) console.log("[page log]", ...a.map(String)); });

const html = await (await fetch(BASE + "/")).text();
const dom = new JSDOM(html, {
  url: BASE + "/",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole: vc,
});
const { window } = dom;
const { document } = window;
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
Object.defineProperty(window, "innerWidth", { value: 1440, writable: true });
window.HTMLElement.prototype.scrollIntoView = () => {};
window.localStorage.clear();

/* jsdom has no fetch of its own: bridge to Node's, resolving repo-relative API paths */
window.fetch = (input, init) => fetch(new URL(typeof input === "string" ? input : input.url, BASE + "/"), init);

/* strip CDN <script> tags (offline determinism) and inject the local app */
document.querySelectorAll("script[src^='https://']").forEach((s) => s.remove());
const app = document.createElement("script");
app.textContent = await readFile(APP_JS, "utf8");
document.body.appendChild(app);

/* top-level `const` bindings are lexical globals: reach them through window.eval */
const G = () => window.eval("({ state, UI, TABS, CLI_CHEAT })");
await (async () => {
  for (let i = 0; i < 80; i += 1) {
    try { if (G().state.meta) return; } catch (e) { /* app still booting */ }
    await sleep(100);
  }
})();
const g = G();
const { state, UI } = g;
const $ = (id) => document.getElementById(id);
const click = (el) => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
const key = (k, init = {}) => document.dispatchEvent(new window.KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true, ...init }));
const pick = async (id) => {
  if ($("schemePop").hidden) click($("schemeBtn"));
  $("schemeFilter").value = id;
  $("schemeFilter").dispatchEvent(new window.Event("input", { bubbles: true }));
  $("schemeFilter").dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  await wait(() => state.scheme === id);
};
const wait = async (fn, ms = 12000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (fn()) return true; await sleep(80); }
  return false;
};
const text = (id) => $(id).textContent;
/* a card only has view tabs once renderOutput() has replaced its placeholder */
const rendered = (id) => !!$(id).querySelector("[data-view]");
const steps = () => [...document.querySelectorAll("#ribbon [data-step]")];

/* ---- boot ----------------------------------------------------------------- */
check("meta loaded", !!state.meta);
check("channels registered", Object.keys(state.schemesById).length === 13,
  Object.keys(state.schemesById).length + " channels");
check("header counts channels", $("channelCount").textContent === "13");
check("reference tables populated", text("schemeTable").includes("zw-octal") && text("charTable").includes("U+2062"));
check("CLI cheat sheet rendered", $("cliCheat").textContent.includes("glyphmark sanitize"));
const nStages = state.meta.sanitize_stages.length;
const nDefaults = state.meta.sanitize_stages.filter((x) => x.default).length;
check("stage checkboxes built", document.querySelectorAll("#stagePicker input").length === nStages, String(nStages));
check("default stages pre-checked", document.querySelectorAll("#stagePicker input:checked").length === nDefaults,
  String(nDefaults));
check("exit-code table in help",
  $("codeTable").children.length === Object.keys(state.meta.exit_codes).length);

/* ---- accessibility scaffolding -------------------------------------------- */
check("skip link present", document.querySelector("a.skip")?.textContent.includes("Skip"));
check("6 tabs + 6 panels with ARIA roles",
  document.querySelectorAll('[role="tab"]').length === 6 &&
  document.querySelectorAll('[role="tabpanel"]').length === 6);
check("every textarea has a <label for>", ["cover", "payload", "decText", "detText", "sanText", "inspText"]
  .every((id) => document.querySelector(`label[for="${id}"]`)));
check("live result regions", ["encOut", "decOut", "detOut", "sanOut", "inspOut"]
  .every((id) => $(id).getAttribute("aria-live") === "polite"));

/* ---- pipeline ribbon ------------------------------------------------------ */
check("ribbon shows 4 pending steps", steps().length === 4 && steps().every((s) => s.dataset.state === "todo"));

/* ---- channel combobox ----------------------------------------------------- */
click($("schemeBtn"));
check("picker opens", $("schemePop").hidden === false && $("schemeBtn").getAttribute("aria-expanded") === "true");
check("picker lists every channel", document.querySelectorAll("#schemeOptions [data-pick]").length === 13);
$("schemeFilter").value = "homoglyph";
$("schemeFilter").dispatchEvent(new window.Event("input", { bubbles: true }));
check("picker filters as you type", document.querySelectorAll("#schemeOptions [data-pick]").length === 1);
$("schemeFilter").dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
$("schemeFilter").dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
check("keyboard selection applies", state.scheme === "homoglyph" && $("schemePop").hidden === true,
  $("pickerId").textContent);

/* ---- keyboard shortcuts --------------------------------------------------- */
key("3", { altKey: true });
check("Alt+3 switches panel", state.tab === "detect" && !$("panel-detect").hidden && $("panel-embed").hidden);
key("1", { altKey: true });
check("Alt+1 returns to embed", !$("panel-embed").hidden);
key("?");
check("? opens the help overlay", $("help").hidden === false && $("help").getAttribute("aria-modal") === "true");
key("Escape");
check("Escape closes it", $("help").hidden === true);

/* ---- embed ---------------------------------------------------------------- */
click(document.querySelector('[data-action="sample"][data-field="cover"]'));
click(document.querySelector('[data-action="sample"][data-field="payload"]'));
const COVER_TEXT = $("cover").value, PAYLOAD_TEXT = $("payload").value;
check("sample buttons fill the fields", COVER_TEXT.length > 60 && PAYLOAD_TEXT.length > 4,
  `${COVER_TEXT.length} cover chars, ${PAYLOAD_TEXT.length} payload bytes`);
check("live stats under the textarea", await wait(() => text("cover-stats").includes("code points")));
check("capacity meter computed", text("capBox").includes("carrier units"));
check("recommended channels offered", await wait(() => document.querySelectorAll("#reco [data-scheme]").length >= 2),
  $("reco").textContent.trim().replace(/\s+/g, " ").slice(0, 70));

await pick("ascii-ctrl");
check("recommendations stay available for a thin channel",
  document.querySelectorAll("#reco [data-scheme]").length >= 1 && text("capBox").includes("carrier units"));
$("cover").value = "way too short to carry anything";
$("cover").dispatchEvent(new window.Event("input", { bubbles: true }));
await wait(() => text("reco").includes("cannot hold"));
check("thin carrier is flagged before submitting", text("reco").includes("cannot hold"),
  $("reco").textContent.trim().replace(/\s+/g, " ").slice(0, 60));
$("cover").value = COVER_TEXT;
$("cover").dispatchEvent(new window.Event("input", { bubbles: true }));
await wait(() => !text("reco").includes("cannot hold"));

await pick("vs-bytes");
check("switched to the highest-density channel", state.scheme === "vs-bytes");

await pick("zw-binary");
click(document.querySelector('[data-action="encode"]'));
check("embed result rendered", await wait(() => rendered("encOut") && text("encOut").includes("Watermarked text")));
check("round-trip verified chip", text("encOut").includes("round-trip verified"));
check("annotated view reveals the payload", $("encOut").innerHTML.includes("hidden-char"));
check("what-changed diff present", text("encOut").includes("What changed") &&
  text("encOut").includes("invisible symbols inserted"));
check("equivalent CLI command shown", text("encOut").includes("glyphmark encode"));
const marked = state.views.encOut;
check("payload really embedded", !marked.includes(PAYLOAD_TEXT) && marked.length > COVER_TEXT.length,
  `cover=${COVER_TEXT.length} marked=${marked.length}`);
check("embed offers 4 result views", document.querySelectorAll("#encOut [data-view]").length === 4);
click(document.querySelector('#encOut [data-view="bytes"]'));
check("UTF-8 byte view renders hex", /^[0-9A-F ]+$/m.test(text("encOut-pre")));
click(document.querySelector('#encOut [data-view="rendered"]'));
check("auto re-scan runs after embed", await wait(() => text("encOut").includes("auto re-scan")));
check("auto re-scan confirms the mark", text("encOut").includes("watermark-confirmed"));
check("ribbon advanced", steps()[1].dataset.state === "done" && steps()[2].dataset.state === "done",
  steps().map((s) => `${s.dataset.step}:${s.dataset.state}`).join(" "));

/* ---- persistence ---------------------------------------------------------- */
check("session persisted, keys excluded", await wait(() => {
  const raw = JSON.parse(window.localStorage.getItem("glyphmark-session-v1") || "{}");
  return raw.cover?.length > 60 && raw.marked?.length > 0 && raw.encKey === undefined && raw.tab;
}));

/* ---- extract -------------------------------------------------------------- */
key("2", { altKey: true });
click(document.querySelector('[data-action="paste-last"][data-target="extract"]'));
check("paste-last reuses the last generated text", $("decText").value === marked);
key("Enter", { ctrlKey: true });
check("Ctrl+Enter runs the panel action", await wait(() => rendered("decOut") &&
  text("decOut").includes("Recovered payload")));
check("payload recovered intact", state.views.decOut === PAYLOAD_TEXT, JSON.stringify(state.views.decOut));
check("magic + CRC chip shown", text("decOut").includes("magic + CRC32 valid"));
check("extract offers 4 result views", document.querySelectorAll("#decOut [data-view]").length === 4);
click(document.querySelector('#decOut [data-view="hex"]'));
check("payload hex view renders", /^[0-9A-F ]+$/i.test(text("decOut-pre")), text("decOut-pre").slice(0, 24));
click(document.querySelector('#decOut [data-view="b64"]'));
check("payload base64 view renders", text("decOut-pre").length > 4);

/* ---- detect --------------------------------------------------------------- */
key("3", { altKey: true });
click(document.querySelector('[data-action="paste-last"][data-target="detect"]'));
click(document.querySelector('[data-action="detect"]'));
check("detection report rendered", await wait(() => text("detOut").includes("Detection report") &&
  !!$("detOut").querySelector(".gauge")));
check("risk score rendered", /^\d+$/.test($("detOut").querySelector(".num")?.textContent || ""));
check("verdict + recommendation shown", text("detOut").includes("watermark-confirmed") &&
  text("detOut").includes("recommendation"));
check("frame confirmed as high risk", $("detOut").innerHTML.includes("finding high confirmed") &&
  text("detOut").includes("watermark-confirmed"));
check("severity filter present", document.querySelectorAll("#detOut .sevfilter [data-sev]").length === 5);
const findingEls = () => [...document.querySelectorAll("#detOut .finding")];
const total = findingEls().length;
const sevCounts = findingEls().reduce((acc, f) => {
  acc[f.dataset.sev] = (acc[f.dataset.sev] || 0) + 1;
  return acc;
}, {});
// pick a severity that is guaranteed to narrow the list (an empty one if all findings share a level)
const wanted = Object.keys(sevCounts).find((k) => sevCounts[k] < total) || "medium";
click(document.querySelector(`#detOut .sevfilter [data-sev="${wanted}"]`));
const shown = findingEls().filter((f) => f.style.display !== "none");
check("severity filter narrows the list", shown.length === (sevCounts[wanted] || 0) && shown.length < total,
  `${wanted}: ${shown.length}/${total}`);
click(document.querySelector('#detOut .sevfilter [data-sev="all"]'));
check("severity filter restores", findingEls().every((f) => f.style.display !== "none"));
check("download JSON offered", !!document.querySelector('#detOut [data-act="dl-json"]'));
check("findings expose code points to copy", document.querySelectorAll("#detOut [data-copy]").length > 3);

/* ---- sanitize ------------------------------------------------------------- */
key("4", { altKey: true });
click(document.querySelector('[data-action="paste-last"][data-target="sanitize"]'));
click(document.querySelector('[data-action="stages"][data-mode="all"]'));
check("all stages selectable",
  document.querySelectorAll("#stagePicker input:checked").length === nStages);
click(document.querySelector('[data-action="stages"][data-mode="default"]'));
check("default pipeline restored",
  document.querySelectorAll("#stagePicker input:checked").length === nDefaults);
click(document.querySelector('[data-action="sanitize"]'));
check("sanitized output rendered", await wait(() => rendered("sanOut") && text("sanOut").includes("Sanitized text")));
check("payload destroyed", !state.views.sanOut.includes(PAYLOAD_TEXT));
check("stage accounting table", text("sanOut").includes("Stage accounting") && text("sanOut").includes("strip_zero_width"));
check("output is plain ASCII", !/[^\x00-\x7F]/.test(state.views.sanOut), state.views.sanOut.slice(0, 40));
check("verified-clean badge after sanitize", await wait(() => text("sanOut").includes("no anomaly")));
check("ribbon marks sanitize done", steps()[3].dataset.state === "done");
click(document.querySelector('[data-action="stages"][data-mode="none"]'));
click(document.querySelector('[data-action="sanitize"]'));
check("empty pipeline leaves the text untouched",
  await wait(() => text("sanOut").includes("removed 0") && text("sanOut").includes("text unchanged")));

/* ---- inspect -------------------------------------------------------------- */
key("5", { altKey: true });
$("inspText").value = marked;
click(document.querySelector('[data-action="inspect"]'));
check("inspector table rendered", await wait(() => text("inspOut").includes("code points")));
check("inspector shows rows", document.querySelectorAll("#inspOut tbody tr").length > 10);
check("visual tile strip", document.querySelectorAll("#inspOut .tile").length > 20);
check("flag filter chips", document.querySelectorAll("#inspOut [data-flag]").length > 1);
const allRows = document.querySelectorAll("#inspOut #inspBody tr").length;
const firstFlag = document.querySelectorAll("#inspOut [data-flag]")[1];
click(firstFlag);
const flagged = [...document.querySelectorAll("#inspOut #inspBody tr")].filter((r) => r.style.display !== "none");
check("flag filter works", flagged.length >= 1 && flagged.length <= allRows, `${flagged.length}/${allRows}`);

/* ---- reference ------------------------------------------------------------ */
key("6", { altKey: true });
$("charSearch").value = "INVISIBLE TIMES";
$("charSearch").dispatchEvent(new window.Event("input", { bubbles: true }));
check("char table filters", await wait(() => text("charTable").includes("INVISIBLE TIMES")));
click(document.querySelector("[data-detail='tags']"));
check("channel detail opens in the inspect panel",
  $("panel-inspect").hidden === false && $("panel-inspect").hidden === false &&
  text("inspOut").includes("U+E0020") && text("inspOut").includes("TAG"),
  text("inspOut").slice(0, 60));

/* ---- error paths ---------------------------------------------------------- */
UI.switchTab("embed");
$("cover").value = "short";
$("payload").value = "a".repeat(500);
await UI.encode();
check("carrier-too-small is caught before the API call",
  [...document.querySelectorAll("#toasts .toast")].some((t) => t.textContent.includes("carrier too small")));
$("cover").value = "";
await UI.encode();
check("missing input is caught client-side",
  [...document.querySelectorAll("#toasts .toast")].some((t) => t.textContent.includes("required")));

/* ---- extract failure path -------------------------------------------------- */
UI.switchTab("extract");
$("decText").value = "totally clean text with nothing hidden in it at all";
$("decScheme").value = "auto";
await UI.decode();
check("failed sweep explains itself", text("decOut").includes("No valid frame") ||
  [...document.querySelectorAll("#toasts .toast")].some((t) => t.textContent.includes("decode")));

console.log("");
if (fails.length) {
  console.log(`${fails.length} check(s) failed:\n - ` + fails.join("\n - "));
  process.exit(1);
}
console.log("all UI smoke checks passed");
process.exit(0);
