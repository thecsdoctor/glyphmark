# Channels

Thirteen channels, two families:

* **insert** — invisible code points are added *between* visible characters. Nothing changes
  visually; the string grows.
* **substitute** — visible characters are *replaced* by look-alikes. The string does not grow; the
  bytes do.

| id | family | bits / unit | bytes / unit | stealth | survival | carrier | killed by |
|---|---|---|---|---|---|---|---|
| `zw-binary` | insert | 1 | 0.125 | ●●●●● | ●●●○○ | one insertion point per character | `strip_zero_width`, `strip_format` |
| `zw-octal` | insert | 3 | 0.375 | ●●●●● | ●●●○○ | one insertion point per character | `strip_zero_width`, `strip_format` |
| `omni16` | insert | 4 | 0.5 | ●●●●○ | ●●●●○ | one insertion point per character | `strip_zero_width`, `strip_format`, `strip_bidi`, `strip_fillers` |
| `tags` | insert | 6 | 0.75 | ●●●●● | ●●○○○ | one insertion point per character | `strip_tags` |
| `vs-bytes` | insert | 8 | 1.0 | ●●●●○ | ●●●○○ | one anchor character per payload byte | `strip_variation_selectors`, `strip_combining` |
| `bidi` | insert | 2 | 0.25 | ●●●○○ | ●●●○○ | one insertion point per character | `strip_bidi`, `strip_format` |
| `fillers` | insert | 1 | 0.125 | ●●●●○ | ●●●●○ | one insertion point per character | `strip_fillers`, `script_allowlist` |
| `homoglyph` | substitute | 1 | 0.125 | ●●●●○ | ●●●●● | each letter that has a confusable counterpart | `confusables_to_ascii`, `script_allowlist` |
| `fullwidth` | substitute | 1 | 0.125 | ●●●○○ | ●●●○○ | any printable ASCII character | `nfkc`, `fullwidth_fold` |
| `punct` | substitute | 1 | 0.125 | ●●●○○ | ●●●●○ | each occurrence of a mappable punctuation character | `punct_fold`, `nfkc` |
| `spaces` | substitute | 4 | 0.5 | ●●○○○ | ●●○○○ | each space in the cover text | `collapse_spaces`, `nfkc` |
| `ascii-ctrl` | insert | 4 | 0.5 | ●●○○○ | ●●○○○ | one insertion point per character | `strip_controls`, `ascii_transcode` |
| `combining` | insert | 4 | 0.5 | ●○○○○ | ●●○○○ | one anchor character per 4 bits | `strip_combining`, `nfkc` |

**stealth** = how much a reader (or a screenshot) can notice.
**survival** = how well the mark survives real pipelines: paste buffers, JSON, HTML, word-wrap,
social platforms, normalization.

`uv run glyphmark schemes` prints the same table live; `uv run glyphmark scheme <id>` adds the full
character alphabet, and the **Reference** panel of the UI shows it with rendering previews.

## Capacity

```
usable bits = carrier units × bits per unit
carrier units = characters the channel can legally touch in your cover text
```

Measured on a **314-character** cover sentence repeated to length (the numbers `encode` reports as
`carrier_units` / spare `capacity_bytes`):

| channel | carrier units | payload capacity |
|---|---|---|
| `zw-binary` | 315 | 39 B |
| `fillers` | 315 | 39 B |
| `bidi` | 315 | 78 B |
| `zw-octal` | 315 | 118 B |
| `omni16` / `combining` / `ascii-ctrl` | 315 / 314 | 157 B |
| `tags` | 315 | 236 B |
| `vs-bytes` | 314 | 314 B |
| `fullwidth` | 252 | 31 B (1 bit per carrier) |
| `spaces` | 62 | 31 B (4 bits per space) |
| `homoglyph` | 133 | 16 B (only letters with a confusable twin) |

`encode` refuses with exit `5` when the payload does not fit and reports spare capacity when it
does; the UI shows the same numbers live while you type (`glyphmark encode --report` prints them to
stderr).

## Channel notes

### `zw-binary` — zero-width binary
ZWSP = 0, ZWNJ = 1: the classic 1-bit channel. Maximum tool compatibility, minimum density. Nearly
every "clean text" library already knows these two code points, so treat it as a demo, not a
production mark.

### `zw-octal` — zero-width octal
3 bits per inserted character: `ZWSP/ZWNJ/ZWJ/WORD JOINER` plus the four invisible mathematical
operators `U+2061..U+2064`. Naive filters strip only `U+200B-200D`, so the math operators often
survive; a full category-`Cf` sweep removes all eight.

### `omni16` — omni-invisible base-16
Zero-widths + invisible operators + BOM + Mongolian vowel separator + Hangul fillers + bidi marks in
one radix: 4 bits per character. Its spread is the point — only a block allow-list catches all of
it. Note that `U+3164`/`U+FFA0` are category **Lo (letters)**, so "strip Cf" filters walk right past
them. Unpaired bidi isolates can visibly reorder glyphs inside RTL text.

### `tags` — Unicode Tags block (Plane 14)
`U+E0020..U+E005F` mirror ASCII `0x20..0x5F` and are suppressed by renderers: 6 bits per character,
and the block that LLM tokenizers read back as text — this is the mechanism behind
hidden-instruction-injection research. Rejected by strict XML/JSON parsers and some DB collations;
social platforms strip Plane 14 on ingestion, raw paste buffers keep it.

### `vs-bytes` — variation selectors
`VS1–VS16` + `VS17–VS256` = exactly 256 selectors, i.e. one whole hidden byte clamped onto each
anchor character — the highest density per character available. Some fonts draw a dotted box for a
selector sitting on an unusual base character.

### `bidi` — bidirectional marks
LRM/RLM plus first/last bidi isolates: 2 bits per character, invisible in LTR prose. Any bidi
control inside an all-LTR document *is* the signal for a defender; mismatched overrides visibly
reverse neighbouring glyphs, which is the classic tell.

### `fillers` — Hangul fillers
`U+3164`/`U+FFA0` render as nothing in Latin text yet are letters (`Lo`), so category-based `Cf`
filters miss them entirely. A good fallback to pair with a homoglyph mark; a mixed-script check
catches it.

### `homoglyph` — cross-script homoglyphs
Latin letters swapped for Cyrillic/Greek/Armenian look-alikes. Nothing invisible is added, so almost
no sanitizer catches it: it survives copy-paste, JSON, SQL and social platforms. It also breaks exact
matching, search and case folding — the same property that makes homograph phishing work, which is
why detection (`UTS #39` skeletons) and `confusables_to_ascii` ship in the same binary.

### `fullwidth` — fullwidth look-alikes
ASCII `0x21-0x7E` → `U+FF01-FF5E`. Identical in most monospace UIs; one NFKC pass collapses the
whole compatibility block, so survival in normalized pipelines is poor but survival in "we just
store the string" systems is good.

### `punct` — punctuation twins
Hyphen, apostrophe, quote, asterisk, tilde and period become near-identical typographic twins. Low
capacity in prose, but enough to sign code blocks and config dumps.

### `spaces` — space alphabet
Each word-gap space becomes one of 15 look-alike blanks (NBSP, en/em/thin/hair, NNBSP, ideographic,
Ogham, Mongolian vowel separator): 4 bits per space. Word-wrap, editor auto-format and
whitespace-trimming formatters destroy it — keep payloads tiny or use pre-formatted text.

### `ascii-ctrl` — ASCII C0 control nibbles
For pipelines forced to 7-bit ASCII: 16 non-rendering C0 codes carry nibbles. Invisible in GUIs,
shouting in terminals (`cat -A` shows `^A^B`). The only channel that survives an ISO-8859-1/US-ASCII
transcode; terminals, compilers and web forms strip or escape it aggressively.

### `combining` — combining marks
16 combining diacritics clamped onto anchors. A channel *in principle* — far from invisible in most
fonts. Bundled deliberately as a stress test: it demonstrates why normalization is the single
highest-value defence.

## Choosing

| requirement | use | avoid |
|---|---|---|
| most payload | `vs-bytes`, `tags` | `zw-binary`, `homoglyph` |
| must survive copy-paste + JSON + social | `homoglyph`, `fullwidth`, `punct` | anything invisible |
| must survive ASCII-only transcode | `ascii-ctrl` | all non-ASCII channels |
| must not be detectable by a `Cf` sweep | `omni16`, `fillers`, `spaces` | `zw-octal`, `bidi` |
| must be provable without a key | any — magic byte + version stay in clear text | — |
| must survive your own normalizer | nothing; that is [sanitize](defence.md#the-sanitizer)'s job | — |

!!! warning "Nothing here is robust"
    Re-typing, translation, model rewriting, or any lossy round trip destroys character-level marks.
    Use them for provenance hints and for training defenders — for durable provenance you need
    document- or model-level watermarking as well.
