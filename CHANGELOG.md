# Changelog

All notable changes to GlyphMark are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html), and **the watermark frame format is
treated as a separate stability boundary** documented in `docs/reference.md` — a format change is a
governance decision regardless of the version number it lands in.

Release notes for *you* go under Added/Changed/Fixed; notes about process, votes and maintainers go
under **Governance**.

## [Unreleased]

### Added

* `docs/` — MkDocs Material usage documentation for both interfaces, built with `glyphmark docs
  build` and served by the app at `/docs/`; `glyphmark docs check` builds strictly for CI.
* Web UI: pipeline ribbon (`cover → watermarked → detected → sanitized`), live capacity meter with
  fit recommendations, annotated proof views, what-changed diffs, automatic re-scan after every
  action, keyboard-driven panels, and session restore (binding keys never persisted).
* Project governance: `LICENSE` (MIT), `NOTICE` (third-party and Unicode data attribution),
  `CODE_OF_CONDUCT.md` (CNCF Code of Conduct), `CONTRIBUTING.md` (incl. the add-a-channel
  checklist), `GOVERNANCE.md` (roles, voting, veto, deadlock, emeritus), `MAINTAINERS.md` (with
  machine-readable affiliations), `SECURITY.md` (scope, private reporting, 90-day ceiling),
  `SUPPORT.md`, `ROADMAP.md`, `ADOPTERS.md`, `TRADEMARKS.md`, `CHANGELOG.md`.
* Supply chain: GitHub Actions for CI (Python 3.10/3.13 + coverage), CodeQL
  (`security-and-quality`), OpenSSF Scorecard (signed results + SARIF), `pip-audit`/`npm audit`,
  dependency review with a licence deny-list, Dependabot, a release workflow with CycloneDX SBOM
  and SLSA build provenance, and branch protection as code (`.github/settings.yml`).
* Contribution surface: issue templates (bug / feature / question), `config.yml` contact links,
  pull-request template, `CODEOWNERS` per subsystem, DCO sign-off enforcement
  (`tools/check_dco.py`), SPDX licence headers on every source file
  (`tools/check_license_headers.py`, with `--fix`).
* Developer experience: `Makefile` (every CI task locally, `make check`), `.devcontainer/`,
  `.editorconfig`, richer package metadata (URLs, classifiers, licence files).
* Documentation: three new pages — security model, contributing, community & governance — so the
  governance model is readable where the rest of the docs are.
* Hardening: `X-Frame-Options: DENY`, `Permissions-Policy` (no camera/microphone/geolocation) and
  CSP `frame-ancestors 'none'` on every response; asserted in the tests that document them.
* Tests: 205, including `tests/test_repo_hygiene.py`, which treats the governance and CI setup as a
  contract — required files, required status checks that map to real jobs, `CODEOWNERS` paths that
  still resolve, docs-to-repo link integrity, and the DCO checker's own logic.

### Fixed

* Channel metadata: a channel declaring a single note as a string produced one list item per
  character in `glyphmark scheme <id>` and crashed the UI's channel detail view.
* The web UI's capacity meter now matches the server's calculation exactly for insert, anchored and
  substitution channels, including frame overhead — it previously under-reported `ascii-ctrl`.

## [0.1.0] - 2026-09-25

First public release. One core, two interfaces (non-interactive CLI + web UI/JSON API).

### Added

* **13 watermark channels** across insert and substitute families: `zw-binary`, `zw-octal`,
  `omni16`, `tags`, `vs-bytes`, `bidi`, `fillers`, `homoglyph`, `fullwidth`, `punct`, `spaces`,
  `ascii-ctrl`, `combining` — each with measured payload density, stealth/survival ratings, and the
  sanitization vector that kills it.
* **Frame format**: `0x57` magic, version, scheme index, flags, u16 length, payload, CRC32 — so a
  corrupt or wrong-keyed mark fails loudly (`exit 4`) instead of returning plausible garbage.
* **Keyed mode**: SHA-256-derived keystream (CTR-style) that decorrelates every code point from the
  payload; documented as obfuscation, not encryption.
* **CLI**: `schemes`, `scheme`, `chars`, `encode`, `decode`, `detect`, `sanitize`, `inspect`,
  `verify`, `serve` — fully non-interactive, with file/stdin input resolution, stdout/stderr
  separation for byte-exact output, and stable exit codes (0/1/2/3/4/5/6).
* **Web UI + JSON API**: six panels (Embed, Extract, Detect, Sanitize, Inspect, Reference) on
  `/api/{encode,decode,detect,sanitize,inspect,verify}`, `/api/meta`, `/healthz`; CSP-restricted,
  localhost-bound, no cookies, no stored state, request size caps.
* **Detection**: 15 finding kinds with severity and weight, risk score, verdict, candidate frame
  recovery, Plane-14 tag-block mirror, and a per-code-point forensic inspector.
* **Sanitization**: 16 stages (14 default, 2 opt-in destructive), ordered so normalization does not
  create new marks.
* Tests: channel round-trip matrix (keyed/unkeyed, tamper, capacity), sanitize-then-detect-must-be-
  clean, CLI behaviour, API contracts, UI markup/JS contract tests, docs-vs-code drift guards.
* Headless DOM smoke test (`tools/ui_smoke.mjs`, jsdom) that drives the real UI against a running
  server, including keyboard shortcuts, tabs, ribbon and sanitization flows.

### Known limitations at 0.1.0

* Pre-1.0: CLI flags and JSON field names may change between minor versions.
* Detection is heuristic; confusable analysis can flag legitimate non-Latin text.
* `serve` is a single-user local development server with no authentication.
* No published package yet: install from source with `uv` or `pip -e`.

## Governance

| date | change |
|---|---|
| 2026-09-25 | Adopted MIT licence with `NOTICE`; CNCF Code of Conduct; GOVERNANCE/SECURITY/SUPPORT/ROADMAP/ADOPTERS/TRADEMARKS; initial maintainer list |

<!-- OWNER: replace with the canonical GitHub owner when the repo is published; keep it identical
     to repository.url in .github/settings.yml (a test asserts the two agree). -->
[Unreleased]: https://github.com/OWNER/glyphmark/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/glyphmark/releases/tag/v0.1.0
