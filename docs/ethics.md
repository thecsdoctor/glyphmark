# Responsible use

Character-level watermarks are a dual-use tool by construction: the mechanism that lets you sign your
own text is the mechanism behind homograph phishing and hidden prompt injection. GlyphMark therefore
ships encode, detect and sanitize in one binary — the defence is not an optional extra.

## Do

* **Watermark text you own or are authorized to mark** — your own model output, your own documents, a
  system you operate.
* **Disclose it.** If your product stamps provenance marks into generated text, say so in the
  documentation and, where practical, in the UI. A mark that surprises its reader becomes an incident.
* **Keep payloads non-sensitive.** A keyed frame is obfuscation, not encryption: magic and version
  stay in clear text and the secret is the only barrier. Put an id or a pointer in the payload, never
  a personal datum.
* **Sanitize at intake.** Text arriving from users, the web, or another model goes through
  `sanitize` before it reaches a model, a template or a render path.
* **Use detection to review, not to accuse.** `watermark-confirmed` is an identification; every other
  finding is a heuristic that legitimate multilingual text can also trigger.
* **Keep the ethics file honest.** If a channel's documented weakness turns out to matter in the
  field, fix the docs and the defaults.

## Don't

* **Don't mark other people's text without consent.** Attribution that a reader cannot see or remove
  is covert data collection.
* **Don't use `homoglyph`, `fullwidth` or `omni16` against people.** Swapping characters in someone
  else's URL, domain or document is the homograph-attack pattern.
* **Don't build a detector that punishes non-Latin scripts.** Confusable detection has a real bias
  risk: legitimate Cyrillic/Greek text looks like an attack to a naive rule. Prefer quarantine +
  human review over auto-blocking, and never ship `script_allowlist` as a silent default.
* **Don't rely on marks for durability.** They do not survive re-typing, translation, OCR, model
  rewriting or a whitespace-trimming formatter. Use them for provenance *hints* and defence
  exercises; use document- or model-level watermarking for anything you must prove later.
* **Don't expose `serve` to a network.** `/api/encode` will forge attribution onto arbitrary text and
  there is no auth; bind to `127.0.0.1` or put it behind real authentication and TLS.

## Legal and policy notes

* Watermark-evasion and watermark-removal are legally protected in some contexts (security research,
  accessibility, interoperability) and restricted in others (some anti-circumvention regimes). Know
  which one you are in before removing a mark you do not own.
* Regulators increasingly expect provenance disclosure for synthetic text
  ([EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) Article 50 machine-readable marking for
  AI-generated text; C2PA for media). A character-level mark can *help* you comply — it does not by
  itself constitute compliance.
* Undisclosed tracking of individuals can engage GDPR/CCPA-style obligations. If the payload can be
  tied back to a person, treat it as personal data.

## Threat model this tool addresses

| threat | GlyphMark's answer |
|---|---|
| hidden instructions in text fed to an LLM | `detect` → `tags_block`, `bidi_controls`, `tag_block_mirror`; `sanitize` kills them |
| look-alike domains / documents | `confusables`, `script_mixing` findings; `confusables_to_ascii`, `script_allowlist` |
| attribution of your own generated text | `encode` with a keyed frame (`vs-bytes`, `tags`) |
| "did our sanitizer work?" | sanitize-then-detect invariant, asserted per channel in the test suite |
| sanitizer blind spots | `omni16`/`fillers` exist specifically to fall through category-`Cf` filters |

## If you find a mark you did not put there

1. Save the raw bytes (`cp suspect.txt suspect.raw`), not a re-typed copy — the marks live in the
   bytes.
2. `uv run glyphmark inspect --text-file suspect.raw --only-suspect` to see exactly what is in it.
3. `uv run glyphmark detect --text-file suspect.raw --json > report.json` for the findings and, if
   you are lucky, a `frame_signature` naming the channel and previewing the payload.
4. `uv run glyphmark sanitize --text-file suspect.raw -o clean.raw` and work from `clean.raw`.
5. If it is a GlyphMark frame, the payload preview usually identifies who wrote it. Report it to the
   owner of the system that produced it.

## Contributing

Changes that make encoding easier should come with changes that make detection better. Pull requests
that add a channel are expected to add: detection coverage, at least one sanitizer stage that kills
it (`killed_by`), a round-trip test, a detect→sanitize→clean test, and a paragraph in
[Channels](channels.md) about how it can be abused.
