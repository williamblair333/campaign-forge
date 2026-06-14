#!/usr/bin/env bash
# Download selective 5etools JSON data from the mirror (no full clone).
# Re-runnable: fetches fresh data to a staging dir before replacing old copies.
# All progress output goes to stderr; stdout is clean for callers.
set -euo pipefail

if ! command -v git &>/dev/null; then
    echo "Error: 'git' not found in PATH. Install git before running." >&2
    exit 1
fi

# Community mirror — subject to DMCA takedowns (mirror-1 and mirror-3 are already gone).
# If this URL 404s, find a replacement at https://github.com/5etools-mirror-N or check
# https://5e.tools. Verify the new repo has data/{bestiary,spells,class}/ dirs and
# data/{items,items-base,backgrounds,races}.json files before updating DIRS/FILES below.
REPO="https://github.com/revilowaldow/5etools-mirror-2.github.io.git"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../data/dnd5e"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Directories under data/ in the mirror repo
DIRS=(bestiary spells class)
# Single JSON files under data/ in the mirror repo
FILES=(items.json items-base.json backgrounds.json races.json)

echo "Fetching 5etools data → $DEST ..." >&2

git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/5etools" >&2
git -C "$TMP/5etools" sparse-checkout set \
    "${DIRS[@]/#/data/}" "${FILES[@]/#/data/}" >&2

# Validate all expected paths are present before touching $DEST
MISSING=()
for dir in "${DIRS[@]}"; do
    [ -d "$TMP/5etools/data/$dir" ] || MISSING+=("data/$dir")
done
for f in "${FILES[@]}"; do
    [ -f "$TMP/5etools/data/$f" ] || MISSING+=("data/$f")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "Error: mirror missing expected paths: ${MISSING[*]}" >&2
    echo "The upstream structure may have changed. Check the mirror and update DIRS/FILES in this script." >&2
    exit 1
fi

# Stage copies first (no partial state if interrupted), then swap into $DEST
mkdir -p "$DEST"
for dir in "${DIRS[@]}"; do
    cp -r "$TMP/5etools/data/$dir" "$TMP/staged-$dir"
done
for f in "${FILES[@]}"; do
    cp "$TMP/5etools/data/$f" "$TMP/staged-$f"
done

for dir in "${DIRS[@]}"; do
    rm -rf "$DEST/$dir"
    mv "$TMP/staged-$dir" "$DEST/$dir"
    echo "  copied $dir/" >&2
done
for f in "${FILES[@]}"; do
    rm -f "$DEST/$f"
    mv "$TMP/staged-$f" "$DEST/$f"
    echo "  copied $f" >&2
done

COUNT=$(find "$DEST" -name '*.json' | wc -l | tr -d ' ')
if [ "$COUNT" -eq 0 ]; then
    echo "Error: fetched 0 JSON files — upstream mirror may be empty or restructured." >&2
    exit 1
fi
echo "Done. $COUNT JSON files in $DEST" >&2
