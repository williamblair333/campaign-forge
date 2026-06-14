#!/usr/bin/env bash
# fmg-setup.sh — Clone Azgaar's Fantasy Map Generator and serve it locally via Docker.
#
# Usage:
#   bash scripts/fmg-setup.sh          # clone + start
#   bash scripts/fmg-setup.sh stop     # stop container
#   bash scripts/fmg-setup.sh status   # show running state
#
# After setup: open http://localhost:8082
#
# To sync settlements/factions to Kanka, use the headless generator — it reads
# FMG's in-memory burgs/states and writes the JSON map_tools.py parses:
#   python scripts/fmg-generate.py --seed 1234 --out maps/world.json
#   python3 map_tools.py sync maps/world.json --dry-run
# NOTE: FMG's File → Save As → .map is a custom pipe-delimited format, NOT JSON —
# map_tools.py can't parse it directly; use the generator's default json output.
#
# Env overrides:
#   FMG_PORT=8082  — host port (default 8082)

set -euo pipefail

FMG_DIR="$(cd "$(dirname "$0")/.." && pwd)/Fantasy-Map-Generator"
FMG_REPO="https://github.com/Azgaar/Fantasy-Map-Generator.git"
CONTAINER="campaign-forge-fmg"
PORT="${FMG_PORT:-8082}"

# Pin to the last static-HTML release. v1.100+ is a Vite/TypeScript rewrite
# (engines: node >=24) whose index.html lives under src/ — it cannot be served
# as static files (nginx returns 403) and its .map format differs from what
# map_tools.py parses. v1.99 keeps the classic root index.html + modules/, and
# exposes the global prepareMapData() that scripts/fmg-generate.py calls.
FMG_TAG="${FMG_TAG:-v1.99}"

case "${1:-start}" in
  stop)
    docker rm -f "$CONTAINER" 2>/dev/null && echo "Stopped $CONTAINER" || echo "Not running"
    exit 0
    ;;
  status)
    docker ps --filter "name=$CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    exit 0
    ;;
  start|"")
    ;;
  *)
    echo "Usage: $0 [start|stop|status]" >&2; exit 1
    ;;
esac

# Clone (or re-pin an existing clone) to the static FMG tag. An existing checkout
# may be on a newer Vite/TS tag that won't serve as static — force it back to
# FMG_TAG rather than silently serving a broken tree.
if [[ ! -d "$FMG_DIR/.git" ]]; then
  echo "Cloning Azgaar/Fantasy-Map-Generator @ $FMG_TAG (shallow)..."
  git clone --depth 1 --branch "$FMG_TAG" "$FMG_REPO" "$FMG_DIR"
else
  current="$(git -C "$FMG_DIR" describe --tags --exact-match 2>/dev/null || echo "?")"
  if [[ "$current" != "$FMG_TAG" ]]; then
    echo "Re-pinning existing clone ($current) → $FMG_TAG..."
    git -C "$FMG_DIR" fetch --tags --depth 1 origin "$FMG_TAG" 2>/dev/null \
      || git -C "$FMG_DIR" fetch --tags origin
    git -C "$FMG_DIR" checkout -q -f "$FMG_TAG"
  else
    echo "Existing clone already at $FMG_TAG."
  fi
fi

# Guard: the static serve needs index.html at the repo root.
if [[ ! -f "$FMG_DIR/index.html" ]]; then
  echo "Error: $FMG_DIR has no root index.html — not a static FMG checkout." >&2
  exit 1
fi

# Stop any running instance
docker rm -f "$CONTAINER" 2>/dev/null || true

# Bind to 127.0.0.1 only — keeps FMG off the LAN
docker run -d \
  --name "$CONTAINER" \
  -p "127.0.0.1:${PORT}:80" \
  -v "${FMG_DIR}:/usr/share/nginx/html:ro" \
  nginx:alpine

echo ""
echo "Fantasy Map Generator → http://localhost:${PORT}"
echo ""
echo "Workflow (manual):"
echo "  1. Open http://localhost:${PORT} and generate or load a map"
echo "  2. Export: File → Save As → .map  (full JSON, needed for sync)"
echo "  3. Sync to Kanka CE: python3 map_tools.py sync path/to/export.map"
echo "  4. Dry-run first: python3 map_tools.py sync path/to/export.map --dry-run"
echo ""
echo "Workflow (headless, no browser):"
echo "  python scripts/fmg-generate.py --seed 1234 --out maps/world.map   # generate"
echo "  python3 map_tools.py sync maps/world.map --dry-run                # then sync"
echo ""
echo "Stop: bash scripts/fmg-setup.sh stop"
