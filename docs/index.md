# GlyphMark

**GlyphMark** is a text watermarking toolkit that works on the gap between *rendered glyphs* and
*code points*: a payload can ride inside a string without changing what a reader sees. The same
engine is reachable two ways — a fully non-interactive **CLI** and a **web UI / JSON API** — and it
ships the attack and the defence in one binary: embed a mark, then find and destroy marks (yours or
someone else's).

```{ .sh .no-copy }
uv run glyphmark encode --cover "Plain carrier text." --payload "id=42" --scheme tags -o marked.txt
uv run glyphmark decode --text-file marked.txt          # -> id=42
uv run glyphmark detect --text-file marked.txt          # -> risk=100 verdict=watermark-confirmed
uv run glyphmark sanitize --text-file marked.txt        # -> mark destroyed, per-stage accounting
```

## What it does

| capability | command | web panel |
|---|---|---|
| embed a payload in visible text | `glyphmark encode` | **Embed** |
| recover a payload (sweeps every channel) | `glyphmark decode` | **Extract** |
| prove a mark is present, or flag anomalies | `glyphmark detect` | **Detect** |
| strip covert channels from untrusted text | `glyphmark sanitize` | **Sanitize** |
| per-code-point forensics | `glyphmark inspect` | **Inspect** |
| channel/character reference + self test | `glyphmark schemes` `scheme` `chars` `verify` | **Reference** |

Two families of channels are implemented:

* **insert** — invisible code points (zero-widths, Plane-14 tags, variation selectors, bidi marks,
  Hangul fillers, C0 controls, combining marks) are woven between the visible characters.
* **substitute** — visible characters are swapped for look-alikes (Cyrillic/Greek homoglyphs,
  fullwidth forms, punctuation twins, whitespace variants). Nothing is added, and the text still
  reads the same.

Every frame is checksummed, so a hit is a *positive identification* rather than a guess, and a
tampered or wrongly keyed mark fails loudly instead of returning garbage.

## Where to go next

* [Quickstart](quickstart.md) — the five-minute tour of both interfaces.
* [CLI reference](cli.md) — every command, flag, output format and exit code.
* [Web UI guide](ui.md) — panels, keyboard shortcuts, and how to read each result view.
* [Channels](channels.md) — capacity, stealth, survival and countermeasures per channel.
* [Detection & sanitization](defence.md) — the defensive playbook, including a CI gate.
* [HTTP API](api.md) — `POST /api/*` shapes and the CLI exit codes they carry.
* [Reference](reference.md) — frame format, keyed mode, limits.
* [Responsible use](ethics.md) — disclosure, privacy and the limits of character-level marks.

## Install

```bash
git clone <this repo> && cd glyphmark
uv sync --extra dev          # runtime deps + pytest/ruff
uv run glyphmark --help
```

Optional extras:

```bash
uv sync --extra dev --extra docs   # + mkdocs-material, used by `glyphmark docs build`
```

??? tip "No `uv`?"
    `python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'`
    works the same; every command below that starts with `uv run` can then drop the `uv run`.

## Documentation as a page

This site is MkDocs Material, built and served **by the app itself**:

```bash
uv run glyphmark docs build          # renders docs/ into build/docs
uv run glyphmark serve               # this site is now on http://127.0.0.1:8123/docs/
```

`/docs/` is served straight from that build directory. If it has not been built yet, the page tells
you the command to run instead of 404-ing — see [Building the docs](reference.md#building-the-docs).

## A four-line mental model

1. Text is a sequence of code points; several code points render identically.
2. Encode maps payload bits onto carrier positions drawn from one channel's alphabet.
3. Decode reads those positions back, then validates a magic byte and a CRC32.
4. Sanitize reorders/removes code points by category — which is exactly what kills those marks.

Everything else in these pages is detail around those four lines.
