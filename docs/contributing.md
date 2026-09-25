# Contributing

Everything a first pull request needs: environment, the commands CI will run, the rules that keep
the two interfaces honest, and the process for channels and releases. The human side — votes, roles,
conduct — is in `GOVERNANCE.md` and `CODE_OF_CONDUCT.md` at the repository root.

## Environment

| need | tool |
|---|---|
| Python | 3.10 → 3.13 (the project's floor is 3.10; CI tests both ends) |
| Package/venv manager | [uv](https://docs.astral.sh/uv/) — nothing else is required |
| Node (optional) | only for the headless UI test (`jsdom`, dev-only) |

```bash
git clone https://github.com/OWNER/glyphmark && cd glyphmark
uv sync --extra dev --extra docs      # runtime + pytest/ruff + mkdocs
npm ci                                # optional: the jsdom UI test
uv run pytest -q                      # 205 tests
uv run glyphmark verify               # every channel round-trips on your interpreter
```

`make help` lists every task CI runs: `test`, `lint`, `fmt`, `docs`, `docs-check`, `ui`, `ui-smoke`,
`verify`, `check`. A devcontainer (`.devcontainer/devcontainer.json`) installs the same set if you
prefer not to touch your machine.

## The bar for every pull request

```bash
make check     # lint + verify + lock consistency + tests + strict docs
```

| gate | what it catches |
|---|---|
| `pytest` | channel round-trips, tamper/wrong-key handling, capacity errors, sanitize→detect-clean, CLI and API contracts, UI markup/JS contracts, docs-vs-code drift |
| `ruff check` + `ruff format --check` | style and the boring correctness rules (`E,F,I,UP,B`, line length 100) |
| `tools/check_license_headers.py` | every source file declares `SPDX-License-Identifier: MIT` |
| `glyphmark docs check --strict` | a broken link or warning in the documentation |
| `tests/test_docs.py` | docs claiming a command, flag, exit code, stage, finding kind or JSON field that does not exist |
| `node --check` + `npm run ui-smoke` | the UI's JS parses, and the real page drives the real API |

If a gate fails for a reason unrelated to your change, say so in the PR instead of working around it.

## Sign your work (DCO)

There is no CLA. Each commit needs a `Signed-off-by:` trailer, which is you stating that you are
allowed to contribute the change:

```bash
git commit -s -m "detect: flag hangul fillers used as separators"
git rebase --exec 'git commit --amend --no-edit -s' origin/main   # re-sign a branch
```

CI verifies the trailer exists and matches the commit author, so a sign-off cannot be borrowed.

## One core, two interfaces

`codec`, `analysis` and `sanitize` hold all behaviour. `cli.py` and `web/app.py` are thin adapters,
and the web UI calls the same API it documents. The rule that follows:

!!! rule "A feature is not finished until both interfaces have it"
    Add the CLI flag, the API field, and the UI control in the same pull request — or say in the
    description why the UI needs none. The drift guards in `tests/test_docs.py` and
    `tests/test_web.py` fail otherwise.

Error mapping is part of the contract: the same failure must produce the same exit code on the CLI
and the same `exit_code` in the API response (`0`, `1`, `2` usage, `3` no payload, `4` corrupt or
wrong key, `5` carrier too small, `6` risk threshold).

## Adding a watermark channel

A channel is cheap to add and expensive to be wrong about, because the metadata is what the detector
and the UI recommend from.

1. **`schemes.py`** — the alphabet, radix (must be a power of two), family (`insert` or
   `substitute`), the carrier rule, and honest metadata: bits per carrier unit, `stealth`,
   `survival`, `carrier`, `killed_by`, `blurb`, `detection`, `notes`.
2. **`sanitize.py`** — at least one stage must remove it. If none does, add the stage; a channel that
   survives every stage is not a watermark, it is damage.
3. **`analysis.py`** — emit a finding: kind, severity, weight, and the stage that removes it.
4. **Tests** — keyed and unkeyed round trip, tamper → `FrameError`, capacity error, and
   sanitize→detect coming back clean. The existing matrix is parametrized, so most of this is free.
5. **Docs** — a row in `channels.md`, a note on how it is abused, and a row in `defence.md`.

Then `glyphmark verify` and `make check`.

## Style that is not in ruff

* **Python** — type hints on public functions, `from __future__ import annotations`, docstrings that
  explain *why* the code exists rather than what the signature already says.
* **JavaScript** — the UI stays framework-free vanilla JS with no build step. CDN assets are
  cosmetic and must stay optional; behaviour that depends on them will be rejected.
* **Tests** — names state the invariant (`test_wrong_key_never_returns_garbage`), not the function
  under test.
* **Docs** — paste real command output rather than reconstructing it from memory. Every number in
  the channel table is measured, not estimated.
* **Commits** — imperative subject, `area: summary` (`codec: keep CRC over the header`, `docs: fix
  capacity table for vs-bytes`).

## Documentation rules

Docs live in `docs/` and are built and served by the app itself:

```bash
uv run glyphmark docs build --strict     # -> build/docs, served at /docs/
uv run glyphmark docs check              # strict build in a temp dir (CI gate)
uv run glyphmark docs status             # where the sources and the build live
make docs-serve                          # mkdocs live reload on :8000 while writing
```

Two constraints worth knowing before you write: `use_directory_urls` is off so the Flask app can
serve flat `page.html` files under `/docs/`, and the theme loads no webfonts because the docs run
under a local-only CSP.

## Review

* A code owner from `.github/CODEOWNERS` must approve (GitHub suggests them).
* Channels and detection changes are reviewed for the attack/defence pairing first: finding kind,
  sanitizer stage, abuse note, false-positive thinking.
* Anything touching the frame format, JSON shapes, CLI flags, dependencies or scoring weights needs
  a governance vote — see `GOVERNANCE.md`. Label it `breaking` or `governance` early.
* Review is on the code, not the author: "this test does not fail if the check is removed" rather
  than "you forgot".

## Releases

Maintainers push a tag; CI builds sdist + wheel, generates a CycloneDX SBOM, attaches SLSA build
provenance, and opens a GitHub Release with the changelog section as notes. Version bumps go in
`pyproject.toml` (and `src/glyphmark/__init__.py`), and the changelog entry is written from the
merged PR list, not from memory.

## Getting help

Open a **Question** issue — see `SUPPORT.md` for what to expect and what kind of request is
declined. Docs gaps are bugs: if you had to ask, the page was incomplete.
