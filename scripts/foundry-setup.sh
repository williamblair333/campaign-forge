#!/usr/bin/env bash
# foundry-setup.sh — Start, stop, or check Foundry VTT (felddy Docker image).
#
# Usage:
#   bash scripts/foundry-setup.sh          # start
#   bash scripts/foundry-setup.sh stop     # stop (data preserved)
#   bash scripts/foundry-setup.sh restart  # stop + start
#   bash scripts/foundry-setup.sh status   # show container state
#   bash scripts/foundry-setup.sh logs     # tail logs
#   bash scripts/foundry-setup.sh backup   # backup world data
#
# Requires: FOUNDRY_LICENSE_KEY and FOUNDRY_ADMIN_KEY in .env
# First run also requires: FOUNDRY_RELEASE_URL in .env (timed URL, expires ~1h)
#   Get it: foundryvtt.com → profile → Purchased Software Licenses → Node.js → 🔗 Timed URL

set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE_FILE="docker-compose.foundry.yml"
CONTAINER="campaign-forge-foundry"

# Read .env with grep — avoids shell-expanding special chars like $$ in values
_env_has() { grep -q "^${1}=" .env 2>/dev/null; }
_env_get() { grep "^${1}=" .env 2>/dev/null | cut -d= -f2-; }

case "${1:-start}" in
  stop)
    docker compose -f "$COMPOSE_FILE" down
    echo "Foundry VTT stopped. Data preserved in ./foundry/data/"
    exit 0
    ;;
  restart)
    docker compose -f "$COMPOSE_FILE" down
    ;;
  status)
    docker ps --filter "name=$CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    exit 0
    ;;
  logs)
    docker logs -f "$CONTAINER"
    exit 0
    ;;
  backup)
    BACKUP="foundry-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    echo "Backing up ./foundry/data/worlds/ → $BACKUP"
    tar -czf "$BACKUP" foundry/data/worlds/ 2>/dev/null || {
      echo "No worlds directory yet (nothing to back up)"
    }
    echo "Done: $BACKUP"
    exit 0
    ;;
  start|"")
    ;;
  *)
    echo "Usage: $0 [start|stop|restart|status|logs|backup]" >&2; exit 1
    ;;
esac

# Validate required env vars (grep-based — avoids shell-expanding $$ in values)
missing=()
_env_has FOUNDRY_LICENSE_KEY || missing+=("FOUNDRY_LICENSE_KEY")
_env_has FOUNDRY_ADMIN_KEY   || missing+=("FOUNDRY_ADMIN_KEY")
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Error: missing required env vars in .env: ${missing[*]}" >&2
  exit 1
fi

# Warn if timed URL is absent and no cached binary exists
CACHE_DIR="foundry/data/container_cache"
if ! _env_has FOUNDRY_RELEASE_URL && [[ ! -d "$CACHE_DIR" ]]; then
  echo "Warning: FOUNDRY_RELEASE_URL not set and no cached binary found." >&2
  echo "  Get a timed URL: foundryvtt.com → Purchased Software Licenses → Node.js → 🔗 Timed URL" >&2
  echo "  Add to .env: FOUNDRY_RELEASE_URL=<url>" >&2
  exit 1
fi

# Start
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "Foundry VTT starting → http://localhost:30000"
echo "  First boot downloads the binary (~200 MB) — takes 1-2 minutes."
echo "  Watch: bash scripts/foundry-setup.sh logs"
echo ""
echo "  Admin panel: http://localhost:30000  (password = FOUNDRY_ADMIN_KEY from .env)"
echo ""
echo "  Backup worlds: bash scripts/foundry-setup.sh backup"
echo "  Stop:          bash scripts/foundry-setup.sh stop"
