# Reference

## Frame format

Every mark is one checksummed frame, big-endian:

```
HEADER   6 bytes : magic 0x57 ('W') | version 1 | scheme_index | flags | payload_len (u16)
PAYLOAD  n bytes
CRC32    4 bytes : zlib.crc32(HEADER || PAYLOAD)
```

Insertion channels write `HEADER || PAYLOAD || CRC32` as a single unit (keystream label `F`).
Substitution channels cannot know the payload length before decoding, so they split it:

```
phase A : HEADER || CRC32(HEADER)     -> 80 bits, keystream label "A"
phase B : PAYLOAD || CRC32(PAYLOAD)   -> (n + 4) * 8 bits, keystream label "B"
```

Why this shape:

* **magic + version** let a scanner prove a GlyphMark frame exists before it can read it;
* **scheme_index** lets `decode --scheme auto` reject a frame written on another channel instead of
  misreading it;
* **payload_len (u16)** bounds the read, so truncated input fails instead of running on;
* **CRC32** turns silent corruption into a loud failure (exit `4`).

## Keyed mode

`--key` derives a SHA-256 keystream (CTR-style counter mode, phase-labelled) and applies it to the
frame body, leaving **only magic and version in clear text**:

```
root      = SHA-256("glyphmark/v1|" + secret)
phase key = SHA-256(root + "|" + label)          # label ∈ F / A / B
keystream = phase key || SHA-256(key||ctr) ...
```

Consequences worth remembering:

* it is **obfuscation, not encryption** — no MAC, no KDF, no brute-force resistance; anyone holding
  the secret reads the payload, and a determined attacker with the plaintext cover can recover the
  keystream. Do not put secrets in a payload.
* magic/version staying clear means a **defender can prove a keyed frame is present** and that a key
  is required (`KeyRequiredError`, exit `4`) — a deliberate transparency trade.
* a wrong key produces `ChecksumError` (exit `4`), never garbage that looks plausible.
* for substitution channels the key also derives **which** carrier positions are used, so an
  unkeyed scanner sees code-point anomalies but cannot even locate the data stream.

Payloads are bytes: `payload.encode("utf-8")` (CLI) / the `payload` JSON string (API).

## Placements

| id | behaviour |
|---|---|
| `spread` | units distributed across all carrier positions (deterministic shuffle) — most natural |
| `interleave` | concentrated in the first third of the carrier |
| `prefix` | packed at the start |
| `suffix` | packed at the end |

Position selection is deterministic: it derives from a hash of the channel + key + text, **not** from
`random`, so identical inputs give byte-identical output and marks are reproducible in tests and CI.

## Channel internals

* All radixes are powers of two (`2, 4, 8, 16, 64, 256`), so bit↔digit conversion is lossless and
  `bits_per_unit == radix.bit_length() - 1` (asserted in the test suite).
* Insertion channels may require an **anchor** (`vs-bytes`, `combining`): marks clamp onto a visible
  character instead of sitting between characters.
* Substitution channels declare a base character plus N look-alikes; the registry validates that
  `1 + N == radix`, so a channel cannot advertise a density it cannot carry.
* `carrier_units` counts only positions the channel may legally touch — spaces for `spaces`,
  letters-with-a-confusable-twin for `homoglyph`, words for `ascii-ctrl`.

## Limits

| thing | limit |
|---|---|
| payload length in one frame | 65 535 bytes (`u16` field) |
| practical payload | far less: see [Capacity](channels.md#capacity) |
| API request body | 4 MB, 400 000 characters per text field |
| `inspect` rows | 4 000 by default (`truncated: true` beyond that) |
| robustness | none against re-typing, translation, OCR, model rewriting |

## Environment

| variable | effect |
|---|---|
| `GLYPHMARK_DOCS_DIR` | where `/docs/` reads its build output (default: `build/docs` next to `mkdocs.yml`) |
| `GLYPHMARK_DOCS_CONFIG` | path to `mkdocs.yml` when it is not at the project root |
| `PYTHONHASHSEED` | irrelevant by design — position selection is hash-based, not `id()`/`random` based |

## Building the docs

```bash
uv sync --extra docs            # mkdocs + mkdocs-material
uv run glyphmark docs build     # -> build/docs (the dir /docs/ serves)
uv run glyphmark docs status    # source dir, output dir, built?, URL
uv run glyphmark docs check     # strict build in a temp dir: broken links / warnings fail
```

`serve` then exposes the site at <http://127.0.0.1:8123/docs/>. Nothing is fetched at runtime: the
site is built once, statically, and served from disk. If it has not been built, `/docs/` renders a
page with the command above instead of a 404 — and the header `Docs` pill links to that page either
way.

Sources live in `docs/`, config in `mkdocs.yml` at the project root, theme
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To edit while reading:

```bash
uv run --extra docs mkdocs serve -a 127.0.0.1:8100
```

## Tests

```bash
uv run pytest -q
```

| file | what it pins down |
|---|---|
| `tests/test_roundtrip.py` | every channel round-trips keyed and unkeyed; tampering/truncation caught by CRC; wrong key never returns garbage; capacity errors are actionable; metadata is itemized |
| `tests/test_detect_sanitize.py` | detection finds every channel; sanitize→detect comes back clean for every channel; stage accounting adds up |
| `tests/test_cli.py` | flags, stdin/stdout byte-exactness, every exit code |
| `tests/test_web.py` | API returns exactly what the core returns; error→status→exit-code mapping; UI markup/JS contract; CDN is presentation-only |
| `tests/test_docs.py` | docs build, nav/markdown consistency, numbers in the channel table match the registry, `/docs/` serving |

`uv run ruff check src tests` is part of the same contract; `npm run ui-smoke` drives the real page in
a headless DOM against a live server.

## Architecture

```
bitstreams.py   MSB bit packing, power-of-two digit conversion
frames.py       header/CRC32, SHA-256 keystream, keyed obfuscation
schemes.py      13 channel definitions + registry validation + capacity math
codec.py        encode/decode, auto channel sweep, round-trip verification
analysis.py     code-point forensics, finding catalog, risk scoring, verdicts
sanitize.py     16-stage pipeline with per-stage accounting
cli.py          click CLI (non-interactive; the reference interface)
web/app.py      Flask factory: UI + /api/*, calling the same functions
docs.py         locate/build/serve the MkDocs Material documentation
```

`codec`, `analysis` and `sanitize` hold all behaviour; `cli.py` and `web/app.py` are adapters. That is
what makes "identical functionality in both interfaces" a structural property rather than a promise.

## Glossary

| term | meaning |
|---|---|
| channel / carrier | the alphabet and the positions a mark may occupy (`vs-bytes` on anchors, `spaces` on gaps) |
| carrier unit | one position that can hold `bits_per_unit` bits |
| frame | magic + version + scheme + flags + length + payload + CRC32 |
| keyed | frame body obfuscated with a SHA-256-derived, phase-labelled keystream |
| anchor | a visible character a mark clamps onto (variation selectors, combining marks) |
| confusable | a code point that renders like another one (UTS #39 skeletons) |
| verdict | `clean` · `minor-anomalies` · `suspicious` · `high-risk` · `watermark-confirmed` |
| stage | one named removal/folding step in the sanitizer pipeline |
