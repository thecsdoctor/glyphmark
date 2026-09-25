# Contributing to GlyphMark

Thanks for being here. This file is the practical part: how to get a change in, what "done" means
here, and the rules that keep the two interfaces honest. Governance (votes, roles) is in
[GOVERNANCE.md](GOVERNANCE.md); conduct is in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md); security
reporting is in [SECURITY.md](SECURITY.md).

## 30-second version

```bash
git clone https://github.com/OWNER/glyphmark && cd glyphmark
uv sync --extra dev --extra docs
uv run pytest -q && uv run ruff check src tests    # the bar for every PR
uv run glyphmark verify                            # all channels round-trip
```

## Development environment

* Python **3.10+** (the project's floor; CI runs 3.10 → 3.13).
* [`uv`](https://docs.astral.sh/uv/) is the toolchain; `make bootstrap` installs everything.
* Node is only needed for the headless UI smoke test (jsdom), which is dev-only.
* VS Code / any editor: `make lint` and `make fmt` cover what extensions would otherwise do.

```bash
make help          # list every task
make test          # pytest
make lint          # ruff check
make fmt           # ruff format
make docs          # strict mkdocs build (fails on broken links)
make ui            # serve on :8123
make check         # everything CI runs, locally
```

A devcontainer is provided (`.devcontainer/devcontainer.json`) so `code --container glyphmark`
gives you a working environment without touching your machine.

## Making a change

1. **Start with an issue** unless the fix is obvious and self-contained. Anything that changes
   behaviour, a CLI flag, a JSON field, detection scoring or the frame format needs one — those are
   the public contracts.
2. **Branch** from `main`, name it after the issue (`123-detect-fillers-in-code`).
3. **Sign your commits** (DCO): `git commit -s`. CI checks that each commit in a pull request has a
   `Signed-off-by:` trailer. This is how we can accept contributions without a CLA, and it is how
   you certify you are allowed to contribute what you send.
   ```
   Signed-off-by: Your Name <you@example.com>
   ```
4. **Write the test first** when the change is behavioural. We are unusually lucky here: the
   invariant "every channel round-trips, and sanitize-then-detect comes back clean" is already
   parametrized over all channels, so a new channel is nearly free to test.
5. **Keep the two interfaces identical.** `codec`/`analysis`/`sanitize` hold logic; `cli.py` and
   `web/app.py` are adapters. If you add a feature, add the CLI flag *and* the API field *and* the
   UI control in the same PR, or say in the PR why you did not.
6. **Update the docs in the same PR** (`docs/`). The docs are checked: `make docs` builds strictly,
   and `tests/test_docs.py` fails if the pages mention a command, flag, exit code, channel number,
   sanitizer stage, detection kind or JSON field that does not exist.
7. **Open the PR.** Fill the template, link the issue, and request a review from a code owner
   (GitHub suggests them from `.github/CODEOWNERS`). CI must be green; if something fails for a
   reason unrelated to your change, say so in a comment rather than force-pushing around it.

## What "done" means

* `make check` passes (pytest, ruff, JS syntax, license headers, strict docs).
* New behaviour has a test that would fail without it — not a test that merely covers it.
* Detection + sanitizer coverage for any new channel, plus `killed_by` metadata and an abuse note in
  `docs/channels.md`. This is a review requirement, not a nice-to-have
  ([docs/ethics.md](docs/ethics.md)).
* No new runtime dependency without a governance vote in the thread (dependencies are attack surface
  and install weight; we currently ship three runtime deps on purpose).
* Errors surface with the right exit code on the CLI *and* the right HTTP status + `exit_code` in
  the API. Exit codes are documented in `docs/cli.md` and asserted in tests.

## Style

* **Python**: `ruff format` + `ruff check` (line length 100, `E,F,I,UP,B`). Type hints on public
  functions; `from __future__ import annotations`. Docstrings say *why*, the signature says *what*.
* **JavaScript**: the web UI is deliberately framework-free vanilla JS with no build step — keep it
  that way; CDN assets are cosmetic. DOM wiring uses `data-action`/`data-*` attributes and ids that
  exist in `index.html` (a test cross-checks every `$("id")` against the markup).
* **Tests**: names state the invariant (`test_wrong_key_never_returns_garbage`), not the function
  under test. Prefer one parametrized test over 13 near-copies.
* **Docs**: British-ish spelling to match the existing voice, tables for comparisons, real command
  output rather than invented output (paste it, don't imagine it).
* **License headers**: every source file carries `SPDX-License-Identifier: MIT` in a comment on the
  first line. `make lint` checks it (`tools/check_license_headers.py`).

## Adding a watermark channel (the checklist)

1. `schemes.py`: define the alphabet, radix (power of two), family (`insert`/`substitute`),
   carrier rule, `killed_by`, honest `stealth`/`survival`, `blurb`, `detection`, `notes`.
2. `sanitize.py`: ensure at least one stage removes it (or add the stage).
3. `analysis.py`: emit a finding for it, with severity, weight and the stage that removes it.
4. Tests: round-trip keyed/unkeyed, tamper → CRC failure, capacity error, sanitize→detect-clean.
5. Docs: `docs/channels.md` row + a note on misuse; `docs/defence.md` table row.
6. `glyphmark verify` and `make check`.

## Reporting problems, not just bugs

Broken docs, confusing errors, a sanitizer that mangles legitimate text, a detector that fires on a
language you read — all of those are bugs worth filing. Use the issue templates; they ask for the
code points and the version, which is usually the whole diagnosis.

## Releases

Maintainers only; see the `release.yml` workflow. Summary: version bump in `pyproject.toml` +
`__init__.py`, changelog section, tag `vX.Y.Z` → CI builds sdist/wheel, generates a CycloneDX SBOM,
attests build provenance, and publishes to PyPI with trusted publishing (no long-lived tokens).
Announce in the changelog and any channels the project uses.

## Acknowledgement

Contributions are licensed under the project's MIT licence (see [LICENSE](LICENSE) and
[NOTICE](NOTICE)). The DCO sign-off is how we track that you had the right to contribute them.
