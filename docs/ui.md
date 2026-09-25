# Web UI guide

`uv run glyphmark serve --port 8123` → <http://127.0.0.1:8123/>. One page, six panels, no build
step: the logic is plain JavaScript served by Flask and every panel calls the same
[`/api/*` endpoints](api.md) the CLI shares, so nothing exists in the UI that the shell cannot do.

## Keyboard

| keys | what |
|---|---|
| ++alt+1 … ++alt+6 | jump between panels |
| ++ctrl+Enter | run the current panel's action |
| ++slash | focus the channel picker (Embed) or the table filter (Reference) |
| ++question | help sheet (shortcuts, verdict meanings, channel advice, exit codes) |
| ++esc | close the help sheet or the channel picker |
| ↑ ↓ then ++return++ | move through, and pick from, the filtered channel list |

## The pipeline ribbon

Under the tab bar: **cover written → watermarked → detected → sanitized**. A step lights up when the
session has produced it, and clicking a step loads that text into the matching panel. It exists so
the loop the tool is built for — *write a mark, prove it is there, then destroy it* — costs no
copy-pasting.

Session text and settings are restored from `localStorage` on reload. **Binding keys are never
stored**; use “start fresh” in the toast to wipe the session.

## Embed

1. **Cover text** — the visible carrier. `Sample` loads the same sample text the CLI uses. The strip
   under the box shows code points, UTF-8 bytes, lines and an “anomalous code points” count.
2. **Payload** — arbitrary UTF-8 (a JSON provenance tag is the typical case).
3. **Channel & key** — the channel picker lists bits per carrier unit plus stealth and survival
   ratings, filters as you type, and shows a live **capacity meter**: carrier units → bytes free vs
   bytes needed, with a warning *before* you submit if the payload cannot fit. Under it,
   **recommended channels** are computed from your actual cover + payload and ranked by
   survival/stealth.

The result card gives you:

* four views — **as the recipient sees it** (invisible code points rendered as labelled chips),
  **visible text only**, **escaped** (`\u…`, what a JSON API transmits) and **raw UTF-8 bytes**;
* chips for channel, payload size, units used, bits, spare capacity, keyed, and
  `round-trip verified`;
* **What changed** — for insert channels the number of insertion offsets and the offsets themselves;
  for substitution channels a swap table (`a → а`, counts, code points) and a side-by-side
  cover/marked comparison with the swapped characters underlined;
* an **auto re-scan** chip (`watermark-confirmed · risk 100`) — the UI re-runs detection on its own
  output so survival is proven rather than assumed;
* the **CLI command** that reproduces the result, copyable.

!!! note "Keys are never logged"
    The key fields are `type=password` with a `show` toggle, are not written to `localStorage`, and
    are not echoed back in any result view — the CLI mirror shows `--key "$GLYPHMARK_KEY"`.

## Extract

Paste suspect text (or `Paste ⧉` from the clipboard, or `Last output` to pull in what Embed produced).
Leave channel on `auto` to sweep all 13, or pin one. On success you get the payload as text, hex,
base64 and escaped, plus units/bits read and a `magic + CRC32 valid` chip. On failure the panel
explains *why* per channel and repeats the exit-code meaning (`3` nothing found, `4` tampered/wrong
key).

## Detect

Risk gauge + verdict, then:

* **recovered frames** — channel, payload preview, payload length, `confirmed (magic + CRC32 valid)`;
* **Plane-14 tag-block mirror** — tag characters decoded back to ASCII. This is how hidden-instruction
  injection against an LLM becomes visible as plain text;
* **findings** — severity, occurrence count, the code points involved (click one to copy it, then
  paste it into Inspect), and the sanitizer stage that removes each one;
* **severity filter** (all / high / medium / low / info) and **download JSON**;
* a *recommendation* line with **open in sanitizer**, which hands the text to the Sanitize panel.

Only `watermark-confirmed` is an identification. Everything else is “review this text” — the UI says
so in the footnote under every report.

## Sanitize

The 16 stages are checkboxes with what each one does and which channels it kills;
`Default pipeline` / `All stages` / `None` set them in one click. The result shows clean text (plus
escaped and byte views), **stage accounting** (removed / length before / length after per stage), and
an **auto re-scan** that reports `no anomaly` and lights the last ribbon step — that is the proof the
payload died.

Choose `None` first if you want to see what the pipeline is actually changing: the report then says
`removed 0 · text unchanged`.

## Inspect

Paste anything to see every code point: index, codepoint, category, script, Unicode name, how it
renders, flags. Above the table, a **tile strip** colours the text's code points by flag so patterns
(block after block of `zero-width`) are visible at a glance; below it, flag chips filter the table.
“Suspicious only” re-runs the scan on just the flagged rows. This is also where you verify that a
`--emit escapes` string contains what you think it contains.

## Reference

* **Channel catalogue** — filterable by id, tag or detection vector; `detail` opens the channel's
  blurb, density, kill-list and full character table in the Inspect panel.
* **Special character reference** — every code point any channel touches; click a row to copy the
  character (paste it into Detect to see it flagged).
* **Sanitizer pipeline** — the stage table.
* **CLI cheat sheet** — copyable commands for everything on this page.
* **Self test every channel** — runs `glyphmark verify` server-side and shows a PASS/FAIL table.

## Behaviour worth knowing

* **CDN is cosmetic.** Tailwind, Alpine (theme toggle) and Google Fonts load from a CDN, but the
  components are styled locally and the logic is framework-free: block the CDN and the page still
  works.
* **Localhost by default.** `serve --host 0.0.0.0` exposes the tool to your network; it has no
  auth, and 4 MB request cap plus a locked-down CSP are hygiene, not protection.
* **Error surfacing.** API errors appear as toasts with the CLI exit code attached
  (`carrier too small · exit 5`), and the offending panel keeps its previous result.
* **Docs.** The header `Docs` pill opens `/docs/` — this site, built and served by the same process
  (see [Building the docs](reference.md#building-the-docs)).
