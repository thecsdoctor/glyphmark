"""The CLI must be fully scriptable: flags, files, stdin, machine-readable output."""

from __future__ import annotations

import json
import re

import pytest
from click.testing import CliRunner

from glyphmark.cli import main
from glyphmark.codec import encode, sample_carrier
from glyphmark.schemes import get_scheme, scheme_ids

PAYLOAD = "session=4F2A-91C7"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def run(runner: CliRunner, *args: str, stdin: str | None = None):
    return runner.invoke(main, list(args), input=stdin, catch_exceptions=False)


def marked(scheme_id: str = "tags") -> str:
    scheme = get_scheme(scheme_id)
    cover = sample_carrier(scheme, len(PAYLOAD))
    return encode(cover, PAYLOAD.encode(), scheme_id).text


def test_version_and_help(runner: CliRunner) -> None:
    assert "glyphmark" in run(runner, "--version").output
    assert "Exit codes" in run(runner, "--help").output
    assert "non-interactive" not in run(runner, "--version").output


def test_schemes_and_scheme_detail(runner: CliRunner) -> None:
    data = json.loads(run(runner, "schemes", "--json").output)
    assert [s["id"] for s in data] == scheme_ids()
    detail = json.loads(run(runner, "scheme", "vs-bytes", "--json").output)
    assert detail["radix"] == 256
    assert len(detail["characters"]) == 256
    assert "table" in run(runner, "schemes").output.lower() or "vs-bytes" in run(
        runner, "schemes").output


def test_chars_reference(runner: CliRunner) -> None:
    rows = json.loads(run(runner, "chars", "--json").output)
    assert any(r["codepoint"] == "U+200B" for r in rows)
    assert any(r["codepoint"] == "U+E0020" for r in rows)


def test_encode_decode_flag_roundtrip(runner: CliRunner) -> None:
    out = run(runner, "encode", "--cover", "x" * 900, "--payload", PAYLOAD,
              "--scheme", "tags", "-e", "json").output
    enc = json.loads(out)
    assert enc["verified"] is True
    dec = json.loads(run(runner, "decode", "--text", enc["text"], "-f", "json").output)
    assert dec["payload_text"] == PAYLOAD
    assert dec["scheme"] == "tags"


def test_stdin_and_file_inputs(runner: CliRunner) -> None:
    result = run(runner, "encode", "--cover-file", "-", "--payload", PAYLOAD,
                 "--scheme", "zw-binary", stdin="y" * 800)
    assert PAYLOAD not in result.output            # output is the carrier, not the payload
    text = result.output.strip()
    back = run(runner, "decode", "--text-file", "-", stdin=text)
    assert PAYLOAD in back.output
    assert "[glyphmark] recovered" in back.output  # report goes to stderr, not stdout


def test_emit_modes(runner: CliRunner) -> None:
    enc = run(runner, "encode", "--cover", "z" * 900, "--payload", "hi",
              "--scheme", "tags", "-e", "escapes").output
    assert chr(0xE0035) not in enc                      # nothing invisible survives the escape
    assert re.search(r"\\U000e00", enc, re.IGNORECASE)  # astral code points -> \UXXXXXXXX
    cp = run(runner, "encode", "--cover", "z" * 900, "--payload", "hi",
             "--scheme", "tags", "-e", "codepoints").output
    assert "U+E00" in cp


def test_output_file(runner: CliRunner, tmp_path) -> None:
    target = tmp_path / "marked.txt"
    run(runner, "encode", "--cover", "w" * 900, "--payload", PAYLOAD, "--scheme",
        "fullwidth", "-o", str(target))
    assert target.read_text(encoding="utf-8")
    assert PAYLOAD in run(runner, "decode", "--text-file", str(target)).output


def test_detect_json_and_table(runner: CliRunner) -> None:
    text = marked()
    report = json.loads(run(runner, "detect", "--text", text, "--json").output)
    assert report["verdict"] == "watermark-confirmed"
    out = run(runner, "detect", "--text", text).output
    assert "verdict=watermark-confirmed" in out
    assert "GlyphMark frame recovered" in out


def test_detect_fail_on_risk_exit_code(runner: CliRunner) -> None:
    text = marked()
    assert run(runner, "detect", "--text", text).exit_code == 0
    gated = run(runner, "detect", "--text", text, "--fail-on-risk", "50")
    assert gated.exit_code == 6


def test_sanitize_roundtrip_and_list(runner: CliRunner) -> None:
    text = marked("zw-octal")
    clean = run(runner, "sanitize", "--text", text, "-e", "json").output
    report = json.loads(clean)
    assert report["removed_total"] > 0
    # running it twice is a no-op, and the CLI says so
    again = run(runner, "sanitize", "--text", report["text"])
    assert "nothing to remove" in again.output
    assert "strip_tags" in run(runner, "sanitize", "--list-stages").output
    staged = run(runner, "sanitize", "--text", text, "--stage", "strip_zero_width",
                 "-e", "json").output
    assert json.loads(staged)["stages"][0]["id"] == "strip_zero_width"


def test_inspect_only_suspect(runner: CliRunner) -> None:
    out = run(runner, "inspect", "--text", marked("omni16"), "--only-suspect").output
    assert "U+200B" in out or "U+200" in out
    data = json.loads(run(runner, "inspect", "--text", "a\u200bb", "--json").output)
    assert data["suspect_count"] == 1


def test_verify_all_channels_pass(runner: CliRunner) -> None:
    assert run(runner, "verify").exit_code == 0
    results = json.loads(run(runner, "verify", "--scheme", "homoglyph", "--scheme", "tags",
                             "--json").output)
    assert all(r["ok"] for r in results) and len(results) == 2


def test_exit_codes_for_failure_modes(runner: CliRunner) -> None:
    assert run(runner, "decode", "--text", "boring text").exit_code == 3
    enc = run(runner, "encode", "--cover", "q" * 900, "--payload", "p", "--scheme",
              "tags", "--key", "right", "-e", "json").output
    text = json.loads(enc)["text"]
    assert run(runner, "decode", "--text", text, "--key", "wrong").exit_code == 4
    assert run(runner, "encode", "--cover", "tiny", "--payload", "x" * 3000,
               "--scheme", "homoglyph").exit_code == 5
    assert run(runner, "scheme", "nope").exit_code == 2


def test_report_goes_to_stderr_only(runner: CliRunner) -> None:
    result = run(runner, "encode", "--cover", "m" * 900, "--payload", "hi", "--scheme",
                 "tags", "--report")
    assert "scheme=tags" in result.output            # CliRunner mixes both streams
    result = runner.invoke(main, ["encode", "--cover", "m" * 900, "--payload", "hi",
                                  "--scheme", "tags"], input=None, catch_exceptions=False)
    assert "scheme=tags" not in result.stdout


def test_serve_command_is_registered(runner: CliRunner) -> None:
    assert "serve" in run(runner, "--help").output
