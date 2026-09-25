---
name: Bug report
about: Something does not do what the docs say it does
title: "[bug] "
labels: [bug]
assignees: []
---

<!--
If this is a SECURITY issue, do not open an issue - use private vulnerability
reporting (SECURITY.md). If the text you are testing belongs to someone else,
redact it: use synthetic cover text in reports.
-->

## What happened

<!-- One or two sentences. "decode returns plausible garbage instead of exit 4" beats "broken". -->

## What I expected

## Reproduce

```bash
# exact commands, including flags and the version from `glyphmark --version`
```

Input, as code points (this is usually the whole diagnosis):

```bash
glyphmark inspect --text 'PASTE' --json | head -40
# or, minimally:
python -c "print([hex(ord(c)) for c in 'PASTE'])"
```

| | |
|---|---|
| GlyphMark | `glyphmark --version` |
| Python | `python -V` |
| OS | |
| Install | `uv sync` / `pip install -e .` / other |

## Output

```
paste stdout/stderr (with --report if you used it)
```

## Which surface

<!-- tick all that apply -->
- [ ] CLI
- [ ] web UI
- [ ] HTTP API (`/api/...`)
- [ ] docs (wrong or missing information)

## Channel / stage involved

<!-- e.g. scheme `tags`, detection kind `tags_block`, sanitizer stage `strip_tags`. `none` if unknown. -->

## Sanity checks already done

- [ ] `glyphmark verify` passes (or fails, with output above)
- [ ] reproduced on a fresh checkout / `pip install -e .`
- [ ] checked `docs/cli.md` / `docs/ui.md` / `docs/reference.md` for a documented limitation

## Additional context

<!-- Related issues, workarounds, a proposed fix, or "this text is synthetic". -->
