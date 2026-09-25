<!--
Thanks for contributing. Delete this banner; keep the headings - they are the checklist a
reviewer works through, and the boxes are how we remember what "done" means (CONTRIBUTING.md).
-->

## Summary

<!-- 2-4 sentences: what changes and why. If it closes an issue, link it below. -->

Closes #

## Type of change

- [ ] bug fix
- [ ] new/changed watermark channel
- [ ] detection or sanitization change
- [ ] CLI / API / UI surface
- [ ] docs only
- [ ] tests / CI / tooling
- [ ] **breaking** (CLI flag, JSON field, frame format) — needs `breaking` label + a governance vote

## How it works

<!-- For behaviour changes: the mechanism, not just the effect. For channels: alphabet, radix, carrier rule. -->

## Attack/defence pairing

<!-- Required for any channel or detection change (docs/ethics.md). -->

- [ ] new channel → detection emits a finding for it (`analysis.py`)
- [ ] new channel → a sanitizer stage removes it (`sanitize.py`), and `killed_by` is set
- [ ] sanitize → detect comes back clean (the parametrized test covers it)
- [ ] abuse note added to `docs/channels.md`
- [ ] false-positive impact considered (non-Latin text, emoji, normalizers)

## Both interfaces

The CLI and the web UI/API must offer the same functionality.

- [ ] CLI flag(s) added/documented (`--help` + `docs/cli.md`)
- [ ] API field(s) added/documented (`/api/...` + `docs/api.md`)
- [ ] UI control added for the API change (`index.html` + `app.js`), or a note on why the UI needs none

## Evidence

```
paste the output that proves it works - real output, not a description
```

- [ ] `make check` passes locally (`pytest`, `ruff`, JS syntax, license headers, strict docs)
- [ ] `npm run ui-smoke` passes when the PR touches the UI
- [ ] new tests would fail without this change
- [ ] docs updated in this PR (`tests/test_docs.py` fails if docs claim things the code does not do)

## Exit codes / status codes

If behaviour changed, confirm both mappings and that `docs/cli.md` + `docs/api.md` match:
`0` ok · `1` error · `2` click usage · `3` no payload · `4` corrupt/wrong key · `5` carrier too small ·
`6` risk threshold.

## Compatibility

- [ ] marks written by an earlier version still decode (or: this is a documented frame-format change
      with a version bump and a governance vote)
- [ ] no new runtime dependency (or: governance vote linked)

## DCO

- [ ] every commit is signed (`git commit -s`) and carries `Signed-off-by:`

## Notes for the reviewer

<!-- Where to start, what you are unsure about, what you deliberately did not do. -->
