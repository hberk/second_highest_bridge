#!/usr/bin/env bash
# Pull the game log from the homelab (docs/MULTIPLAYER_PLAN.md, "Game logs")
# into logs/<when>/ here (gitignored):
#   export.json  every table with activity in the window: boards, timed
#                actions, the table log (joins, drops, refusals, reports,
#                errors) and summary stats
#   boards.lin   the finished boards, for History's "Import LIN"
#
#   BRIDGE_HOST=192.168.169.118 server/fetch-logs.sh [--since 7d|36h|2026-10-28] [--table <id>]
#
# The export runs as `bridge` (the database is its own) through one sudo rule
# for `builder`, and opens the database read-only beside the live server.
set -euo pipefail

HOST="${BRIDGE_HOST:?set BRIDGE_HOST to the container address}"
KEY="${BRIDGE_KEY:-$HOME/.ssh/bridge_deploy}"
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes "builder@$HOST")
here="$(cd "$(dirname "$0")" && pwd)"

# Only these flags, so nothing else reaches the remote shell.
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --since|--table)
      [[ "${2:-}" =~ ^[A-Za-z0-9_:.-]+$ ]] || { echo "bad value for $1: ${2:-}" >&2; exit 2; }
      args+=("$1" "$2"); shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

export_cmd="sudo -u bridge /usr/bin/node --disable-warning=ExperimentalWarning /opt/bridge/server.js export --db /var/lib/bridge/bridge.db ${args[*]:-}"
out="$here/../logs/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$out"
"${SSH[@]}" "$export_cmd" > "$out/export.json"
"${SSH[@]}" "$export_cmd --lin" > "$out/boards.lin"

node -e '
const o = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
const s = o.stats;
console.log(`since ${o.since}: ${s.tables} tables, ${s.boardsFinished} boards finished, ${s.people} people`);
console.log(`robot think ms: median ${s.robotMs.median}, p95 ${s.robotMs.p95}, max ${s.robotMs.max} (n=${s.robotMs.n})`);
console.log(`reports ${s.reports}, page errors ${s.clientErrors}, robot errors ${s.robotErrors}, refused ${JSON.stringify(s.refused)}`);
for (const t of o.tables) for (const l of t.log) if (l.kind === "report") console.log(`  report ${t.id} board ${l.board} ${l.detail.name ?? ""}: ${l.detail.note}`);
' "$out/export.json"
echo "== $out"
