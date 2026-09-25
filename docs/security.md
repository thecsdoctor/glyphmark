# Security model

This page is what GlyphMark is and is not protected against — the threat model behind the tool, and
behind running it. The reporting policy (how to tell us about a bug, timelines, what is in scope) is
`SECURITY.md` at the repository root.

## What GlyphMark protects, and how

| you want | mechanism | strength |
|---|---|---|
| a mark that survives copy/paste and looks like plain text | insert-family channels (zero-width, tags, variation selectors, bidi, fillers, combining) | as strong as the pipeline's tolerance: anything that normalizes or re-renders text weakens it |
| attribution you can prove later | frame format with magic byte + version + scheme index + CRC32 | verifiable integrity of *what was embedded*, not of who embedded it |
| a mark only the intended reader can decode | keyed frames — SHA-256-derived keystream | **obfuscation only.** Anyone with the key decodes; anyone without the key sees plausible noise. Not encryption |
| evidence that text was sanitised before use | detect → sanitize → re-detect, with the automatic re-scan in the UI and `--fail-on-risk` on the CLI | auditable if you keep the report |

!!! danger "What no text watermark can do"
    Prove *who* wrote something, survive deliberate adversarial stripping, or resist someone willing
    to retype the text. A text watermark is a Tamper-Evident Envelope, not a signature: it tells you
    a payload was placed here and whether it is intact. Attributing authorship needs signatures over
    content (PGP, C2PA, or a document-level signature) — GlyphMark does not do that, and a workflow
    that needs it should not pretend otherwise.

Keyed mode deserves the same honesty: SHA-256 keystream + CRC32 makes a mark *unreadable without the
key* and *tamper-evident*, and nothing more. It has no nonce management, no authentication tag, no
forward secrecy. If the confidentiality of the payload matters, encrypt it properly first and
watermark the ciphertext.

## Threat model for the text

| attacker | capability | what they can do | what stops them |
|---|---|---|---|
| casual reader | reads text | nothing — marks are invisible by construction | — |
| content pipeline | normalizes, converts, re-renders | strips marks as a side effect (NFKC, HTML strip, transliteration) | choose a channel by survival rating; re-stamp after each hop |
| suspicious analyst | inspects code points | finds insert-family marks with `glyphmark detect` or a hex editor | keyed mode hides the payload, not the presence |
| deliberate adversary | controls the pipeline | retypes, screenshots/OCR, re-encodes, strips all Cf characters | nothing at the code-point level; this is why structural/semantic watermarking is a different field |
| adversary with the key | knows the scheme | decodes and forges marks | out of scope: key custody is the whole security boundary |

The last two rows are the reason this project ships detection and sanitization alongside the writer.
A toolkit that only writes marks is half a tool.

## Threat model for the API

`glyphmark serve` is a **single-user, local** server. Everything below is the actual deployed
posture, not an aspiration:

| aspect | posture |
|---|---|
| bind address | `127.0.0.1` by default; no authentication exists, so anything beyond localhost needs an authenticating proxy in front |
| state | none: no cookies, no sessions, nothing persisted server-side; the browser's session restore is `localStorage` and never stores a binding key |
| request size | 4 MB body cap, 400 000 characters per text field |
| CSP | scripts from this origin plus `cdn.jsdelivr.net` (Tailwind/Alpine — cosmetic; the UI works without them). `'unsafe-inline'` scripts are allowed **only** under `/docs/`, where the docs theme needs them |
| other headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` denying camera/mic/geolocation |
| docs assets | served with `send_from_directory` from the build directory; `../` traversal returns 404 |
| output | the UI renders user text as text, never as HTML; code points are escaped in every proof view |

The API can *forge attribution*: `POST /api/encode` writes a mark into arbitrary text. If you expose
it, you are exposing the ability to stamp documents as if they were yours. Treat it as privileged,
put auth in front of it, and log the caller.

## Keys

* A binding key is a shared secret with no KDF, no salt and no rotation — treat it as a symmetric
  key and protect it accordingly.
* A binding key arrives as a command-line argument (`--key`), so on a shared machine assume it is
  visible in `ps` output and in your shell history. Passing it as a shell variable
  (`--key "$GLYPHMARK_KEY"`) at least keeps the literal out of your history — the resolved value is
  still in the process list. There is no key-file or environment-variable input yet; it is a roadmap
  item, so treat a key typed on a shared host as exposed and rotate it.
* Keys are never written to logs, into API responses, or into `localStorage` (`app.js` strips them
  from the persisted session; a test asserts it).
* Losing a key makes keyed marks permanently unreadable — there is no recovery path, by design.

## Defensive reading of detections

A detection is a **signal, not a verdict**. `confusables` fires on legitimate Cyrillic/Greek text that
merely mixes scripts; `fullwidth_forms` fires on Japanese text; `space_variants` fires on typographic
quotes. Read the report as "these code points are unusual for this text" and act on the kind and the
count, not on the score alone. Before you accuse anyone of anything with this tool:

1. `glyphmark inspect --only-suspect` — what exactly is in there.
2. Is there a **frame signature**? `watermark-confirmed` means our frame decoded with a valid CRC;
   that is evidence. A high risk score alone is not.
3. Could the text have passed through a pipeline that produces these code points legitimately
   (translation, transliteration, PDF copy/paste, a rich-text editor)?
4. Sanitize and compare. If removing the code points does not change the meaning, the mark was
   ornamental — which is its own answer.

## Running this in production

* Pin the version. The frame format carries a version byte; a mark written by 0.1 must stay readable.
* Call `/api/detect` (or the CLI with `--json`) from a deny-by-default intake path; keep the JSON
  report with the item so a later decision can be re-examined.
* Gate CI with `glyphmark detect --fail-on-risk 25` on anything you publish.
* Do not post untrusted text into the UI on a shared machine — the detect panel renders text, and
  the input itself may carry social-engineering payloads.
* If you keep watermarked documents, keep the keys in a secret manager. A leaked key is a forgery
  capability, not just a disclosure.

## Reporting

Private vulnerability reporting, timelines, and the in-scope/out-of-scope table live in
`SECURITY.md` at the root. Short version: GitHub private advisory, acknowledgement inside 5 business
days, fix or public statement inside 90 days.

Related: [Defence playbook](defence.md) · [Reference](reference.md) · [Responsible use](ethics.md)
