# 5e Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace cloud-dependent `mnehmos.open5e.mcp` with `dnd5e_mcp.py` — a self-hosted FastMCP server that loads the full 5etools compendium into DuckDB in-memory and exposes four structured lookup tools.

**Architecture:** `scripts/dnd5e-fetch.sh` sparse-clones only the data directories from the 5etools mirror into `data/dnd5e/` (gitignored). `dnd5e_mcp.py` loads those JSON files into DuckDB in-memory tables at startup (auto-fetching if absent), then serves four FastMCP tools. Module-level functions take a `conn` arg so they are unit-testable without `mcp` installed.

**Tech Stack:** Python 3.11+, `duckdb`, `mcp[cli]>=1.2,<2`, `requests`, pytest, bash (fetch script)

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `scripts/dnd5e-fetch.sh` | Sparse-clone 5etools JSON into `data/dnd5e/` |
| Create | `requirements-dnd5e.txt` | `duckdb`, `mcp[cli]`, `requests` pinned |
| Create | `dnd5e_mcp.py` | FastMCP server — data loading, lookup, search, startup guard |
| Create | `test_dnd5e_mcp.py` | Pytest suite — fixture-based, no real data files needed |
| Modify | `.gitignore` | Add `data/dnd5e/` |
| Modify | `.mcp.json.example` | Add `dnd5e` entry; note `mnehmos.open5e.mcp` is retired |
| Modify | `README.md` | Add `dnd5e_mcp` to stack table; document fetch step |
| Modify | `HANDOFF.md` | Close open question #1 |

---

## Task 1: Fetch Script, Requirements, Gitignore

**Files:**
- Create: `scripts/dnd5e-fetch.sh`
- Create: `requirements-dnd5e.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Create `scripts/dnd5e-fetch.sh`**

```bash
#!/usr/bin/env bash
# Download selective 5etools JSON data from the mirror (no full clone).
# Re-runnable: deletes and re-copies each directory on each run.
set -euo pipefail

REPO="https://github.com/5etools-mirror-3/5etools-mirror-3.github.io.git"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../data/dnd5e"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Fetching 5etools data → $DEST ..." >&2

git clone --depth 1 --filter=blob:none --sparse "$REPO" "$TMP/5etools" >&2
cd "$TMP/5etools"
git sparse-checkout set bestiary spells items backgrounds races classes >&2

mkdir -p "$DEST"
for dir in bestiary spells items backgrounds races classes; do
    if [ -d "$dir" ]; then
        rm -rf "$DEST/$dir"
        cp -r "$dir" "$DEST/"
        echo "  copied $dir" >&2
    fi
done

COUNT=$(find "$DEST" -name '*.json' | wc -l | tr -d ' ')
echo "Done. $COUNT JSON files in $DEST" >&2
```

- [ ] **Step 2: Create `requirements-dnd5e.txt`**

```
# 5e MCP server (dnd5e_mcp.py) — isolated from the base / rag / mcp envs.
#
# Setup:
#   python3 -m venv .venv-dnd5e
#   .venv-dnd5e/bin/pip install -r requirements-dnd5e.txt
#   bash scripts/dnd5e-fetch.sh   # one-time data fetch
#   # then register dnd5e_mcp.py via .mcp.json (see .mcp.json.example)
#
# Pinned so a future `mcp` major can't silently break server startup.
mcp[cli]>=1.2,<2
duckdb>=0.10
requests>=2.31
```

- [ ] **Step 3: Add `data/dnd5e/` to `.gitignore`**

Open `.gitignore` and add after the RAG block (around `rag/corpus/*.pdf`):

```
# ── 5e compendium data (dnd5e_mcp.py) — fetch via scripts/dnd5e-fetch.sh ────
data/dnd5e/
```

- [ ] **Step 4: Make fetch script executable and verify syntax**

```bash
chmod +x scripts/dnd5e-fetch.sh
bash -n scripts/dnd5e-fetch.sh
```

Expected: no output (syntax OK).

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/dnd5e-mcp
git add scripts/dnd5e-fetch.sh requirements-dnd5e.txt .gitignore
git commit -m "feat(dnd5e): fetch script, requirements, gitignore"
```

---

## Task 2: Core Data Loader (TDD)

**Files:**
- Create: `dnd5e_mcp.py` (initial — data loading only, no FastMCP)
- Create: `test_dnd5e_mcp.py` (data loading tests)

- [ ] **Step 1: Write the failing tests for data loading**

Create `test_dnd5e_mcp.py`:

```python
"""Tests for dnd5e_mcp.py — fixture-based, no real 5etools data needed."""
import json
import pytest
from pathlib import Path

import dnd5e_mcp as m

# ── Fixtures ──────────────────────────────────────────────────────────────────

FIXTURE_BESTIARY = {"monster": [
    {"name": "Goblin", "source": "MM", "type": "humanoid", "cr": "1/4", "hp": {"average": 7}},
    {"name": "Fire Giant", "source": "MM", "type": "giant", "cr": "9", "hp": {"average": 162}},
    {"name": "Young Red Dragon", "source": "MM", "type": "dragon", "cr": "10", "hp": {"average": 178}},
]}
FIXTURE_SPELLS = {"spell": [
    {"name": "Fireball", "source": "PHB", "school": "V", "level": 3},
    {"name": "Fire Storm", "source": "PHB", "school": "C", "level": 7},
    {"name": "Cure Wounds", "source": "PHB", "school": "A", "level": 1},
]}
FIXTURE_ITEMS = {"item": [
    {"name": "Longsword", "source": "PHB", "type": "M", "rarity": "none"},
    {"name": "Flame Tongue", "source": "DMG", "type": "M", "rarity": "rare"},
]}


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "bestiary").mkdir()
    (tmp_path / "spells").mkdir()
    (tmp_path / "items").mkdir()
    (tmp_path / "bestiary" / "bestiary-mm.json").write_text(json.dumps(FIXTURE_BESTIARY))
    (tmp_path / "spells" / "spells-phb.json").write_text(json.dumps(FIXTURE_SPELLS))
    (tmp_path / "items" / "items.json").write_text(json.dumps(FIXTURE_ITEMS))
    return tmp_path


@pytest.fixture
def conn(data_dir):
    return m.load_data(data_dir)


# ── Data loading ──────────────────────────────────────────────────────────────

def test_load_data_creates_monsters_table(conn):
    rows = conn.execute("SELECT count(*) FROM monsters").fetchone()
    assert rows[0] == 3


def test_load_data_creates_spells_table(conn):
    rows = conn.execute("SELECT count(*) FROM spells").fetchone()
    assert rows[0] == 3


def test_load_data_creates_items_table(conn):
    rows = conn.execute("SELECT count(*) FROM items").fetchone()
    assert rows[0] == 2


def test_load_data_skips_bad_json(tmp_path):
    (tmp_path / "bestiary").mkdir()
    (tmp_path / "bestiary" / "corrupt.json").write_text("{not valid json")
    conn = m.load_data(tmp_path)
    rows = conn.execute("SELECT count(*) FROM monsters").fetchone()
    assert rows[0] == 0  # skipped, did not crash
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv-dnd5e/bin/pip install -r requirements-dnd5e.txt -q 2>/dev/null || python3 -m venv .venv-dnd5e && .venv-dnd5e/bin/pip install -r requirements-dnd5e.txt -q
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py::test_load_data_creates_monsters_table -v
```

Expected: `ModuleNotFoundError: No module named 'dnd5e_mcp'`

- [ ] **Step 3: Create `dnd5e_mcp.py` with data loading**

```python
#!/usr/bin/env python3
"""MCP server — full 5etools compendium lookup from a local DuckDB in-memory store.

Tools:
  lookup_monster(name)  — statblock by name (exact then fuzzy)
  lookup_spell(name)    — spell entry by name
  lookup_item(name)     — item entry by name
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

import duckdb

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
_conn: duckdb.DuckDBPyConnection | None = None


# ── Data loading (no `mcp` dependency; unit-tested) ──────────────────────────

def load_data(data_dir: str | Path) -> duckdb.DuckDBPyConnection:
    """Parse all 5etools JSON files from data_dir into DuckDB in-memory tables."""
    conn = duckdb.connect()
    for table in _TABLE_MAP.values():
        conn.execute(
            f"CREATE TABLE {table} (name TEXT, source TEXT, type TEXT, data JSON)"
        )

    data_dir = Path(data_dir)
    for json_file in sorted(data_dir.rglob("*.json")):
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Warning: skipping {json_file}: {exc}", file=sys.stderr)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -k "load_data" -v
```

Expected:
```
test_dnd5e_mcp.py::test_load_data_creates_monsters_table PASSED
test_dnd5e_mcp.py::test_load_data_creates_spells_table PASSED
test_dnd5e_mcp.py::test_load_data_creates_items_table PASSED
test_dnd5e_mcp.py::test_load_data_skips_bad_json PASSED
```

- [ ] **Step 5: Commit**

```bash
git add dnd5e_mcp.py test_dnd5e_mcp.py
git commit -m "feat(dnd5e): core data loader + load_data tests"
```

---

## Task 3: Lookup Tools (TDD)

**Files:**
- Modify: `test_dnd5e_mcp.py` — add lookup tests
- Modify: `dnd5e_mcp.py` — add `_lookup`, `lookup_monster`, `lookup_spell`, `lookup_item`

- [ ] **Step 1: Add failing lookup tests to `test_dnd5e_mcp.py`**

Append to `test_dnd5e_mcp.py`:

```python
# ── Lookup ────────────────────────────────────────────────────────────────────

def test_lookup_monster_exact(conn):
    result = m.lookup_monster(conn, "Goblin")
    assert result["cr"] == "1/4"


def test_lookup_monster_case_insensitive(conn):
    result = m.lookup_monster(conn, "goblin")
    assert result["cr"] == "1/4"


def test_lookup_monster_fuzzy(conn):
    # "Fire Giante" is close enough to "Fire Giant" (jaro_winkler ≥ 0.85)
    result = m.lookup_monster(conn, "Fire Giante")
    assert result.get("name") == "Fire Giant"


def test_lookup_monster_missing(conn):
    result = m.lookup_monster(conn, "Tarrasque")
    assert result == {"error": "not_found", "name": "Tarrasque"}


def test_lookup_spell_level_and_school(conn):
    result = m.lookup_spell(conn, "Fireball")
    assert result["level"] == 3
    assert result["school"] == "V"


def test_lookup_spell_missing(conn):
    result = m.lookup_spell(conn, "Nonexistent Spell XYZ")
    assert result["error"] == "not_found"


def test_lookup_item_rarity(conn):
    result = m.lookup_item(conn, "Flame Tongue")
    assert result["rarity"] == "rare"


def test_lookup_item_missing(conn):
    result = m.lookup_item(conn, "Vorpal Sword")
    assert result["error"] == "not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -k "lookup" -v
```

Expected: `AttributeError: module 'dnd5e_mcp' has no attribute 'lookup_monster'`

- [ ] **Step 3: Add `_lookup` and lookup functions to `dnd5e_mcp.py`**

Append to `dnd5e_mcp.py` after `load_data`:

```python
# ── Lookup (no `mcp` dependency; unit-tested) ─────────────────────────────────

def _lookup(conn: duckdb.DuckDBPyConnection, table: str, name: str) -> dict:
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


def lookup_monster(conn: duckdb.DuckDBPyConnection, name: str) -> dict:
    """Return a monster statblock by name, or {"error": "not_found", "name": name}."""
    return _lookup(conn, "monsters", name)


def lookup_spell(conn: duckdb.DuckDBPyConnection, name: str) -> dict:
    """Return a spell entry by name, or {"error": "not_found", "name": name}."""
    return _lookup(conn, "spells", name)


def lookup_item(conn: duckdb.DuckDBPyConnection, name: str) -> dict:
    """Return an item entry by name, or {"error": "not_found", "name": name}."""
    return _lookup(conn, "items", name)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -k "lookup" -v
```

Expected: all 8 lookup tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dnd5e_mcp.py test_dnd5e_mcp.py
git commit -m "feat(dnd5e): lookup_monster / lookup_spell / lookup_item + tests"
```

---

## Task 4: Search Tool (TDD)

**Files:**
- Modify: `test_dnd5e_mcp.py` — add search tests
- Modify: `dnd5e_mcp.py` — add `search_entities`

- [ ] **Step 1: Add failing search tests to `test_dnd5e_mcp.py`**

Append to `test_dnd5e_mcp.py`:

```python
# ── Search ────────────────────────────────────────────────────────────────────

def test_search_entities_all_types(conn):
    results = m.search_entities(conn, "fire")
    names = [r["name"] for r in results]
    assert "Fireball" in names       # spell
    assert "Fire Giant" in names     # monster


def test_search_entities_scoped_to_spell(conn):
    results = m.search_entities(conn, "fire", type="spell")
    types = {r["type"] for r in results}
    assert types == {"spell"}
    assert len(results) == 2         # Fireball + Fire Storm


def test_search_entities_scoped_to_monster(conn):
    results = m.search_entities(conn, "fire", type="monster")
    types = {r["type"] for r in results}
    assert types == {"monster"}


def test_search_entities_no_matches(conn):
    results = m.search_entities(conn, "xyzzy_no_match_ever")
    assert results == []


def test_search_entities_returns_name_source_type_only(conn):
    results = m.search_entities(conn, "goblin")
    assert len(results) == 1
    keys = set(results[0].keys())
    assert keys == {"name", "source", "type"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -k "search" -v
```

Expected: `AttributeError: module 'dnd5e_mcp' has no attribute 'search_entities'`

- [ ] **Step 3: Add `search_entities` to `dnd5e_mcp.py`**

Append to `dnd5e_mcp.py` after the `lookup_item` function:

```python
def search_entities(
    conn: duckdb.DuckDBPyConnection, query: str, type: str = "all"
) -> list[dict]:
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

    results: list[dict] = []
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -k "search" -v
```

Expected: all 5 search tests PASS.

- [ ] **Step 5: Run the full test suite**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -v
```

Expected: all tests pass (no failures).

- [ ] **Step 6: Commit**

```bash
git add dnd5e_mcp.py test_dnd5e_mcp.py
git commit -m "feat(dnd5e): search_entities + tests"
```

---

## Task 5: Startup Guard + Auto-fetch (TDD)

**Files:**
- Modify: `test_dnd5e_mcp.py` — add startup guard tests
- Modify: `dnd5e_mcp.py` — add `ensure_data`

- [ ] **Step 1: Add failing startup guard tests to `test_dnd5e_mcp.py`**

Append to `test_dnd5e_mcp.py`:

```python
# ── Startup guard ─────────────────────────────────────────────────────────────

def test_ensure_data_skips_fetch_when_data_present(data_dir, monkeypatch):
    fetched = []
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: fetched.append(a))
    m.ensure_data(data_dir=data_dir, fetch_script=Path("/fake/fetch.sh"))
    assert fetched == []  # fetch was NOT called


def test_ensure_data_runs_fetch_when_dir_empty(tmp_path, monkeypatch):
    calls = []

    class _Result:
        returncode = 0

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    m.ensure_data(data_dir=tmp_path, fetch_script=Path("/fake/fetch.sh"))
    assert len(calls) == 1
    assert calls[0] == ["bash", "/fake/fetch.sh"]


def test_ensure_data_exits_on_fetch_failure(tmp_path, monkeypatch):
    class _Failed:
        returncode = 1
        stderr = b"network error"

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _Failed())
    with pytest.raises(SystemExit):
        m.ensure_data(data_dir=tmp_path, fetch_script=Path("/fake/fetch.sh"))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -k "ensure_data" -v
```

Expected: `AttributeError: module 'dnd5e_mcp' has no attribute 'ensure_data'`

- [ ] **Step 3: Add `ensure_data` to `dnd5e_mcp.py`**

Append `ensure_data` after `search_entities` (`subprocess` is already imported from Task 2):

```python
# ── Startup guard ─────────────────────────────────────────────────────────────

def ensure_data(
    data_dir: Path = DATA_DIR,
    fetch_script: Path = FETCH_SCRIPT,
) -> None:
    """Check that data_dir has content; auto-fetch if absent or empty."""
    if data_dir.exists() and any(data_dir.iterdir()):
        return
    print("5etools data not found — running auto-fetch...", file=sys.stderr)
    result = subprocess.run(
        ["bash", str(fetch_script)], capture_output=True
    )
    if result.returncode != 0:
        sys.exit(
            "Error: 5etools data not found and auto-fetch failed.\n"
            f"Run `bash {fetch_script}` manually and check your network connection.\n"
            + result.stderr.decode(errors="replace")
        )
```

- [ ] **Step 4: Run all tests**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add dnd5e_mcp.py test_dnd5e_mcp.py
git commit -m "feat(dnd5e): ensure_data startup guard + tests"
```

---

## Task 6: FastMCP Server + Smoke Test

**Files:**
- Modify: `dnd5e_mcp.py` — add `build_server`, `main`

No new tests — `build_server` is the FastMCP wiring layer; the underlying logic is already tested. Smoke-tested manually.

- [ ] **Step 1: Append `build_server` and `main` to `dnd5e_mcp.py`**

```python
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
    build_server().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Set up the venv and verify startup (no data yet)**

```bash
python3 -m venv .venv-dnd5e
.venv-dnd5e/bin/pip install -r requirements-dnd5e.txt -q
```

Expected: installs without error.

- [ ] **Step 3: Run the fetch script to populate data**

```bash
bash scripts/dnd5e-fetch.sh
```

Expected output (approximate):
```
Fetching 5etools data → .../data/dnd5e ...
  copied bestiary
  copied spells
  copied items
  copied backgrounds
  copied races
  copied classes
Done. N JSON files in .../data/dnd5e
```

This takes 30–90 seconds depending on network speed.

- [ ] **Step 4: Smoke-test the server starts**

```bash
timeout 5 .venv-dnd5e/bin/python dnd5e_mcp.py 2>&1 || true
```

Expected: server starts, loads data (you see no crash), then times out after 5s (normal — it's a long-running server).

- [ ] **Step 5: Smoke-test a lookup via Python**

```bash
.venv-dnd5e/bin/python - <<'EOF'
import dnd5e_mcp as m
conn = m.load_data("data/dnd5e")
print(m.lookup_monster(conn, "Goblin"))
print(m.lookup_spell(conn, "Fireball"))
print(m.search_entities(conn, "dragon", type="monster")[:3])
EOF
```

Expected: JSON dicts with real 5etools statblock data, no errors.

- [ ] **Step 6: Commit**

```bash
git add dnd5e_mcp.py
git commit -m "feat(dnd5e): FastMCP server build_server + main entry point"
```

---

## Task 7: Config + Docs Updates + PR

**Files:**
- Modify: `.mcp.json.example`
- Modify: `README.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Update `.mcp.json.example`**

Replace the existing content with:

```json
{
  "_comment": "MCP server registrations for campaign-forge. Copy relevant blocks into your Claude client's MCP config. MCP servers do NOT inherit your shell's .env — pass tokens in 'env'.",
  "_setup_dnd5e": "python3 -m venv .venv-dnd5e && .venv-dnd5e/bin/pip install -r requirements-dnd5e.txt && bash scripts/dnd5e-fetch.sh",
  "_setup_kanka": "python3 -m venv .venv-mcp && .venv-mcp/bin/pip install -r requirements-mcp.txt",
  "_retired": "mnehmos.open5e.mcp is retired — replaced by dnd5e below",
  "mcpServers": {
    "dnd5e": {
      "command": "/opt/proj/campaign-forge/.venv-dnd5e/bin/python",
      "args": ["/opt/proj/campaign-forge/dnd5e_mcp.py"]
    },
    "kanka": {
      "command": "/opt/proj/campaign-forge/.venv-mcp/bin/python",
      "args": ["/opt/proj/campaign-forge/kanka_mcp.py"],
      "env": {
        "KANKA_TOKEN": "<your-kanka-api-token>",
        "KANKA_BASE_URL": "http://localhost:8081"
      }
    }
  }
}
```

- [ ] **Step 2: Update `README.md` stack table**

Find the stack table row for `mnehmos.open5e.mcp` and replace it:

```markdown
| 5e rules data (structured) | dnd5e_mcp.py | local — 5etools JSON via DuckDB | ✅ MCP (Python) |
```

Add a setup note under the table (or in the Setup section) for the one-time fetch:

```markdown
**One-time 5e data fetch:**
```bash
python3 -m venv .venv-dnd5e && .venv-dnd5e/bin/pip install -r requirements-dnd5e.txt
bash scripts/dnd5e-fetch.sh   # ~50–100 MB, re-run to update
```
```

- [ ] **Step 3: Update `HANDOFF.md` open question #1**

Change:

```markdown
1. **5e data layer** — Design spec complete (PR #24, `docs/superpowers/specs/2026-06-14-dnd5e-data-layer-design.md`). Implementation pending: `dnd5e_mcp.py` FastMCP server + 5etools JSON via DuckDB; retires cloud `mnehmos.open5e.mcp`.
```

To:

```markdown
1. **5e data layer** — ✅ RESOLVED. `dnd5e_mcp.py` FastMCP server (4 tools: lookup_monster / lookup_spell / lookup_item / search_5e) loads full 5etools compendium via DuckDB in-memory. `scripts/dnd5e-fetch.sh` populates `data/dnd5e/` on first run. `mnehmos.open5e.mcp` retired. See spec PR #24 for design rationale.
```

- [ ] **Step 4: Run full test suite one final time**

```bash
.venv-dnd5e/bin/pytest test_dnd5e_mcp.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit and open PR**

```bash
git add .mcp.json.example README.md HANDOFF.md
git commit -m "docs(dnd5e): update mcp.json.example, README stack table, close HANDOFF #1"
git push -u origin feat/dnd5e-mcp
gh pr create --title "feat(dnd5e): self-hosted 5e data layer via dnd5e_mcp.py + 5etools JSON" \
  --body "$(cat <<'EOF'
## Summary
- Adds \`dnd5e_mcp.py\` — FastMCP server with 4 tools: \`lookup_monster\`, \`lookup_spell\`, \`lookup_item\`, \`search_5e\`
- Loads full 5etools compendium JSON into DuckDB in-memory at startup
- \`scripts/dnd5e-fetch.sh\` — sparse-clone data from 5etools mirror; auto-runs on first startup
- \`test_dnd5e_mcp.py\` — 16 pytest cases, fixture-based, no real data needed in CI
- Retires cloud-dependent \`mnehmos.open5e.mcp\`
- Closes open question #1 in HANDOFF

## Test plan
- [ ] \`pytest test_dnd5e_mcp.py -v\` passes (all 20 tests)
- [ ] \`bash scripts/dnd5e-fetch.sh\` populates \`data/dnd5e/\`
- [ ] Smoke test: \`.venv-dnd5e/bin/python -c "import dnd5e_mcp as m; conn = m.load_data('data/dnd5e'); print(m.lookup_monster(conn, 'Goblin'))"\`
- [ ] Server starts: \`timeout 5 .venv-dnd5e/bin/python dnd5e_mcp.py\`
- [ ] \`mnehmos.open5e.mcp\` removed from \`.mcp.json\`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --merge --delete-branch
```
