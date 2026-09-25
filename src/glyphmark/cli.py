"""GlyphMark command line.

Fully non-interactive: every value comes from flags, files or stdin, so the CLI
is scriptable and mirrors 1:1 the JSON API the web UI consumes.

Exit codes
    0 success
    1 usage / internal error
    2 bad CLI arguments (click)
    3 no watermark found while decoding / detecting
    4 frame present but corrupt, or wrong --key
    5 carrier too small for the payload
    6 detection risk score reached the --fail-on-risk threshold
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import __version__
from .analysis import detect, inspect_text
from .codec import (
    PLACEMENTS,
    GlyphMarkError,
    decode,
    encode,
    roundtrip_ok,
)
from .frames import FrameError
from .sanitize import DEFAULT_PIPELINE, sanitize, stage_docs
from .schemes import SCHEMES, all_reference_rows, get_scheme, scheme_ids

try:
    from rich.console import Console
    from rich.table import Table

    HAVE_RICH = True
except ImportError:  # pragma: no cover
    HAVE_RICH = False

console = Console(highlight=False) if HAVE_RICH else None
EXIT_DETECTION = 6


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #

def _read(value: str | None, file: str | None, opt: str) -> str:
    """Resolve a text option: inline flag, file path, '-' or piped stdin."""
    if value is not None:
        return value
    if file is not None:
        if file == "-":
            return sys.stdin.read()
        return Path(file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise click.UsageError(f"give --{opt} ... or --{opt}-file PATH (use '-' for stdin)")


def _write(text: str, out: str | None, encoding: str = "utf-8") -> None:
    if out in (None, "-"):
        sys.stdout.write(text if text.endswith("\n") or not text else text + "\n")
        return
    Path(out).write_text(text, encoding=encoding, newline="")


def _escapes(text: str) -> str:
    """ASCII-safe rendering: keeps \n\t, escapes every other non-ASCII code point."""
    out = []
    for ch in text:
        if ch in "\n\t":
            out.append(ch)
        elif ord(ch) < 0x7F:
            out.append(ch)
        else:
            out.append(ch.encode("unicode_escape").decode("ascii"))
    return "".join(out)


def _emit(text: str, emit: str, out: str | None, payload: dict) -> None:
    if emit == "json":
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    elif emit == "escapes":
        _write(_escapes(text), out)
    elif emit == "codepoints":
        _print_codepoints(text)
    else:
        _write(text, out)


def _print_codepoints(text: str) -> None:
    info = inspect_text(text, limit=100000)
    click.echo(f"{'idx':>6}  {'codepoint':<10} {'cat':<4} {'utf8':<14} name / flags")
    for row in info["rows"]:
        click.echo(
            f"{row['index']:>6}  {row['codepoint']:<10} {row['category']:<4} "
            f"{row['utf8']:<14} {row['name']}"
            + (f"  [{','.join(row['flags'])}]" if row["flags"] else "")
        )


def _bar(value: int, total: int = 5) -> str:
    return "█" * max(0, min(total, value)) + "·" * max(0, total - value)


def _table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    if console:
        tbl = Table(title=title, header_style="bold cyan", title_style="bold")
        for col in columns:
            tbl.add_column(col, overflow="fold")
        for row in rows:
            tbl.add_row(*row)
        console.print(tbl)
    else:  # pragma: no cover
        click.echo(title)
        click.echo(" | ".join(columns))
        for row in rows:
            click.echo(" | ".join(row))


def _fail(exc: Exception) -> None:
    code = getattr(exc, "exit_code", 1)
    click.secho(f"error: {exc}", fg="red", err=True)
    sys.exit(code)


# --------------------------------------------------------------------------- #
# Root
# --------------------------------------------------------------------------- #

@click.group(invoke_without_command=True, context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, prog_name="glyphmark")
@click.pass_context
def main(ctx: click.Context, ) -> None:
    """GlyphMark — text watermarking over ASCII/Unicode channels.

    \b
    Embed, extract, detect and sanitize invisible/look-alike text watermarks.
    Everything here is also available as a web UI + JSON API:  glyphmark serve
    Usage docs (mkdocs-material, served at /docs/):  glyphmark docs build
    \b
    Exit codes: 0 ok · 1 error · 3 no payload · 4 corrupt/wrong key ·
                5 carrier too small · 6 risk threshold hit
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command("schemes")
@click.option("--json", "as_json", is_flag=True, help="Machine readable output.")
def cmd_schemes(as_json: bool) -> None:
    """List every watermark channel with capacity, stealth and survival."""
    if as_json:
        click.echo(json.dumps([s.to_dict(with_chars=False) for s in SCHEMES], indent=2))
        return
    _table(
        "Watermark channels",
        ["id", "family", "bits/unit", "stealth", "survival", "carrier", "detection vector"],
        [
            [s.id, s.family, str(s.bits_per_unit), _bar(s.stealth), _bar(s.survival),
             s.carrier, s.detection]
            for s in SCHEMES
        ],
    )
    click.echo("\nDetail + character table for one channel: glyphmark scheme <id>")


@main.command("scheme")
@click.argument("scheme_id", type=click.Choice(scheme_ids()))
@click.option("--json", "as_json", is_flag=True)
def cmd_scheme(scheme_id: str, as_json: bool) -> None:
    """Show one channel in detail, including its character set."""
    scheme = get_scheme(scheme_id)
    if as_json:
        click.echo(json.dumps(scheme.to_dict(), indent=2, ensure_ascii=False))
        return
    click.secho(f"{scheme.id}  —  {scheme.label}", fg="cyan", bold=True)
    click.echo(scheme.blurb)
    click.echo(f"\nfamily={scheme.family}  radix={scheme.radix}  "
               f"bits/unit={scheme.bits_per_unit}  carrier={scheme.carrier}")
    click.echo(f"stealth={_bar(scheme.stealth)}  survival={_bar(scheme.survival)}")
    click.echo(f"detection: {scheme.detection}")
    click.echo(f"killed by: {', '.join(scheme.killed_by)}")
    for note in scheme.notes:
        click.echo(f"  • {note}")
    rows = [[r["codepoint"], r["category"], r["utf8"], r["render"], r["name"][:60]]
            for r in scheme.unit_rows()]
    _table("Characters in use", ["codepoint", "cat", "utf-8", "render", "unicode name"], rows)


@main.command("chars")
@click.option("--json", "as_json", is_flag=True)
def cmd_chars(as_json: bool) -> None:
    """Reference table of every special character used by any channel."""
    rows = all_reference_rows()
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    _table(
        "Character reference",
        ["codepoint", "cat", "utf-8", "render", "used by"],
        [[r["codepoint"], r["category"], r["utf8"], r["render"], ", ".join(r["schemes"])]
         for r in rows],
    )


@main.command("encode")
@click.option("--cover", "cover_text", help="Cover (carrier) text.")
@click.option("--cover-file", "cover_file", help="Cover text file, '-' = stdin.")
@click.option("--payload", "payload_text", help="Payload string to embed.")
@click.option("--payload-file", "payload_file", help="Payload file, '-' = stdin.")
@click.option("-s", "--scheme", "scheme", type=click.Choice(scheme_ids()), default="zw-octal",
              show_default=True, help="Watermark channel.")
@click.option("-k", "--key", "key", help="Binding secret (obfuscation, not crypto).")
@click.option("-p", "--placement", "placement", type=click.Choice(PLACEMENTS),
              default="spread", show_default=True)
@click.option("-o", "--out", "out", help="Output file, '-' = stdout.")
@click.option("-e", "--emit", "emit", default="raw",
              type=click.Choice(["raw", "escapes", "json", "codepoints"]), show_default=True)
@click.option("--report", "report", is_flag=True, help="Print report to stderr.")
def cmd_encode(cover_text: str | None, cover_file: str | None, payload_text: str | None,
               payload_file: str | None, scheme: str, key: str | None, placement: str,
               out: str | None, emit: str, report: bool) -> None:
    """Embed a payload into cover text."""
    try:
        cover = _read(cover_text, cover_file, "cover")
        payload = _read(payload_text, payload_file, "payload")
        result = encode(cover, payload.encode("utf-8"), scheme, key=key, placement=placement)
    except (GlyphMarkError, FrameError) as exc:
        _fail(exc)
        return
    if report or emit != "json":
        click.echo(
            f"[glyphmark] scheme={scheme} payload={result.payload_len}B "
            f"units={result.units_used} ({result.bits_used} bits) of {result.carrier_units} "
            f"carrier slots · spare capacity≈{result.capacity_bytes}B · "
            f"keyed={'yes' if result.keyed else 'no'} · verified={result.verified}",
            err=True,
        )
    _emit(result.text, emit, out, result.to_dict())


@main.command("decode")
@click.option("--text", "text", help="Watermarked text.")
@click.option("--text-file", "text_file", help="Input file, '-' = stdin.")
@click.option("-s", "--scheme", "scheme", default="auto", show_default=True,
              help="Channel id, or 'auto' to sweep every channel.")
@click.option("-k", "--key", "key", help="Binding secret.")
@click.option("-f", "--format", "fmt", default="text",
              type=click.Choice(["text", "hex", "base64", "json"]), show_default=True)
@click.option("-o", "--out", "out")
def cmd_decode(text: str | None, text_file: str | None, scheme: str, key: str | None,
               fmt: str, out: str | None) -> None:
    """Recover a payload (auto-detects the channel)."""
    try:
        body = _read(text, text_file, "text")
        result = decode(body, key=key, scheme_id=scheme)
    except (GlyphMarkError, FrameError) as exc:
        _fail(exc)
        return
    if fmt == "json":
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    if fmt == "hex":
        _write(result.payload.hex(), out)
    elif fmt == "base64":
        from base64 import b64encode

        _write(b64encode(result.payload).decode("ascii"), out)
    else:
        _write(result.payload.decode("utf-8", errors="replace"), out)
    click.echo(
        f"[glyphmark] recovered {len(result.payload)}B via '{result.scheme_id}' "
        f"({result.bits_read} bits read)", err=True,
    )


@main.command("detect")
@click.option("--text", "text", help="Text to analyse.")
@click.option("--text-file", "text_file", help="Input file, '-' = stdin.")
@click.option("--json", "as_json", is_flag=True)
@click.option("--fail-on-risk", "fail_on_risk", type=int, default=None,
              help="Exit 6 when risk score >= N (CI gate).")
@click.option("--no-frames", is_flag=True, help="Skip frame-signature recovery.")
def cmd_detect(text: str | None, text_file: str | None, as_json: bool,
               fail_on_risk: int | None, no_frames: bool) -> None:
    """Analyse text for covert channels (defensive scan)."""
    try:
        body = _read(text, text_file, "text")
    except click.UsageError:
        raise
    report = detect(body, try_frames=not no_frames)
    if as_json:
        click.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_detect(report)
    if fail_on_risk is not None and report["risk_score"] >= fail_on_risk:
        sys.exit(EXIT_DETECTION)


def _print_detect(report: dict) -> None:
    color = {"clean": "green", "minor-anomalies": "yellow", "suspicious": "yellow",
             "high-risk": "red", "watermark-confirmed": "red"}[report["verdict"]]
    click.secho(
        f"risk={report['risk_score']}/100  verdict={report['verdict']}  "
        f"suspect_codepoints={report['suspect_total']}  codepoints={report['codepoints']}",
        fg=color, bold=True,
    )
    if not report["findings"]:
        click.echo(report["recommendation"])
        return
    _table(
        "Findings",
        ["severity", "kind", "count", "characters", "remove with"],
        [
            [f["severity"], f["kind"], str(f["count"]),
             ", ".join(sorted({c["codepoint"] for c in f.get("characters", [])})) or "—",
             f.get("remove_with", "—")]
            for f in report["findings"]
        ],
    )
    for f in report["findings"]:
        click.secho(f"\n■ {f['title']} ({f['severity']}, {f['count']} occurrence(s))", bold=True)
        click.echo(f"  {f['why']}")
        if f.get("payload_preview"):
            click.secho(f"  recovered payload preview: {f['payload_preview']}", fg="red")
        for tok in (f.get("tokens") or [])[:5]:
            click.echo(f"  mixed-script token at {tok['offset']}: {tok['text']!r} "
                       f"scripts={','.join(tok['scripts'])}")
    if report["tag_block_mirror"]:
        click.secho(f"\nPlane-14 tag block decodes to: {report['tag_block_mirror'][:200]!r}",
                    fg="red")
    click.echo(f"\n{report['recommendation']}")


@main.command("sanitize")
@click.option("--text", "text", help="Text to clean.")
@click.option("--text-file", "text_file", help="Input file, '-' = stdin.")
@click.option("--stage", "stages", multiple=True,
              help="Run only these stages (repeatable). Default pipeline is used otherwise.")
@click.option("--list-stages", is_flag=True, help="Show the sanitizer pipeline and exit.")
@click.option("-e", "--emit", default="raw",
              type=click.Choice(["raw", "escapes", "json"]), show_default=True)
@click.option("-o", "--out")
def cmd_sanitize(text: str | None, text_file: str | None, stages: tuple[str, ...],
                 list_stages: bool, emit: str, out: str | None) -> None:
    """Strip covert-channel code points (intake hygiene / watermark removal)."""
    if list_stages:
        _table("Sanitizer stages", ["id", "default", "kills", "what it does"],
               [[s["id"], "yes" if s["default"] else "opt-in", ", ".join(s["kills"]) or "—",
                 s["description"]] for s in stage_docs()])
        click.echo(f"\ndefault pipeline: {', '.join(DEFAULT_PIPELINE)}")
        return
    try:
        body = _read(text, text_file, "text")
        result = sanitize(body, list(stages) or None)
    except KeyError as exc:
        _fail(GlyphMarkError(str(exc)))
        return
    if emit == "json":
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if emit == "escapes":
            _write(_escapes(result["text"]), out)
        else:
            _write(result["text"], out)
        changed = [f"{s['id']}(-{s['removed']})" for s in result["stages"] if s["removed"]]
        click.echo(
            f"[glyphmark] {result['codepoints_before']}→{result['codepoints_after']} "
            f"codepoints, {result['removed_total']} removed/rewritten: "
            + (", ".join(changed) if changed else "nothing to remove"), err=True,
        )


@main.command("inspect")
@click.option("--text", "text", help="Text to inspect.")
@click.option("--text-file", "text_file", help="Input file, '-' = stdin.")
@click.option("--json", "as_json", is_flag=True)
@click.option("--only-suspect", is_flag=True, help="Show only anomalous code points.")
def cmd_inspect(text: str | None, text_file: str | None, as_json: bool,
                only_suspect: bool) -> None:
    """Per-code-point breakdown of a string (what is actually in it)."""
    body = _read(text, text_file, "text")
    if as_json:
        click.echo(json.dumps(inspect_text(body), indent=2, ensure_ascii=False))
        return
    info = inspect_text(body)
    click.secho(f"{info['codepoints']} codepoints · {info['utf8_bytes']} utf-8 bytes · "
                f"{info['utf16_units']} utf-16 units · {info['suspect_count']} suspicious")
    rows = [r for r in info["rows"] if not only_suspect or r["suspect"]]
    _table("Codepoints", ["idx", "codepoint", "cat", "script", "utf-8", "name", "flags"],
           [[str(r["index"]), r["codepoint"], r["category"], r["script"], r["utf8"],
             r["name"][:48], ",".join(r["flags"]) or "—"] for r in rows[:400]])


@main.command("verify")
@click.option("--scheme", "only", multiple=True, help="Only these channels.")
@click.option("-k", "--key", help="Also exercise the keyed path.")
@click.option("--json", "as_json", is_flag=True)
def cmd_verify(only: tuple[str, ...], key: str | None, as_json: bool) -> None:
    """Self-test: encode + extract round trip for every channel."""
    ids = list(only) or scheme_ids()
    results = [roundtrip_ok(s, key=key) for s in ids]
    if as_json:
        click.echo(json.dumps(results, indent=2))
    else:
        _table("Channel self test", ["scheme", "result", "bits", "carrier", "capacity B",
                                      "detail"],
               [[r["scheme"], "PASS" if r["ok"] else "FAIL", str(r["bits_used"]),
                 str(r["carrier_units"]), str(r["capacity_bytes"]), r["error"] or ""]
                for r in results])
    if not all(r["ok"] for r in results):
        sys.exit(1)


@main.group("docs")
def cmd_docs() -> None:
    """Build the documentation that the web app serves under /docs/."""


@cmd_docs.command("build")
@click.option("-o", "--out", help="Output directory (default: the one /docs/ serves).")
@click.option("--strict/--no-strict", default=False, help="Turn warnings and broken links into errors.")
@click.option("--clean/--no-clean", default=True, help="Drop previous output first (default: clean).")
def cmd_docs_build(out: str | None, strict: bool, clean: bool) -> None:
    """Render docs/ with mkdocs-material into a static site."""
    from . import docs as docs_mod

    result = docs_mod.build(out=out, strict=strict, clean=clean)
    if not result["ok"]:
        for line in (result.get("output") or "").splitlines()[-25:]:
            click.secho(line, err=True)
        _fail(GlyphMarkError(result["error"] or "mkdocs build failed"))
        return
    tail = (result.get("output") or "").splitlines()[-8:]
    for line in tail:
        click.echo(line)
    click.secho(f"\ndocs built -> {result['output_dir']}", fg="green")
    click.echo(f"serve it with:  glyphmark serve   (then open {docs_mod.URL})")


@cmd_docs.command("check")
@click.option("--strict/--no-strict", default=True, help="Fail on warnings and broken links.")
def cmd_docs_check(strict: bool) -> None:
    """Build into a temp directory: broken links and warnings exit 1 (CI gate)."""
    from . import docs as docs_mod

    result = docs_mod.check(strict=strict)
    if not result["ok"]:
        click.secho((result.get("output") or "")[-4000:], err=True)
        _fail(GlyphMarkError(result["error"] or "docs build failed"))
        return
    click.secho("docs OK — no broken links, no warnings", fg="green")
    click.echo(f"(strict build in {result['output_dir']})")


@cmd_docs.command("status")
@click.option("--json", "as_json", is_flag=True)
def cmd_docs_status(as_json: bool) -> None:
    """Show where the docs live and whether they have been built."""
    from . import docs as docs_mod

    info = docs_mod.status()
    if as_json:
        click.echo(json.dumps(info, indent=2))
        return
    click.echo(f"built:      {'yes' if info['built'] else 'no'}   ({info['url']})")
    click.echo(f"sources:    {info['source_dir'] or 'not found'}")
    click.echo(f"config:     {info['config'] or 'not found'}")
    click.echo(f"build dir:  {info['build_dir']}")
    if info["pages"]:
        click.echo(f"pages:      {', '.join(info['pages'])}")
    if not info["built"]:
        click.secho("\nnot built yet:  glyphmark docs build", fg="yellow")
    if not _mkdocs_installed():
        click.secho(f"mkdocs not installed:  {info['install_hint']}", fg="yellow")


def _mkdocs_installed() -> bool:
    try:
        import mkdocs  # noqa: F401
    except ImportError:
        return False
    return True


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--debug/--no-debug", default=False, help="Flask reloader + verbose errors.")
def serve(host: str, port: int, debug: bool) -> None:
    """Run the web UI (same features as the CLI, plus /api/*)."""
    from .web import create_app

    click.secho(f"GlyphMark UI on http://{host}:{port}  (JSON API under /api/*)", fg="cyan")
    create_app().run(host=host, port=port, debug=debug)


if __name__ == "__main__":  # pragma: no cover
    main()
