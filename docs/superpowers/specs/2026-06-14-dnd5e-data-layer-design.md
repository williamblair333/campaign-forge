# 5e Data Layer — Design Spec

**Date:** 2026-06-14  
**Status:** Approved — pending implementation  
**Scope:** Replace cloud-dependent `mnehmos.open5e.mcp` with a fully self-hosted structured 5e data layer covering the full 5etools compendium.

---

## Problem

The existing stack lists `mnehmos.open5e.mcp` (TypeScript MCP) as a tool for 5e rules data. It queries `open5e.com` (cloud), covers SRD + limited OGL content only, and adds an external network dependency. The Phase 4 RAG covers SRD prose/rules queries but returns unstructured text — no machine-readable fields (HP, AC, ability scores, spell slots, damage dice).

## Goal

A single-file FastMCP server (`dnd5e_mcp.py`) that:
- Loads full 5etools compendium JSON into DuckDB in-memory at startup
- Exposes four MCP tools for structured entity lookup
- Requires no cloud access, no extra Docker container, no REST intermediary
- Auto-fetches data on first run; fails fast with a clear message if fetch fails

---

## Architecture

```
data/dnd5e/              ← gitignored; populated by fetch script or auto-fetch
  bestiary/bestiary-*.json
  spells/spells-*.json
  items/items.json, items-base.json
  backgrounds/backgrounds.json
  races/races*.json
  classes/classes-*.json

scripts/dnd5e-fetch.sh   ← committed; downloads selective 5etools JSON from mirror
dnd5e_mcp.py             ← FastMCP server (single file, mirrors kanka_mcp.py pattern)
requirements-dnd5e.txt   ← fastmcp, duckdb, requests
test_dnd5e_mcp.py        ← pytest suite using fixture JSON (no real data files in CI)
.mcp.json                ← add dnd5e_mcp entry; retire mnehmos.open5e.mcp
```

`dnd5e_mcp.py` follows the same pattern as `kanka_mcp.py`: FastMCP server, guarded import, standalone `__main__` entry point.

The existing RAG (`rag/`) is untouched. Prose/rules queries continue to go there. This layer handles structured entity lookups only.

---

## Data Layer

### Source

5etools mirror JSON files downloaded via GitHub raw URLs from `github.com/5etools-mirror-3/5etools-mirror-3.github.io` (selective file fetch — not a full clone of the ~2GB repo). Target files:

| Files | Content |
|---|---|
| `bestiary/bestiary-*.json` | All monster statblocks |
| `spells/spells-*.json` | All spells |
| `items/items.json`, `items/items-base.json` | Equipment, magic items |
| `backgrounds/backgrounds.json` | Backgrounds |
| `races/races*.json` | Races and subraces |
| `classes/classes-*.json` | Classes and subclasses |

### DuckDB Schema

Each entity type gets its own in-memory table with:
- `name TEXT` — indexed for fast lookup and fuzzy match
- `source TEXT` — book abbreviation (PHB, MM, XGE, etc.)
- `type TEXT` — entity subtype where applicable (creature type, spell school, item type)
- `data JSON` — full raw 5etools JSON blob

5etools JSON envelope is uniform (`{"monster": [...]}`, `{"spell": [...]}`) — loading is a single parse-and-insert loop per file.

Estimated load time: under 2 seconds for ~3,000 monsters + ~1,000 spells + items on this machine.

### Auto-fetch

On server startup, `dnd5e_mcp.py` checks for `data/dnd5e/` with expected files. If absent or empty, it runs `scripts/dnd5e-fetch.sh` automatically before loading. If the fetch fails, the server exits with:

```
Error: 5etools data not found and auto-fetch failed.
Run `bash scripts/dnd5e-fetch.sh` manually and check your network connection.
```

`scripts/dnd5e-fetch.sh` is re-runnable to update data.

---

## MCP Tools

### `lookup_monster(name: str)`
Exact name match (case-insensitive), falling back to DuckDB's `jaro_winkler_similarity` fuzzy match (threshold ≥ 0.85).  
Returns full statblock blob: HP, AC, ability scores, speed, actions, legendary actions, CR, traits, saves, skills.

### `lookup_spell(name: str)`
Exact then `jaro_winkler_similarity` fuzzy match (threshold ≥ 0.85).  
Returns full spell entry: level, school, casting time, range, components, duration, description, upcasting.

### `lookup_item(name: str)`
Exact then `jaro_winkler_similarity` fuzzy match (threshold ≥ 0.85).  
Returns full item entry: type, rarity, attunement requirement, properties, description.

### `search_5e(query: str, type: str = "all")`
Fuzzy name search across monsters/spells/items (or scoped to one type via `type` param).  
Returns top-10 matches as `[{name, source, type}]` — names only, no blobs, for exploration queries.

**Not in scope:** write tools, rules/prose queries (stay in RAG), class feature lookups beyond the blob (can be parsed from the `data` field by Claude).

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `lookup_*` — no match | `{"error": "not_found", "name": "<query>"}` — not an exception |
| `search_5e` — no matches | `[]` — empty list, not an error |
| Individual JSON file fails to load | Log warning, skip file, continue (partial data beats no server) |
| `data/dnd5e/` absent on startup | Auto-fetch; if fetch fails, exit with clear message |
| DuckDB in-memory table error | Propagate as MCP tool error with message |

---

## Testing

File: `test_dnd5e_mcp.py` — pytest, matching `test_rag_ingest.py` conventions.  
Fixture: small inline JSON blob (3–5 monsters, 3 spells, 2 items) — no real data files needed in CI.

| Test | What it checks |
|---|---|
| `test_lookup_monster_exact` | Exact name match returns expected CR |
| `test_lookup_monster_fuzzy` | "goblin" matches "Goblin" |
| `test_lookup_monster_missing` | Returns `not_found`, does not raise |
| `test_lookup_spell` | Spell level and school correct |
| `test_lookup_item` | Item rarity correct |
| `test_search_5e_all` | "fire" returns monsters and spells with "fire" in name |
| `test_search_5e_scoped` | `type="spell"` returns only spells |
| `test_startup_guard` | Missing data dir triggers fetch (mocked fetch), not crash |

---

## Integration

### `.mcp.json` changes
- Add `dnd5e_mcp` server entry (same pattern as `kanka_mcp`)
- Remove `mnehmos.open5e.mcp` entry (retired)

### `.mcp.json.example` update
Document the new entry and the fetch step in the setup comment.

### `.gitignore`
Add `data/dnd5e/` (already has `rag/lancedb/`, `rag/corpus/*.pdf` as precedent).

### README / HANDOFF
- README: add `dnd5e_mcp` to the stack table, document one-time fetch step
- HANDOFF: mark backlog item 1 resolved

---

## Out of Scope

- `mnehmos.open5e.mcp` migration path — it is retired, not migrated
- Foundry VTT actor import from lookup results — that's a separate flow using the existing Foundry MCP bridge
- PDF/RAG overlap — RAG handles prose queries; this handles structured lookups
- Automated data refresh / version pinning — re-run the fetch script manually when new 5etools data is wanted
