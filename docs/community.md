# Community & governance

GlyphMark is a small project with a written governance model, because a tool that can be used for
attribution *and* for deception needs explicit answers to "who decides" and "what happens when we
disagree". This page is the summary; the authoritative texts are `GOVERNANCE.md`,
`MAINTAINERS.md`, `CODE_OF_CONDUCT.md` and `SUPPORT.md` at the repository root.

## How decisions are made

| kind of change | process |
|---|---|
| bug fix, docs, test, channel metadata | one maintainer approves and merges once CI is green |
| frame format, CLI flags, JSON fields, detection weights, new dependency, licence or governance | open issue/RFC → 5 working days of discussion → maintainer majority vote, no veto exercised without a stated alternative |
| security fix | private until the release; see `SECURITY.md` |

Everyday engineering is deliberately boring: prove it with a test, get a review from a code owner,
merge. The vote threshold exists for the handful of decisions that are expensive to undo — the frame
format in particular, because marks already in the wild cannot be rewritten.

Two rules shape more reviews than any other:

* **attack and defence move together** — no channel lands without a detection finding, a sanitizer
  stage that kills it, and a note on misuse ([Responsible use](ethics.md));
* **the two interfaces stay identical** — the CLI and the web UI/JSON API expose the same
  functionality, and the tests fail if they drift.

## Who does what

| role | can | how |
|---|---|---|
| Contributor | open issues and PRs | nothing |
| Triager | label and close issues, request review | maintainer nomination, no objection in 7 days |
| Approver | merge in one subsystem (`CODEOWNERS`) | maintainer majority |
| Maintainer | merge anywhere, cut releases, vote | nomination PR + majority, 7-day window |
| Emeritus | advise, no vote | automatic on stepping down |

Current maintainers are listed in `MAINTAINERS.md`. Subsystem ownership is machine-readable in
`.github/CODEOWNERS`: `core` (frame, codec, bitstreams, schemes), `defence` (analysis, sanitize),
`interfaces` (cli, web), plus the docs/governance/CI set owned by all maintainers.

## Where things happen

| purpose | place |
|---|---|
| bugs, questions, feature discussion | GitHub issues (templates ask for the code points and the version — that is usually the whole diagnosis) |
| code review | pull requests, with a code owner's approval required |
| releases and notes | GitHub Releases + `CHANGELOG.md` |
| direction | `ROADMAP.md`, argued in issues |
| security | private advisory thread, then a public advisory |
| conduct | `CODE_OF_CONDUCT.md` (CNCF Code of Conduct), reports to maintainers or the CNCF conduct address |

There is no private list, no Slack, no Discord. Anything that would be decided there is decided in
an issue instead — a project this size cannot keep a searchable history and a chat log, so it keeps
the searchable one.

## Getting involved

Order of usefulness, from lowest effort to highest:

1. **File a good issue.** A detection that fires on text you actually read, a sanitizer that mangles
   something legitimate, a confusing error message. These change the tool more than most feature
   requests.
2. **Send a failing test.** A pull request that adds a test reproducing your bug and opens the issue
   in its description is the fastest possible contribution.
3. **Docs.** Every page is generated-adjacent to the code and drift-checked; a docs gap is a bug and
   docs patches are merged fastest.
4. **A channel**, with its detection and sanitization coverage — see
   [Contributing](contributing.md) for the checklist.
5. **Review.** Reviewing other people's pull requests is how maintainers are chosen; writing code is
   not.

New contributor work is labelled `good first issue`; `help wanted` means no maintainer is on it.
Asking in a **Question** issue before starting is free and often saves a rejected pull request.

## Recognition and rights

Contributions are licensed under the project's MIT licence, with a `Signed-off-by` trailer on each
commit as the record that you were allowed to contribute it (DCO, no CLA). Authorship stays in the
git history, and the changelog names contributors for anything user-visible.

The name GlyphMark and its logo are covered by `TRADEMARKS.md`: say "works with GlyphMark", do not
name your product that.

## Road to something bigger

If the project is proposed to a foundation, the review looks at exactly the artefacts this repository
keeps current: governance, code of conduct, maintainer list with affiliations, security policy and
disclosure history, adopters, a public roadmap, licence headers on source, and published Scorecard
results. The gaps are tracked in `ROADMAP.md` — chiefly a second active maintainer and adopters
self-listing themselves.

Related: [Contributing](contributing.md) · [Security model](security.md) · [Responsible use](ethics.md)
