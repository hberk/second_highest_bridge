#!/usr/bin/env bash
# Deploy the multiplayer beta to the homelab: LXC 213 "bridge", behind Caddy
# at https://bridge.ettamei.com (docs/MULTIPLAYER_PLAN.md, "Hosting the beta").
#
#   BRIDGE_HOST=192.168.169.x server/deploy.sh
#
# Builds the beta site and the server bundle here, streams them to
# /opt/bridge as `builder` (no rsync needed: a tarball over ssh), restarts
# bridge.service (builder's only sudo), and waits for /healthz. The database
# lives in /var/lib/bridge, outside what this replaces. A deploy drops every
# socket; clients reconnect and resume.
#
# Normally the container deploys itself from main (server/pull/). A manual
# deploy holds that off, so the next release doesn't replace what you're
# testing; `ssh builder@$BRIDGE_HOST rm /opt/bridge/.hold` hands it back.
set -euo pipefail

HOST="${BRIDGE_HOST:?set BRIDGE_HOST to the container address}"
KEY="${BRIDGE_KEY:-$HOME/.ssh/bridge_deploy}"
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes "builder@$HOST")
here="$(cd "$(dirname "$0")" && pwd)"

echo "== building the beta site"
(cd "$here/../frontend" && VITE_BUILD="$(git rev-parse HEAD 2>/dev/null || echo manual)" npm run build:beta)
echo "== building the server"
(cd "$here" && npm run build)

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp "$here/dist/server.js" "$here/dist/server.js.map" "$stage/"
cp -r "$here/../frontend/dist-beta" "$stage/public"
git -C "$here" rev-parse HEAD > "$stage/VERSION" 2>/dev/null || echo unknown > "$stage/VERSION"

echo "== copying to $HOST"
tar -C "$stage" -czf - . | "${SSH[@]}" 'set -e
  cd /opt/bridge
  rm -rf .incoming && mkdir .incoming
  tar -xzmf - -C .incoming
  rm -rf .previous && mkdir .previous
  for f in server.js server.js.map public VERSION; do [ -e "$f" ] && mv "$f" .previous/; done
  mv .incoming/* . && rmdir .incoming
  echo "manual deploy of $(cat VERSION) on $(date -u +%FT%TZ)" > .hold'

echo "== restarting bridge.service"
"${SSH[@]}" sudo /usr/bin/systemctl restart bridge.service

# Port 8787 takes only Caddy and Uptime Kuma, so ask from inside the container.
health='fetch("http://127.0.0.1:8787/healthz").then((r) => r.text()).then(console.log).catch(() => process.exit(1))'
for _ in $(seq 1 20); do
  if out="$("${SSH[@]}" node -e "'$health'" 2>/dev/null)" && [[ "$out" == *'"ok":true'* ]]; then
    echo "== up: $out (version $(cut -c1-12 "$stage/VERSION"))"
    echo "== auto-deploy from main is held; resume: ssh builder@$HOST rm /opt/bridge/.hold"
    exit 0
  fi
  sleep 1
done
echo "!! /healthz did not answer; see: ssh builder@$HOST journalctl -u bridge -n 50" >&2
exit 1
