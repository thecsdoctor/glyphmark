# Quickstart

Two interfaces, one engine. Pick whichever you would rather type; both are shown for each step.

## 0. Serve the docs and the UI

```bash
uv run glyphmark docs build      # optional: builds this site
uv run glyphmark serve --port 8123
```

* lab UI → <http://127.0.0.1:8123/>
* these docs → <http://127.0.0.1:8123/docs/>
* JSON API → `POST http://127.0.0.1:8123/api/encode` …

## 1. Pick a channel

```bash
uv run glyphmark schemes                       # table: bits/unit, stealth, survival
uv run glyphmark scheme vs-bytes               # one channel + its full alphabet
uv run glyphmark chars                         # every code point any channel touches
```

Rules of thumb (see [Channels](channels.md) for the full table):

| you want | reach for |
|---|---|
| most payload per character | `vs-bytes` (1 B per anchor) or `tags` (6 bits/char) |
| survive copy-paste, JSON, social filters | `homoglyph`, `fullwidth`, `punct` |
| nothing visible added, plain-ASCII systems only | `ascii-ctrl` |
| a stress test for a sanitizer | `combining`, `spaces` |

## 2. Embed

=== "CLI"

    ```bash
    uv run glyphmark encode \
        --cover-file cover.txt \
        --payload-file provenance.json \
        --scheme tags --placement spread \
        --key "$GLYPHMARK_KEY" \
        -o marked.txt --report
    ```

    The watermarked text goes to **stdout** (or `-o`), byte-exact, so it pipes cleanly. The report
    line goes to **stderr**:

    ```
    [glyphmark] scheme=tags payload=14B units=19 (114 bits) of 474 carrier slots ·
    spare capacity≈219B · keyed=yes · verified=True
    ```

=== "Web UI"

    Open the **Embed** panel: paste cover text, paste a payload, choose the channel in the picker
    (it shows bits/unit and live capacity, and recommends channels that actually fit), then press
    ++ctrl+Enter. You get:

    * the watermarked text, with views: *as the recipient sees it*, *visible text only*,
      `\u`-escaped (what a JSON API would send), and raw UTF-8 bytes;
    * a **what changed** diff — insertion offsets, or the homoglyph swap table;
    * `round-trip verified` and an **auto re-scan** chip confirming the mark survived;
    * the exact CLI command that reproduces the result.

=== "HTTP"

    ```bash
    curl -s localhost:8123/api/encode -H 'content-type: application/json' \
         -d '{"cover":"Plain carrier text for a watermark.","payload":"id=42","scheme":"tags"}'
    ```

## 3. Extract

```bash
uv run glyphmark decode --text-file marked.txt --key "$GLYPHMARK_KEY"        # scheme auto-detects
printf '%s' "$MARKED" | uv run glyphmark decode -f json                       # sweep + machine output
```

`--scheme auto` (the default) tries every channel and accepts the one whose **magic byte and CRC32**
both validate. Exit `3` means nothing was found; exit `4` means a frame was found but the checksum
failed (wrong key, or the carrier was edited).

## 4. Detect

```bash
uv run glyphmark detect --text-file incoming.txt                 # human report
uv run glyphmark detect --text-file incoming.txt --json          # for tooling
uv run glyphmark detect --text-file incoming.txt --fail-on-risk 60   # CI gate, exit 6
```

Verdicts: `clean` · `minor-anomalies` · `suspicious` · `high-risk` · `watermark-confirmed`. Only the
last one is a positive identification — everything else means “review this text”.

## 5. Sanitize

```bash
uv run glyphmark sanitize --list-stages
uv run glyphmark sanitize --text-file incoming.txt -o clean.txt
uv run glyphmark sanitize --text-file incoming.txt --stage strip_tags --stage nfkc -e json
```

Each stage reports how many code points it removed, so you can **prove** the payload died:

```
[glyphmark] 473→331 codepoints, 142 removed/rewritten: strip_zero_width(-142)
```

Only stages that actually changed something are listed; `identical: true` in `--emit json` means the
text came out unchanged.

## 6. Look under the hood

```bash
uv run glyphmark inspect --text-file marked.txt --only-suspect
uv run glyphmark verify                       # encode+extract self test for all 13 channels
```

## 7. Chain it in a script

```bash
set -euo pipefail
uv run glyphmark encode --cover-file doc.txt --payload-file tag.txt \
                        --scheme vs-bytes -o doc.marked.txt
uv run glyphmark decode --text-file doc.marked.txt            # exit 3/4 aborts the script
uv run glyphmark sanitize --text-file doc.marked.txt -o doc.clean.txt
uv run glyphmark detect --text-file doc.clean.txt --fail-on-risk 1   # must be clean now
```

Because stdout is byte-exact and diagnostics are on stderr, every step is pipe-friendly — and the
same exit codes come back from the HTTP API inside the JSON body (`{"error":…,"exit_code":5}`).

Next: [CLI reference](cli.md) · [Web UI guide](ui.md) · [Defence playbook](defence.md)
