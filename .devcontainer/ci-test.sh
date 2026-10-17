#!/bin/bash
# Run inside the dev container by .github/workflows/devcontainer-ci.yml (and
# runnable by hand: `bash .devcontainer/ci-test.sh`). It checks that the image
# is the environment it claims to be, then runs the backend test suite.
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE"

echo "==> Environment parity"
test "$(id -u)" != "0" || { echo "ERROR: running as root"; exit 1; }
echo "user: $(id -un) (uid $(id -u))"
python --version | grep -q '^Python 3\.12\.' || { echo "ERROR: expected Python 3.12"; exit 1; }
node --version | grep -q '^v22\.' || { echo "ERROR: expected Node 22"; exit 1; }
pnpm --version | grep -q '^9\.' || { echo "ERROR: expected pnpm 9"; exit 1; }
claude --version
gh --version | head -1
test "${DISABLE_AUTOUPDATER:-}" = "1" || { echo "ERROR: DISABLE_AUTOUPDATER not set"; exit 1; }
test -f /etc/claude-code/managed-settings.json || { echo "ERROR: managed settings missing"; exit 1; }
python -c "import torch; assert not torch.cuda.is_available(); print('torch', torch.__version__)"

echo "==> Database (migrations ran in postStartCommand)"
(cd backend && alembic current)

if [ "${ARBITER_DEVCONTAINER_FIREWALL:-0}" = "1" ]; then
  echo "==> Egress firewall"
  if curl --connect-timeout 5 -fsS https://example.com >/dev/null 2>&1; then
    echo "ERROR: example.com reachable with the firewall on"
    exit 1
  fi
  curl --connect-timeout 5 -fsS https://api.github.com/zen >/dev/null
  if sudo -n true 2>/dev/null; then
    echo "ERROR: blanket sudo still available after lock"
    exit 1
  fi
  echo "firewall on: example.com blocked, api.github.com reachable, sudo locked"
fi

echo "==> Backend tests"
# Pre-existing failures on develop are deselected so this job only fails on new
# ones. See .devcontainer/known-failing-tests.txt.
DESELECT=()
while read -r id; do
  case "$id" in ''|'#'*) continue ;; esac
  DESELECT+=("--deselect=$id")
done < .devcontainer/known-failing-tests.txt
echo "deselecting ${#DESELECT[@]} known-failing tests"
cd backend
python -m pytest -q -p no:cacheprovider "${DESELECT[@]}"
