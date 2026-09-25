# Roadmap

Direction, not a commitment. Dates here are intentions; the project is maintained in spare time and
"when it's done" is the honest schedule. Priorities are set in issues per
[GOVERNANCE.md](GOVERNANCE.md) — if you want something moved up, the argument belongs in an issue.

## Now (in flight or next up)

| item | why | status |
|---|---|---|
| Frame format stability policy | marks written today must stay readable; versioning rules for the magic byte/version need to be written down, not implied | `docs/reference.md` records the format; policy text is open |
| Channel capacity measurement harness | capacity claims are measured per release against fixed covers today, by hand; automate them so `docs/channels.md` numbers cannot drift | open |
| Detector threshold calibration | severity weights and risk bands were reasoned, not fitted; need a corpus-backed pass (including non-Latin cover text, to bound false positives) | open |
| Streaming / file-batch APIs | `detect` and `sanitize` on directories and stdin streams without loading whole files | open |
| Two-release deprecation policy applied | documented in GOVERNANCE; nothing deprecated yet | n/a |
| Key input hardening | a binding key arrives in argv, so it is visible in `ps` and shell history; needs file/environment input and a rotation note. `docs/security.md` points here | open |

## Next

| item | why |
|---|---|
| `glyphmark audit` — one-shot intake pipeline (detect → sanitize → re-detect → report) | the defence recipe is four commands; the composition is what teams actually need |
| Configurable policy file | pin stages, allowed scripts and exit thresholds per organisation instead of repeating flags |
| Position-preserving sanitization | emit a report of what was removed where, so sanitization is reviewable rather than silent |
| Column/line mapping for findings | findings report code-point offsets; humans want line:col |
| Package distribution: PyPI publish + wheel | today you install from source with `uv`/`pip -e`; a published package removes a whole class of setup friction |
| OpenSSF Best Practices badge (passing level) | self-assessment against the criteria, then claim the badge; the gap list is short and mostly process |
| CNCF sandbox application | needs: two active maintainers, a public roadmap (this file), governance (done), adopters (`ADOPTERS.md`), security self-assessment, and either CII badge or an equivalent narrative |

## Later / research

| item | why |
|---|---|
| Robustness scoring under real pipelines | publish measured survival across a matrix (Markdown render, JSON round-trip, HTML strip, copy/paste through common apps) instead of a 1–5 rating |
| Image and PDF text pipelines | the marks discussed in the research (PDF text objects, invisible glyphs) are adjacent and mostly a different substrate |
| Language-model-aware detectors | prompt-injection defence where the reader is a model; the detection signal differs from human-visible spoofing |
| Structural watermarking (paraphrase-level) | genuinely different problem; would be a separate project if ever attempted |
| Keyed integrity hardening | CRC32 is a tamper *indicator*, not a MAC; a keyed hash is a small change with a compatibility cost, so it needs a governance vote |

## Explicitly not planned

* Anything whose primary purpose is stealthy surveillance or evading abuse detection.
* Cryptographic claims: this project will not advertise "encrypted watermarking" for what is a
  keystream (see `docs/reference.md`).
* Breaking other people's watermarks as a service.

## How to influence it

Open an issue with the use case and, if you have it, data. A PR is a strong vote: shipped code moves
roadmaps faster than arguments.
