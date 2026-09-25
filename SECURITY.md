# Security Policy

GlyphMark is a tool for writing and destroying invisible marks in text. It is also, by design,
usable to attack: the same primitives that sign your documents are the ones behind homograph
phishing and hidden prompt injection. This policy covers both halves — how to report a problem,
what we consider a vulnerability, and what you can expect back.

## Supported versions

| version | supported | notes |
|---|---|---|
| `0.1.x` (current `main` + latest tag) | ✅ | security fixes are back-ported to the latest tag when possible |
| anything older | ❌ | upgrade first; most reports are already fixed |

The project is pre-1.0: frame format, CLI flags and JSON shapes may change. The **frame format is a
stability boundary** — `docs/reference.md` records magic byte and version, and a format change is a
governance decision because it silently invalidates marks already in the wild.

## What counts as a vulnerability

| in scope | out of scope |
|---|---|
| `encode`/`decode`/`detect`/`sanitize` crashing or misbehaving on hostile input (memory safety is delegated to CPython, but panics, unbounded memory, quadratic blowups, or a denial of service via a small input are in scope) | marks surviving a pipeline that is documented as destructive (normalization, re-typing, translation) |
| the web UI or API being reachable in a way that lets someone read another user's data, execute code, or bypass the CSP | the fact that `detect` is a heuristic and can be evaded by a channel we do not implement |
| XSS / script injection through the UI's rendering of text, code points or names | a third party's normalizer removing our marks |
| path traversal, SSRF, or arbitrary file read via any endpoint (including `/docs/`) | payloads being readable by anyone holding the `--key` — keyed mode is documented as obfuscation, not encryption |
| a frame-format collision: text that is *not* ours decoding as `watermark-confirmed` | detection not flagging a channel that is documented as confusable-ambiguous |
| a channel becoming distinguishable in a way that breaks a documented claim in the docs | legitimate non-Latin text triggering `confusables` (that is a documented heuristic limitation, though please still file it — bias matters, it is just not a security bug) |

## Reporting a vulnerability

**Do not open a public issue.**

1. Use **GitHub private vulnerability reporting** on this repository:
   *Security* → *Advisories* → *Report a vulnerability*. If that is disabled, email every
   maintainer listed in [MAINTAINERS.md](MAINTAINERS.md) with the subject
   `glyphmark: security report`.
2. Include: version or commit, the exact input (a minimal reproducer — a code point list is enough),
   the platform, and what you expected instead.
3. We acknowledge within **5 business days**, triage within **10**, and keep a private advisory
   thread with you while a fix lands.
4. Fix + test land on `main`, then a release is published with a Security section in
   [CHANGELOG.md](CHANGELOG.md), and the advisory is made public with credit to you (your choice of
   anonymity is respected).
5. Coordinated disclosure window: **90 days** or the release, whichever comes first. We will not
   sit on a fix past 90 days; if we cannot fix it in time we will say so publicly and document the
   mitigation.

Please do not publish a reproducer before the advisory is public.

## Hardening expectations for users

`glyphmark serve` is a **single-user, local** dev server. Before exposing it to anything else:

* keep `--host 127.0.0.1`; anything beyond localhost needs auth in front of it (there is none);
* treat `POST /api/encode` as privileged — it forges attribution onto arbitrary text;
* keys are secrets: `--key` values are never logged, stored in `localStorage`, or echoed into result
  views, but they *do* reach the process list and (if typed literally) your shell history —
  `--key "$GLYPHMARK_KEY"` keeps the literal out of history, though `ps` still shows the resolved
  value. A `--key-file`/environment input is a roadmap item;
* the web UI is served with a CSP that allows scripts from this origin plus `cdn.jsdelivr.net`
  (Tailwind/Alpine, cosmetic only) and permits `'unsafe-inline'` scripts **only** on `/docs/*`,
  because the MkDocs Material runtime needs it; block the CDN and the UI still works. `frame-ancestors
  'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  same-origin` and a restrictive `Permissions-Policy` are set on every response;
* request bodies are capped at 4 MB / 400 000 characters per text field, and `/docs/<asset>` is
  served through `send_from_directory`, which refuses path traversal.

## Threat model (summary)

Full version in [`docs/security.md`](docs/security.md).

| asset | threat | control |
|---|---|---|
| integrity of your marks | silent corruption read as success | magic byte + CRC32 → exit 4, never silent garbage |
| confidentiality of a mark | casual reading | keyed frames (SHA-256 keystream); documented as obfuscation only |
| your text against untrusted input | hidden instructions in text you feed a model | `detect` (`tags_block`, `bidi_controls`, `tag_block_mirror`), `sanitize` at intake |
| the API | unauthenticated remote use | binds to localhost by default, no cookies, 4 MB cap, strict CSP, no state |
| the sanitizer | damage to legitimate text | aggressive stages (`script_allowlist`, `ascii_transcode`) are opt-in and labelled |

## Audits, scanning and evidence

| control | where |
|---|---|
| CI unit + integration tests (205) on Python 3.10 and 3.13 | `.github/workflows/ci.yml` (`test`) |
| Lint, formatting, SPDX licence headers | `.github/workflows/ci.yml` (`lint`, `license-headers`) |
| DCO sign-off enforced on pull requests | `.github/workflows/ci.yml` (`dco`) + `tools/check_dco.py` |
| Headless DOM UI tests against the real API | `.github/workflows/ci.yml` (`ui`) |
| Docs strict build + docs/code drift tests | `.github/workflows/ci.yml` (`docs`) |
| Repository-governance contract tests | `.github/workflows/ci.yml` (`repo-hygiene`) |
| SAST (CodeQL, Python + JavaScript, `security-and-quality`) | `.github/workflows/codeql.yml` |
| OpenSSF Scorecard, published as an artifact + SARIF | `.github/workflows/scorecard.yml` |
| Dependency vulnerability audit (`pip-audit`, `npm audit`) + secret scan | `.github/workflows/deps-audit.yml` |
| Advisory/licence gate on new dependencies | `.github/workflows/dependency-review.yml`, `.github/dependabot.yml` |
| Build provenance (SLSA attestations) + CycloneDX SBOM on releases | `.github/workflows/release.yml` |
| Branch protection and repository settings as code | `.github/settings.yml` |

Workflow actions are pinned by release tag and kept current by Dependabot rather than by commit SHA
(the Scorecard maximum); SHA pinning is recorded in `ROADMAP.md`. Signed Scorecard attestations
(`publish_results: true`) are the compensating control for the moment.

If you need a formal third-party assessment for a deployment, ask; we will share the Scorecard
artifacts and, if you fund it, publish the report.

## Related documents

[docs/security.md](docs/security.md) · [docs/defence.md](docs/defence.md) ·
[docs/ethics.md](docs/ethics.md) · [GOVERNANCE.md](GOVERNANCE.md) · [SUPPORT.md](SUPPORT.md)
