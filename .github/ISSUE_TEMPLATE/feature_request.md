---
name: Feature request
about: A new channel, a defence improvement, or an interface change
title: "[feat] "
labels: [enhancement]
assignees: []
---

## The problem, in your words

<!-- What were you trying to do? A use case beats a feature list: it lets us propose something better. -->

## Ideal shape

```bash
# what the CLI would look like
glyphmark ...

# what the API call would look like
curl -s localhost:8123/api/... -d '{...}'
```

<!-- The CLI and the API/UI must offer the same thing. Sketch both, or say why only one applies. -->

## Which family (if it is a new channel)

- [ ] `insert` — invisible symbols between/around characters
- [ ] `substitute` — look-alike replacement of visible characters
- [ ] neither / defence-side only

Expected properties, using the project's axes:

| axis | value | why |
|---|---|---|
| bits per carrier unit | | |
| visual stealth (1–5) | | |
| cross-platform survival (1–5) | | |
| dies to which sanitizer stage | | ← every channel needs one, see docs/ethics.md |
| detection signal | | ← and a finding kind for it |

## Abuse review

<!-- Required, even for defence features. Who can use this to harm someone, and what stops it? -->

## Alternatives considered

<!-- Existing channels/flags that nearly do this, and what goes wrong when you try them. -->

## Implementation

- [ ] I intend to open a PR for this
- [ ] I can test it against my text corpus
- [ ] This is a request only

<!-- If you plan a PR, read CONTRIBUTING.md first: the "adding a channel" checklist and the DCO
     sign-off will save you a review cycle. -->
