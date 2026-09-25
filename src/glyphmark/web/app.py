"""Flask routes. Every endpoint is a thin wrapper over the exact same core the
CLI calls, so the two interfaces can never diverge.

    GET  /                     single page UI
    GET  /healthz              liveness + version
    GET  /api/meta             schemes, sanitizer stages, placements, samples
    POST /api/encode           embed a payload
    POST /api/decode           recover a payload (auto channel sweep)
    POST /api/detect           covert-channel analysis
    POST /api/sanitize         strip code points
    POST /api/inspect          code point table
    POST /api/verify           encode+extract self test
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from .. import __version__
from ..analysis import detect, inspect_text
from ..codec import (
    PLACEMENTS,
    CapacityError,
    GlyphMarkError,
    NoPayloadError,
    decode,
    encode,
    roundtrip_ok,
)
from ..frames import FrameError
from ..sanitize import DEFAULT_PIPELINE, sanitize, stage_docs
from ..schemes import SCHEMES, all_reference_rows, scheme_ids

SAMPLE_COVER = (
    "GlyphMark ships a bidirectional toolkit: the same engine answers to a "
    "non-interactive CLI and to an HTTP API. Provenance marks, session tags and "
    "attribution ids can ride inside plain text without touching what a reader "
    "sees - and every one of those marks can be found and stripped."
)
SAMPLE_PAYLOAD = {"provenance": "glyphmark-demo", "model": "local-llm", "session": "4F2A-91C7"}

MAX_CHARS = 400_000


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: int = 1) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def _body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("expected a JSON object body")
    return data


def _text_field(data: dict, *names: str, required: bool = True) -> str:
    for name in names:
        value = data.get(name)
        if isinstance(value, str) and value:
            return value[:MAX_CHARS]
    if required:
        raise ApiError(f"missing required field: {names[0]}")
    return ""


def _str_field(data: dict, name: str, default: str = "") -> str:
    value = data.get(name, default)
    return value if isinstance(value, str) else default


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
            "https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'none'; form-action 'none'",
        )
        return resp

    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return jsonify({"error": str(exc), "type": type(exc.__cause__ or exc).__name__,
                        "exit_code": exc.code}), exc.status

    @app.errorhandler(404)
    def _not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "no such endpoint"}), 404
        return render_template("index.html"), 404

    @app.errorhandler(413)
    def _too_big(_e):
        return jsonify({"error": "request body too large (4 MB cap)"}), 413

    def _core_errors(func):
        """Map core exceptions onto HTTP status + CLI exit codes."""
        try:
            return func()
        except CapacityError as exc:
            raise ApiError(str(exc), 422, exc.exit_code) from exc
        except NoPayloadError as exc:
            raise ApiError(str(exc), 422, exc.exit_code) from exc
        except FrameError as exc:
            raise ApiError(str(exc), 422, exc.exit_code) from exc
        except GlyphMarkError as exc:
            raise ApiError(str(exc), 400, exc.exit_code) from exc
        except (KeyError, ValueError) as exc:
            raise ApiError(str(exc), 400) from exc

    # ---------------------------------------------------------------- pages #
    @app.get("/")
    def index():
        return render_template("index.html", version=__version__)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "version": __version__, "schemes": len(SCHEMES)})

    # ------------------------------------------------------------------ api #
    @app.get("/api/meta")
    def api_meta():
        return jsonify({
            "version": __version__,
            "schemes": [s.to_dict() for s in SCHEMES],
            "sanitize_stages": stage_docs(),
            "default_pipeline": DEFAULT_PIPELINE,
            "placements": list(PLACEMENTS),
            "characters": all_reference_rows(),
            "samples": {
                "cover": SAMPLE_COVER,
                "payload": SAMPLE_PAYLOAD["provenance"],
                "payload_json": SAMPLE_PAYLOAD,
            },
            "exit_codes": {
                "0": "ok", "1": "error", "3": "no payload found",
                "4": "corrupt frame or wrong key", "5": "carrier too small",
                "6": "detection threshold reached",
            },
        })

    @app.post("/api/encode")
    def api_encode():
        data = _body()

        def work():
            cover = _text_field(data, "cover", "text")
            payload = _str_field(data, "payload", "")
            if not payload:
                raise ApiError("payload is required")
            result = encode(
                cover,
                payload.encode("utf-8"),
                _str_field(data, "scheme", "zw-octal"),
                key=_str_field(data, "key") or None,
                placement=_str_field(data, "placement", "spread"),
            )
            return jsonify(result.to_dict())

        return _core_errors(work)

    @app.post("/api/decode")
    def api_decode():
        data = _body()

        def work():
            text = _text_field(data, "text", "watermarked")
            result = decode(text, key=_str_field(data, "key") or None,
                            scheme_id=_str_field(data, "scheme", "auto"))
            return jsonify(result.to_dict())

        return _core_errors(work)

    @app.post("/api/detect")
    def api_detect():
        data = _body()

        def work():
            text = _text_field(data, "text")
            report = detect(text, try_frames=bool(data.get("try_frames", True)))
            return jsonify(report)

        return _core_errors(work)

    @app.post("/api/sanitize")
    def api_sanitize():
        data = _body()
        stages = data.get("stages")
        if stages is not None and not isinstance(stages, list):
            raise ApiError("'stages' must be a list of stage ids")

        def work():
            text = _text_field(data, "text")
            return jsonify(sanitize(text, stages))

        return _core_errors(work)

    @app.post("/api/inspect")
    def api_inspect():
        data = _body()

        def work():
            text = _text_field(data, "text")
            return jsonify(inspect_text(text, limit=int(data.get("limit", 4000))))

        return _core_errors(work)

    @app.post("/api/verify")
    def api_verify():
        data = _body()
        ids = data.get("schemes") or scheme_ids()
        if not isinstance(ids, list):
            raise ApiError("'schemes' must be a list")
        key = _str_field(data, "key") or None
        results = [roundtrip_ok(s, key=key) for s in ids]
        return jsonify({
            "results": results,
            "passed": sum(1 for r in results if r["ok"]),
            "total": len(results),
        })

    return app


def main() -> None:  # pragma: no cover
    from ..cli import main as cli_main

    cli_main(["serve"])


if __name__ == "__main__":  # pragma: no cover
    create_app().run(debug=True)
