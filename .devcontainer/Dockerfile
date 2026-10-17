# syntax=docker/dockerfile:1
#
# Arbiter dev container image. One image for local editors, Codespaces, CI
# (.github/workflows/devcontainer-ci.yml) and coding agents, so all of them get
# the same toolchain by construction. See docs/devcontainer.md.
#
# Toolchain pins (keep in sync with the app images):
#   Python 3.12        backend/Dockerfile uses python:3.12-slim
#   Node 22 + pnpm 9   frontend/Dockerfile uses node:22-alpine + pnpm@9.15.9
#   Claude Code        pinned npm install; the auto-updater is disabled below

# Node 22 comes from the official image (same major as frontend/Dockerfile).
# It is copied in rather than installed through a Feature because Claude Code
# has to be installed during this build, and Features are applied after it.
FROM node:22-bookworm-slim AS node

FROM python:3.12-slim-bookworm

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
ARG PNPM_VERSION=9.15.9
ARG UV_VERSION=0.13.1
ARG CLAUDE_CODE_VERSION=2.1.300

# System packages:
#   build-essential, curl                    same as backend/Dockerfile
#   git, sudo, procps, less, openssh-client  day-to-day dev + VS Code server
#   postgresql-client                        psql against the compose Postgres
#   iptables, ipset, iproute2, dnsutils,
#   aggregate, jq                            init-firewall.sh (opt-in egress lockdown)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      git \
      sudo \
      procps \
      less \
      openssh-client \
      postgresql-client \
      iptables \
      ipset \
      iproute2 \
      dnsutils \
      aggregate \
      jq \
    && rm -rf /var/lib/apt/lists/*

# ── Node 22, pnpm 9, Claude Code (pinned) ─────────────────────────────────────
# pnpm comes from corepack, as in frontend/Dockerfile. Claude Code is the one
# global npm install: it is the pinning method Anthropic documents for
# containers (https://code.claude.com/docs/en/devcontainer).
ENV COREPACK_HOME=/usr/local/share/corepack \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && corepack enable \
    && corepack prepare "pnpm@${PNPM_VERSION}" --activate \
    && chmod -R a+rX "${COREPACK_HOME}" \
    && npm install -g --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force \
    && node --version && pnpm --version && claude --version

# ── uv (Python installer used by post-create.sh) ──────────────────────────────
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

# ── Claude Code managed policy ────────────────────────────────────────────────
# Highest-precedence settings scope on Linux. Root-owned, so the non-root user
# (and an agent running as that user) cannot edit it. See managed-settings.json
# and docs/devcontainer.md for what it enforces and why.
COPY managed-settings.json /etc/claude-code/managed-settings.json
RUN chmod 0644 /etc/claude-code/managed-settings.json

# ── Opt-in egress firewall ────────────────────────────────────────────────────
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod 0755 /usr/local/bin/init-firewall.sh

# ── Non-root user ─────────────────────────────────────────────────────────────
# Two sudoers entries:
#   arbiter-firewall  the user may run init-firewall.sh as root (iptables needs
#                     it), with no arguments only. Stays in place.
#   dev-admin         general passwordless sudo for apt and friends. The
#                     firewall script deletes this file when it locks the
#                     container down, so an agent cannot `sudo iptables -F`.
# The mount points are pre-created so named volumes inherit the user's ownership.
RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}" \
    && echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh \"\"" > /etc/sudoers.d/arbiter-firewall \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/dev-admin \
    && chmod 0440 /etc/sudoers.d/arbiter-firewall /etc/sudoers.d/dev-admin \
    && mkdir -p "/home/${USERNAME}/.claude" /workspaces/arbiter \
    && chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}" /workspaces

# Claude Code: keep config (auth, sessions) on the persisted volume, and never
# self-update away from the pinned version. The backend virtualenv is created by
# post-create.sh. The UV_* settings make uv pull CPU-only torch for
# sentence-transformers (no CUDA wheels, several GB smaller).
ENV DEVCONTAINER=true \
    CLAUDE_CONFIG_DIR=/home/${USERNAME}/.claude \
    DISABLE_AUTOUPDATER=1 \
    VIRTUAL_ENV=/home/${USERNAME}/.venv \
    PATH=/home/${USERNAME}/.venv/bin:${PATH} \
    UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu \
    UV_INDEX_STRATEGY=unsafe-best-match \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

USER ${USERNAME}
WORKDIR /workspaces/arbiter
