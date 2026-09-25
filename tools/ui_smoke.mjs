/* Headless DOM smoke test for the GlyphMark web UI (jsdom + the live Flask API).

   It boots the real served page in jsdom, executes app.js, then drives the UI the
   way a user would: embed -> annotated view -> scan -> sanitize -> re-detect ->
   extract -> inspect -> in-page self test.

       npm --prefix tools install jsdom          # one-off
       uv run glyphmark serve --port 8123 &      # start the UI
       GM_BASE=http://127.0.0.1:8123 node tools/ui_smoke.mjs

   Exits non-zero if any check fails, so it can run in CI next to pytest. */
import { JSDOM, VirtualConsole } from "jsdom";

const BASE = process.env.GM_BASE || "http://127.0.0.1:8123";
const problems = [];
const ok = (label, cond, extra = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${extra ? " — " + extra : ""}`);
  if (!cond) problems.push(label);
};

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => problems.push("jsdomError: " + e.message));
vc.on("error", (...a) => problems.push("console.error: " + a.join(" ")));

const html = await (await fetch(BASE + "/")).text();
const appjs = await (await fetch(BASE + "/static/app.js")).text();

const dom = new JSDOM(html, { url: BASE + "/", runScripts: "dangerously", virtualConsole: vc });
const { window } = dom;
window.fetch = (url, opts) => fetch(new URL(url, BASE).href, opts);
window.eval(appjs);

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const click = (sel) => window.document.querySelector(sel)?.dispatchEvent(
  new window.MouseEvent("click", { bubbles: true }));
const $ = (sel) => window.document.querySelector(sel);
const text = (sel) => ($(sel)?.textContent || "").trim();

await wait(1500);
ok("boot populated the channel <select>", $("#encScheme").options.length === 13);
ok("channel counter pill filled", text("#channelCount") === "13", text("#channelCount"));
ok("capacity meter computed", /capacity ≈/.test(text("#capBox")), text("#capBox").slice(0, 70));
ok("stage picker rendered", window.document.querySelectorAll("#stagePicker input").length === 16);
ok("reference tables rendered", /zw-binary/.test(text("#schemeTable")) && /\u200B|U\+200B/.test(text("#charTable")));
ok("CLI cheat sheet rendered", /glyphmark serve/.test(text("#cliCheat")));

// --- embed -----------------------------------------------------------------
click('[data-action="encode"]');
await wait(1800);
const encOut = text("#encOut");
ok("embed produced a verified frame", /round-trip verified/.test(encOut), encOut.slice(0, 60));
ok("embed shows annotated view", /ZWSP|TAG:|VS\d/.test($("#encOut pre").textContent));
ok("embed shows the CLI equivalent", /glyphmark encode/.test(encOut));
const rawView = [...window.document.querySelectorAll("#encOut [data-view]")];
rawView.find((b) => b.textContent.includes("raw"))?.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const rawText = $("#encOut pre").textContent;
ok("raw view contains real watermark chars",
   [...rawText].some((c) => c.codePointAt(0) >= 0x200b), "len=" + rawText.length);

// --- scan it (detect) ------------------------------------------------------
click('#encOut [data-act="send"]');
await wait(1500);
ok("→ scan switched to the detect panel", $("#panel-detect").hidden === false && $("#panel-embed").hidden === true);
const detOut = text("#detOut");
ok("detect reports a confirmed watermark", /watermark-confirmed/.test(detOut), detOut.slice(0, 60));
ok("detect renders a finding card", /remove with/.test(detOut));

// --- sanitize from the finding ---------------------------------------------
click('#detOut [data-act="clean"]');
await wait(1600);
ok("sanitize ran and cleaned the text", /removed \/ rewritten/.test(text("#sanOut")), text("#sanOut").slice(0, 60));
click('#sanOut [data-act="redetect"]');
await wait(1500);
ok("re-detect comes back clean", /clean/.test(text("#detOut")));

// --- extract ---------------------------------------------------------------
click('[data-tab="extract"]');
ok("tabs switch panels", $("#panel-extract").hidden === false);
const enc = await (await fetch(BASE + "/api/encode", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ cover: $("#cover").value, payload: "id=7",
                         scheme: "fullwidth" }) })).json();
$("#decText").value = enc.text;
click('[data-action="decode"]');
await wait(1500);
ok("extract recovers the payload over the fullwidth channel",
   /Recovered payload/.test(text("#decOut")) && /fullwidth/.test(text("#decOut")));

// --- failure path ----------------------------------------------------------
$("#decText").value = "completely ordinary text with no marks at all, nothing to find";
click('[data-action="decode"]');
await wait(1500);
ok("failed extraction explains itself", /No payload recovered/.test(text("#decOut")));

// --- inspect ---------------------------------------------------------------
click('[data-tab="inspect"]');
$("#inspText").value = "hello" + String.fromCharCode(0x200b) + " world";
click('[data-action="inspect"]');
await wait(1200);
ok("inspect flags the zero-width", /suspicious/.test(text("#inspOut")) && /U\+200B/.test(text("#inspOut")));

// --- self test button ------------------------------------------------------
click('[data-tab="reference"]');
click("#cliCard button.btn.tiny");
await wait(4000);
ok("in-page verify button round-trips all channels", /13\/13 channels pass/.test(text("#verifyOut")),
   text("#verifyOut").slice(0, 40));

console.log(problems.length ? "\nPROBLEMS:\n- " + problems.join("\n- ") : "\nall UI checks passed");
process.exit(problems.length ? 1 : 0);
