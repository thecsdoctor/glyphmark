# SPDX-License-Identifier: MIT
"""The repository's own governance and supply-chain contract.

These tests fail when a foundation-review artegoact goes missing or drifts: a required file, a CI
status that checks a job that no longer exists, a CODEOWNERS path that was renamed, an SPDX header,
a `make` target the docs promise, a link to a page that is not there. In other words: the CNCF-style
repo hygiene is not a folder of markdown that rots, it is an asserted property of the tree.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML ships with mkdocs; sync --extra docs")

ROOT = Path(__file__).resolve().parent.parent

# The canonical home is not chosen yet; every URL in the repo uses the same placeholder owner so a
# single search-and-replace finishes the job.
OWNER_PLACEHOLDER = "OWNER/glyphmark"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _jsonc(text: str) -> str:
    """Strip // comments (devcontainer.json is JSONC)."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


# ----------------------------------------------------------------- required artefacts
COMMUNITY_FILES = [
    "README.md",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "ROADMAP.md",
    "ADOPTERS.md",
    "CHANGELOG.md",
    "TRADEMARKS.md",
]


def test_every_review_artefact_exists_and_says_something():
    """A file that exists but is empty is worse than none: it signals process theatre."""
    for rel in COMMUNITY_FILES:
        path = ROOT / rel
        assert path.is_file(), f"{rel} is missing"
        body = path.read_text(encoding="utf-8")
        assert len(body) > 800, f"{rel} is too thin to be a real policy ({len(body)} bytes)"
        assert len(body) < 60_000, f"{rel} has grown past the point of being read"


def test_governance_files_reference_each_other():
    """Ownership is only real if a reader can follow the chain from any entry point."""
    gov = read("GOVERNANCE.md")
    for target in ("MAINTAINERS.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "CHANGELOG.md"):
        assert target in gov, f"GOVERNANCE.md does not mention {target}"
    for rel in ("CONTRIBUTING.md", "SUPPORT.md", "SECURITY.md"):
        assert "GOVERNANCE.md" in read(rel) or "governance" in read(rel).lower(), rel
    assert "CNCF Code of Conduct" in read("CODE_OF_CONDUCT.md")
    assert "veto" in gov and "majority" in gov, "no decision procedure?"


def test_maintainers_file_is_machine_readable():
    body = read("MAINTAINERS.md")
    front = body.split("---")[1]
    assert "title: Maintainers" in front
    assert re.search(r"^\| Maintainer \| GitHub \| Email", body, re.M), "no maintainer table"
    assert "affiliation" in body.lower(), (
        "affiliations are required for conflict-of-interest review"
    )
    assert "## Emeritus" in body, "no emeritus path"
    handles = re.findall(r"\[@([\w-]+)\]\(https://github\.com/", body)
    assert handles, "no GitHub handles in MAINTAINERS.md"
    owners = read(".github/CODEOWNERS")
    for handle in handles:
        assert f"@{handle}" in owners, f"{handle} is a maintainer but owns nothing in CODEOWNERS"


def test_licence_file_matches_the_package_metadata():
    licence = read("LICENSE")
    assert "MIT License" in licence
    assert "Permission is hereby granted, free of charge" in licence
    assert "THE SOFTWARE IS PROVIDED" in licence  # the warranty disclaimer is not optional
    assert re.search(r"Copyright \(c\) \d{4}", licence), "copyright line missing"

    pyproject = read("pyproject.toml")
    assert 'license = { text = "MIT" }' in pyproject or 'license = "MIT"' in pyproject
    assert "License :: OSI Approved :: MIT License" in pyproject
    assert "NOTICE" in pyproject, "licence files must be declared for the build"
    # NOTICE must name the third-party material the binary/CDN actually pulls in
    notice = read("NOTICE")
    for third_party in ("Tailwind", "Alpine", "Material for MkDocs", "Unicode"):
        assert third_party in notice, f"NOTICE omits {third_party}"


def test_security_policy_has_the_parts_a_reviewer_checks():
    sec = read("SECURITY.md")
    assert re.search(r"## Supported versions", sec)
    assert "private vulnerability reporting" in sec.lower()
    assert re.search(r"\b90 days?\b", sec), "no disclosure ceiling"
    assert "in scope" in sec.lower() and "out of scope" in sec.lower()
    # every workflow it advertises must exist, with the job it names
    for workflow in set(re.findall(r"`(\.github/workflows/[a-z-]+\.yml)`", sec)):
        assert (ROOT / workflow).is_file(), f"SECURITY.md points at missing {workflow}"
    named_jobs: set[str] = set()
    for labels in re.findall(r"`\.github/workflows/[a-z-]+\.yml` \(([^)]*)\)", sec):
        named_jobs.update(re.findall(r"`([a-z-]+)`", labels))
    assert named_jobs, "the evidence table names no jobs, so the check would be vacuous"
    unbacked = named_jobs - _ci_job_names()
    assert not unbacked, f"SECURITY.md advertises checks no workflow produces: {sorted(unbacked)}"


def test_security_headers_are_actually_set_by_the_app():
    """The policy claims specific headers; the app must send them (docs-security drift guard)."""
    from glyphmark.web import create_app

    app = create_app()
    app.config.update(TESTING=True)
    resp = app.test_client().get("/healthz")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "camera=()" in resp.headers["Permissions-Policy"]
    assert resp.headers["Referrer-Policy"] == "same-origin"
    csp = resp.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp


# ------------------------------------------------------------------------ CI / supply chain
def _workflow(name: str) -> dict:
    return yaml.safe_load(read(f".github/workflows/{name}.yml"))


def _ci_job_names() -> set[str]:
    """Every status-check name CI can produce, matrix expanded."""
    names: set[str] = set()
    for wf in ("ci", "codeql", "scorecard", "deps-audit", "dependency-review", "release"):
        doc = _workflow(wf)
        for key, job in doc["jobs"].items():
            label = job.get("name", key)
            if "${{" in label:  # templated; expand the matrix below
                label = key
            matrix = job.get("strategy", {}).get("matrix", {})
            if matrix.get("python-version"):
                names.add(key)
                for v in matrix["python-version"]:
                    names.add(f"{key} ({v})")
            else:
                names.add(label if "${{" not in label else key)
    return names


def test_all_workflows_are_valid_and_least_privilege():
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    assert len(workflows) >= 5, "expected a workflow per concern"
    for path in workflows:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert doc.get("name"), f"{path.name} has no name"
        # `on` parses as the YAML boolean key True in some loaders; accept either.
        assert ("on" in doc) or (True in doc), f"{path.name} never triggers"
        assert "jobs" in doc and doc["jobs"], f"{path.name} has no jobs"
        top = doc.get("permissions", {})
        for job_name, job in doc["jobs"].items():
            perms = job.get("permissions", top)
            assert perms, f"{path.name}:{job_name} runs with the default (write) token"
            if isinstance(perms, str):
                assert perms in ("read-all", "read", "none"), f"{path.name}:{job_name} = {perms}"
            else:
                assert set(perms) <= {
                    "contents",
                    "actions",
                    "security-events",
                    "id-token",
                    "attestations",
                    "pull-requests",
                }, f"{path.name}:{job_name} asks for unexpected permissions: {sorted(perms)}"
                assert set(perms.values()) <= {
                    "read",
                    "write",
                    "none",
                }, f"{path.name}:{job_name}"
        for step_uses in re.findall(r"uses:\s*(\S+)", path.read_text(encoding="utf-8")):
            assert "@" in step_uses, f"{path.name} uses an unpinned action: {step_uses}"


def test_branch_protection_refs_real_checks():
    """A required status that no job produces blocks every future PR forever."""
    settings = yaml.safe_load(read(".github/settings.yml"))
    branch = next(b for b in settings["branches"] if b["name"] == "main")
    contexts = branch["protection"]["required_status_checks"]["contexts"]
    available = _ci_job_names()
    missing = [c for c in contexts if c not in available]
    assert not missing, f"required contexts with no job: {missing} (have: {sorted(available)})"
    assert branch["protection"]["required_pull_request_reviews"]["require_codeowners_review"]
    assert branch["protection"]["enforce_admins"] is True
    protection = branch["protection"]
    assert protection["required_pull_request_reviews"]["required_approving_review_count"] >= 1


def test_codeowners_paths_exist():
    owners_seen: set[str] = set()
    for line in read(".github/CODEOWNERS").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        path, *owners = line.split()
        owners_seen.update(owners)
        target = ROOT / path.lstrip("/")
        if path != "*":
            assert any(target.parent.glob(target.name)), f"CODEOWNERS path does not resolve: {path}"
    first_field = [
        line.split()[0]
        for line in read(".github/CODEOWNERS").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert "*" in first_field, "no catch-all owner"
    assert any(o.startswith("@glyphmark/") for o in owners_seen), "no teams as owners"


def test_dependabot_covers_every_ecosystem_in_the_tree():
    dep = yaml.safe_load(read(".github/dependabot.yml"))
    ecosystems = {u["package-ecosystem"] for u in dep["updates"]}
    assert {"github-actions", "npm"} <= ecosystems, ecosystems
    assert ecosystems & {"uv", "pip"}, "Python dependencies are not monitored"
    for update in dep["updates"]:
        assert update["schedule"]["interval"] in ("daily", "weekly"), "updates must be scheduled"
        assert update["open-pull-requests-limit"] <= 10, "update noise is unreviewed noise"


def test_dco_and_license_header_gates_are_wired_into_ci():
    ci = read(".github/workflows/ci.yml")
    assert "tools/check_license_headers.py" in ci
    assert "tools/check_dco.py" in ci
    assert "codeql-action/init@v3" in read(".github/workflows/codeql.yml")
    assert "scorecard-action" in read(".github/workflows/scorecard.yml")
    release = read(".github/workflows/release.yml")
    assert "cyclonedx" in release, "releases must ship an SBOM"
    assert "attest-build-provenance" in release, "releases must ship build provenance"


def test_license_headers_are_clean_right_now():
    result = subprocess.run(
        [sys.executable, "tools/check_license_headers.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dco_checker_accepts_a_proper_signoff_and_rejects_the_rest():
    dco = _load_tool("check_dco")
    good = {
        "sha": "a" * 40,
        "author": "Dev",
        "author_email": "dev@example.com",
        "body": "fix: something\n\nSigned-off-by: Dev <dev@example.com>\n",
    }
    unsigned = {**good, "body": "fix: something\n"}
    borrowed = {
        **good,
        "body": "fix: something\n\nSigned-off-by: Someone Else <other@example.com>\n",
    }
    assert dco.check([good]) == []
    assert len(dco.check([unsigned])) == 1
    assert len(dco.check([borrowed])) == 1, "a sign-off must match the commit author"
    merge = {**good, "parents": ["b" * 40, "c" * 40]}
    assert dco.check([merge]) == [], "merge commits carry no sign-off of their own"


def test_development_container_and_editor_config_are_valid():
    config = json.loads(_jsonc(read(".devcontainer/devcontainer.json")))
    assert "glyphmark" in config["name"]
    assert "postCreateCommand" in config
    assert 8123 in config["forwardPorts"]
    assert config["image"].startswith("mcr.microsoft.com/")
    assert "root = true" in read(".editorconfig")


# ------------------------------------------------------------------------ docs <-> repo
def test_local_links_in_the_repository_docs_resolve():
    """Markdown links between root files rot silently unless something checks them."""
    for rel in [f for f in COMMUNITY_FILES if f.endswith(".md")]:
        body = read(rel)
        for target in re.findall(r"\]\(([^)\s]+)\)", body):
            if target.startswith(("http://", "https://", "mailto:", "#", "/")):
                continue
            path = (ROOT / rel).parent / target.split("#")[0]
            assert path.exists(), f"{rel} links to a missing file: {target}"


def test_documented_make_targets_exist():
    makefile = read("Makefile")
    targets = set(re.findall(r"^([a-z][a-z_-]+):", makefile, re.M))
    for rel in ("CONTRIBUTING.md", "docs/contributing.md", "README.md"):
        for target in set(re.findall(r"`make ([a-z][a-z_-]+)`", read(rel))):
            assert target in targets, (
                f"{rel} promises 'make {target}', the Makefile has no such target"
            )


def test_docs_pages_cover_the_governance_surface():
    for page in ("docs/contributing.md", "docs/security.md", "docs/community.md"):
        assert (ROOT / page).is_file(), page
    community = read("docs/community.md")
    for artefact in ("GOVERNANCE.md", "MAINTAINERS.md", "CODE_OF_CONDUCT.md", "TRADEMARKS.md"):
        assert artefact in community, f"docs/community.md never mentions {artefact}"
    security = read("docs/security.md")
    assert "obfuscation" in security.lower() and "not encryption" in security.lower().replace(
        "**", ""
    ), "the keyed-mode honesty note must stay in the security page"


def test_owner_placeholder_is_used_consistently():
    urls_by_file = {}
    for rel in (
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "README.md",
        ".github/settings.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/workflows/release.yml",
        "pyproject.toml",
        "docs/index.md",
        "docs/contributing.md",
    ):
        found = set(re.findall(r"github\.com/[\w.<>-]+/[\w.<>-]+", read(rel)))
        urls_by_file[rel] = found
    own = {
        url
        for urls in urls_by_file.values()
        for url in urls
        if "glyphmark" in url and not url.endswith("devcontainers/spec")
    }
    assert own == {f"github.com/{OWNER_PLACEHOLDER}"}, (
        f"the project's own URLs must share one placeholder owner, found {sorted(own)}"
    )


def test_readme_points_at_the_project_operations():
    readme = read("README.md").lower()
    for target in (
        "contributing.md",
        "governance.md",
        "security.md",
        "changelog.md",
        "code_of_conduct.md",
        "roadmap.md",
        "logo/glyphmark.svg",
    ):
        assert target in readme, f"README.md does not link {target}"
    assert "MIT" in read("README.md")


def test_release_workflow_verifies_its_own_tag():
    release = read(".github/workflows/release.yml")
    assert "GITHUB_REF_NAME" in release
    assert "PEP 440" in release or "pep440" in release.lower()
    assert "--verify-tag" in release, (
        "a release must not build a tag that does not match its version"
    )
    assert "gh release create" in release


def test_repository_hygiene_files_are_not_gitignored():
    """Artefacts that CI and reviewers need must never be ignored by accident."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", *COMMUNITY_FILES[:6], ".github/workflows/ci.yml", "Makefile"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # git check-ignore exits 0 if ANY path is ignored
    assert ignored.returncode != 0, f"required files are gitignored:\n{ignored.stdout}"
