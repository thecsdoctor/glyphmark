# Support

GlyphMark is free software with no support contract attached. This file states what help looks like
in practice, so nobody has to guess whether asking is welcome.

## Free, community-supported

| need | where to go | realistic expectation |
|---|---|---|
| "is this a bug?" / "how do I…?" | open an issue and pick the **Question** template | a reply within a few days; answers get folded into `docs/` |
| bug with a reproducer | open an issue and pick the **Bug report** template | triaged within a week; fixes land in the next release |
| feature / new channel | open an issue and pick the **Feature request** template | honest answer about feasibility; PRs welcome, see CONTRIBUTING |
| vulnerability | [SECURITY.md](SECURITY.md) — private advisory | 5-business-day acknowledgement, 90-day disclosure ceiling |
| conduct problem | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | see that file's process |
| "why was my PR closed?" / how decisions get made | [GOVERNANCE.md](GOVERNANCE.md), then an issue | the process is written down; ask and you'll get a link to it |

The best support usually comes from a good issue report: version (`glyphmark --version`), the exact
input as code points (`glyphmark inspect --json`), what you expected, what happened.

## Self-service

* `docs/` — served at `/docs/` once built (`uv run glyphmark docs build`), covering CLI, UI, API,
  channels, defence and reference.
* `glyphmark <cmd> --help` and `docs/cli.md` are the same information; the docs are tested against
  the code so they cannot drift.
* `glyphmark schemes`, `glyphmark scheme <id>` and `glyphmark chars` answer most "what is possible"
  and "what character is that" questions without leaving the terminal.
* `glyphmark verify` tells you whether your install round-trips all channels on your Python.

## Commercial support

None is offered or endorsed by this repository. If a vendor claims to sell GlyphMark support, that
claim is not from the project; the licence grants no such right to the name
(see [TRADEMARKS.md](TRADEMARKS.md)).

## What we will not help with

Requests whose purpose is to watermark or manipulate text without the reader's knowledge, or to
evade detection in a way that harms people, are declined under
[docs/ethics.md](docs/ethics.md). Asking about the *defence* against such use is always welcome.
