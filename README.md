<p align="center">
  <img src="logo/glyphmark.svg" alt="GlyphMark logo: visible characters carrying invisible marks" width="132" height="132">
</p>

# GlyphMark

<!-- The GitHub badges resolve as soon as this repository is published at this path; the static
     badges work already. Keep the OWNER path identical to .github/settings.yml. -->
<p align="center">
  <a href="https://github.com/OWNER/glyphmark/actions/workflows/ci.yml"><img src="https://github.com/OWNER/glyphmark/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/OWNER/glyphmark/actions/workflows/codeql.yml"><img src="https://github.com/OWNER/glyphmark/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="https://securityscorecards.dev/viewer/?uri=github.com/OWNER/glyphmark"><img src="https://api.securityscorecards.dev/projects/github.com/OWNER/glyphmark/badge" alt="OpenSSF Scorecard"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-blue" alt="MIT licence"></a>
  <img src="https://img.shields.io/badge/python-3.10%20%C2%B7%203.11%20%C2%B7%203.12%20%C2%B7%203.13-informational" alt="Python 3.10-3.13">
</p>

Text watermarking / steganography across the ASCII–Unicode divide — **one engine, two
identical interfaces**:

* a **non-interactive CLI** (`glyphmark …`) that reads flags, files or stdin and never prompts, and
* a **Flask web UI + JSON API** (`glyphmark serve`) whose every endpoint maps 1:1 onto a CLI command.

It writes invisible marks into plain text, reads them back, **detects** them, and **destroys** them —
so you can evaluate a channel and its defense in the same sitting.

```
glyphmark encode --cover-file cover.txt --payload 'session=4F2A' --scheme zw-octal -o marked.txt
glyphmark decode --text-file marked.txt                 # auto-detects the channel
glyphmark detect --text-file marked.txt --fail-on-risk 60
glyphmark sanitize --text-file marked.txt -o clean.txt  # clean.txt now scans clean
```

---

## Why text watermarks work

Humans read rendered glyphs; computers read code points. That gap lets you write a payload into a
string without changing what a reader sees — zero-widths, renderer-suppressed Plane-14 tag
characters, variation selectors, confusable look-alikes, whitespace alphabets, C0 nibbles. Each
channel trades **capacity ↔ stealth ↔ survival ↔ detectability**, and GlyphMark ships the metadata
for all four plus the sanitizer that kills each one.

## Install

```bash
# prerequisites: uv (https://docs.astral.sh/uv/) — nothing else
curl -LsSf https://astral.sh/uv/install.sh | sh
cd glyphmark
uv sync --extra dev        # creates .venv, installs flask/click/rich + pytest/ruff
uv run glyphmark verify    # round-trip self test of every channel
```

Without `uv`: `python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'`.
`make bootstrap` does the whole setup (Python extras + the dev-only jsdom dependency); `make help`
lists every task CI runs. A devcontainer is in `.devcontainer/`.

Extras: `dev` (pytest, ruff) and `docs` (mkdocs + mkdocs-material, used by `glyphmark docs build`).

## Documentation

The usage docs for both interfaces are **MkDocs Material, built and served by this app**:

```bash
uv sync --extra docs
uv run glyphmark docs build          # renders docs/ -> build/docs
uv run glyphmark serve --port 8123   # lab UI on /, docs on /docs/
uv run glyphmark docs status         # where they live, whether they are built
uv run glyphmark docs check          # strict build in a temp dir: broken links fail (CI)
```

Twelve pages: overview, quickstart, CLI reference, web UI guide, channel catalogue, defence
playbook, HTTP API, reference (frame format, keyed mode, limits), security model, responsible use,
contributing, and community & governance. The build is static and
same-origin only — `/docs/` fetches nothing remote, and `tests/test_docs.py` asserts the pages agree
with the code (documented commands, flags, exit codes, channel numbers, sanitizer stages, detection
kinds and JSON field names all come from the registry itself).

## The 13 channels

| id | family | bit/unit | stealth | survival | where it fails |
|---|---|---|---|---|---|
| `zw-binary` | insert | 1 | ●●●●● | ●●●○○ | any `[\u200B-\u200D]` regex |
| `zw-octal` | insert | 3 | ●●●●● | ●●●○○ | full `Cf` sweep (invisible ops often survive naive filters) |
| `omni16` | insert | 4 | ●●●●○ | ●●●●○ | needs a block allow-list to catch all 16 symbols |
| `tags` | insert | 6 | ●●●●● | ●●○○○ | `U+E0000–E007F` range filter; strict XML/JSON rejects it |
| `vs-bytes` | insert | 8 | ●●●●○ | ●●●○○ | NFKC / selector sweep; 1 byte per anchor char |
| `bidi` | insert | 2 | ●●●○○ | ●●●○○ | any bidi control in LTR prose is itself the tell |
| `fillers` | insert | 1 | ●●●●○ | ●●●●○ | allow-list / mixed-script check (they are *letters*, not `Cf`) |
| `homoglyph` | substitute | 1 | ●●●●○ | ●●●●● | UTS #39 skeleton + mixed-script (NFKC does **not** help) |
| `fullwidth` | substitute | 1 | ●●●○○ | ●●●○○ | one NFKC pass |
| `punct` | substitute | 1 | ●●●○○ | ●●●●○ | typographic normalization |
| `spaces` | substitute | 4 | ●●○○○ | ●●○○○ | whitespace collapsing, word wrap |
| `ascii-ctrl` | insert | 4 | ●●○○○ | ●●○○○ | `xxd`/`cat -A`; the only channel that survives an ASCII transcode |
| `combining` | insert | 4 | ●○○○○ | ●●○○○ | NFC/NFKC composes them away |

`glyphmark schemes` prints the live table; `glyphmark scheme <id>` prints the exact code points,
their Unicode names, UTF-8 bytes and the sanitizer stages that remove them.

### Framing

```
HEADER  6 B : magic 0x57 | version | scheme index | flags | payload length (u16 BE)
PAYLOAD n B
CRC32   4 B : zlib.crc32(HEADER || PAYLOAD)
```

* Insertion channels emit `HEADER||PAYLOAD||CRC32` as one symbol stream.
* Substitution channels cannot know the payload length before decoding, so they split:
  phase A = `HEADER||CRC32(HEADER)` (80 bits) then phase B = `PAYLOAD||CRC32(PAYLOAD)`.
  Carrier positions for both phases are recomputed deterministically from
  `(carrier length, bit budget, key)` — no length field is needed to find the slots.
* Radixes are exact powers of two, so symbol ⇄ bit conversion is loss-free.
* `--key` XORs a SHA-256/CTR keystream over the framed bytes. That is **keyed obfuscation, not
  encryption**: it binds the mark to a secret and makes a wrong key fail loudly on the magic byte /
  CRC instead of silently returning garbage. Never treat it as confidentiality.
* Because the frame carries a magic byte *and* a CRC32, detection can say
  “watermark confirmed”, not “this text looks suspicious”.

## CLI (all non-interactive)

Input resolves in this order: inline flag → `--*-file PATH` → piped stdin (`-` supported).
stdout stays byte-exact; diagnostics go to stderr (`--report`).

| command | what it does |
|---|---|
| `glyphmark schemes` | channel catalogue (`--json`) |
| `glyphmark scheme <id>` | one channel + its full character table |
| `glyphmark chars` | every special code point any channel uses |
| `glyphmark encode` | embed: `--cover[-file] --payload[-file] --scheme --key --placement --out --emit{raw,escapes,json,codepoints}` |
| `glyphmark decode` | extract: `--text[-file] --scheme auto|<id> --key --format{text,hex,base64,json}` |
| `glyphmark detect` | covert-channel scan: `--json`, `--fail-on-risk N` (CI gate), `--no-frames` |
| `glyphmark sanitize` | strip marks: `--stage X` (repeatable), `--list-stages`, `-o` |
| `glyphmark inspect` | per-code-point forensics: `--only-suspect`, `--json` |
| `glyphmark verify` | encode+extract round trip for every channel (`--scheme`, `--json`) |
| `glyphmark serve` | web UI + JSON API: `--host --port --debug` |
| `glyphmark docs` | usage docs: `build [-o DIR] [--strict]`, `check` (CI), `status [--json]` |

Exit codes: `0` ok · `1` error · `2` bad arguments · `3` nothing found · `4` corrupt frame /
wrong key · `5` carrier too small · `6` detection threshold reached.

```bash
# CI example: fail the pipeline if inbound text carries a covert channel
glyphmark detect --text-file incoming.txt --fail-on-risk 60 || echo "quarantine"

# batch strip over a corpus
find corpus -name '*.txt' -print -exec sh -c \
  'glyphmark sanitize --text-file "$1" -o "$1.clean"' _ {} \;

# keyed, dense mark on a document
glyphmark encode --cover-file doc.txt --payload-file provenance.json \
                 --scheme vs-bytes --key "$SECRET" -o doc.marked.txt
```

## Web UI / HTTP API

```bash
uv run glyphmark serve --port 8000     # http://127.0.0.1:8000
```

Six panels: **Embed · Extract · Detect · Sanitize · Inspect · Reference** (`Alt`+`1…6`, or
`Ctrl/⌘`+`↵` to run whichever panel is open — press `?` in the browser for the full sheet).

What the UI does beyond the raw API:

* **Pipeline ribbon** across the top (`cover → watermarked → detected → sanitized`). Each step is
  clickable and loads its text into the next panel, so the whole write-it / find-it / kill-it loop
  happens in one session. State is restored from `localStorage` on reload — binding keys never are.
* **Channel picker with live capacity**: type to filter (`/`, arrows, `Enter`), see bits per carrier
  unit and stealth/survival ratings, watch the capacity meter and the “this carrier cannot hold
  N bytes” warning *before* you submit, and pick from the channels it recommends for the cover and
  payload you actually have.
* **Proof, not vibes**, after every action: an annotated view that renders invisible code points as
  labelled chips, a *what changed* diff (insertion offsets, or the homoglyph swap table with a
  side-by-side comparison), payload hex / base64 / `\u`-escaped / UTF-8-byte views, and an
  **automatic re-scan** that confirms the mark survived the embed and reports “no anomaly” after
  sanitizing.
* Detection report with risk gauge, verdict, recovered frames, the Plane-14 tag-block mirror,
  severity filtering, click-to-copy code points, the sanitizer stage that kills each finding, and a
  JSON download — with the equivalent **CLI command printed under every result**.
* Reference panel: channel catalogue, every code point any channel touches (click a row to copy the
  character), the sanitizer pipeline, the CLI cheat sheet, and an in-page `verify` self test.
* Keyboard-driven and screen-reader sane (skip link, `tablist`/`tabpanel`, labelled inputs, live
  regions, focus management, `?`/`Esc` help dialog), responsive to phone width, light/dark themed.
  Logic is framework-free vanilla JS + local CSS, so a blocked CDN degrades instead of breaking.

| endpoint | mirrors |
|---|---|
| `GET /api/meta` | `glyphmark schemes` + `chars` + `sanitize --list-stages` |
| `POST /api/encode` | `glyphmark encode` |
| `POST /api/decode` | `glyphmark decode` |
| `POST /api/detect` | `glyphmark detect` |
| `POST /api/sanitize` | `glyphmark sanitize` |
| `POST /api/inspect` | `glyphmark inspect` |
| `POST /api/verify` | `glyphmark verify` |
| `GET /docs/` | usage docs (mkdocs-material build output, same origin) |
| `GET /healthz` | liveness |

Core errors map to HTTP status **and** carry the CLI exit code in the JSON body
(`{"error": …, "exit_code": 5}` → HTTP 422), so a client can branch on the same codes a shell
script sees. Bind address defaults to `127.0.0.1`; this is a single-user research tool, not a
hardened multi-tenant service — put it behind auth before exposing it beyond localhost.

## Defensive use

Detection (`glyphmark detect`) reports: C0 controls, zero-widths, invisible math operators, bidi
controls, Plane-14 tags, variation selectors, confusable homoglyphs, mixed-script tokens, fullwidth
forms, whitespace variants, Hangul fillers, combining marks, default-ignorable ranges, NFKC drift,
and **recovered frame signatures** (including the decoded Plane-14 mirror text, which is how hidden
instruction injection shows up).

Sanitization (`glyphmark sanitize`) runs a staged pipeline — controls, zero-widths, bidi, tags,
selectors, fillers, combining, `Cf`, default-ignorable, confusable folding, fullwidth folding,
punctuation folding, whitespace collapsing, NFKC — plus two opt-in aggressive stages (script
allow-list, force-ASCII). Each stage reports how many code points it removed, so you can prove the
payload died instead of hoping.

**Intake recipe for untrusted text (esp. anything reaching an LLM):**
`strip_tags`, `strip_zero_width`, `strip_bidi`, `strip_variation_selectors`, `nfkc` — or just the
default pipeline, which is exactly that plus the rest.

## Ethics & limits

* Undisclosed watermarking of other people's text is covert data collection. Disclose it, or don't
  ship it. Provenance marks that leak session ids back to a reader are a privacy incident.
* Character-level marks are **not** robust: normalization, re-typing, translation, model rewriting
  or a whitespace-trimming formatter destroy them. Robust provenance needs document-level or
  model-level watermarking as well.
* Marks break exact matching, search, dedup, and case folding — the same property that makes
  homograph phishing work. That is why detection/sanitization ships in the same binary.

## Project operations

Everything a project review asks for is in this repository and is **asserted by tests**
(`tests/test_repo_hygiene.py` fails if a file goes missing, a required status check stops existing, a
`CODEOWNERS` path is renamed, or a source file loses its licence header).

| | |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | setup, the gates CI runs, DCO sign-off, the "add a channel" checklist |
| [GOVERNANCE.md](GOVERNANCE.md) | roles, voting, vetoes, deadlock-breaking, how maintainers join and leave |
| [MAINTAINERS.md](MAINTAINERS.md) | who owns what (with affiliations), roles, emeritus, contact routes |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | the CNCF Code of Conduct, plus rules specific to a dual-use tool |
| [SECURITY.md](SECURITY.md) | what counts as a vulnerability here, private reporting, 90-day disclosure |
| [SUPPORT.md](SUPPORT.md) | what help looks like without a support contract — and what is declined |
| [CHANGELOG.md](CHANGELOG.md) | release notes, with the frame format treated as a stability boundary |
| [ROADMAP.md](ROADMAP.md) | now / next / later, and what is explicitly not planned |
| [ADOPTERS.md](ADOPTERS.md) | who runs this (self-listing; a discreet row format is provided) |
| [TRADEMARKS.md](TRADEMARKS.md) | "works with GlyphMark" yes, "GlyphMark Cloud" no |
| [LICENSE](LICENSE) · [NOTICE](NOTICE) | MIT, with third-party assets and Unicode data attributed |
| [.github/](.github/) | workflows (CI, CodeQL, Scorecard, dependency review/audit, release), CODEOWNERS, issue/PR templates, settings as code |

Supply chain: locked dependencies (`uv.lock`), weekly `pip-audit`/`npm audit`, Dependabot, a
licence/advisory gate on new dependencies, CycloneDX SBOM and SLSA build provenance on every
release, and signed Scorecard results. Workflow actions are pinned by release tag and kept current
by Dependabot; SHA pinning is recorded in the roadmap.

## Layout

```
src/glyphmark/
  schemes.py    channel registry: alphabets, confusable tables, capacity, deterministic spreading
  frames.py     frame layout, CRC32, SHA-256/CTR keyed obfuscation
  bitstreams.py MSB bit packing / power-of-two digit conversion
  codec.py      encode/extract API (auto channel sweep, round-trip verification)
  analysis.py   code-point forensics + covert-channel detection + risk scoring
  sanitize.py   staged sanitizer with per-stage accounting
  cli.py        click CLI (the one non-interactive entry point)
  web/app.py    Flask factory: UI + /api/* + /docs/, calling codec/analysis/sanitize directly
  web/templates/index.html, web/static/{styles.css,app.js}
  docs.py       locate/build/status for the documentation, served by web/app.py under /docs/
docs/           12 markdown pages  ·  mkdocs.yml  MkDocs Material config  (build/docs is generated)
tests/          round-trip, tamper, detection, sanitizer, CLI, Flask API, docs-drift and
                repository-hygiene tests (205 total)
tools/          ui_smoke.mjs (headless DOM walk-through, jsdom), check_license_headers.py,
                check_dco.py
.github/        workflows, CODEOWNERS, issue/PR templates, settings.yml, codeql config
logo/           glyphmark.svg (+ mono variant) - see TRADEMARKS.md
Makefile        every CI task, locally: make check
.devcontainer/  ready-to-build dev container (python 3.13 + node 22 + uv)
```

`codec`/`analysis`/`sanitize` hold all logic; CLI and Flask are thin adapters, which is what keeps
the two interfaces provably equivalent — `tests/test_web.py` asserts the HTTP layer returns exactly
what `codec` returns, and `tests/test_cli.py` does the same for the shell.

## Development

```bash
make check                # what CI runs: lint + verify + lock consistency + tests + strict docs

uv run pytest -q          # 205 tests: every channel round-trips, tamper & key checks,
                          # sanitize-then-detect-must-come-back-clean, CLI + API behaviour,
                          # UI markup/JS contract tests (ids, field names, ARIA, CDN split),
                          # docs-vs-code drift guards, and repo-hygiene checks (governance files,
                          # CI contexts, CODEOWNERS paths, SPDX headers, DCO logic)
uv run ruff check src tests tools
uv run ruff format --check src tests tools
python tools/check_license_headers.py     # SPDX header on every source file

# optional: drive the real UI in a headless DOM (jsdom is the only Node dependency)
uv run glyphmark serve --port 8123 &
npm install
npm run ui-smoke            # == node tools/ui_smoke.mjs ; honours GM_BASE=http://host:port
                          # also asserts the browser's capacity meter matches the server's math
```

The page's logic is framework-free vanilla JS (`web/static/app.js`), so the lab still
works if the CDN layer (Tailwind, Alpine theme toggle, Google Fonts) is blocked; the
test suite asserts that the served HTML, CSP and static assets line up with what the
JS expects.

## Licence

MIT — see [LICENSE](LICENSE); third-party assets and Unicode data are attributed in
[NOTICE](NOTICE), and the name/logo are covered by [TRADEMARKS.md](TRADEMARKS.md). Built for
provenance engineering, stego research and input-hygiene QA.
