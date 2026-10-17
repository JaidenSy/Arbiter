# Dev Container

`.devcontainer/` defines one environment that is used by local editors, GitHub
Codespaces, CI and coding agents. Same image, same lockfile, same Postgres and
Redis, same lifecycle scripts. "Works on my machine" and "works in CI" mean the
same thing.

| Piece | What it gives you |
|---|---|
| `.devcontainer/Dockerfile` | Python 3.12, Node 22, pnpm 9.15.9, uv, Claude Code (pinned npm install, auto-updater off), non-root `dev` user |
| `.devcontainer/docker-compose.yml` | `workspace` + `postgres` (pgvector pg16) + `redis` 7. The two services `extends` the root `docker-compose.yml`, so the images can't drift |
| `.devcontainer/devcontainer.json` | Compose wiring, the `github-cli` Feature (from OCI), declarative `secrets`, lifecycle commands, VS Code extensions |
| `.devcontainer/devcontainer-lock.json` | Feature digests (`resolved` + `integrity`). CI fails if it goes stale |
| `.devcontainer/post-create.sh` | Backend deps into `/home/dev/.venv` (CPU-only torch) + `pnpm install --frozen-lockfile` |
| `.devcontainer/post-start.sh` | `alembic upgrade head`, then the opt-in egress firewall |
| `.devcontainer/init-firewall.sh` | Default-deny egress allowlist (GitHub, npm, PyPI, Anthropic) |
| `.devcontainer/managed-settings.json` | Claude Code managed policy, baked to `/etc/claude-code/managed-settings.json` |
| `.mcp.json.example` | Project-scoped MCP config pointing Claude Code at the local Arbiter gateway |

## Local: VS Code (or Cursor, JetBrains)

1. Install Docker and the **Dev Containers** extension.
2. Open the repo and run **Dev Containers: Reopen in Container**.
3. First build takes a few minutes (Python deps include torch). Then:

```bash
cd backend && uvicorn app.main:app --reload --host 0.0.0.0   # API on :8000
cd frontend && pnpm dev --host                                # UI on :5173
cd backend && python -m pytest                                # tests
```

Ports 8000 and 5173 are forwarded. Postgres and Redis are reachable from the
container as `postgres:5432` and `redis:6379`. `DATABASE_URL` and `REDIS_URL`
are already set.

**Secrets.** On first create, `post-create.sh` writes `backend/.env` (gitignored)
with random `APP_SECRET_KEY`, `VAULT_ENCRYPTION_KEY` and `JWT_SECRET_KEY` if
the file doesn't exist. Real environment variables always override it. If you
already have a `backend/.env` from host-side development, it is left alone; it
must contain a valid 64-hex `VAULT_ENCRYPTION_KEY`.

The dev stack is its own compose project with its own volumes. It never touches
the data of a self-host `docker compose up` from the repo root.

## GitHub Codespaces

Create a codespace on the repo. Codespaces reads the `secrets` block in
`devcontainer.json` and offers to set `ANTHROPIC_API_KEY`,
`VAULT_ENCRYPTION_KEY`, `APP_SECRET_KEY` and `JWT_SECRET_KEY` as Codespaces
secrets. All are optional for development. `hostRequirements` asks for a
4-core / 8 GB machine.

## CI

`.github/workflows/devcontainer-ci.yml` uses
[`devcontainers/ci`](https://github.com/devcontainers/ci) (pinned by SHA,
`v0.3.1900000450`) with `@devcontainers/cli` 0.89.0. It:

1. builds this exact image (Features resolved through `devcontainer-lock.json`),
2. starts it with Postgres and Redis and runs the lifecycle commands, so
   dependency install and migrations are tested on every run,
3. turns the egress firewall **on** (`ARBITER_DEVCONTAINER_FIREWALL=1`), so CI
   runs the same locked-down configuration an unattended agent would,
4. runs `.devcontainer/ci-test.sh` inside the container: toolchain and policy
   checks (non-root, Python 3.12, Node 22, pnpm 9, CPU torch, managed settings,
   firewall blocks `example.com` and sudo is gone), then the backend tests,
5. fails if the build had to rewrite `devcontainer-lock.json`.

**Pre-existing test failures.** `develop` has 34 failing backend tests. They are
listed in `.devcontainer/known-failing-tests.txt` and deselected, so this job
fails on any *new* failure instead of being permanently red or `|| true`.
Remove lines from that file as the backend-CI work fixes them.

To reproduce CI locally:

```bash
npm install -g @devcontainers/cli@0.89.0
ARBITER_DEVCONTAINER_FIREWALL=1 devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . bash .devcontainer/ci-test.sh
```

## Run an agent inside it

Claude Code is installed in the image at a pinned version
(`CLAUDE_CODE_VERSION` in the Dockerfile) with `DISABLE_AUTOUPDATER=1`, so every
container runs the same CLI. Its state lives on the `claude-config` volume
(`CLAUDE_CONFIG_DIR=/home/dev/.claude`), so sign-in survives rebuilds.

```bash
claude                 # interactive; sign in once, or export ANTHROPIC_API_KEY
claude -p "run the backend tests and summarize failures" --permission-mode auto
```

**Point it at the local gateway.** Copy the example and give it an agent key
from your local Arbiter (Agents page):

```bash
cp .mcp.json.example .mcp.json
export ARBITER_AGENT_KEY=nxai_...     # ARBITER_MCP_URL defaults to http://localhost:8000/mcp
```

Claude Code then reaches Arbiter's MCP tools through the full gateway pipeline
(RBAC, vault injection, cache, audit). `.mcp.json` is kept as an example rather
than committed because the key variable has no default, and Claude Code
fails to parse an `.mcp.json` whose required variables are unset and have no default.

### Lock egress down (recommended for unattended agents)

Set the flag on the host before the container starts (or rebuild):

```bash
export ARBITER_DEVCONTAINER_FIREWALL=1
export ARBITER_FIREWALL_EXTRA_DOMAINS="huggingface.co cdn-lfs.hf.co"   # optional
```

`post-start.sh` then runs `init-firewall.sh`, modeled on
[Anthropic's reference script](https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh):

- Outbound traffic is rejected except DNS, SSH, the compose network, GitHub
  (ranges from `api.github.com/meta`), npm, PyPI + the CPU torch index,
  `api.anthropic.com` / `claude.ai` / `platform.claude.com`, and the VS Code
  marketplace. IPv6 egress is also blocked.
- It then **locks** the container: the `dev` user's blanket sudo is removed, so
  nothing inside (an agent included) can flush the rules. `dev` keeps one sudo
  rule: re-running `init-firewall.sh` with no arguments, which re-applies the
  same allowlist (useful when CDN IPs rotate). Rebuild to undo.
- It needs `NET_ADMIN` and `NET_RAW`. They are granted to the workspace
  container in `docker-compose.yml` and only affect the container's own
  network namespace.
- Hosts are resolved to IPs at start, like the reference. The semantic cache's
  sentence-transformers model downloads from Hugging Face, which is not on the
  default list. Add it with `ARBITER_FIREWALL_EXTRA_DOMAINS`.

### Managed policy and `--dangerously-skip-permissions`

`managed-settings.json` is installed root-owned at
`/etc/claude-code/managed-settings.json`, the highest-precedence settings scope
on Linux. It:

- **disables `bypassPermissions` mode** (`--dangerously-skip-permissions`),
- denies reading `.env` files (except `.env.example`), Claude Code's
  credentials file and `~/.ssh`,
- denies force pushes and direct pushes to `main` / `develop`.

Deny rules apply in every permission mode. Bash deny rules are guardrails, not
a security boundary (they don't match every spelling of a command). GitHub
branch protection is what actually protects `main` and `develop`.

Why bypass mode stays off even inside the container: the
[Claude Code docs](https://code.claude.com/docs/en/devcontainer) note that a
bypassed session can exfiltrate anything the container can reach, including the
credentials in `~/.claude`, and recommend pairing it with egress restrictions.
The firewall is opt-in, so the image can't assume it is on. For unattended
runs, use **auto mode** (a classifier reviews each action) or `claude -p` with
an explicit `--allowedTools` list. If a team decides bypass mode is acceptable
in firewalled containers, delete `disableBypassPermissionsMode` from
`managed-settings.json` in a reviewed PR.

This file is only as strong as the repo's review process: anyone with write
access can change it. For policy that must not be bypassable, use
[server-managed settings](https://code.claude.com/docs/en/server-managed-settings).

## Updating pins

| Pin | Where |
|---|---|
| Claude Code, pnpm, uv | `ARG`s at the top of `.devcontainer/Dockerfile` |
| Python / Node base images | `FROM` lines in `.devcontainer/Dockerfile` (keep in step with `backend/Dockerfile` and `frontend/Dockerfile`) |
| Features | `devcontainer.json`, then `devcontainer upgrade --workspace-folder .` to refresh `devcontainer-lock.json` |
| CI actions / CLI | SHAs and `@devcontainers/cli@x.y.z` in `.github/workflows/devcontainer-ci.yml` |
