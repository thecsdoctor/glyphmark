# Detection & sanitization

The defensive half of the toolkit: decide whether text carries something hidden, then neutralize it.
Both halves are usable from the [CLI](cli.md), the [UI](ui.md) and the [HTTP API](api.md).

## What detection looks for

| kind | what it means | severity | removed by |
|---|---|---|---|
| `c0_controls` | C0/C1 control codes (the classic ASCII nibble channel, `^A` in `cat -A`) | high | `strip_controls` |
| `zero_width` | ZWSP/ZWNJ/ZWJ/WORD JOINER/BOM/soft hyphen/Mongolian vowel separator | high | `strip_zero_width` |
| `invisible_operators` | `U+2061-U+2064`, the slots most "strip zero width" regexes forget | high | `strip_zero_width` |
| `bidi_controls` | bidi overrides/isolates — OWASP LLM-top-10 injection carrier | high | `strip_bidi` |
| `tags_block` | Plane-14 tags: renderer-suppressed ASCII mirror, invisible to humans, readable by tokenizers | high | `strip_tags` |
| `variation_selectors` | up to one hidden byte clamped onto a base character | medium | `strip_variation_selectors` |
| `confusables` | cross-script look-alikes (homograph phishing) | high | `confusables_to_ascii` |
| `script_mixing` | one token mixing incompatible scripts — the UTS #39 signal browsers use | medium | `confusables_to_ascii` |
| `fullwidth_forms` | fullwidth twins of printable ASCII | low | `fullwidth_fold` |
| `space_variants` | NBSP / thin / ideographic spaces at word boundaries | low | `collapse_spaces` |
| `hangul_fillers` | `U+3164`/`U+FFA0`: letters (`Lo`) that render as nothing, invisible to `Cf` strippers | medium | `strip_fillers` |
| `combining_marks` | stacked diacritics on unexpected bases | low | `strip_combining` |
| `default_ignorable` | other ignorable-range code points, anomalous in prose | medium | `strip_format` |
| `nfkc_drift` | the text changes under NFKC, so compatibility characters are in play | low | `nfkc` |
| **`frame_signature`** | **a GlyphMark frame was actually recovered** | **high (confirmed)** | default pipeline |

Risk score `0–100` and a verdict:

| score | verdict | how to treat it |
|---|---|---|
| 0–29 | `clean` | nothing anomalous |
| 30–69 | `minor-anomalies` / `suspicious` | heuristics only — review, sanitize before use |
| 70+ | `high-risk` | several strong signals; sanitize and quarantine |
| — | `watermark-confirmed` | **identification**: magic byte *and* CRC32 validated |

!!! important "Heuristics are not accusations"
    A Cyrillic `а` inside a Russian sentence is not an attack. `frame_signature` is the only finding
    that means "data was encoded here"; everything else means "this string contains code points that a
    covert channel could use".

## Scanning

```bash
uv run glyphmark detect --text-file incoming.txt                 # human report
uv run glyphmark detect --text-file incoming.txt --json          # for tooling
uv run glyphmark detect --text-file incoming.txt --no-frames     # heuristics only, faster
uv run glyphmark detect --text-file incoming.txt --fail-on-risk 60
```

Interesting JSON fields:

| field | meaning |
|---|---|
| `risk_score`, `verdict` | the numbers above |
| `suspect_total`, `codepoints` | how much of the text is anomalous |
| `findings[]` | `kind`, `severity`, `count`, `offsets`, `characters[]` (codepoint, name, category, UTF-8, offset), `remove_with`, `why` |
| `frame_signatures[]` | recovered frames: `scheme`, `payload_preview`, `payload_len`, `strength` |
| `tag_block_mirror` | Plane-14 tags decoded back to ASCII — read it, it may be an injected instruction |
| `nfkc_equal` | does the text survive NFKC unchanged? |
| `recommendation` | which stages neutralize what was found |

## The sanitizer

`sanitize` runs a staged pipeline and reports **per-stage removal counts**, so you can prove the
payload died rather than hope.

=== "Default pipeline (14 stages)"

    ```
    strip_controls             Remove C0/C1 control codes                     → ascii-ctrl
    strip_zero_width           Remove zero-widths & invisible operators       → zw-binary, zw-octal, omni16
    strip_bidi                 Remove bidi controls                           → bidi, omni16
    strip_tags                 Remove Plane 14 tag block                      → tags
    strip_variation_selectors  Remove variation selectors                     → vs-bytes
    strip_fillers              Remove Hangul fillers                          → fillers, omni16
    strip_combining            Remove combining marks                         → combining
    strip_format               Remove all category-Cf controls                → omni16
    strip_default_ignorable    Remove default-ignorable ranges                → belt and braces
    confusables_to_ascii       Fold confusables to ASCII                      → homoglyph, punct
    fullwidth_fold             Fold fullwidth/compatibility forms             → fullwidth
    punct_fold                 Normalize punctuation twins                    → punct
    collapse_spaces            Collapse whitespace variants                   → spaces
    nfkc                       NFKC normalize                                 → fullwidth, combining, vs-bytes, spaces
    ```

Arrows name the channels each stage kills. `glyphmark sanitize --list-stages` prints the same list
with one explanatory sentence per stage.

=== "Opt-in aggressive stages (2)"

    ```
    script_allowlist           Keep Latin+Common letters only                 → homoglyph, fillers
    ascii_transcode            Force 7-bit ASCII                              → zw-binary, zw-octal, omni16, tags, vs-bytes, bidi, fillers, homoglyph, fullwidth, punct, spaces, combining
    ```

    Both **damage legitimate text** (any non-Latin script, any accent). Use them only for ASCII-only
    sinks, and know that you are choosing damage over leakage.

```bash
uv run glyphmark sanitize --list-stages                    # the table, live
uv run glyphmark sanitize --text-file in.txt -o out.txt    # default pipeline
uv run glyphmark sanitize --text-file in.txt \
    --stage strip_tags --stage strip_zero_width --stage nfkc
uv run glyphmark sanitize --text-file in.txt -e json | jq '.removed_total'
```

## Intake recipe for untrusted text

Anything that reaches a model, a template, or a render path should be sanitized *before* use:

```bash
uv run glyphmark sanitize --text-file user_input.txt \
    --stage strip_controls --stage strip_zero_width --stage strip_bidi \
    --stage strip_tags --stage strip_variation_selectors --stage nfkc \
    -o safe.txt
uv run glyphmark detect --text-file safe.txt --fail-on-risk 5 || exit 1
```

The default pipeline is that plus the rest, and is what you want unless you have a reason not to.
Passing it through twice is idempotent for the invisible families (a second pass removes nothing).

!!! tip "Prompt-injection triage"
    Check `tag_block_mirror` **first**: Plane-14 tags are invisible to humans but survive tokenizers,
    so a mirrored ASCII string like `ignore previous instructions` is the highest-value thing in the
    report.

## Proving removal (the invariant)

```bash
uv run glyphmark encode --cover-file doc.txt --payload "id=7" --scheme homoglyph -o m.txt
uv run glyphmark detect --text-file m.txt --fail-on-risk 1      # exit 6: something is there
uv run glyphmark sanitize --text-file m.txt -o c.txt
uv run glyphmark detect --text-file c.txt --fail-on-risk 1      # exit 0: nothing left
```

The test suite asserts exactly this for every channel, so a sanitizer regression is a build failure.

## CI gate example

```yaml
# .github/workflows/text-intake.yml
- name: reject covert channels in submitted text
  run: |
    uv run glyphmark detect --text-file build/submitted.txt --fail-on-risk 40
```

Exit `6` fails the step, and GitHub shows the report from stderr. For a fleet, call
`POST /api/detect` and branch on `risk_score` / the `exit_code` in error bodies.

## Limits of detection

* A mark from a *different* framing (not GlyphMark's magic + CRC) shows up as raw code-point
  anomalies, never as `watermark-confirmed`.
* Substitution channels are inherently ambiguous with legitimate text; only script/block policies
  make them actionable, and those policies cost you real characters.
* Detection is a snapshot: a downstream `.strip()`, HTML unescape or normalizer may remove (or add)
  signals after you scanned. Scan as late as possible, sanitize at intake.
