# SPDX-License-Identifier: MIT
"""MkDocs Material documentation, built and served from inside the app.

The layout is the standard MkDocs one: ``mkdocs.yml`` at the project root, Markdown in ``docs/``.
``glyphmark docs build`` renders it into a static site; the Flask app serves that directory under
``/docs/``.

Nothing here is required at import time by the library, the CLI's other commands or the API: if the
site has not been built, ``/docs/`` says so instead of 404-ing, and ``docs status`` reports it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

#: environment overrides (documented in docs/reference.md)
ENV_CONFIG = "GLYPHMARK_DOCS_CONFIG"
ENV_BUILD_DIR = "GLYPHMARK_DOCS_DIR"

#: where the web app mounts the built site
URL = "/docs/"

_INSTALL_HINT = "uv sync --extra docs   # or: pip install 'glyphmark[docs]'"


def config_path() -> Path | None:
    """The ``mkdocs.yml`` to build from, or ``None`` when it is absent (e.g. wheel install)."""
    candidates: list[Path] = []
    env = os.environ.get(ENV_CONFIG)
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / "mkdocs.yml")  # src/glyphmark/docs.py -> repo root
    candidates.append(Path(__file__).resolve().parent / "mkdocs.yml")
    candidates.append(Path.cwd() / "mkdocs.yml")
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def source_dir() -> Path | None:
    """The Markdown directory declared by the config (``docs_dir``, default ``docs/``)."""
    cfg = config_path()
    if cfg is None:
        return None
    for line in cfg.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("docs_dir:"):
            return (cfg.parent / stripped.split(":", 1)[1].strip()).resolve()
    return cfg.parent / "docs"


def build_dir() -> Path:
    """Where the built site lives — the directory ``/docs/`` serves and ``docs build`` writes."""
    env = os.environ.get(ENV_BUILD_DIR)
    if env:
        return Path(env)
    cfg = config_path()
    if cfg is not None:
        return cfg.parent / "build" / "docs"
    return Path(__file__).resolve().parent / "web" / "static" / "docs"


def is_built(site: Path | None = None) -> bool:
    site = site or build_dir()
    return (site / "index.html").is_file()


def status() -> dict:
    """Everything the CLI, the API and the UI need to know about the docs."""
    site = build_dir()
    src = source_dir()
    return {
        "built": is_built(site),
        "url": URL,
        "source_dir": str(src) if src else None,
        "build_dir": str(site),
        "config": str(config_path()) if config_path() else None,
        "index": str(site / "index.html") if is_built(site) else None,
        "pages": sorted(p.name for p in (src or Path(".")).glob("*.md")) if src else [],
        "install_hint": _INSTALL_HINT,
    }


def _mkdocs_available() -> bool:
    try:
        import mkdocs  # noqa: F401
    except ImportError:
        return False
    return True


def _run_mkdocs(args: list[str]) -> dict:
    """Run ``python -m mkdocs`` with our config, capturing output for the caller."""
    if not _mkdocs_available():
        return {
            "ok": False,
            "output": "",
            "error": f"mkdocs is not installed. Install it with:  {_INSTALL_HINT}",
        }
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mkdocs", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "output": output.strip(),
        "error": None if proc.returncode == 0 else f"mkdocs exited {proc.returncode}",
    }


def build(out: str | Path | None = None, strict: bool = False, clean: bool = True) -> dict:
    """Render ``docs/`` into ``out`` (default: :func:`build_dir`).

    ``-d`` is always passed as an absolute path because mkdocs resolves a relative one against the
    *config file's* directory, which is a different place.
    """
    cfg = config_path()
    if cfg is None:
        return {
            "ok": False,
            "error": f"no mkdocs.yml found (set {ENV_CONFIG} to point at it)",
            "output": "",
            "output_dir": str(build_dir()),
            "built": False,
        }

    target = Path(out).expanduser().resolve() if out else build_dir()
    target.mkdir(parents=True, exist_ok=True)
    result = _run_mkdocs(
        ["build", "-f", str(cfg), "-d", str(target)]
        + (["--strict"] if strict else [])
        + (["--clean"] if clean else [])
    )
    result["output_dir"] = str(target)
    result["built"] = is_built(target)
    return result


def check(strict: bool = True) -> dict:
    """Build into a throwaway directory: broken links and warnings become failures."""
    tmp = Path(tempfile.mkdtemp(prefix="glyphmark-docs-check-"))
    try:
        cfg = config_path()
        if cfg is None:
            return {"ok": False, "error": "no mkdocs.yml found", "output": "", "output_dir": ""}
        result = _run_mkdocs(
            ["build", "-f", str(cfg), "-d", str(tmp)] + (["--strict"] if strict else [])
        )
        result["output_dir"] = str(tmp)
        result["built"] = is_built(tmp)
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
