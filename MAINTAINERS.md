---
title: Maintainers
description: >-
  Maintainers of the GlyphMark project, with the CNCF/gitdm machine-readable fields.
---

# Maintainers

Formal ownership of GlyphMark: review authority, release authority, and stewardship of
[GOVERNANCE.md](GOVERNANCE.md). Names here are the people a vulnerability report, a code-of-conduct
report, or a maintainer vote goes to.

| Maintainer | GitHub | Email | Affiliation | Focus |
|---|---|---|---|---|
| dibrahim | [@dibrahim](https://github.com/dibrahim) | <daniyal.ibrahim@accenture.com> | independent | core, channels, CLI, web UI |

> **Affiliation note.** CNCF disclosure asks for the organisation that sponsors your time on the
> project. "independent" here means no employer sponsorships are on record for this project; update
> this column (and `affiliation` below) if that changes.

## Machine-readable records

Consumed by community tooling (`cncf/gitdm`, CLOMonitor):

```yaml
maintainers:
  - name: dibrahim
    github: dibrahim
    email: daniyal.ibrahim@accenture.com
    affiliation: independent
```

## Roles

* **Maintainer** — merge rights on everything, release authority, vote in governance decisions.
* **Approver** (`@glyphmark/approvers`, see `.github/CODEOWNERS`) — merge rights in a subsystem
  without a full maintainer seat.
* **Triager** — issue triage and `lgtm` suggestion rights, no merge rights.

Roles are granted and revoked as described in [GOVERNANCE.md](GOVERNANCE.md). The `@glyphmark/*`
teams referenced by `.github/CODEOWNERS` are GitHub teams in this repository; keep this file and
CODEOWNERS in sync (a test asserts every maintainer here also appears in CODEOWNERS).

## Becoming a maintainer

1. Contribute consistently for a period in which you review, not only write: fixes to the core,
   new channels with their detection + sanitizer coverage, or docs.
2. Be nominated by an existing maintainer in a pull request against this file.
3. Existing maintainers vote (lazy majority, 7-day window, no veto; see GOVERNANCE).
4. The nominee opens a PR adding their row, joins the team, and gets a 1:1 handover on releases.

Stepping down (or being removed) moves the row to [Emeritus](#emeritus); the git history stays as
the record of contribution.

## Emeritus

Emeritus maintainers are thanked, listed here, and may be re-nominated at any time. They have no
vote.

| Name | GitHub | Maintainer years |
|---|---|---|
| — | — | — |

## Contact

* Regular issues and PRs: this repository (the default and preferred channel).
* Security issues: [SECURITY.md](SECURITY.md) — GitHub private vulnerability reporting, **not** a
  public issue.
* Governance or conduct: any maintainer directly, or `MAINTAINERS.md`'s list plus the CNCF conduct
  address.
