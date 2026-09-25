# Governance

This document is the contract for how GlyphMark decisions get made, who can make them, and how the
project changes hands. It is deliberately small: a project this size should not need a
constitution, but it should not need to improvise either.

## Principles

1. **Everything in the open.** Decisions happen in issues and pull requests, not in private chat.
   A private channel exists only for security embargoes and conduct reports.
2. **Written evidence beats seniority.** A change to capacity math, detection scoring or the frame
   format needs a test or a measurement in the PR, not an argument.
3. **Attack and defence move together.** No channel lands without detection coverage, a sanitizer
   stage that kills it, and a paragraph on how it can be abused. That rule is in
   [docs/ethics.md](docs/ethics.md) and enforced in review.
4. **Users over features.** When a feature and a defence are in tension (a stealthier channel vs a
   detector that stays quiet on non-Latin text), the defence wins.
5. **Small, reversible steps.** Deprecations run at least one minor release and are announced in
   [CHANGELOG.md](CHANGELOG.md).

## Roles

| role | rights | how it is granted |
|---|---|---|
| Contributor | open issues and PRs | none required |
| Triager | label/close issues, request review | maintainer nomination, no objection within 7 days |
| Approver | merge within a subsystem (`CODEOWNERS`) | maintainer majority vote |
| Maintainer | merge anywhere, releases, governance vote | nomination + maintainer majority (see below) |
| Emeritus maintainer | none (advisory) | automatic on stepping down |

Rights are GitHub permissions; the list of people who hold them lives in
[MAINTAINERS.md](MAINTAINERS.md) and `.github/CODEOWNERS`.

## Decision making

**Everyday changes** (bug fixes, docs, tests, a channel's metadata): one maintainer approves and
merges after CI is green. Self-merge by the author is allowed only with another reviewer's approval.

**Contested or structural changes** — frame format, wire/JSON compatibility, detection scoring
weights, new dependencies, anything that changes what a mark survives, licensing, governance:

1. Open an issue or RFC-style PR describing the problem, the options and the risk.
2. Discuss for a **minimum of 5 working days** (72 hours for urgent regressions).
3. Vote. Maintainers vote `+1 / 0 / -1` in the thread; silence after the window counts as `0`, not
   as a veto.
4. The change passes with a **majority of active maintainers** in favour and no veto.
5. The person who shepherds the change writes the merge-up summary into the PR and the changelog.

**Veto.** A single `veto (-1)` from a maintainer blocks a change, but must be accompanied by a
reason and a technical alternative or a follow-up issue. Vetoes are recorded in the thread and may
not be used for style preferences.

**Deadlock.** If a vote is tied or a veto is disputed, the maintainers pick one of: a time-boxed
spike to gather data, a reversible feature flag, or a 14-day extended discussion followed by a
simple-majority revote. No decision defaults to "the incumbent behaviour stays".

**Escalation.** If the project joins the CNCF, project decisions stay with the maintainers; the
CNCF Technical Oversight Committee is the escalation path for governance disputes and for
graduation/incubation review. Conflicts of interest are disclosed in the thread, and a maintainer
with a commercial interest in an outcome is expected to say so and may still vote.

## Subsystems and ownership

| area | owner (GitHub team) | notes |
|---|---|---|
| core (`frames`, `codec`, `bitstreams`, `schemes`) | `@glyphmark/core` | frame/compat changes need a vote |
| defence (`analysis`, `sanitize`) | `@glyphmark/defence` | scoring weights need a vote |
| interfaces (`cli`, `web`) | `@glyphmark/interfaces` | API shape is public contract |
| docs, governance, CI | `@glyphmark/maintainers` | anyone with a CLA/DCO sign-off may propose |

Ownership is recorded mechanically in `.github/CODEOWNERS`.

## Maintainership changes

* **Adding:** nomination PR to `MAINTAINERS.md`, then a 7-day maintainer vote; see MAINTAINERS.
* **Stepping down:** a PR moving the row to Emeritus. Maintainers are asked to hand over any
  in-flight release before the merge.
* **Inactivity:** 6 months with no reviews, commits or votes → another maintainer opens an issue,
  offers the option of Emeritus, and only then removes permissions. Never silent.
* **Removal for cause:** conduct or security violations follow
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) / [SECURITY.md](SECURITY.md); a maintainer majority may
  suspend permissions immediately and confirm retroactively in the public log.
* **Bus factor:** at least two maintainers must be able to cut a release. Below that, recruiting is
  the project's top priority over features.

## Relationship to a foundation

GlyphMark is currently an independent open-source project. If it applies to CNCF:

* this file, `CODE_OF_CONDUCT.md` (CNCF CoC), `MAINTAINERS.md`, `SECURITY.md` and
  `ADOPTERS.md` are the artefacts the application review looks at, together with the
  [OpenSSF Scorecard](https://securityscorecards.dev/) results published by CI;
* the project would adopt the CNCF trademark policy (already mirrored in `TRADEMARKS.md`), the CNCF
  code of conduct (already adopted), and the CNCF copyright notice on new files;
* licensing: the project is MIT. MIT is on the CNCF-approved licence list; if the landscape norm of
  Apache-2.0 is required at intake, the change is a governance vote plus per-file notice updates.

## Changing this document

Edits to governance, code of conduct, licence or trademark policy need a formal vote (step 3 above
with no 72-hour shortcut) and must be summarised in [CHANGELOG.md](CHANGELOG.md) under
`Governance`.

## Public log

Record here only decisions that change the contract: governance edits, new/retired maintainers,
process changes, and any security-incident post-mortem link.

| date | decision | thread |
|---|---|---|
| 2026-09-25 | governance, code of conduct (CNCF CoC), security policy and maintainer list adopted | initial |
