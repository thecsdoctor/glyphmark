"""The HTTP API must expose exactly what the CLI exposes (same core, same codes)."""

from __future__ import annotations

import pathlib
import re

import pytest

from glyphmark.codec import encode, sample_carrier
from glyphmark.schemes import get_scheme, scheme_ids
from glyphmark.web import create_app

PAYLOAD = '{"provenance":"glyphmark","id":42}'


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def marked(scheme_id: str = "vs-bytes") -> str:
    scheme = get_scheme(scheme_id)
    cover = sample_carrier(scheme, len(PAYLOAD))
    return encode(cover, PAYLOAD.encode(), scheme_id).text


def test_index_and_health(client) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert b"GlyphMark" in page.data and b"/static/app.js" in page.data
    assert b'x-data="themeState()"' in page.data
    assert b'data-tab="detect"' in page.data and b'id="panel-reference"' in page.data
    assert b"cdn.jsdelivr.net" in page.data          # CDN layer is present
    assert b"alpinejs" in page.data and b"tailwindcss" in page.data
    assert client.get("/healthz").get_json()["status"] == "ok"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_meta_exposes_schemes_stages_and_samples(client) -> None:
    meta = client.get("/api/meta").get_json()
    assert [s["id"] for s in meta["schemes"]] == scheme_ids()
    assert meta["schemes"][0]["characters"]
    assert {s["id"] for s in meta["sanitize_stages"]} >= {"nfkc", "strip_tags"}
    assert meta["samples"]["cover"]
    assert meta["exit_codes"]["5"] == "carrier too small"
    assert meta["default_pipeline"] and meta["placements"]


def test_encode_decode_matches_the_core(client) -> None:
    cover = sample_carrier(get_scheme("tags"), len(PAYLOAD))
    resp = client.post("/api/encode", json={
        "cover": cover, "payload": PAYLOAD, "scheme": "tags", "placement": "spread"})
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["verified"] is True
    assert body["text"] == encode(cover, PAYLOAD.encode(), "tags").text   # CLI parity
    decoded = client.post("/api/decode", json={"text": body["text"]}).get_json()
    assert decoded["payload_text"] == PAYLOAD
    assert decoded["scheme"] == "tags" and decoded["payload_base64"]


def test_keyed_roundtrip_over_http(client) -> None:
    cover = sample_carrier(get_scheme("omni16"), len(PAYLOAD))
    enc = client.post("/api/encode", json={"cover": cover, "payload": PAYLOAD,
                                          "scheme": "omni16", "key": "s3cret"}).get_json()
    assert client.post("/api/decode", json={"text": enc["text"]}).status_code == 422
    back = client.post("/api/decode", json={"text": enc["text"], "key": "s3cret"})
    assert back.get_json()["payload_text"] == PAYLOAD


def test_detect_endpoint(client) -> None:
    report = client.post("/api/detect", json={"text": marked("tags")}).get_json()
    assert report["verdict"] == "watermark-confirmed"
    assert report["frame_signatures"]
    clean = client.post("/api/detect", json={"text": "plain text", "try_frames": False})
    assert clean.get_json()["verdict"] == "clean"


def test_sanitize_endpoint_and_stage_selection(client) -> None:
    result = client.post("/api/sanitize", json={"text": marked("zw-octal")}).get_json()
    assert result["removed_total"] > 0 and not result["identical"]
    narrow = client.post("/api/sanitize", json={"text": "a\u200bb",
                                                "stages": ["strip_zero_width"]}).get_json()
    assert [s["id"] for s in narrow["stages"]] == ["strip_zero_width"]
    assert narrow["text"] == "ab"


def test_inspect_endpoint(client) -> None:
    info = client.post("/api/inspect", json={"text": "a\u200bb"}).get_json()
    assert info["codepoints"] == 3 and info["suspect_count"] == 1
    assert info["rows"][1]["codepoint"] == "U+200B"


def test_verify_endpoint(client) -> None:
    report = client.post("/api/verify", json={}).get_json()
    assert report["total"] == len(scheme_ids())
    assert report["passed"] == report["total"]
    subset = client.post("/api/verify", json={"schemes": ["punct"], "key": "k"}).get_json()
    assert subset["results"][0]["ok"] is True


def test_error_mapping_carries_cli_exit_codes(client) -> None:
    too_big = client.post("/api/encode", json={"cover": "tiny", "payload": "x" * 4000,
                                              "scheme": "homoglyph"})
    assert too_big.status_code == 422
    assert too_big.get_json()["exit_code"] == 5

    nothing = client.post("/api/decode", json={"text": "nothing here at all"})
    assert nothing.status_code == 422 and nothing.get_json()["exit_code"] == 3

    bad_scheme = client.post("/api/encode", json={"cover": "x", "payload": "y",
                                                 "scheme": "not-a-scheme"})
    assert bad_scheme.status_code == 400

    missing = client.post("/api/encode", json={"cover": "x"})
    assert missing.status_code == 400 and "payload" in missing.get_json()["error"]

    assert client.post("/api/sanitize", json={"text": "x", "stages": "nfkc"}).status_code == 400
    assert client.post("/api/decode", json={}).status_code == 400
    assert client.get("/api/nope").status_code == 404


def test_security_headers(client) -> None:
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in resp.headers["Content-Security-Policy"]


def test_oversized_body_is_rejected(client) -> None:
    huge = "word " * 200_000
    info = client.post("/api/inspect", json={"text": huge, "limit": 50}).get_json()
    assert info["truncated"] is True and len(info["rows"]) == 50
    assert client.post("/api/detect", json={"text": huge[:1000]}).status_code == 200
    assert client.post("/api/detect", json={"text": huge * 13}).status_code == 413


# --------------------------------------------------------------- UI contract
# The page and app.js are written by hand, so the wiring between them is asserted
# here: every id the script looks up must exist in the markup, and the response
# field names the script reads must match what the endpoints actually emit.

def _asset(name: str) -> str:
    path = pathlib.Path(__file__).resolve().parent.parent / "src" / "glyphmark" / "web" / name
    return path.read_text(encoding="utf-8")


def test_every_id_the_script_touches_exists_in_the_markup(client) -> None:
    html = client.get("/").data.decode()
    js = _asset("static/app.js")
    referenced = set(re.findall(r'\$\("([A-Za-z0-9_]+)"\)', js))
    assert len(referenced) > 20                       # the query is really finding ids
    missing = {i for i in referenced if f'id="{i}"' not in html}
    assert not missing, f"app.js looks up ids that the template does not define: {sorted(missing)}"


def test_script_reads_only_fields_the_api_emits(client) -> None:
    js = _asset("static/app.js")
    for stale in ("cover_text", "risk_level", "text_without_payload", "visible_text",
                  "state.meta.stages.", "sanitized_text", "x.cp"):
        assert stale not in js, f"app.js still uses the removed field {stale!r}"
    meta = client.get("/api/meta").get_json()
    for key in ("sanitize_stages", "exit_codes", "samples", "placements", "schemes", "characters"):
        assert key in js and key in meta
    assert "payload_text" in js and "removed_total" in js and "frame_signatures" in js


def test_markup_carries_the_accessibility_scaffolding(client) -> None:
    html = client.get("/").data.decode()
    assert html.index('<a class="skip"') < html.index("<header")
    assert html.count('role="tab"') >= 6 and html.count('role="tabpanel"') >= 6
    assert 'role="dialog"' in html and 'aria-modal="true"' in html
    assert 'aria-live="polite"' in html
    assert 'id="ribbon"' in html and 'aria-label="Workbench pipeline"' in html
    for field in ("cover", "payload", "decText", "detText", "sanText", "inspText"):
        assert f'<label for="{field}"' in html or f'<label for="{field}">' in html, field


def test_cdn_is_presentation_only(client) -> None:
    """CDN assets must stay cosmetic: logic lives in the locally served app.js."""
    html = client.get("/").data.decode()
    scripts = re.findall(r'<script[^>]*src="([^"]+)"', html)
    assert any(s.startswith("https://cdn.jsdelivr.net") for s in scripts)
    assert any("/static/app.js" in s for s in scripts)
    assert all(s.startswith("https://") or "/static/" in s for s in scripts)
    css = _asset("static/styles.css")
    assert "@import" not in css and "http://" not in css.replace("http://www.w3.org", "")
