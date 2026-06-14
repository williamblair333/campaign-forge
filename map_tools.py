#!/usr/bin/env python3
"""
map_tools.py — Parse a FMG burgs/states JSON export and sync it to Kanka CE.

Commands:
    python3 map_tools.py parse  world.json                     # show what's in the file
    python3 map_tools.py sync   world.json                     # push to Kanka CE
    python3 map_tools.py sync   world.json --dry-run           # preview without pushing
    python3 map_tools.py sync   world.json --campaign-id 1 --yes

Expected input format:
    JSON with FMG's in-memory map data — produced by `scripts/fmg-generate.py
    --format json` (the default), which serializes:
      {"info": {seed, width, height, version},
       "pack": {"burgs": [...], "states": [...]}}    (arrays 1-indexed; [0] is null)
      pack.burgs  — settlements: name, x, y, state, capital, type, population
      pack.states — political entities: name, type, color, capital (burg index)

    NOTE: a raw FMG ".map" (File → Save As → .map) is a custom pipe-delimited
    format, NOT JSON — this tool cannot parse it. Use the json export above.

Workflow:
    1. bash scripts/fmg-setup.sh                                # serve FMG (v1.99) at :8082
    2. .venv-fmg/bin/python scripts/fmg-generate.py --seed 1234 --out maps/world.json
    3. python3 map_tools.py sync maps/world.json --dry-run      # preview, then drop --dry-run

Env vars:
    KANKA_TOKEN     — required for sync
    KANKA_BASE_URL  — default http://localhost:8081
"""

import argparse
import json
import os
import sys

from kanka_client import KankaClient

# ---------------------------------------------------------------------------
# .map file parsing
# ---------------------------------------------------------------------------

def load_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_burgs(data: dict) -> list:
    raw = data.get("pack", {}).get("burgs", [])
    return [b for b in raw if b and not b.get("removed")]


def extract_states(data: dict) -> list:
    raw = data.get("pack", {}).get("states", [])
    return [
        s for s in raw
        if s and not s.get("removed") and s.get("name") != "Neutral"
    ]


def burg_type(burg: dict) -> str:
    if burg.get("capital"):
        return "Capital City"
    pop = burg.get("population", 0)
    if pop > 20:
        return "City"
    if pop > 5:
        return "Town"
    return "Village"


def state_type(state: dict) -> str:
    return state.get("type", "Kingdom").capitalize()


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def existing_names(client: KankaClient, campaign_id: int, entity_kind: str) -> set:
    try:
        if entity_kind == "locations":
            items = client.list_locations(campaign_id)
        elif entity_kind == "organisations":
            items = client.list_organisations(campaign_id)
        else:
            return set()
        return {item["name"] for item in items}
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_parse(args: argparse.Namespace) -> None:
    data = load_map(args.map_file)
    info = data.get("info", {})
    burgs = extract_burgs(data)
    states = extract_states(data)

    print(f"Map file : {args.map_file}")
    print(f"Seed     : {info.get('seed', '—')}")
    print(f"Version  : {info.get('version', '—')}")
    print(f"Size     : {info.get('width', '?')} × {info.get('height', '?')}")
    print()

    state_map = {s["i"]: s for s in states}

    print(f"States ({len(states)}):")
    for s in states:
        cap_burg = next((b for b in burgs if b.get("i") == s.get("capital")), None)
        cap_name = cap_burg["name"] if cap_burg else "—"
        print(f"  [{s['i']:>3}] {s['name']:<30} type={state_type(s):<12} capital={cap_name}")

    print()
    print(f"Burgs ({len(burgs)}):")
    for b in burgs:
        sname = state_map.get(b.get("state", 0), {}).get("name", "—")
        print(f"  [{b['i']:>3}] {b['name']:<30} type={burg_type(b):<14} state={sname}")


def cmd_sync(args: argparse.Namespace) -> None:
    token = os.environ.get("KANKA_TOKEN")
    if not token:
        print("Error: KANKA_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    data = load_map(args.map_file)
    burgs = extract_burgs(data)
    states = extract_states(data)
    state_map = {s["i"]: s["name"] for s in states}

    if not burgs and not states:
        print("No burgs or states found in map file.")
        return

    kanka = KankaClient(token)
    try:
        campaigns = kanka.list_campaigns()
    except Exception as e:
        print(f"Error: could not reach Kanka CE — {e}", file=sys.stderr)
        print("Is the stack running?  cd kanka-ce && vendor/bin/sail up -d", file=sys.stderr)
        sys.exit(1)

    if args.campaign_id:
        campaign = next((c for c in campaigns if c["id"] == args.campaign_id), None)
        if not campaign:
            print(f"Error: campaign id={args.campaign_id} not found", file=sys.stderr)
            sys.exit(1)
    elif campaigns:
        campaign = campaigns[0]
    else:
        print("Error: no campaigns found", file=sys.stderr)
        sys.exit(1)

    print(f'Target campaign: "{campaign["name"]}" (id={campaign["id"]})')
    print(f"Entities to sync: {len(states)} states → organisations, {len(burgs)} burgs → locations")

    if not args.dry_run and not args.yes:
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    # Fetch existing names once to skip duplicates
    if not args.dry_run:
        print("Checking for existing entities...")
        existing_locs = existing_names(kanka, campaign["id"], "locations")
        existing_orgs = existing_names(kanka, campaign["id"], "organisations")
    else:
        existing_locs = set()
        existing_orgs = set()

    n_created = 0
    n_skipped = 0
    prefix = "[dry] " if args.dry_run else ""

    # States → organisations
    print(f"\n{prefix}Syncing states → organisations...")
    for s in states:
        name = s["name"]
        if not args.dry_run and name in existing_orgs:
            print(f"  skip  organisation : {name!r} (already exists)")
            n_skipped += 1
            continue

        entry = f"A {state_type(s).lower()} of {s.get('burgs', 0)} settlements."
        if s.get("color"):
            entry += f" Heraldic color: {s['color']}."

        if args.dry_run:
            print(f"  [dry] organisation : {name!r} (type={state_type(s)})")
        else:
            result = kanka.create_organisation(campaign["id"], name, type=state_type(s), entry=entry)
            n_created += 1
            print(f"  +     organisation : {name} (id={result['id']})")

    # Burgs → locations
    print(f"\n{prefix}Syncing burgs → locations...")
    for b in burgs:
        name = b["name"]
        if not args.dry_run and name in existing_locs:
            print(f"  skip  location     : {name!r} (already exists)")
            n_skipped += 1
            continue

        sname = state_map.get(b.get("state", 0), "")
        entry = f"A {burg_type(b).lower()} in {sname}." if sname else f"A {burg_type(b).lower()}."
        if b.get("capital"):
            entry += " This is the state capital."

        if args.dry_run:
            print(f"  [dry] location     : {name!r} (type={burg_type(b)}, state={sname or '—'})")
        else:
            result = kanka.create_location(campaign["id"], name, type=burg_type(b), entry=entry)
            n_created += 1
            print(f"  +     location     : {name} (id={result['id']})")

    if not args.dry_run:
        base_url = os.environ.get("KANKA_BASE_URL", "http://localhost:8081")
        print(f"\nDone. {n_created} created, {n_skipped} skipped (already existed).")
        print(f"View: {base_url}/campaign/{campaign['id']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse FMG .map exports and sync to Kanka CE.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Show summary of a .map file")
    p_parse.add_argument("map_file", metavar="MAP", help="Path to .map export")

    p_sync = sub.add_parser("sync", help="Sync .map entities to Kanka CE")
    p_sync.add_argument("map_file", metavar="MAP", help="Path to .map export")
    p_sync.add_argument("--campaign-id", "-c", type=int, metavar="ID",
                        help="Kanka campaign ID (default: first campaign)")
    p_sync.add_argument("--dry-run", action="store_true",
                        help="Preview without creating anything")
    p_sync.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation")

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "sync":
        cmd_sync(args)


if __name__ == "__main__":
    main()
