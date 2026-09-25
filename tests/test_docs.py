"""The documentation must build, must be served by the app, and must not drift from the code."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from glyphmark import docs as docs_mod
from glyphmark.cli import main
from glyphmark.sanitize import stage_docs
from glyphmark.schemes import SCHEMES
from glyphmark.web import create_app

ROOT = Path(__file__).resolve().parent.parent
DOCS_SRC = ROOT / "docs"
PAGES = ["index.md", "quickstart.md", "cli.md", "ui.md", "channels.md",
         "defence.md", "api.md", "reference.md", "ethics.md"]


def _mkdocs_importable() -> bool:
    try:
        import mkdocs  # noqa: F401
    except ImportError:
        return False
    return True


def _page(name: str) -> str:
    return (DOCS_SRC / name).read_text(encoding="utf-8")


def _all_docs() -> str:
    return "\n".join(_page(p) for p in PAGES)


@pytest.fixture
def docs_env(tmp_path, monkeypatch):
    """Point the docs machinery at a throwaway build dir so tests never touch build/docs."""
    target = tmp_path / "site"
    target.mkdir(parents=True)
    monkeypatch.setenv(docs_mod.ENV_BUILD_DIR, str(target))
    return target


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


# ------------------------------------------------------------- locating docs
def test_config_and_sources_are_found_from_the_checkout() -> None:
    assert docs_mod.config_path() == ROOT / "mkdocs.yml"
    assert docs_mod.source_dir() == DOCS_SRC
    assert docs_mod.status()["config"]


def test_pages_exist() -> None:
    for page in PAGES:
        assert (DOCS_SRC / page).is_file(), page
    assert (DOCS_SRC / "stylesheets" / "extra.css").is_file()


def test_status_reports_paths_and_pages(docs_env) -> None:
    info = docs_mod.status()
    assert info["built"] is False
    assert info["url"] == "/docs/"
    assert info["build_dir"] == str(docs_env)
    assert sorted(info["pages"]) == sorted(PAGES)


# --------------------------------------------------------------- serving them
def test_missing_docs_page_tells_you_the_command(docs_env, client) -> None:
    resp = client.get("/docs/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "glyphmark docs build" in body
    assert docs_env.name in body                  # tells you where it looked
    assert "not built" in body.lower()


def test_built_docs_are_served_and_traversal_is_refused(docs_env, client) -> None:
    (docs_env / "assets").mkdir(parents=True)
    (docs_env / "index.html").write_text("<h1>GlyphMark docs</h1><a href='cli.html'>cli</a>")
    (docs_env / "cli.html").write_text("<h1>CLI reference</h1>")
    (docs_env / "assets" / "x.css").write_text("body{}")

    assert client.get("/docs/").data.decode().startswith("<h1>GlyphMark docs</h1>")
    assert client.get("/docs/cli.html").status_code == 200
    assert client.get("/docs/assets/x.css").status_code == 200
    assert client.get("/docs").status_code == 308
    assert client.get("/docs").headers["Location"].endswith("/docs/")
    assert client.get("/docs/missing.html").status_code == 404
    # the builder must refuse to walk out of the build directory
    assert client.get("/docs/../../pyproject.toml").status_code == 404
    assert client.get("/docs/%2e%2e/pyproject.toml").status_code == 404


def test_docs_csp_is_scoped_to_the_docs_prefix(docs_env, client) -> None:
    (docs_env / "index.html").write_text("<h1>docs</h1>")
    docs_csp = client.get("/docs/").headers["Content-Security-Policy"]
    lab_csp = client.get("/").headers["Content-Security-Policy"]
    script_src = docs_csp.split("script-src")[1].split(";")[0]
    assert "'unsafe-inline'" in script_src          # Material's inline bootstrap
    assert "cdn.jsdelivr.net" not in docs_csp       # docs load nothing remote
    assert "connect-src 'self'" in docs_csp
    assert "https://cdn.jsdelivr.net" in lab_csp    # the lab keeps its own policy


def test_health_and_meta_advertise_the_docs(docs_env, client) -> None:
    assert client.get("/healthz").get_json()["docs"] is False
    assert client.get("/api/meta").get_json()["docs"] == {"built": False, "url": "/docs/"}
    (docs_env / "index.html").write_text("<h1>docs</h1>")
    assert client.get("/healthz").get_json()["docs"] is True
    assert client.get("/api/meta").get_json()["docs"] == {"built": True, "url": "/docs/"}


def test_lab_ui_links_to_the_docs(client) -> None:
    page = client.get("/").data.decode()
    assert 'href="/docs/"' in page
    assert "docs" in client.get("/static/app.js").data.decode()      # cheat sheet mentions it


# ----------------------------------------------------- docs must not lie (CLI)
def test_nav_in_mkdocs_yml_matches_the_markdown_files() -> None:
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav_targets = set(re.findall(r":\s+([a-z_]+\.md)\s*$", config, re.M))
    assert nav_targets == {p for p in PAGES}, f"nav/markdown mismatch: {nav_targets ^ set(PAGES)}"
    assert "docs_dir: docs" in config
    assert "use_directory_urls: false" in config   # required for /docs/<page>.html serving


def test_every_command_named_in_the_docs_exists() -> None:
    used = set(re.findall(r"glyphmark ([a-z][a-z-]+)", _all_docs()))
    assert used, "the query found no commands, so the check is vacuous"
    unknown = used - set(main.commands)
    assert not unknown, f"docs mention commands that do not exist: {sorted(unknown)}"


def test_every_flag_named_in_the_docs_is_real() -> None:
    """Flags drift when commands change; every documented flag must exist in `--help`."""
    runner = CliRunner()
    real: set[str] = set()
    chains: list[list[str]] = []
    for name, cmd in main.commands.items():
        chains.append([name])
        for sub in getattr(cmd, "commands", {}):
            chains.append([name, sub])
    for chain in chains:
        result = runner.invoke(main, [*chain, "--help"])
        assert result.exit_code == 0, chain
        real.update(re.findall(r"--[a-z][a-z0-9-]+", result.output))
    mentioned = set(re.findall(r"`(--[a-z][a-z0-9-]+)`", _all_docs()))
    assert mentioned, "no flags documented?"
    missing = mentioned - real
    assert not missing, f"docs document flags the CLI does not accept: {sorted(missing)}"


def test_documented_exit_codes_match_the_core() -> None:
    from glyphmark.codec import CapacityError, GlyphMarkError, NoPayloadError
    from glyphmark.frames import FrameError

    assert GlyphMarkError.exit_code == 1
    assert NoPayloadError.exit_code == 3
    assert FrameError.exit_code == 4
    assert CapacityError.exit_code == 5

    table = _page("cli.md").split("## Exit codes")[1]
    for code, meaning in [("3", "no payload"), ("4", "wrong key"),
                          ("5", "carrier too small"), ("6", "risk threshold")]:
        assert f"| `{code}` |" in table, code
        assert meaning in table, meaning


# ------------------------------------------------- docs must not lie (content)
def test_channel_table_matches_the_registry() -> None:
    page = _page("channels.md")
    for scheme in SCHEMES:
        row = next((line for line in page.splitlines()
                    if line.startswith(f"| `{scheme.id}` |")), None)
        assert row, f"{scheme.id} is missing from the channel table"
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[1] == scheme.family, scheme.id
        assert cells[2] == str(scheme.bits_per_unit), scheme.id
        assert float(cells[3]) == pytest.approx(scheme.density_bytes_per_unit), scheme.id
        assert cells[4] == "●" * scheme.stealth + "○" * (5 - scheme.stealth), scheme.id
        assert cells[5] == "●" * scheme.survival + "○" * (5 - scheme.survival), scheme.id
        assert cells[6] == scheme.carrier, scheme.id
        for killed in scheme.killed_by:
            assert f"`{killed}`" in cells[7], f"{scheme.id} killed_by drift"


def test_documented_stages_are_the_real_stages() -> None:
    page = _page("defence.md")
    for stage in stage_docs():
        assert stage["id"] in page, f"{stage['id']} undocumented"
        assert stage["label"].lower() in page.lower() or stage["description"][:24].lower() in page.lower()
    for killer in {k for stage in stage_docs() for k in stage["kills"]}:
        assert killer in page


def test_documented_findings_kinds_are_real() -> None:
    from glyphmark.analysis import _META

    page = _page("defence.md")
    for kind in _META:
        assert f"`{kind}`" in page, f"detection kind {kind} is undocumented"


def test_documented_endpoints_are_routed(client) -> None:
    rules = {rule.rule for rule in client.application.url_map.iter_rules()}
    documented = set(re.findall(r"`(/api/[a-z]+|/healthz|/docs/|/)`", _page("api.md")))
    assert documented >= {"/api/encode", "/api/decode", "/api/detect",
                          "/api/sanitize", "/api/inspect", "/api/verify", "/healthz"}
    assert documented <= rules, f"documented but not routed: {sorted(documented - rules)}"


def test_documented_json_fields_are_returned(docs_env, client) -> None:
    """The API tables list response keys; if the core renames one, this fails."""
    encode = client.post("/api/encode", json={
        "cover": "Plain carrier text for a watermark, long enough to carry bytes.",
        "payload": "id=42", "scheme": "tags"}).get_json()
    for key in ("scheme", "placement", "keyed", "verified", "text", "payload_len", "units_used",
                "bits_used", "carrier_units", "capacity_bytes", "cover_len", "utilization"):
        assert key in encode, key

    decode = client.post("/api/decode", json={"text": encode["text"]}).get_json()
    for key in ("scheme", "keyed", "payload_text", "payload_base64", "payload_hex", "payload_len",
                "units_used", "bits_read", "carrier_units", "attempts"):
        assert key in decode, key

    clean = client.post("/api/sanitize", json={"text": encode["text"]}).get_json()
    for key in ("text", "identical", "removed_total", "codepoints_before", "codepoints_after",
                "channels_targeted", "stages"):
        assert key in clean, key

    report = client.post("/api/detect", json={"text": encode["text"]}).get_json()
    for key in ("risk_score", "verdict", "findings", "frame_signatures", "tag_block_mirror",
                "nfkc_equal", "recommendation", "suspect_total"):
        assert key in report, key

    rows = client.post("/api/inspect",
                       json={"text": encode["text"], "only_suspect": True}).get_json()
    for key in ("codepoints", "utf8_bytes", "utf16_units", "suspect_count", "visible_guess",
                "truncated", "rows"):
        assert key in rows, key

    # the docs quote these names, so they may not silently disappear
    page = _page("api.md")
    for key in ("payload_text", "payload_hex", "payload_base64", "removed_total",
                "frame_signatures", "tag_block_mirror", "risk_score"):
        assert key in page, key


# ------------------------------------------------------------------ building
@pytest.mark.skipif(not _mkdocs_importable(),
                    reason="docs extra not installed (uv sync --extra docs)")
def test_docs_build_strictly_and_cleanly(tmp_path) -> None:
    out = tmp_path / "site"
    result = docs_mod.build(out=out, strict=True, clean=True)
    assert result["ok"], result["output"][-1500:]
    assert result["built"] and (out / "index.html").is_file()
    assert (out / "search" / "search_index.json").is_file(), "Material search must work"
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="cli.html"' in index
    assert 'src="/assets' not in index, "absolute asset URLs would 404 under /docs/"


def test_cli_docs_status_reports_unbuilt_json(docs_env) -> None:
    result = CliRunner().invoke(main, ["docs", "status", "--json"])
    assert result.exit_code == 0
    info = json.loads(result.output)
    assert info["built"] is False and info["url"] == "/docs/"
    assert docs_env.name in info["build_dir"]


def test_cli_docs_status_says_not_built(docs_env) -> None:
    result = CliRunner().invoke(main, ["docs", "status"])
    assert result.exit_code == 0
    assert "not built yet" in result.output


def test_cli_docs_build_reports_failure(monkeypatch, docs_env) -> None:
    monkeypatch.setattr(docs_mod, "_run_mkdocs", lambda args: {
        "ok": False, "output": "INFO - building\nERROR - bogus config value",
        "error": "mkdocs exited 1"})
    result = CliRunner().invoke(main, ["docs", "build"])
    assert result.exit_code == 1
    assert "mkdocs exited 1" in result.output


def test_cli_docs_check_failure_is_actionable(monkeypatch, docs_env) -> None:
    monkeypatch.setattr(docs_mod, "check", lambda strict=True: {
        "ok": False, "output": "WARNING - broken link: cli.md",
        "error": "mkdocs exited 1", "output_dir": "/tmp/x"})
    result = CliRunner().invoke(main, ["docs", "check"])
    assert result.exit_code == 1
    assert "broken link" in result.output
