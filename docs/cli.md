# CLI reference

Everything is **non-interactive**: values come from flags, files or stdin, never from a prompt.
`stdout` carries the payload/text (byte-exact, pipe-friendly); diagnostics and reports go to
`stderr`. `-h` and `--help` both work on every command.

```
glyphmark [--version] [-h]
  schemes   |  scheme <id>  |  chars           reference
  encode    |  decode                           write / read a mark
  detect    |  sanitize     |  inspect          defence
  verify                                        self test
  docs      |  serve                            documentation, web UI
```

## Input conventions

| pattern | meaning |
|---|---|
| `--cover "text"` / `--payload "text"` / `--text "text"` | inline value |
| `--cover-file f.txt` / `--payload-file f.txt` / `--text-file f.txt` | read from file |
| `--cover-file -` (etc.) | read from **stdin** |
| `-o out.txt` | write result to a file instead of stdout |
| `-k SECRET` / `--key SECRET` | binding secret for keyed marks |

Nothing is ever written unless you ask (`-o`), and no command reads a TTY.

---

## Reference commands

### `glyphmark schemes`

Channel catalogue: family, bits per carrier unit, stealth, survival, carrier description, detection
vector.

| flag | effect |
|---|---|
| `--json` | machine-readable list (no character tables) |

### `glyphmark scheme <id>`

One channel in detail: blurb, radix, density, stealth/survival, detection vector, what kills it,
notes, and the **full character table** it uses.

| flag | effect |
|---|---|
| `--json` | full channel dict including `characters` |

### `glyphmark chars`

The union of every code point any channel touches — codepoint, category, UTF-8 bytes, how it
renders, which channels use it.

| flag | effect |
|---|---|
| `--json` | rows as JSON |

---

## `glyphmark encode`

Embed a payload into cover text.

| flag | default | notes |
|---|---|---|
| `--cover` / `--cover-file` | — | carrier text; `-` = stdin |
| `--payload` / `--payload-file` | — | payload bytes (UTF-8); `-` = stdin |
| `-s, --scheme` | `zw-octal` | one of the 13 channel ids |
| `-k, --key` | — | keyed (obfuscated) frame |
| `-p, --placement` | `spread` | `spread` · `interleave` · `prefix` · `suffix` |
| `-e, --emit` | `raw` | `raw` · `escapes` · `json` · `codepoints` |
| `-o, --out` | stdout | |
| `--report` | off | print the capacity/verification report to stderr |

```bash
# the report always lands on stderr, the text on stdout
uv run glyphmark encode --cover-file cover.txt --payload "id=42" --scheme homoglyph --report > out.txt

# what a JSON API would transmit, with escapes for the invisible code points
uv run glyphmark encode --cover "Plain carrier text here." --payload "id=42" \
                        --scheme tags --emit escapes

# inspect where the payload actually went
uv run glyphmark encode --cover-file cover.txt --payload "id=42" --scheme zw-octal --emit codepoints
```

Placement controls *where* the marks sit, which is a stealth/capacity trade:
`spread` distributes units across the whole carrier (most natural), `interleave` concentrates them in
the first third, `prefix`/`suffix` pack them at one end (fewer boundaries touched, easier to spot).

`encode` also **self-verifies**: it decodes what it just wrote, so `verified=False` in the report
means the result should not be trusted.

---

## `glyphmark decode`

Recover a payload.

| flag | default | notes |
|---|---|---|
| `--text` / `--text-file` | — | watermarked text; `-` = stdin |
| `-s, --scheme` | `auto` | channel id, or sweep all channels |
| `-k, --key` | — | required if the mark was keyed |
| `-f, --format` | `text` | `text` · `hex` · `base64` · `json` |
| `-o, --out` | stdout | |

```bash
uv run glyphmark decode --text-file marked.txt
uv run glyphmark decode --text-file marked.txt --scheme vs-bytes --key "$SECRET"
printf '%s' "$MARKED" | uv run glyphmark decode -f json
```

`--scheme auto` tries every channel and only accepts a candidate whose magic byte **and** CRC32
validate, so a success is an identification, not a guess. In `json` mode you also get
`payload_hex`, `payload_base64`, `bits_read`, `carrier_units` and, on failure, the per-channel
`attempts` list.

---

## `glyphmark detect`

Defensive scan. Never modifies input.

| flag | effect |
|---|---|
| `--text` / `--text-file` | input text (`-` = stdin) |
| `--json` | full report as JSON |
| `--no-frames` | skip frame recovery (faster, purely heuristic) |
| `--fail-on-risk N` | exit **6** when `risk_score >= N` |

```bash
uv run glyphmark detect --text-file incoming.txt
uv run glyphmark detect --text-file incoming.txt --json | jq '.findings[].kind'
uv run glyphmark detect --text-file incoming.txt --fail-on-risk 60 || exit 1
```

Score bands: `0–29 clean` · `30–69 suspicious` · `70+ high-risk`, plus the terminal verdict
`watermark-confirmed` when a GlyphMark frame was actually recovered. See
[Detection & sanitization](defence.md).

---

## `glyphmark sanitize`

Strip covert-channel code points — intake hygiene, and the way to destroy a mark.

| flag | effect |
|---|---|
| `--text` / `--text-file` | input text (`-` = stdin) |
| `--stage ID` | run only these stages (repeatable); default pipeline otherwise |
| `--list-stages` | print the pipeline table and exit |
| `-e, --emit` | `raw` · `escapes` · `json` (per-stage accounting as JSON) |
| `-o, --out` | output file |

```bash
uv run glyphmark sanitize --list-stages
uv run glyphmark sanitize --text-file incoming.txt -o clean.txt
uv run glyphmark sanitize --text-file incoming.txt \
    --stage strip_controls --stage strip_zero_width --stage strip_bidi \
    --stage strip_tags --stage strip_variation_selectors --stage nfkc
uv run glyphmark sanitize --text-file incoming.txt -e json | jq '.stages[] | select(.removed>0)'
```

A bad stage name exits `1` and prints `unknown sanitize stage(s): …  available: …`, so you can
copy a valid id straight out of the error. The 14 default stages and 2 opt-in aggressive stages are
listed in
[Detection & sanitization](defence.md#the-sanitizer).

---

## `glyphmark inspect`

Per-code-point breakdown: index, codepoint, category, script, UTF-8 bytes, Unicode name, flags.

| flag | effect |
|---|---|
| `--text` / `--text-file` | input text (`-` = stdin) |
| `--only-suspect` | print only flagged code points |
| `--json` | full row list + counts (`codepoints`, `utf8_bytes`, `utf16_units`, `suspect_count`) |

```bash
uv run glyphmark inspect --text "safe‮text"  --only-suspect
uv run glyphmark inspect --text-file marked.txt --json | jq '.rows[] | select(.suspect)'
```

---

## `glyphmark verify`

Encode+extract self test — the fastest proof that a channel (or an install) is healthy.

| flag | effect |
|---|---|
| `--scheme ID` | limit to these channels (repeatable) |
| `-k, --key` | also exercise the keyed path |
| `--json` | results as JSON |

```bash
uv run glyphmark verify
uv run glyphmark verify --scheme homoglyph --scheme spaces -k test --json
echo $?            # 0 all pass, 1 something failed
```

---

## `glyphmark serve`

Run the web UI + JSON API. Same engine, same features — see the [Web UI guide](ui.md) and
[HTTP API](api.md).

| flag | default |
|---|---|
| `--host` | `127.0.0.1` |
| `--port` | `8000` |
| `--debug` / `--no-debug` | off (reloader + verbose errors) |

The dev server is single-user; bind to `127.0.0.1` unless you have put authentication in front of it.

---

## `glyphmark docs`

Build the documentation you are reading (MkDocs Material) and report where it lives. The Flask app
serves the result under `/docs/`.

| subcommand | flags | effect |
|---|---|---|
| `docs build` | `-o/--out DIR`, `--strict/--no-strict`, `--no-clean` | render `docs/` into the build dir |
| `docs check` | `--strict/--no-strict` | build into a temp dir and fail on warnings/broken links |
| `docs status` | `--json` | show source dir, output dir, whether it is built, and the URL |

```bash
uv run glyphmark docs build
uv run glyphmark docs status --json
uv run glyphmark docs check --strict || echo "docs need fixing"
```

Requires the `docs` extra (`uv sync --extra docs`). If `mkdocs-material` is missing, the command
exits `1` and prints the install hint rather than silently doing nothing.

---

## Exit codes

The same codes are returned by the CLI and inside API error bodies, so scripts and HTTP clients can
branch identically.

| code | meaning | typical trigger |
|---|---|---|
| `0` | success | |
| `1` | error | bad channel stage name, unreadable file, mkdocs missing |
| `2` | bad CLI arguments | unknown flag / invalid choice (raised by `click`) |
| `3` | no payload found | `decode` on text with no frame |
| `4` | corrupt frame or wrong key | CRC mismatch, keyed frame without `--key` |
| `5` | carrier too small | payload does not fit the cover text in that channel |
| `6` | risk threshold reached | `detect --fail-on-risk N` and `score >= N` |

```bash
uv run glyphmark decode --text-file x.txt
case $? in
  0) echo "payload on stdout" ;;
  3) echo "no watermark" ;;
  4) echo "tampered, or wrong --key" ;;
  *) echo "see the message on stderr" ;;
esac
```

## Recipes

**Stamp a batch of documents**

```bash
for f in docs/*.txt; do
  uv run glyphmark encode --cover-file "$f" --payload "batch=7 doc=$f" \
      --scheme fullwidth -o "marked/$f"
done
```

**Audit an incoming feed, quarantine anything suspicious**

```bash
while read -r file; do
  if uv run glyphmark detect --text-file "$file" --fail-on-risk 40; then
    mv "$file" accepted/
  else
    mv "$file" quarantine/
  fi
done < feed.txt
```

**Prove a sanitizer neutralised a mark** (the invariant the test suite also asserts)

```bash
uv run glyphmark sanitize --text-file marked.txt -o clean.txt
uv run glyphmark detect --text-file clean.txt --fail-on-risk 1 && echo "clean"
```

**Round-trip keyed marks in CI**

```bash
uv run glyphmark verify --key "$CI_TEST_KEY" --json > verify.json
jq -e '.[] | select(.ok | not)' verify.json && exit 1 || exit 0
```
