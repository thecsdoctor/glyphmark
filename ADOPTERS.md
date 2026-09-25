# Adopters

This is the list of organisations and projects using GlyphMark in production or in an internal
security programme. CNCF maturity reviews ask for it, and it tells new users that the design has met
real text.

## Who can be listed

Anyone running GlyphMark outside a single laptop session: a detection pipeline that calls
`/api/detect` or `glyphmark detect`, a document workflow that stamps `glyphmark encode` output, a
classroom or research group that uses it as a reference implementation. Self-listing is fine — open a
pull request adding a row. No permission needed, just accuracy.

**Discretion is legitimate.** Because this is a dual-use tool, some users have good reasons not to be
named. The table has a "discreet" row format for exactly that: add yourself to the count, not the
list, and open a PR with an entry whose organisation column says `Discreet adopter`. Maintainers may
ask for private confirmation that you actually use it.

## Listed adopters

| organisation | use case | since | contact / note |
|---|---|---|---|
| *(none self-listed yet)* | | | |

## Discreet adopters

*none recorded yet*

## How to add yourself

```markdown
| Example Corp | `glyphmark detect` in the CMS intake path, `--fail-on-risk 25` as a CI gate | 2026 | @yourhandle |
| Discreet adopter | homograph screening for published documents | 2026 | details withheld |
```

## Why we ask

Adoption evidence changes design decisions: it is the reason capacity and survival numbers are
measured rather than estimated, and the reason the frame format is treated as a stability boundary.
