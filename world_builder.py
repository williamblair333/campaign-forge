#!/usr/bin/env python3
"""
world_builder.py — Seed a Kanka CE campaign from a natural-language description.

Usage:
    python world_builder.py                           # interactive (Ctrl+D to submit)
    python world_builder.py --description "..."       # non-interactive
    python world_builder.py --campaign-id 1 --dry-run
    python world_builder.py --yes                     # skip confirmation

Env vars:
    ANTHROPIC_API_KEY  — required
    KANKA_TOKEN        — required
    KANKA_BASE_URL     — default http://localhost:8081
    ANTHROPIC_MODEL    — default claude-sonnet-4-6

Requires: pip install anthropic requests
"""

import argparse
import os
import sys

try:
    import anthropic
except ImportError:
    print("Error: 'anthropic' not installed — run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

from kanka_client import KankaClient

# ---------------------------------------------------------------------------
# Claude prompt + tool schema
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a TTRPG world-building assistant. Analyze the dungeon master's campaign
description and extract every distinct world entity mentioned or clearly implied.

Extract:
- locations      : named places (cities, dungeons, forests, regions, planes, landmarks)
- characters     : named NPCs or notable individuals
- organisations  : factions, guilds, cults, kingdoms, secret societies, orders
- events         : named historical events, battles, disasters, founding moments
- notes          : lore that doesn't fit the above (prophecies, artifacts, magic systems)

Rules:
- Infer a reasonable type for each entity (e.g. "crumbling fortress" → type "Fortress")
- Write entry text as present-tense campaign lore, 2–4 sentences
- For locations, set parent_name when one place is clearly inside another
- Keep entity names exactly as the DM wrote them
- Extract only what is present in the description — do not invent new entities
- Always call extract_world_entities with your results\
"""

_EXTRACT_TOOL = {
    "name": "extract_world_entities",
    "description": "Extract all world-building entities from the campaign description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "locations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "description": "e.g. City, Dungeon, Forest, Region"},
                        "entry": {"type": "string"},
                        "parent_name": {
                            "type": "string",
                            "description": "Name of the containing location, if applicable",
                        },
                    },
                    "required": ["name"],
                },
            },
            "characters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "entry": {"type": "string"},
                        "is_dead": {"type": "boolean"},
                    },
                    "required": ["name"],
                },
            },
            "organisations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "description": "e.g. Guild, Kingdom, Cult, Secret Society"},
                        "entry": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "entry": {"type": "string"},
                        "date": {"type": "string", "description": "In-world date if mentioned"},
                    },
                    "required": ["name"],
                },
            },
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "entry": {"type": "string"},
                        "is_pinned": {"type": "boolean"},
                    },
                    "required": ["name"],
                },
            },
        },
        "required": ["locations", "characters", "organisations", "events", "notes"],
    },
}


# ---------------------------------------------------------------------------
# Entity extraction via Claude
# ---------------------------------------------------------------------------

def extract_entities(description: str, model: str) -> dict:
    """Call Claude to extract world entities. Returns the tool input dict."""
    client = anthropic.Anthropic()

    print(f"Calling Claude ({model}) to extract entities...", flush=True)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                # Prompt caching — requires anthropic SDK >= 0.25 and a cache-capable model.
                # Silently ignored if unsupported; does not affect correctness.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_EXTRACT_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": description}],
    )

    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use" and block.name == "extract_world_entities":
            return block.input

    raise RuntimeError("Claude did not call extract_world_entities — unexpected response")


# ---------------------------------------------------------------------------
# Entity creation in Kanka CE
# ---------------------------------------------------------------------------

def push_entities(client: KankaClient, campaign_id: int, entities: dict, dry_run: bool = False) -> dict:
    """Create extracted entities in Kanka CE. Returns counts of created entities."""
    created = {k: [] for k in entities}
    location_name_to_id: dict = {}

    def _fields(d: dict, *skip) -> dict:
        return {k: v for k, v in d.items() if k not in skip and v is not None and v != ""}

    # Locations first — enables single-pass parent_location_id resolution
    for loc in entities.get("locations", []):
        kwargs = _fields(loc, "name", "parent_name")
        parent_name = loc.get("parent_name", "")
        if parent_name and parent_name in location_name_to_id:
            kwargs["parent_location_id"] = location_name_to_id[parent_name]

        if dry_run:
            suffix = f", parent={parent_name}" if parent_name else ""
            print(f"  [dry] location     : {loc['name']!r} (type={loc.get('type', '—')}{suffix})")
        else:
            result = client.create_location(campaign_id, loc["name"], **kwargs)
            location_name_to_id[loc["name"]] = result["id"]
            created["locations"].append(result)
            print(f"  + location     : {result['name']} (id={result['id']})")

    for char in entities.get("characters", []):
        kwargs = _fields(char, "name")
        if dry_run:
            print(f"  [dry] character    : {char['name']!r} ({char.get('title', '—')})")
        else:
            result = client.create_character(campaign_id, char["name"], **kwargs)
            created["characters"].append(result)
            print(f"  + character    : {result['name']} (id={result['id']})")

    for org in entities.get("organisations", []):
        kwargs = _fields(org, "name")
        if dry_run:
            print(f"  [dry] organisation : {org['name']!r} (type={org.get('type', '—')})")
        else:
            result = client.create_organisation(campaign_id, org["name"], **kwargs)
            created["organisations"].append(result)
            print(f"  + organisation : {result['name']} (id={result['id']})")

    for evt in entities.get("events", []):
        kwargs = _fields(evt, "name")
        if dry_run:
            print(f"  [dry] event        : {evt['name']!r}")
        else:
            result = client.create_event(campaign_id, evt["name"], **kwargs)
            created["events"].append(result)
            print(f"  + event        : {result['name']} (id={result['id']})")

    for note in entities.get("notes", []):
        kwargs = _fields(note, "name")
        if dry_run:
            print(f"  [dry] note         : {note['name']!r}")
        else:
            result = client.create_note(campaign_id, note["name"], **kwargs)
            created["notes"].append(result)
            print(f"  + note         : {result['name']} (id={result['id']})")

    return created


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed a Kanka CE campaign from a natural-language description.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--description", "-d", metavar="TEXT",
                        help="Campaign description (omit for interactive / piped input)")
    parser.add_argument("--campaign-id", "-c", type=int, metavar="ID",
                        help="Kanka campaign ID (default: first campaign)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be created without pushing to Kanka CE")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip the confirmation prompt")
    parser.add_argument("--model", metavar="MODEL",
                        default=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                        help="Claude model (default: claude-sonnet-4-6)")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    token = os.environ.get("KANKA_TOKEN")
    if not token:
        print("Error: KANKA_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # Get description
    if args.description:
        description = args.description.strip()
    elif not sys.stdin.isatty():
        description = sys.stdin.read().strip()
    else:
        print("Describe your campaign world (Ctrl+D when done):\n")
        try:
            description = sys.stdin.read().strip()
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)

    if not description:
        print("Error: no description provided", file=sys.stderr)
        sys.exit(1)

    # Connect to Kanka CE and select campaign
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
        print("Error: no campaigns found — create one in Kanka CE first", file=sys.stderr)
        sys.exit(1)

    # Show campaign before calling Claude (so DM can abort if wrong campaign)
    print(f'\nTarget campaign: "{campaign["name"]}" (id={campaign["id"]})')
    if not args.yes and not args.dry_run and sys.stdin.isatty():
        try:
            answer = input("Continue with this campaign? [Y/n] ").strip().lower()
            if answer in ("n", "no"):
                print("Use --campaign-id to specify a different campaign.")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return

    # Extract entities via Claude
    entities = extract_entities(description, args.model)

    # Print extraction summary
    total = sum(len(v) for v in entities.values())
    if not total:
        print("No entities extracted — try a more detailed description.")
        return

    label_width = max((len(k) for k, v in entities.items() if v), default=8)
    print(f"\nExtracted {total} entities:")
    for kind, items in entities.items():
        if not items:
            continue
        print(f"  {kind:<{label_width}} ({len(items)})")
        for item in items:
            extra = f" — {item['type']}" if item.get("type") else ""
            print(f"    · {item['name']}{extra}")

    # Confirm before push
    if not args.dry_run and not args.yes:
        try:
            answer = input(f"\nPush {total} entities to \"{campaign['name']}\"? [y/N] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    # Push
    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Creating entities...")
    created = push_entities(kanka, campaign["id"], entities, dry_run=args.dry_run)

    if not args.dry_run:
        total_created = sum(len(v) for v in created.values())
        base_url = os.environ.get("KANKA_BASE_URL", "http://localhost:8081")
        print(f"\nDone. {total_created} entities created.")
        print(f"View: {base_url}/campaign/{campaign['id']}")


if __name__ == "__main__":
    main()
