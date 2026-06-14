#!/usr/bin/env bash
# Download selective 5etools JSON data from the mirror (no full clone).
# Re-runnable: fetches fresh data to a staging dir before replacing old copies.
# All progress output goes to stderr; stdout is clean for callers.
set -euo pipefail

if ! command -v git &>/dev/null; then
    echo "Error: 'git' not found in PATH. Install git before running." >&2
    exit 1
fi

REPO="https://github.com/5etools-mirror-3/5etools-mirror-3.github.io.git"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../data/dnd5e"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

DIRS=(bestiary spells items backgrounds races classes)

echo "Fetching 5etools data → $DEST ..." >&2

git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/5etools" >&2
cd "$TMP/5etools"
git sparse-checkout set "${DIRS[@]}" >&2

# Validate all expected directories are present before touching $DEST
MISSING=()
for dir in "${DIRS[@]}"; do
    [ -d "$dir" ] || MISSING+=("$dir")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "Error: mirror missing expected directories: ${MISSING[*]}" >&2
    echo "The upstream structure may have changed. Check the mirror and update DIRS in this script." >&2
    exit 1
fi

# Stage copies first (no partial state if interrupted), then swap into $DEST
mkdir -p "$DEST"
for dir in "${DIRS[@]}"; do
    cp -r "$dir" "$TMP/staged-$dir"
done
for dir in "${DIRS[@]}"; do
    rm -rf "$DEST/$dir"
    mv "$TMP/staged-$dir" "$DEST/$dir"
    echo "  copied $dir" >&2
done

COUNT=$(find "$DEST" -name '*.json' | wc -l | tr -d ' ')
if [ "$COUNT" -eq 0 ]; then
    echo "Error: fetched 0 JSON files — upstream mirror may be empty or restructured." >&2
    exit 1
fi
echo "Done. $COUNT JSON files in $DEST" >&2
