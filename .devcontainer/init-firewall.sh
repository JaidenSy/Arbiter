#!/bin/bash
# Default-deny egress firewall for the Arbiter dev container.
#
# Modeled on Anthropic's reference script:
#   https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh
#
# OPT-IN. post-start.sh only runs this when ARBITER_DEVCONTAINER_FIREWALL=1.
# Needs the NET_ADMIN and NET_RAW capabilities (granted in docker-compose.yml)
# and root (the image lets the `dev` user sudo this one script).
#
# What it allows out:
#   - DNS, SSH, loopback, and the container's own Docker networks (Postgres,
#     Redis and the other compose services)
#   - GitHub (web/api/git ranges from https://api.github.com/meta)
#   - npm, PyPI (+ the CPU torch index), the Anthropic API and sign-in hosts
#   - extra domains given as arguments (post-start.sh passes
#     ARBITER_FIREWALL_EXTRA_DOMAINS), e.g. huggingface.co for the cache model
# Everything else is rejected, IPv4 and IPv6.
#
# Differences from the reference script:
#   - PyPI and download.pytorch.org are allowed (backend installs), the
#     Statsig/Sentry hosts are not (current Claude Code does not need them).
#   - The Docker networks the container is attached to are allowed by their real
#     subnets instead of guessing a /24 around the default gateway.
#   - IPv6 egress is also default-deny (the reference only touches IPv4).
#   - "Lock" step: it removes the dev user's blanket sudo, so a process inside
#     the container (an agent included) cannot simply flush the rules again.
#     Rebuild the container to get sudo back.
#
# Known limitation (shared with the reference): hosts are resolved to IPs once,
# at start. CDN-fronted registries (npm, PyPI) rotate IPs, so a long-running
# container can start getting rejections. Re-run `sudo init-firewall.sh`.
set -euo pipefail
IFS=$'\n\t'

ALLOWED_DOMAINS=(
  # Anthropic API + Claude Code sign-in (https://code.claude.com/docs/en/network-config)
  "api.anthropic.com"
  "claude.ai"
  "platform.claude.com"
  # npm (pnpm installs, Claude Code itself)
  "registry.npmjs.org"
  # PyPI + the CPU-only torch index used by post-create.sh
  "pypi.org"
  "files.pythonhosted.org"
  "download.pytorch.org"
  # VS Code server + extensions (same as the reference script)
  "marketplace.visualstudio.com"
  "vscode.blob.core.windows.net"
  "update.code.visualstudio.com"
)

# Extra domains (ARBITER_FIREWALL_EXTRA_DOMAINS, passed as arguments by
# post-start.sh) are only accepted while the container is still unlocked, and
# are then persisted root-owned. Once locked, the dev user can only re-run this
# script with no arguments (see the sudoers entry), which re-applies the same
# persisted allowlist, so it cannot be used to widen egress.
EXTRA_FILE=/etc/arbiter-firewall-extra-domains
if [ "$#" -gt 0 ]; then
  if [ ! -e /etc/sudoers.d/dev-admin ]; then
    echo "ERROR: container is locked; extra domains can no longer be added (rebuild)"
    exit 1
  fi
  for d in "$@"; do
    if [[ ! "$d" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]]; then
      echo "ERROR: invalid domain: $d"
      exit 1
    fi
  done
  printf '%s\n' "$@" > "$EXTRA_FILE"
  chmod 0644 "$EXTRA_FILE"
fi
if [ -f "$EXTRA_FILE" ]; then
  while read -r d; do
    if [ -n "$d" ]; then
      ALLOWED_DOMAINS+=("$d")
    fi
  done < "$EXTRA_FILE"
fi

# 1. Keep Docker's embedded DNS (127.0.0.11) working: save its NAT rules first.
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

if [ -n "$DOCKER_DNS_RULES" ]; then
  echo "Restoring Docker DNS rules..."
  iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
  iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
  echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
else
  echo "No Docker DNS rules to restore"
fi

# 2. DNS, SSH, loopback.
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
iptables -A INPUT -p tcp --sport 53 -m state --state ESTABLISHED -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# 3. Build the allowlist.
ipset create allowed-domains hash:net

echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -fsS --connect-timeout 10 https://api.github.com/meta)
if ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null; then
  echo "ERROR: GitHub meta response missing required fields"
  exit 1
fi
while read -r cidr; do
  if [[ ! "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
    echo "ERROR: Invalid CIDR range from GitHub meta: $cidr"
    exit 1
  fi
  ipset add -exist allowed-domains "$cidr"
done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | grep -v ':' | aggregate -q)
echo "Added GitHub ranges"

for domain in "${ALLOWED_DOMAINS[@]}"; do
  echo "Resolving $domain..."
  ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
  if [ -z "$ips" ]; then
    echo "ERROR: Failed to resolve $domain"
    exit 1
  fi
  while read -r ip; do
    if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
      echo "ERROR: Invalid IP from DNS for $domain: $ip"
      exit 1
    fi
    ipset add -exist allowed-domains "$ip"
  done <<< "$ips"
done

# 4. The container's own networks: compose services (postgres, redis) and the
#    Docker host gateway (VS Code port forwarding, host-side tooling).
LOCAL_NETS=$(ip -o -4 addr show scope global | awk '{print $4}')
if [ -z "$LOCAL_NETS" ]; then
  echo "ERROR: Failed to detect container networks"
  exit 1
fi
while read -r net; do
  echo "Allowing local network $net"
  iptables -A INPUT -s "$net" -j ACCEPT
  iptables -A OUTPUT -d "$net" -j ACCEPT
done <<< "$LOCAL_NETS"

# 5. Default deny.
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

# IPv6: loopback only. Everything on the allowlist is reachable over IPv4.
if command -v ip6tables >/dev/null 2>&1 && ip6tables -L >/dev/null 2>&1; then
  ip6tables -F
  ip6tables -X
  ip6tables -A INPUT -i lo -j ACCEPT
  ip6tables -A OUTPUT -o lo -j ACCEPT
  ip6tables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
  ip6tables -P INPUT DROP
  ip6tables -P FORWARD DROP
  ip6tables -P OUTPUT DROP
  ip6tables -A OUTPUT -j REJECT 2>/dev/null || true
fi

echo "Firewall configuration complete"

# 6. Verify.
if curl --connect-timeout 5 -s https://example.com >/dev/null 2>&1; then
  echo "ERROR: Firewall verification failed - was able to reach https://example.com"
  exit 1
fi
echo "Verified: https://example.com is blocked"
if ! curl --connect-timeout 5 -s https://api.github.com/zen >/dev/null 2>&1; then
  echo "ERROR: Firewall verification failed - unable to reach https://api.github.com"
  exit 1
fi
echo "Verified: https://api.github.com is reachable"

# 7. Lock: drop the blanket sudo so the rules cannot be flushed from inside.
#    The narrow sudoers entry for this script stays, so re-running it (to refresh
#    rotated CDN IPs) still works and still ends in the same allowlist.
rm -f /etc/sudoers.d/dev-admin
echo "Locked: blanket sudo removed for this container (rebuild to restore)"
