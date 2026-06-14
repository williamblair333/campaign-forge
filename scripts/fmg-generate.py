#!/usr/bin/env python3
"""Headless Fantasy Map Generator → map data (no manual browser step).

Drives a locally-served FMG v1.99 (start it with scripts/fmg-setup.sh) in a
headless browser, lets it generate a map, then serializes the result and writes
it to disk. No UI scraping, no download interception.

Two output formats:
  --format json  (default)  → ``{info, pack:{burgs, states}}`` — a JSON dump of
      FMG's in-memory burgs + political states, exactly the shape map_tools.py
      parses. Use this to sync settlements/factions to Kanka.
  --format map              → FMG's native ``.map`` (prepareMapData()) for
      re-loading into the FMG UI. (map_tools.py can NOT read this — it expects
      the json form above.)

    bash scripts/fmg-setup.sh                                  # serve FMG :8082
    python scripts/fmg-generate.py --seed 1234 --out maps/world.json
    python3 map_tools.py sync maps/world.json --dry-run

Requires the isolated FMG venv (see requirements-fmg.txt):
    python3 -m venv .venv-fmg
    .venv-fmg/bin/pip install -r requirements-fmg.txt
    .venv-fmg/bin/playwright install chromium
"""

import argparse
import sys
from pathlib import Path

# FMG generation is done when prepareMapData() exists and the Voronoi cell graph
# is populated. NOTE: v1.99 declares `pack`/`seed` as top-level `let` globals,
# which are NOT window properties — they must be referenced as bare identifiers.
_GEN_READY = (
    "() => typeof prepareMapData === 'function'"
    " && typeof pack !== 'undefined' && pack.cells"
    " && pack.cells.i && pack.cells.i.length > 0"
)


# Serialize FMG's in-memory burgs + states into the JSON shape map_tools.py reads
# (data["pack"]["burgs"], data["pack"]["states"], data["info"]). pack.burgs/states
# are 1-indexed (index 0 is null) — map_tools.py already filters those out. We omit
# pack.cells (the huge Voronoi geometry) since map_tools doesn't use it.
_JSON_EXTRACT = """() => JSON.stringify({
    info: {
        seed: (typeof seed !== 'undefined') ? seed : null,
        width: (typeof graphWidth !== 'undefined') ? graphWidth : null,
        height: (typeof graphHeight !== 'undefined') ? graphHeight : null,
        version: (typeof version !== 'undefined') ? version : null
    },
    pack: {burgs: pack.burgs, states: pack.states}
})"""


def generate_map(url, seed=None, width=0, height=0, wait_ms=120000,
                 headed=False, fmt="json"):
    """Return (data_string, seed_used). Raises on launch/generation failure.

    fmt="json" → map_tools-compatible burgs/states JSON; fmt="map" → FMG .map.
    """
    from playwright.sync_api import sync_playwright

    target = url.rstrip("/") + "/"
    params = []
    if seed is not None:
        params.append(f"seed={seed}")
    if width:
        params.append(f"width={width}")
    if height:
        params.append(f"height={height}")
    if params:
        target += "?" + "&".join(params)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page(
            viewport={"width": width or 1280, "height": height or 1024}
        )
        try:
            page.goto(target, wait_until="load", timeout=wait_ms)
            page.wait_for_function(_GEN_READY, timeout=wait_ms)
            seed_used = page.evaluate("() => (typeof seed !== 'undefined') ? seed : null")
            extract = "() => prepareMapData()" if fmt == "map" else _JSON_EXTRACT
            map_data = page.evaluate(extract)
        finally:
            browser.close()
    return map_data, seed_used


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Headless FMG map generation → .map (drives FMG v1.99 served "
                    "by scripts/fmg-setup.sh)."
    )
    ap.add_argument("--out", "-o", required=True, metavar="FILE",
                    help="Where to write the .map (created if needed).")
    ap.add_argument("--seed", type=int, default=None,
                    help="FMG seed for a reproducible map (default: FMG's random). "
                         "The actual seed used is printed for re-runs.")
    ap.add_argument("--url", default="http://localhost:8082",
                    help="Served FMG base URL (default: http://localhost:8082).")
    ap.add_argument("--width", type=int, default=0, help="Map width override.")
    ap.add_argument("--height", type=int, default=0, help="Map height override.")
    ap.add_argument("--wait-ms", type=int, default=120000,
                    help="Generation timeout in ms (default 120000).")
    ap.add_argument("--format", choices=("json", "map"), default="json",
                    help="json (default): map_tools-compatible burgs/states JSON; "
                         "map: FMG-native .map for re-loading in the FMG UI.")
    ap.add_argument("--headed", action="store_true",
                    help="Run the browser headed (debugging).")
    args = ap.parse_args(argv)

    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        print(
            "Error: playwright not installed. Set up the FMG venv:\n"
            "  python3 -m venv .venv-fmg\n"
            "  .venv-fmg/bin/pip install -r requirements-fmg.txt\n"
            "  .venv-fmg/bin/playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        map_data, seed_used = generate_map(
            args.url, args.seed, args.width, args.height, args.wait_ms,
            args.headed, args.format
        )
    except Exception as exc:  # noqa: BLE001 — translate to an actionable message
        msg = str(exc)
        low = msg.lower()
        hint = ""
        if "executable doesn't exist" in low or "playwright install" in low:
            hint = "\n→ Run: .venv-fmg/bin/playwright install chromium"
        elif "missing dependencies" in low or "error while loading shared" in low:
            hint = ("\n→ Missing system libs for headless chromium: "
                    "sudo .venv-fmg/bin/playwright install-deps")
        elif "err_connection_refused" in low or "net::" in low:
            hint = "\n→ Is FMG served? Run: bash scripts/fmg-setup.sh"
        print(f"Error: FMG generation failed: {msg}{hint}", file=sys.stderr)
        sys.exit(1)

    if not map_data or len(map_data) < 100:
        print("Error: prepareMapData() returned empty/short output — generation "
              "did not complete.", file=sys.stderr)
        sys.exit(1)

    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(map_data, encoding="utf-8")
    print(f"Wrote {out} ({len(map_data):,} bytes, seed={seed_used})", file=sys.stderr)


if __name__ == "__main__":
    main()
