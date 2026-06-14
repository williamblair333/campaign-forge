#!/usr/bin/env python3
"""MCP server — full 5etools compendium lookup from a local DuckDB in-memory store.

Tools:
  lookup_monster(name)   — statblock by name (exact then fuzzy)
  lookup_spell(name)     — spell entry by name
  lookup_item(name)      — item entry by name
  search_5e(query, type) — name search across entity types

Setup:
    python3 -m venv .venv-dnd5e
    .venv-dnd5e/bin/pip install -r requirements-dnd5e.txt
    bash scripts/dnd5e-fetch.sh   # one-time; re-run to update data
    # register via .mcp.json (see .mcp.json.example)
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print(
        "[dnd5e_mcp] ERROR: duckdb not found.\n"
        "  Setup: python3 -m venv .venv-dnd5e && "
        ".venv-dnd5e/bin/pip install -r requirements-dnd5e.txt",
        file=sys.stderr,
    )
    sys.exit(1)

DATA_DIR = Path(__file__).parent / "data" / "dnd5e"
FETCH_SCRIPT = Path(__file__).parent / "scripts" / "dnd5e-fetch.sh"

# Keys in 5etools JSON envelopes → DuckDB table names
_TABLE_MAP = {
    "monster": "monsters",
    "spell": "spells",
    "item": "items",
    "background": "backgrounds",
    "race": "races",
    "class": "classes",
}

# Module-level connection — set by main() before build_server()
_conn: "duckdb.DuckDBPyConnection | None" = None


# ── Data loading (no `mcp` dependency; unit-tested) ──────────────────────────

def load_data(data_dir: "str | Path") -> "duckdb.DuckDBPyConnection":
    """Parse all 5etools JSON files from data_dir into DuckDB in-memory tables."""
    conn = duckdb.connect()
    for table in _TABLE_MAP.values():
        conn.execute(
            f"CREATE TABLE {table} (name TEXT, source TEXT, type TEXT, data JSON)"
        )

    # foundry.json uses the same envelope keys but contains Foundry VTT overlay data
    # (sparse system fields, not full statblocks) — exclude to avoid polluting lookups.
    # index.json and sources.json are metadata, not entity records.
    _SKIP = {"foundry.json", "index.json", "sources.json", "fluff-index.json"}

    data_dir = Path(data_dir)
    for json_file in sorted(data_dir.rglob("*.json")):
        if json_file.name in _SKIP:
            continue
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[dnd5e_mcp] Warning: skipping {json_file}: {exc}", file=sys.stderr)
            continue
        for key, table in _TABLE_MAP.items():
            if key not in raw:
                continue
            for entity in raw[key]:
                name = entity.get("name", "")
                source = entity.get("source", "")
                etype = entity.get("type", "")
                if not isinstance(etype, str):
                    etype = ""
                conn.execute(
                    f"INSERT INTO {table} VALUES (?, ?, ?, ?)",
                    [name, source, etype, json.dumps(entity)],
                )
    return conn


# ── Lookup (no `mcp` dependency; unit-tested) ─────────────────────────────────

def _lookup(conn: "duckdb.DuckDBPyConnection", table: str, name: str) -> dict:
    """Exact name match, then jaro_winkler fuzzy fallback (threshold 0.85)."""
    rows = conn.execute(
        f"SELECT data FROM {table} WHERE lower(name) = lower(?)", [name]
    ).fetchall()
    if rows:
        return json.loads(rows[0][0])
    rows = conn.execute(
        f"""SELECT data FROM {table}
            WHERE jaro_winkler_similarity(lower(name), lower(?)) >= 0.85
            ORDER BY jaro_winkler_similarity(lower(name), lower(?)) DESC
            LIMIT 1""",
        [name, name],
    ).fetchall()
    if rows:
        return json.loads(rows[0][0])
    return {"error": "not_found", "name": name}


def lookup_monster(conn: "duckdb.DuckDBPyConnection", name: str) -> dict:
    """Return a monster statblock by name, or {"error": "not_found", "name": name}."""
    return _lookup(conn, "monsters", name)


def lookup_spell(conn: "duckdb.DuckDBPyConnection", name: str) -> dict:
    """Return a spell entry by name, or {"error": "not_found", "name": name}."""
    return _lookup(conn, "spells", name)


def lookup_item(conn: "duckdb.DuckDBPyConnection", name: str) -> dict:
    """Return an item entry by name, or {"error": "not_found", "name": name}."""
    return _lookup(conn, "items", name)


def search_entities(
    conn: "duckdb.DuckDBPyConnection", query: str, type: str = "all"
) -> list:
    """Substring name search across monsters/spells/items (up to 10 results).

    type: 'monster', 'spell', 'item', or 'all' (default).
    Returns [{name, source, type}] — no data blobs.
    """
    scope = {
        "monster": "monsters",
        "spell": "spells",
        "item": "items",
    }
    if type != "all" and type in scope:
        tables = {type: scope[type]}
    else:
        tables = scope

    results: list = []
    q = f"%{query.lower()}%"
    for entity_type, table in tables.items():
        rows = conn.execute(
            f"SELECT name, source FROM {table} WHERE lower(name) LIKE ? LIMIT 10",
            [q],
        ).fetchall()
        results.extend(
            {"name": r[0], "source": r[1], "type": entity_type} for r in rows
        )
    return results[:10]


# ── Startup guard ─────────────────────────────────────────────────────────────

def ensure_data(
    data_dir: Path = DATA_DIR,
    fetch_script: Path = FETCH_SCRIPT,
) -> None:
    """Check that data_dir has content; auto-fetch if absent or empty."""
    if data_dir.exists() and any(data_dir.iterdir()):
        return
    print("[dnd5e_mcp] 5etools data not found — running auto-fetch...", file=sys.stderr)
    result = subprocess.run(
        ["bash", str(fetch_script)], capture_output=True
    )
    if result.returncode != 0:
        print(
            f"[dnd5e_mcp] ERROR: data fetch failed (exit {result.returncode}).\n"
            f"  Fix: bash {fetch_script}\n"
            "  Requires: git + network access to github.com\n"
            + result.stderr.decode(errors="replace"),
            file=sys.stderr,
        )
        sys.exit(1)


# ── FastMCP server (imported lazily so core stays dependency-free) ─────────────

def build_server() -> object:
    """Construct the FastMCP server. Imports `mcp` lazily — call only when serving."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "dnd5e",
        instructions=(
            "Structured 5e compendium lookup — monsters, spells, and items from "
            "the full 5etools dataset. Use lookup_monster / lookup_spell / "
            "lookup_item for exact entity retrieval by name (fuzzy matching "
            "handles minor typos). Use search_5e to explore by partial name. "
            "For rules prose (how does grappling work?) use the RAG layer instead."
        ),
    )

    @server.tool()
    def lookup_monster(name: str) -> dict:
        """Look up a monster statblock by name. Returns HP, AC, CR, abilities, actions."""
        return _lookup(_conn, "monsters", name)

    @server.tool()
    def lookup_spell(name: str) -> dict:
        """Look up a spell by name. Returns level, school, range, components, description."""
        return _lookup(_conn, "spells", name)

    @server.tool()
    def lookup_item(name: str) -> dict:
        """Look up an item by name. Returns type, rarity, attunement, properties."""
        return _lookup(_conn, "items", name)

    @server.tool()
    def search_5e(query: str, type: str = "all") -> list:
        """Search 5e entities by partial name. type: 'monster', 'spell', 'item', or 'all'."""
        return search_entities(_conn, query, type)

    return server


def main() -> None:
    global _conn
    ensure_data()
    _conn = load_data(DATA_DIR)
    n = _conn.execute("SELECT COUNT(*) FROM monsters").fetchone()[0]
    m = _conn.execute("SELECT COUNT(*) FROM spells").fetchone()[0]
    k = _conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    print(f"[dnd5e_mcp] loaded {n} monsters, {m} spells, {k} items", file=sys.stderr)
    build_server().run()


if __name__ == "__main__":
    main()
