#!/usr/bin/env bash
# fmg-setup.sh — Clone Azgaar's Fantasy Map Generator and serve it locally via Docker.
#
# Usage:
#   bash scripts/fmg-setup.sh          # clone + start
#   bash scripts/fmg-setup.sh stop     # stop container
#   bash scripts/fmg-setup.sh status   # show running state
#
# After setup: open http://localhost:8082
# To export a map: File → Save As → .map  (saves full JSON state)
# To export GeoJSON per layer: Tools → Layers → any layer → Export → GeoJSON
#
# Env overrides:
#   FMG_PORT=8082  — host port (default 8082)

set -euo pipefail

FMG_DIR="$(cd "$(dirname "$0")/.." && pwd)/Fantasy-Map-Generator"
FMG_REPO="https://github.com/Azgaar/Fantasy-Map-Generator.git"
CONTAINER="campaign-forge-fmg"
PORT="${FMG_PORT:-8082}"

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

# Clone if not present
if [[ ! -d "$FMG_DIR" ]]; then
  echo "Cloning Azgaar/Fantasy-Map-Generator (shallow)..."
  git clone --depth 1 "$FMG_REPO" "$FMG_DIR"
else
  echo "Using existing clone at $FMG_DIR"
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
echo "Workflow:"
echo "  1. Open http://localhost:${PORT} and generate or load a map"
echo "  2. Export: File → Save As → .map  (full JSON, needed for sync)"
echo "  3. Sync to Kanka CE: python3 map_tools.py sync path/to/export.map"
echo "  4. Dry-run first: python3 map_tools.py sync path/to/export.map --dry-run"
echo ""
echo "Stop: bash scripts/fmg-setup.sh stop"
