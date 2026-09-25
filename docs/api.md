# HTTP API

`uv run glyphmark serve --host 127.0.0.1 --port 8123`

Every endpoint is a thin wrapper around the same functions the CLI calls, so the UI, the JSON API and
the shell cannot drift apart. Bodies are JSON (`Content-Type: application/json`), requests are capped
at **4 MB** / 400 000 characters per text field, and responses are plain JSON (no auth, no cookies —
this is a single-user local tool).

| method | path | mirrors |
|---|---|---|
| `GET` | `/` | the web UI (one page) |
| `GET` | `/docs/` | this site, served from the `glyphmark docs build` output |
| `GET` | `/healthz` | liveness, version, channel count |
| `GET` | `/api/meta` | `glyphmark schemes` + `chars` + `sanitize --list-stages` |
| `POST` | `/api/encode` | `glyphmark encode` |
| `POST` | `/api/decode` | `glyphmark decode` |
| `POST` | `/api/detect` | `glyphmark detect` |
| `POST` | `/api/sanitize` | `glyphmark sanitize` |
| `POST` | `/api/inspect` | `glyphmark inspect` |
| `POST` | `/api/verify` | `glyphmark verify` |

## Errors carry the CLI exit code

```http
HTTP/1.1 422 UNPROCESSABLE ENTITY
Content-Type: application/json

{"error": "'vs-bytes' needs 136 carrier units but this cover text offers 12", "exit_code": 5, "type": "CapacityError"}
```

| `exit_code` | HTTP | meaning |
|---|---|---|
| 1 | 400 | generic error: missing/blank field, non-JSON body, unknown channel or stage |
| 3 | 422 | no payload found |
| 4 | 422 | corrupt frame or wrong key |
| 5 | 422 | carrier too small |
| 6 | — | (CLI only: `--fail-on-risk`; compare `risk_score` yourself over HTTP) |
| — | 413 | request body over 4 MB |
| — | 404 | unknown `/api/*` path (`{"error":"no such endpoint"}`) |

So a client can branch on the same numbers a shell script sees:

```python
r = requests.post(f"{BASE}/api/decode", json={"text": marked})
if r.status_code == 422 and r.json()["exit_code"] == 4:
    print("frame present, wrong key")
```

## `GET /api/meta`

One call gives the UI everything it needs to render:

| key | contents |
|---|---|
| `version` | package version |
| `schemes` | all 13 channels, each with `characters` (alphabet, codepoint, category, UTF-8, render, `base` for substitution twins), capacity, stealth, survival, `killed_by`, notes |
| `sanitize_stages` | 16 stages: `id`, `label`, `description`, `default`, `kills` |
| `default_pipeline` | ordered default stage ids |
| `placements` | `spread`, `interleave`, `suffix`, `prefix` |
| `characters` | the union reference table of every code point used by any channel |
| `samples` | `cover`, `payload`, `payload_json` — the same samples the CLI uses |
| `exit_codes` | the table above, as data |
| `docs` | whether `/docs/` has been built, plus its path |

## `POST /api/encode`

```json
{ "cover": "Plain carrier text for a watermark.",
  "payload": "id=42",
  "scheme": "tags",
  "key": "optional-secret",
  "placement": "spread" }
```

`cover` may also be sent as `text`; `payload` is required and UTF-8 encoded. Response:

```json
{ "scheme": "tags", "placement": "spread", "keyed": true, "verified": true,
  "text": "…watermarked text…", "payload_len": 5, "units_used": 7, "bits_used": 42,
  "carrier_units": 29, "capacity_bytes": 18, "cover_len": 30, "utilization": 0.24 }
```

## `POST /api/decode`

```json
{ "text": "…", "scheme": "auto", "key": "optional-secret" }
```

`scheme` accepts `auto` (sweep every channel, default) or a channel id. Response:

```json
{ "scheme": "tags", "keyed": true, "payload_text": "id=42", "payload_base64": "aWQ9NDI=",
  "payload_hex": "69643d3432", "payload_len": 5, "units_used": 7, "bits_read": 136,
  "carrier_units": 29, "attempts": [] }
```

On failure you get the error shape instead — and for `auto`, `attempts` (in the 422 body when the
core provides it) lists each channel and why it failed.

## `POST /api/detect`

```json
{ "text": "…", "try_frames": true }
```

Returns `risk_score`, `verdict`, `codepoints`, `suspect_total`, `findings[]`, `frame_signatures[]`,
`tag_block_mirror`, `nfkc_equal`, `recommendation` — see
[Detection & sanitization](defence.md#scanning) for what each means.

## `POST /api/sanitize`

```json
{ "text": "…", "stages": ["strip_tags", "nfkc"] }
```

Omit `stages` for the default pipeline; pass `[]` to check the text unchanged. Response:

```json
{ "text": "…clean…", "identical": false, "removed_total": 142,
  "codepoints_before": 473, "codepoints_after": 331, "channels_targeted": ["tags"],
  "stages": [{ "id": "strip_tags", "label": "Remove Plane-14 tags",
               "removed": 142, "before_len": 473, "after_len": 331 }] }
```

## `POST /api/inspect`

```json
{ "text": "…", "only_suspect": false, "limit": 4000 }
```

Returns `codepoints`, `utf8_bytes`, `utf16_units`, `suspect_count`, `visible_guess`, `truncated` and
`rows[]` (`index`, `codepoint`, `decimal`, `char`, `display`, `category`, `script`, `name`, `utf8`,
`flags[]`, `suspect`).

## `POST /api/verify`

```json
{ "schemes": ["tags", "homoglyph"], "key": "optional-secret" }
```

Omit `schemes` to test all 13. Returns `results[]` (`scheme`, `ok`, `bits_used`, `carrier_units`,
`capacity_bytes`, `cover_len`, `error`), plus `passed` and `total`.

## Headers

Every response sets `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` and a CSP that
allows scripts from this origin plus `cdn.jsdelivr.net` (Tailwind/Alpine are cosmetic only),
`fonts.googleapis.com`/`fonts.gstatic.com` for the UI fonts, and `connect-src 'self'` — the page can
only talk to its own API. `/docs/` widens `script-src` with `'unsafe-inline'` because the MkDocs
Material runtime injects a small bootstrap script; it stays same-origin for everything else.

## Turning the API into a service

The dev server is fine for a lab. Anything else should run it behind a real server and, if it leaves
localhost, behind authentication:

```bash
uv sync --with gunicorn
uv run gunicorn -w 4 -b 127.0.0.1:8000 'glyphmark.web:create_app()'
```

Notes:

* no rate limiting, no CSRF (there are no cookies), no multi-tenancy;
* `key` values are secrets — send them over TLS only, and never log request bodies;
* `/api/encode` will happily forge attribution onto someone else's text: treat the whole API as
  privileged.

## Parity with the CLI

| CLI | API |
|---|---|
| `--cover-file`, `--cover` | `cover` (or `text`) |
| `--payload-file`, `--payload` | `payload` |
| `-s/--scheme`, `-k/--key`, `-p/--placement` | `scheme`, `key`, `placement` |
| `-e/--emit escapes` | read `text` and escape it yourself (`json.dumps` does it) |
| `--stage` (repeatable) | `stages: []` |
| `--only-suspect` | `only_suspect` |
| `--fail-on-risk N` | compare `risk_score` in the response |
| exit codes | `exit_code` in the body, mirrored by HTTP status |

`tests/test_web.py` asserts the API returns exactly what `codec`/`analysis`/`sanitize` return, and
`tests/test_cli.py` asserts the same for the shell — the equivalence is a tested property, not a
claim.
