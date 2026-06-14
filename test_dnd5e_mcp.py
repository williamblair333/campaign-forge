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


# ── Lookup ────────────────────────────────────────────────────────────────────

def test_lookup_monster_exact(conn):
    result = m.lookup_monster(conn, "Goblin")
    assert result["cr"] == "1/4"


def test_lookup_monster_case_insensitive(conn):
    result = m.lookup_monster(conn, "goblin")
    assert result["cr"] == "1/4"


def test_lookup_monster_fuzzy(conn):
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


# ── Search ────────────────────────────────────────────────────────────────────

def test_search_entities_all_types(conn):
    results = m.search_entities(conn, "fire")
    names = [r["name"] for r in results]
    assert "Fireball" in names
    assert "Fire Giant" in names


def test_search_entities_scoped_to_spell(conn):
    results = m.search_entities(conn, "fire", type="spell")
    types = {r["type"] for r in results}
    assert types == {"spell"}
    assert len(results) == 2


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


# ── Startup guard ─────────────────────────────────────────────────────────────

def test_ensure_data_skips_fetch_when_data_present(data_dir, monkeypatch):
    fetched = []
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: fetched.append(a))
    m.ensure_data(data_dir=data_dir, fetch_script=Path("/fake/fetch.sh"))
    assert fetched == []


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
