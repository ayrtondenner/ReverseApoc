# syntax=docker/dockerfile:1.7
#
# ReverseApoc build/dev image.
#
# WHAT THIS IMAGE DOES NOT CONTAIN (on purpose):
#   - No Watcom C/C++ 10.x compiler (wcc386 etc.). It is proprietary, the user
#     supplies it and it is bind-mounted at /work/watcom at runtime.
#   - No game files (X-COM Apocalypse). They are bind-mounted at /work/orig.
#   - No project source. The repo is bind-mounted at /work; the image only
#     pre-installs tools.
#   - Open Watcom v2's compiler is installed on disk but NOT put on PATH and
#     NOT used for matching (its codegen differs from Watcom 10.x). Only its
#     binary tools wdis, wlink and wlib are exposed.
#
# Platform: x86-64 only (wibo, objdiff-cli and Open Watcom are x86-64 Linux
# binaries).

# ---------------------------------------------------------------------------
# Pinned versions. Bump here only.
# ---------------------------------------------------------------------------
# Base image pinned by digest (ubuntu:24.04 as of 2026-10-19). The apt package
# versions below are the 24.04 archive versions at the same date; if the build
# fails with "version not found", Ubuntu has published a security update:
# refresh the versions with `apt-cache policy <pkg>` in a fresh ubuntu:24.04.
ARG UBUNTU_IMAGE=ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac

# Python interpreter that uv installs (the project pins 3.14).
ARG PYTHON_VERSION=3.14.5

# objdiff-cli, the Linux x86-64 release binary from GitHub.
ARG OBJDIFF_VERSION=v3.8.2
ARG OBJDIFF_SHA256=e5445089a6f707e30cb5e02992451b604619cedfd2660ee2373a86bfefd9e718

# Open Watcom v2 dated snapshot (a named release tag with a stable asset URL;
# "Current-build" is NOT used because it is rewritten daily).
ARG OW_TAG=2026-10-01-Build
ARG OW_SHA256=e6aa1b1e40ac8bbf97658d2c70fff8a4242d6ca4a1c60806f2baa5317083d4fe

# ---------------------------------------------------------------------------
# Stage: pinned third-party tool sources (copied into the final image).
# ---------------------------------------------------------------------------
# uv, version matching the host's uv.
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
# wibo 1.2.0: runs Win32 console binaries (the Watcom compiler) on Linux.
# Same pattern as decomp.me's cromper Dockerfile.
FROM ghcr.io/decompals/wibo:1.2.0 AS wibo

# ---------------------------------------------------------------------------
# Stage: download and verify objdiff-cli and Open Watcom v2.
# ---------------------------------------------------------------------------
FROM ${UBUNTU_IMAGE} AS fetch
ARG OBJDIFF_VERSION
ARG OBJDIFF_SHA256
ARG OW_TAG
ARG OW_SHA256
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates=20260601~24.04.1 \
      curl=8.5.0-2ubuntu10.16 \
      xz-utils=5.6.1+really5.4.5-1ubuntu0.3 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /dl
# objdiff-cli: single static-ish binary; verify sha256 before installing.
RUN curl -fsSL -o objdiff-cli \
      "https://github.com/encounter/objdiff/releases/download/${OBJDIFF_VERSION}/objdiff-cli-linux-x86_64" \
 && echo "${OBJDIFF_SHA256}  objdiff-cli" | sha256sum -c - \
 && install -m 0755 objdiff-cli /usr/local/bin/objdiff-cli
# Open Watcom v2: only the Linux x64 host binaries are kept (binl64/).
RUN curl -fsSL -o ow-snapshot.tar.xz \
      "https://github.com/open-watcom/open-watcom-v2/releases/download/${OW_TAG}/ow-snapshot.tar.xz" \
 && echo "${OW_SHA256}  ow-snapshot.tar.xz" | sha256sum -c - \
 && mkdir -p /opt/watcom-v2 \
 && tar -xJf ow-snapshot.tar.xz -C /opt/watcom-v2 ./binl64 \
 && rm ow-snapshot.tar.xz

# ---------------------------------------------------------------------------
# Final image.
# ---------------------------------------------------------------------------
FROM ${UBUNTU_IMAGE} AS final
ARG PYTHON_VERSION

ENV DEBIAN_FRONTEND=noninteractive

# Build and analysis tools from the Ubuntu 24.04 archive.
#   ninja-build  build.ninja executor
#   binutils     GNU as / ld / objdump
#   clang-format, clangd  formatting and language server for the C sources
#   git, curl, ca-certificates, xz-utils, unzip  general plumbing
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ninja-build=1.11.1-2 \
      binutils=2.42-4ubuntu2.10 \
      clang-format=1:18.0-59~exp2 \
      clangd=1:18.0-59~exp2 \
      git=1:2.43.0-1ubuntu7.4 \
      curl=8.5.0-2ubuntu10.16 \
      ca-certificates=20260601~24.04.1 \
      xz-utils=5.6.1+really5.4.5-1ubuntu0.3 \
      unzip=6.0-28ubuntu4.1 \
 && rm -rf /var/lib/apt/lists/*

# uv and wibo from their official images.
COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=wibo /usr/local/bin/wibo /usr/local/bin/wibo

# objdiff-cli (verified in the fetch stage).
COPY --from=fetch /usr/local/bin/objdiff-cli /usr/local/bin/objdiff-cli

# Open Watcom v2: expose ONLY the binary tools. The OW compiler (wcc386) is
# deliberately not on PATH and is not used for matching.
COPY --from=fetch /opt/watcom-v2 /opt/watcom-v2
RUN ln -s /opt/watcom-v2/binl64/wdis  /usr/local/bin/wdis \
 && ln -s /opt/watcom-v2/binl64/wlink /usr/local/bin/wlink \
 && ln -s /opt/watcom-v2/binl64/wlib  /usr/local/bin/wlib

# Non-root user `dev` (uid 1000). Ubuntu 24.04 ships an `ubuntu` user with
# uid 1000; remove it first so `dev` can take that uid (matches the usual
# WSL2/Linux host user, so files written to the bind mount are owned by you).
RUN userdel -r ubuntu \
 && useradd --uid 1000 --create-home --shell /bin/bash dev \
 && mkdir -p /work /opt/venv /opt/uv-python /home/dev/.cache/uv \
 && chown -R dev:dev /work /opt/venv /opt/uv-python /home/dev/.cache

# uv configuration:
#   UV_PROJECT_ENVIRONMENT  venv lives outside the bind mount, so a Linux venv
#                           never lands in the Windows checkout (/work/.venv).
#   UV_LINK_MODE=copy       cache and venv are on different filesystems
#                           (named volumes), hardlinks would only warn.
#   UV_PYTHON_INSTALL_DIR   interpreter baked into the image, outside /work.
#   UV_PYTHON_DOWNLOADS=manual  only explicit `uv python install` downloads, none
#                           silently during uv sync or run.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON_DOWNLOADS=manual \
    UV_CACHE_DIR=/home/dev/.cache/uv \
    PATH="/opt/venv/bin:${PATH}"

USER dev
RUN uv python install "${PYTHON_VERSION}"

WORKDIR /work
# No ENTRYPOINT; default command is an interactive shell.
CMD ["bash"]
