# syntax=docker/dockerfile:1.7
# GlyphMark — multi-stage image.
#
#   docker build --target test    .   # runs the whole suite + lint + strict docs inside the image
#   docker build .                    # slim, non-root runtime image with prebuilt documentation
#
# The runtime image contains: the interpreter, a venv with the three runtime deps plus the
# installed package, and the documentation site built from *this* source tree (so /docs/ can
# never disagree with the code it came from). No toolchain, no compiler, no package manager.
#
# Image name/version metadata comes from the CI workflow (build args), so `docker inspect` on a
# published image points back at the commit and the SPDX licence.

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.12

# --------------------------------------------------------------------------- base
FROM python:${PYTHON_VERSION}-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
# Base images are pinned by tag here and kept current by Dependabot; digest pinning is a roadmap
# item (ROADMAP.md), so that the pin lives in version control rather than in a registry move.
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------- deps
# Dependency resolution first, in its own layer, so editing source does not reinstall the world.
FROM base AS deps
ARG UV_VERSION
RUN python -m pip install "uv==${UV_VERSION}.*"
WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
# runtime deps + the project itself, then the dev/docs extras on top (cached together)
RUN uv sync --frozen \
    && uv sync --frozen --extra dev --extra docs

# --------------------------------------------------------------------------- source
FROM deps AS source
COPY . /src

# --------------------------------------------------------------------------- test
# `docker build --target test` is a CI step: it fails the build when the checks fail.
FROM source AS test
RUN uv run ruff check src tests tools \
    && uv run ruff format --check src tests tools \
    && uv run python tools/check_license_headers.py
RUN uv run glyphmark verify
RUN uv run glyphmark docs check --strict
RUN uv run pytest -q
CMD ["pytest", "-q"]

# --------------------------------------------------------------------------- docs
# Built from the same source as the binary, into a path the runtime image inherits.
FROM source AS build
RUN uv run glyphmark docs build --strict --clean \
    && mkdir -p /opt/docs \
    && cp -R build/docs/. /opt/docs/

# --------------------------------------------------------------------- runtime-venv
# A second, minimal venv: runtime dependencies only (no pytest, no ruff, no mkdocs).
FROM base AS runtime-venv
ARG UV_VERSION
RUN python -m pip install "uv==${UV_VERSION}.*"
WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
RUN uv sync --frozen --no-cache --no-editable \
    && find /opt/venv -depth -name '__pycache__' -type d -exec rm -rf {} + \
    && rm -rf /root/.cache/uv

# --------------------------------------------------------------------------- runtime
FROM base AS runtime
ARG VERSION=0.0.0.dev0
ARG REVISION=unknown
ARG IMAGE_DESCRIPTION="GlyphMark - text watermarking across the ASCII/Unicode divide"
LABEL org.opencontainers.image.title="GlyphMark" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.source="https://github.com/OWNER/glyphmark" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.documentation="/docs/ inside this image, and docs/ in the repository" \
      io.artifacthub.package.readme-url="https://github.com/OWNER/glyphmark/blob/main/README.md"

# Non-root, no shell login, no home writes: the process only ever reads its venv and the docs.
RUN groupadd --gid 10001 glyphmark \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin glyphmark

COPY --from=runtime-venv /opt/venv /opt/venv
COPY --from=build /opt/docs /opt/glyphmark/docs
COPY LICENSE NOTICE /opt/glyphmark/legal/
# stdlib-only end-to-end probe, used by `docker compose run --rm smoke` and by CI after any
# image build; it is the container equivalent of the CLI's own `verify` command.
COPY tools/container_smoke.py /opt/glyphmark/tools/container_smoke.py

ENV GLYPHMARK_DOCS_DIR=/opt/glyphmark/docs \
    GLYPHMARK_PORT=8123

WORKDIR /opt/glyphmark
EXPOSE 8123

# No curl in a slim image: probe with the interpreter that is already there.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request;\nsys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8123/healthz', timeout=4).status == 200 else 1)"]

USER 10001:10001

# 0.0.0.0 *inside* the container's network namespace. Publishing the port beyond the host is a
# separate decision, and compose.yaml binds 127.0.0.1 by default for exactly that reason:
# this API can forge attribution, so it has no business on a public interface unauthenticated.
ENTRYPOINT ["/opt/venv/bin/glyphmark"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8123"]
