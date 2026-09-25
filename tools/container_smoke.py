#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""End-to-end probe of a running GlyphMark server, through HTTP only.

Why a separate script from `tools/ui_smoke.mjs` (which needs node + jsdom): this one is stdlib
only, so it can run *inside* the shipped image, in CI after the image is built, and in
`docker compose run --rm smoke` without installing anything. It answers one question: does the
thing we are about to publish actually work end to end?

    python tools/container_smoke.py --base http://127.0.0.1:8123
    GM_BASE=http://host:port python tools/container_smoke.py --skip-docs

Exit codes: 0 all checks passed · 1 a check failed · 2 the server could not be reached.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

PASSED = 0
FAILED: list[str] = []

COVER = (
    "GlyphMark carries attribution inside ordinary text: the same engine answers the command "
    "line and the HTTP API, and every mark it writes can be found and stripped again."
)


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if ok:
        PASSED += 1
        print(f"PASS  {label}")
    else:
        FAILED.append(label)
        print(f"FAIL  {label}{'  ' + detail if detail else ''}")


class Api:
    def __init__(self, base: str, timeout: float) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: dict | None = None, raw: bool = False):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"content-type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read()
                return resp.status, (payload if raw else json.loads(payload)), dict(resp.headers)
        except urllib.error.HTTPError as exc:  # 4xx/5xx carry the JSON error shape
            payload = exc.read()
            try:
                return exc.code, (payload if raw else json.loads(payload)), dict(exc.headers)
            except json.JSONDecodeError:
                return exc.code, payload, dict(exc.headers)

    def get(self, path: str, raw: bool = False):
        return self.request("GET", path, None, raw)

    def post(self, path: str, body: dict, raw: bool = False):
        return self.request("POST", path, body, raw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=os.environ.get("GM_BASE", "http://127.0.0.1:8123"))
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument(
        "--skip-docs",
        action="store_true",
        help="don't require the documentation site (a source checkout without a docs build)",
    )
    args = ap.parse_args()

    api = Api(args.base, args.timeout)

    # ------------------------------------------------------------------ liveness + headers
    try:
        status, health, headers = api.get("/healthz")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        print(f"cannot reach {args.base}/healthz: {exc}", file=sys.stderr)
        return 2

    check("GET /healthz answers 200", status == 200, str(status))
    check(
        "healthz reports ok with a version",
        health.get("status") == "ok" and bool(health.get("version")),
    )
    schemes = int(health.get("schemes", 0))
    check("healthz counts the channel registry", schemes >= 10, f"schemes={schemes}")

    check(
        "X-Content-Type-Options: nosniff",
        headers.get("X-Content-Type-Options") == "nosniff",
        str(headers.get("X-Content-Type-Options")),
    )
    check("X-Frame-Options: DENY", headers.get("X-Frame-Options") == "DENY")
    check(
        "Permissions-Policy denies devices",
        "camera=()" in (headers.get("Permissions-Policy") or ""),
    )
    csp = headers.get("Content-Security-Policy", "")
    check("CSP pins default-src to this origin", "default-src 'self'" in csp)
    check("CSP forbids framing", "frame-ancestors 'none'" in csp)

    # --------------------------------------------------------------------- reference data
    status, meta, _ = api.get("/api/meta")
    ids = {s["id"] for s in meta.get("schemes", [])}
    check(
        "GET /api/meta lists every channel",
        status == 200 and len(ids) == schemes,
        f"{len(ids)} vs {schemes}",
    )
    check("registry contains both families", {"zw-octal", "homoglyph"} <= ids, str(sorted(ids)[:4]))
    check("sanitize stages are advertised", len(meta.get("sanitize_stages", [])) >= 14)
    check(
        "default pipeline strips zero-widths",
        "strip_zero_width" in meta.get("default_pipeline", []),
    )
    check(
        "placements are advertised",
        "spread" in meta.get("placements", []),
        str(meta.get("placements")),
    )

    # ----------------------------------------------------------------------- write / read
    status, enc, _ = api.post(
        "/api/encode", {"cover": COVER, "payload": "session=4F2A", "scheme": "zw-octal"}
    )
    check("POST /api/encode succeeds", status == 200, str(status))
    marked = enc.get("text", "")
    check("the mark is invisible but present", marked and marked != COVER)
    check("encode self-verifies", enc.get("verified") is True)
    check("encode reports utilisation", isinstance(enc.get("utilization"), float))

    status, dec, _ = api.post("/api/decode", {"text": marked})
    check(
        "auto-detect extract returns the payload",
        dec.get("payload_text") == "session=4F2A",
        str(dec.get("payload_text")),
    )
    check(
        "auto-detect names the right channel",
        dec.get("scheme") == "zw-octal",
        str(dec.get("scheme")),
    )

    # keyed: right key reads, wrong key fails loudly (never plausible garbage)
    _, keyed_enc, _ = api.post(
        "/api/encode",
        {"cover": COVER, "payload": "session=4F2A", "scheme": "zw-octal", "key": "right-key"},
    )
    check("keyed encode marks itself as keyed", keyed_enc.get("keyed") is True)
    _, keyed_dec, _ = api.post("/api/decode", {"text": keyed_enc["text"], "key": "right-key"})
    check("keyed extract with the right key", keyed_dec.get("payload_text") == "session=4F2A")
    status, wrong, _ = api.post("/api/decode", {"text": keyed_enc["text"], "key": "wrong-key"})
    check(
        "wrong key -> integrity error (exit 4), not garbage",
        status >= 400 and wrong.get("exit_code") == 4,
        f"{status} {wrong}",
    )

    # -------------------------------------------------------------------- detect / sanitize
    status, report, _ = api.post("/api/detect", {"text": marked})
    check(
        "POST /api/detect scores the marked text",
        status == 200 and report.get("suspect_total", 0) > 0,
    )
    kinds = {f["kind"] for f in report.get("findings", [])}
    check("detection names the zero-width channel", "zero_width" in kinds, str(sorted(kinds)))
    check("the frame signature is recovered", len(report.get("frame_signatures", [])) >= 1)

    status, clean, _ = api.post("/api/sanitize", {"text": marked})
    check("sanitize changes the text", status == 200 and clean.get("identical") is False)
    check("sanitize accounts for what it removed", clean.get("removed_total", 0) > 0)
    _, after, _ = api.post("/api/detect", {"text": clean["text"]})
    check(
        "the sanitized text scans clean",
        after.get("suspect_total") == 0,
        str(after.get("suspect_total")),
    )

    # ------------------------------------------------------------------- failure semantics
    status, err, _ = api.post(
        "/api/encode", {"cover": "too short", "payload": "x" * 200, "scheme": "homoglyph"}
    )
    check(
        "substitute channel without room -> exit 5",
        status >= 400 and err.get("exit_code") == 5,
        str(err),
    )
    status, err, _ = api.post("/api/decode", {"text": "nothing was ever embedded here"})
    check("text with no mark -> exit 3", status >= 400 and err.get("exit_code") == 3, str(err))
    status, _, _ = api.post("/api/detect", {"text": "x" * 500})
    check("normal-size detect still works", status == 200)
    status, _, _ = api.request("POST", "/api/detect", {"text": "A" * 5_000_000})
    check("request body over the cap -> 413", status == 413, str(status))
    status, body, _ = api.post("/api/nope", {})
    check("unknown endpoint -> 404 JSON", status == 404 and "error" in body, str(status))

    status, verify, _ = api.post("/api/verify", {})
    check(
        "every channel round-trips on this host",
        status == 200
        and verify.get("passed") == verify.get("total", len(verify.get("results", []))),
        f"{verify.get('passed')}/{verify.get('total')}",
    )

    # ------------------------------------------------------------------------- lab + docs
    status, page, headers = api.get("/", raw=True)
    text = page.decode("utf-8", "replace")
    check("the lab UI is served", status == 200 and "GlyphMark" in text)
    check("the lab links to the docs", "/docs/" in text)
    check(
        "the lab CSP allows the cosmetic CDN only",
        "https://cdn.jsdelivr.net" in headers.get("Content-Security-Policy", ""),
    )

    if args.skip_docs:
        print("SKIP  documentation checks (--skip-docs)")
    else:
        check("healthz advertises built docs", health.get("docs") is True, str(health.get("docs")))
        status, page, headers = api.get("/docs/", raw=True)
        text = page.decode("utf-8", "replace")
        check("GET /docs/ serves the site", status == 200 and "GlyphMark" in text, str(status))
        check(
            "docs pages are flat files (use_directory_urls off)",
            api.get("/docs/cli.html", raw=True)[0] == 200,
        )
        check("docs search index exists", api.get("/docs/search/search_index.json")[0] == 200)
        docs_csp = headers.get("Content-Security-Policy", "")
        check(
            "docs CSP stays same-origin for scripts",
            "cdn.jsdelivr.net" not in docs_csp and "connect-src 'self'" in docs_csp,
        )
        status, _, _ = api.get("/docs/%2e%2e/pyproject.toml")
        check("path traversal out of the docs build is refused", status in (400, 404), str(status))

    print()
    if FAILED:
        print(f"{len(FAILED)} of {len(FAILED) + PASSED} checks FAILED:")
        for label in FAILED:
            print(f"  - {label}")
        return 1
    print(f"all {PASSED} container checks passed against {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
