# AI Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `table/` — a Python module that runs an autonomous D&D table (1 AI GM + 2–5 AI players) through a combat encounter and outputs a structured transcript.

**Architecture:** A minimal event loop (`orchestrator.py`) owns all combat state (HP, initiative, conditions) and routes turns between a GM agent (Claude Sonnet via Anthropic API) and player agents (Ollama `llama3.1:8b` via HTTP). Dice rolls are handled by a dedicated `dice.py` — LLMs never self-report rolls. Output is an append-only `Transcript` rendered to markdown for handoff to CampaignGenerator.

**Tech Stack:** Python 3.10+, `anthropic` SDK, Ollama HTTP API (`localhost:11434`), `pytest`, stdlib only for dice/transcript/personas/combat. No new framework deps for Phase A/B.

**Spec:** `docs/superpowers/specs/2026-06-14-ai-table-design.md`  
**Brainstorm:** `reviews/ai-table-gm-and-players-exploration.md` (gitignored)

---

## File Map

| File | Responsibility |
|---|---|
| `table/__init__.py` | Package marker |
| `table/transcript.py` | `TurnRecord` dataclass + `Transcript` append-only log → markdown |
| `table/personas.py` | `Persona` dataclass + `PHASE_A_PERSONAS` / `PHASE_B_PERSONAS` registries |
| `table/dice.py` | `RollRequest` dataclass, `local_roll()`, `request_roll()` (Foundry fallback) |
| `table/combat.py` | `Combatant` dataclass, `CombatState` (initiative, HP ledger, conditions, end_condition) |
| `table/player_agent.py` | `PlayerTurn` dataclass, `PlayerAgent.take_turn()` via Ollama |
| `table/gm_agent.py` | `GMTurn` dataclass, `GMAgent.narrate()` via Claude Sonnet |
| `table/orchestrator.py` | `TableOrchestrator.run_encounter()` event loop + `__main__` CLI |
| `table/smoke_test.py` | Zero-dep smoke test — validates data flow, exits 0/1 |
| `tests/__init__.py` | Test package marker |
| `tests/table/__init__.py` | Test sub-package marker |
| `tests/table/test_transcript.py` | Unit tests for `Transcript` + `TurnRecord` |
| `tests/table/test_personas.py` | Unit tests for persona registry |
| `tests/table/test_dice.py` | Unit tests for `local_roll` + `request_roll` fallback |
| `tests/table/test_combat.py` | Unit tests for `CombatState` transitions and `end_condition` |
| `tests/table/test_player_agent.py` | Unit tests for `PlayerAgent` with mocked Ollama |
| `tests/table/test_gm_agent.py` | Unit tests for `GMAgent` with mocked Anthropic client |
| `tests/table/test_orchestrator.py` | Integration tests with mocked GM + mocked players |
| `requirements-table.txt` | Runtime deps for the table module |

---

## Task 1: Package scaffold + transcript.py

**Files:**
- Create: `table/__init__.py`
- Create: `table/transcript.py`
- Create: `tests/__init__.py`
- Create: `tests/table/__init__.py`
- Create: `tests/table/test_transcript.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_transcript.py
from table.transcript import Transcript, TurnRecord


def test_append_and_len():
    t = Transcript()
    assert len(t) == 0
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="Begin!"))
    assert len(t) == 1


def test_tail_returns_last_n():
    t = Transcript()
    for i in range(10):
        t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text=f"turn {i}"))
    tail = t.tail(3)
    assert len(tail) == 3
    assert tail[0].text == "turn 7"
    assert tail[-1].text == "turn 9"


def test_tail_fewer_than_n():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="only"))
    assert len(t.tail(10)) == 1


def test_to_markdown_contains_speaker_and_text():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="The goblin lunges!"))
    t.append(TurnRecord(round=1, actor="Brakka", kind="player_action", text="I charge!"))
    md = t.to_markdown()
    assert "GM" in md
    assert "The goblin lunges!" in md
    assert "Brakka" in md
    assert "I charge!" in md


def test_to_markdown_has_round_header():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="Round 1 starts."))
    t.append(TurnRecord(round=2, actor="GM", kind="gm_narration", text="Round 2 starts."))
    md = t.to_markdown()
    assert "Round 1" in md
    assert "Round 2" in md


def test_turn_record_metadata_defaults_empty():
    r = TurnRecord(round=1, actor="GM", kind="gm_narration", text="hi")
    assert r.metadata == {}


def test_roll_result_shown_in_markdown():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="Brakka", kind="roll_result", text="attack roll: 17",
                        metadata={"formula": "1d20+3", "result": 17}))
    md = t.to_markdown()
    assert "17" in md
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_transcript.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'table'`

- [ ] **Step 3: Create package files and implement transcript.py**

```python
# table/__init__.py
# (empty)
```

```python
# tests/__init__.py
# (empty)
```

```python
# tests/table/__init__.py
# (empty)
```

```python
# table/transcript.py
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TurnRecord:
    round: int
    actor: str
    kind: Literal["gm_narration", "player_action", "roll_result", "scene_update"]
    text: str
    metadata: dict = field(default_factory=dict)


class Transcript:
    def __init__(self) -> None:
        self._records: list[TurnRecord] = []

    def append(self, record: TurnRecord) -> None:
        self._records.append(record)

    def tail(self, n: int) -> list[TurnRecord]:
        return self._records[-n:]

    def __len__(self) -> int:
        return len(self._records)

    def to_markdown(self) -> str:
        lines: list[str] = []
        current_round = -1
        for r in self._records:
            if r.round != current_round:
                current_round = r.round
                lines.append(f"\n## Round {r.round}\n")
            if r.kind == "roll_result":
                lines.append(f"**[ROLL]** {r.actor}: {r.text}")
            else:
                lines.append(f"**{r.actor}:** {r.text}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_transcript.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add table/__init__.py table/transcript.py tests/__init__.py tests/table/__init__.py tests/table/test_transcript.py
git commit -m "feat(table): package scaffold + transcript.py (TurnRecord, Transcript)"
```

---

## Task 2: personas.py

**Files:**
- Create: `table/personas.py`
- Create: `tests/table/test_personas.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_personas.py
from table.personas import Persona, PHASE_A_PERSONAS, PHASE_B_PERSONAS


def test_phase_a_has_two_personas():
    assert len(PHASE_A_PERSONAS) == 2


def test_phase_a_first_is_barbarian():
    assert PHASE_A_PERSONAS[0].cls == "Barbarian"
    assert PHASE_A_PERSONAS[0].name == "Brakka Stonefist"


def test_phase_a_second_is_wizard():
    assert PHASE_A_PERSONAS[1].cls == "Wizard"
    assert PHASE_A_PERSONAS[1].name == "Elara Moonwhisper"


def test_phase_b_has_five_personas():
    assert len(PHASE_B_PERSONAS) == 5


def test_phase_b_starts_with_phase_a():
    assert PHASE_B_PERSONAS[:2] == PHASE_A_PERSONAS


def test_phase_b_includes_rogue_cleric_bard():
    classes = {p.cls for p in PHASE_B_PERSONAS}
    assert "Rogue" in classes
    assert "Cleric" in classes
    assert "Bard" in classes


def test_persona_personality_is_nonempty():
    for p in PHASE_B_PERSONAS:
        assert p.personality, f"{p.name} has empty personality"


def test_persona_level_is_one():
    for p in PHASE_B_PERSONAS:
        assert p.level == 1


def test_persona_optional_fields_default_none():
    p = Persona(name="Test", cls="Fighter", level=1, personality="brave")
    assert p.foundry_actor_id is None
    assert p.voice is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_personas.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'table.personas'`

- [ ] **Step 3: Implement personas.py**

```python
# table/personas.py
from dataclasses import dataclass


@dataclass
class Persona:
    name: str
    cls: str
    level: int
    personality: str
    foundry_actor_id: str | None = None
    voice: str | None = None


PHASE_A_PERSONAS: list[Persona] = [
    Persona(
        name="Brakka Stonefist",
        cls="Barbarian",
        level=1,
        personality=(
            "Reckless, loyal, allergic to plans. Solves problems by hitting them. "
            "Distrusts magic. Speaks in short, blunt sentences. Always charges first. "
            "Secret goal: prove herself to the clan she was exiled from."
        ),
    ),
    Persona(
        name="Elara Moonwhisper",
        cls="Wizard",
        level=1,
        personality=(
            "Cautious, analytical, hoards spell slots for emergencies. Speaks in "
            "precise, measured sentences. Suspicious of the barbarian's recklessness. "
            "Secret goal: find evidence of an ancient spell catastrophe in the area."
        ),
    ),
]

PHASE_B_PERSONAS: list[Persona] = PHASE_A_PERSONAS + [
    Persona(
        name="Brother Aldric",
        cls="Cleric",
        level=1,
        personality=(
            "Devout, protective, slow to anger. Heals first, asks questions after. "
            "Speaks in formal, slightly archaic prose. "
            "Secret goal: atone for a failure that cost a companion their life."
        ),
    ),
    Persona(
        name="Silk",
        cls="Rogue",
        level=1,
        personality=(
            "Cynical, self-interested, charming when convenient. Never trusts the "
            "GM's read of a situation. Speaks in clipped sentences with dry humor. "
            "Secret goal: pocket the best loot before anyone notices."
        ),
    ),
    Persona(
        name="Finn the Fortunate",
        cls="Bard",
        level=1,
        personality=(
            "Optimistic, verbose, narrates everything in the third person. Treats "
            "danger as dramatic opportunity. Speaks in flowing, theatrical sentences. "
            "Secret goal: compose a ballad about this adventure and make it famous."
        ),
    ),
]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_personas.py -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add table/personas.py tests/table/test_personas.py
git commit -m "feat(table): personas.py — Phase A (2) and Phase B (5) persona registries"
```

---

## Task 3: dice.py

**Files:**
- Create: `table/dice.py`
- Create: `tests/table/test_dice.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_dice.py
import pytest
from table.dice import local_roll, request_roll, RollRequest


def test_local_roll_1d20_in_range():
    for _ in range(50):
        r = local_roll("1d20")
        assert 1 <= r <= 20


def test_local_roll_2d6_plus_3_in_range():
    for _ in range(50):
        r = local_roll("2d6+3")
        assert 5 <= r <= 15


def test_local_roll_1d20_minus_1_in_range():
    for _ in range(50):
        r = local_roll("1d20-1")
        assert 0 <= r <= 19


def test_local_roll_invalid_formula_raises():
    with pytest.raises(ValueError, match="Invalid roll formula"):
        local_roll("roll the dice")


def test_local_roll_1d1_returns_one():
    assert local_roll("1d1") == 1


def test_request_roll_uses_local_when_foundry_disabled():
    req = RollRequest(actor="Brakka", formula="1d20+3", purpose="attack")
    result = request_roll(req, use_foundry=False)
    assert 4 <= result <= 23


def test_roll_request_fields():
    req = RollRequest(actor="Elara", formula="1d8+2", purpose="spell damage")
    assert req.actor == "Elara"
    assert req.formula == "1d8+2"
    assert req.purpose == "spell damage"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_dice.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'table.dice'`

- [ ] **Step 3: Implement dice.py**

```python
# table/dice.py
import re
import random
from dataclasses import dataclass


@dataclass
class RollRequest:
    actor: str
    formula: str   # e.g. "1d20+3"
    purpose: str   # e.g. "attack roll"


def local_roll(formula: str) -> int:
    """Parse NdX[+-]Y and return sum. No external dependencies."""
    match = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", formula.strip())
    if not match:
        raise ValueError(f"Invalid roll formula: {formula!r}")
    n = int(match.group(1))
    x = int(match.group(2))
    mod = int(match.group(3)) if match.group(3) else 0
    return sum(random.randint(1, x) for _ in range(n)) + mod


def request_roll(req: RollRequest, *, use_foundry: bool = True) -> int:
    """Roll dice via Foundry MCP, falling back to local_roll."""
    if use_foundry:
        try:
            return _foundry_roll(req)
        except Exception:
            pass
    return local_roll(req.formula)


def _foundry_roll(req: RollRequest) -> int:
    """Invoke Foundry MCP request-player-rolls. Raises on any failure."""
    # Foundry MCP is accessed through the Claude Code MCP client at runtime.
    # In tests, mock this function. In production, the MCP bridge handles the call.
    raise NotImplementedError("Foundry roll requires a live MCP connection")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_dice.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add table/dice.py tests/table/test_dice.py
git commit -m "feat(table): dice.py — local_roll + request_roll with Foundry fallback"
```

---

## Task 4: combat.py

**Files:**
- Create: `table/combat.py`
- Create: `tests/table/test_combat.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_combat.py
import pytest
from table.combat import CombatState, Combatant


def _make_state(max_rounds=20):
    combatants = [
        Combatant(name="Brakka", max_hp=13, current_hp=13, initiative=14, is_player=True),
        Combatant(name="Goblin A", max_hp=7, current_hp=7, initiative=10, is_player=False),
        Combatant(name="Elara", max_hp=7, current_hp=7, initiative=8, is_player=True),
    ]
    return CombatState(combatants, max_rounds=max_rounds)


def test_initiative_order_descending():
    state = _make_state()
    names = [c.name for c in state.initiative_order]
    assert names == ["Brakka", "Goblin A", "Elara"]


def test_no_end_condition_at_start():
    assert _make_state().end_condition() is None


def test_party_wins_when_all_monsters_dead():
    state = _make_state()
    state.apply_hp_delta("Goblin A", -7)
    assert state.end_condition() == "party_wins"


def test_tpk_when_all_players_dead():
    state = _make_state()
    state.apply_hp_delta("Brakka", -13)
    state.apply_hp_delta("Elara", -7)
    assert state.end_condition() == "tpk"


def test_round_limit_when_max_rounds_reached():
    state = _make_state(max_rounds=1)
    # advance through all 3 combatants to complete round 1
    state.advance_turn()
    state.advance_turn()
    state.advance_turn()
    assert state.end_condition() == "round_limit"


def test_apply_hp_delta_damage_floors_at_zero():
    state = _make_state()
    state.apply_hp_delta("Goblin A", -100)
    goblin = next(c for c in state.combatants if c.name == "Goblin A")
    assert goblin.current_hp == 0


def test_apply_hp_delta_healing_caps_at_max():
    state = _make_state()
    state.apply_hp_delta("Brakka", -5)   # take 5 damage → 8 HP
    state.apply_hp_delta("Brakka", +10)  # heal 10 → should cap at max_hp 13
    brakka = next(c for c in state.combatants if c.name == "Brakka")
    assert brakka.current_hp == 13


def test_add_condition():
    state = _make_state()
    state.add_condition("Brakka", "prone")
    brakka = next(c for c in state.combatants if c.name == "Brakka")
    assert "prone" in brakka.conditions


def test_add_condition_no_duplicates():
    state = _make_state()
    state.add_condition("Brakka", "prone")
    state.add_condition("Brakka", "prone")
    brakka = next(c for c in state.combatants if c.name == "Brakka")
    assert brakka.conditions.count("prone") == 1


def test_apply_hp_delta_unknown_name_raises():
    state = _make_state()
    with pytest.raises(ValueError, match="Unknown combatant"):
        state.apply_hp_delta("Nobody", -1)


def test_current_actor_cycles():
    state = _make_state()
    assert state.current_actor().name == "Brakka"
    state.advance_turn()
    assert state.current_actor().name == "Goblin A"
    state.advance_turn()
    assert state.current_actor().name == "Elara"
    state.advance_turn()
    assert state.current_actor().name == "Brakka"  # wraps


def test_round_increments_after_full_cycle():
    state = _make_state()
    assert state.round == 0
    state.advance_turn()
    state.advance_turn()
    state.advance_turn()
    assert state.round == 1


def test_to_dict_structure():
    state = _make_state()
    d = state.to_dict()
    assert "round" in d
    assert "combatants" in d
    assert d["combatants"][0]["name"] == "Brakka"
    assert d["combatants"][0]["hp"] == 13
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_combat.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'table.combat'`

- [ ] **Step 3: Implement combat.py**

```python
# table/combat.py
from dataclasses import dataclass, field


@dataclass
class Combatant:
    name: str
    max_hp: int
    current_hp: int
    initiative: int
    is_player: bool
    conditions: list[str] = field(default_factory=list)


class CombatState:
    def __init__(self, combatants: list[Combatant], max_rounds: int = 20) -> None:
        self.combatants = sorted(combatants, key=lambda c: -c.initiative)
        self.max_rounds = max_rounds
        self.round = 0
        self._turn_index = 0

    @property
    def initiative_order(self) -> list[Combatant]:
        return self.combatants

    def current_actor(self) -> Combatant:
        return self.combatants[self._turn_index % len(self.combatants)]

    def advance_turn(self) -> None:
        self._turn_index += 1
        if self._turn_index % len(self.combatants) == 0:
            self.round += 1

    def apply_hp_delta(self, target_name: str, delta: int) -> None:
        """Apply HP change. Negative = damage, positive = healing. Clamps to [0, max_hp]."""
        for c in self.combatants:
            if c.name == target_name:
                c.current_hp = max(0, min(c.max_hp, c.current_hp + delta))
                return
        raise ValueError(f"Unknown combatant: {target_name!r}")

    def add_condition(self, target_name: str, condition: str) -> None:
        for c in self.combatants:
            if c.name == target_name:
                if condition not in c.conditions:
                    c.conditions.append(condition)
                return
        raise ValueError(f"Unknown combatant: {target_name!r}")

    def end_condition(self) -> str | None:
        """Returns 'party_wins', 'tpk', 'round_limit', or None if combat continues."""
        monsters = [c for c in self.combatants if not c.is_player]
        players = [c for c in self.combatants if c.is_player]
        if all(m.current_hp <= 0 for m in monsters):
            return "party_wins"
        if all(p.current_hp <= 0 for p in players):
            return "tpk"
        if self.round >= self.max_rounds:
            return "round_limit"
        return None

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "combatants": [
                {
                    "name": c.name,
                    "hp": c.current_hp,
                    "max_hp": c.max_hp,
                    "initiative": c.initiative,
                    "is_player": c.is_player,
                    "conditions": c.conditions,
                }
                for c in self.combatants
            ],
        }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_combat.py -v
```

Expected: 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add table/combat.py tests/table/test_combat.py
git commit -m "feat(table): combat.py — CombatState with HP ledger, initiative order, end conditions"
```

---

## Task 5: player_agent.py

**Files:**
- Create: `table/player_agent.py`
- Create: `tests/table/test_player_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_player_agent.py
import json
from unittest.mock import patch, MagicMock
from table.player_agent import PlayerAgent, PlayerTurn, OLLAMA_MODEL
from table.personas import PHASE_A_PERSONAS
from table.transcript import TurnRecord


def _make_ollama_response(speech, action_type, target, roll_needed):
    content = json.dumps({
        "speech": speech,
        "action_type": action_type,
        "target": target,
        "roll_needed": roll_needed,
    })
    return {"message": {"content": content}}


def _mock_urlopen(response_dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_dict).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_take_turn_returns_player_turn():
    persona = PHASE_A_PERSONAS[0]
    agent = PlayerAgent(persona)
    mock_response = _make_ollama_response("I charge the goblin!", "attack", "Goblin A", True)

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(mock_response)):
        result = agent.take_turn(
            scene_state={"round": 1, "combatants": []},
            gm_narration="The goblin lunges at you, Brakka!",
            transcript_tail=[],
        )

    assert isinstance(result, PlayerTurn)
    assert result.actor == "Brakka Stonefist"
    assert result.speech == "I charge the goblin!"
    assert result.action_type == "attack"
    assert result.target == "Goblin A"
    assert result.roll_needed is True


def test_take_turn_falls_back_on_malformed_json():
    persona = PHASE_A_PERSONAS[1]
    agent = PlayerAgent(persona)
    # LLM returns prose wrapping JSON
    wrapped = 'Sure! Here is my response: {"speech": "I cast Fire Bolt", "action_type": "spell", "target": "Goblin B", "roll_needed": true}'
    mock_response = {"message": {"content": wrapped}}

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(mock_response)):
        result = agent.take_turn({}, "Your turn Elara.", [])

    assert result.speech == "I cast Fire Bolt"
    assert result.action_type == "spell"


def test_take_turn_pass_on_completely_invalid_response():
    persona = PHASE_A_PERSONAS[0]
    agent = PlayerAgent(persona)
    mock_response = {"message": {"content": "I dunno what to do."}}

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(mock_response)):
        result = agent.take_turn({}, "Your turn.", [])

    assert result.action_type == "pass"
    assert result.roll_needed is False


def test_transcript_tail_included_in_prompt():
    persona = PHASE_A_PERSONAS[0]
    agent = PlayerAgent(persona)
    tail = [TurnRecord(round=1, actor="GM", kind="gm_narration", text="A goblin appears!")]
    captured_payload = {}

    def fake_urlopen(req, **kwargs):
        captured_payload["body"] = json.loads(req.data)
        return _mock_urlopen(_make_ollama_response("I attack", "attack", "Goblin A", True))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        agent.take_turn({}, "Your move.", tail)

    messages = captured_payload["body"]["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "A goblin appears!" in user_content


def test_system_prompt_contains_persona_name():
    persona = PHASE_A_PERSONAS[0]
    agent = PlayerAgent(persona)
    captured_payload = {}

    def fake_urlopen(req, **kwargs):
        captured_payload["body"] = json.loads(req.data)
        return _mock_urlopen(_make_ollama_response("charge", "attack", None, True))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        agent.take_turn({}, "Go.", [])

    messages = captured_payload["body"]["messages"]
    system_content = next(m["content"] for m in messages if m["role"] == "system")
    assert "Brakka Stonefist" in system_content
    assert "Barbarian" in system_content


def test_ollama_model_used():
    persona = PHASE_A_PERSONAS[0]
    agent = PlayerAgent(persona)
    captured_payload = {}

    def fake_urlopen(req, **kwargs):
        captured_payload["body"] = json.loads(req.data)
        return _mock_urlopen(_make_ollama_response("go", "attack", None, False))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        agent.take_turn({}, "Go.", [])

    assert captured_payload["body"]["model"] == OLLAMA_MODEL
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_player_agent.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'table.player_agent'`

- [ ] **Step 3: Implement player_agent.py**

```python
# table/player_agent.py
import json
import re
import urllib.request
from dataclasses import dataclass

from table.personas import Persona
from table.transcript import TurnRecord

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
TRANSCRIPT_TAIL = 6


@dataclass
class PlayerTurn:
    actor: str
    speech: str
    action_type: str   # "attack" | "spell" | "skill" | "move" | "pass"
    target: str | None
    roll_needed: bool


class PlayerAgent:
    def __init__(self, persona: Persona, ollama_url: str = OLLAMA_URL) -> None:
        self.persona = persona
        self._ollama_url = ollama_url

    def take_turn(
        self,
        scene_state: dict,
        gm_narration: str,
        transcript_tail: list[TurnRecord],
    ) -> PlayerTurn:
        system = self._build_system()
        user = self._build_user(scene_state, gm_narration, transcript_tail)
        raw = self._call_ollama(system, user)
        return self._parse_response(raw)

    def _build_system(self) -> str:
        return (
            f"You are {self.persona.name}, a level {self.persona.level} "
            f"{self.persona.cls}.\n{self.persona.personality}\n\n"
            "Stay in character at all times. Declare your intent and speech only — "
            "never roll your own dice or decide the outcome of rolls.\n"
            'Respond as JSON: {"speech": str, "action_type": str, '
            '"target": str|null, "roll_needed": bool}'
        )

    def _build_user(
        self,
        scene_state: dict,
        gm_narration: str,
        tail: list[TurnRecord],
    ) -> str:
        tail_text = "\n".join(f"[{r.actor}]: {r.text}" for r in tail)
        return (
            f"Scene state:\n{json.dumps(scene_state, indent=2)}\n\n"
            f"Recent transcript:\n{tail_text}\n\n"
            f"GM: {gm_narration}\n\nYour turn, {self.persona.name}:"
        )

    def _call_ollama(self, system: str, user: str) -> str:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            self._ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]

    def _parse_response(self, raw: str) -> PlayerTurn:
        obj: dict = {}
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return PlayerTurn(
            actor=self.persona.name,
            speech=obj.get("speech", ""),
            action_type=obj.get("action_type", "pass"),
            target=obj.get("target"),
            roll_needed=bool(obj.get("roll_needed", False)),
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_player_agent.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add table/player_agent.py tests/table/test_player_agent.py
git commit -m "feat(table): player_agent.py — PlayerAgent via Ollama HTTP with persona system prompt"
```

---

## Task 6: gm_agent.py

**Files:**
- Create: `table/gm_agent.py`
- Create: `tests/table/test_gm_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_gm_agent.py
import json
from unittest.mock import MagicMock, patch
from table.gm_agent import GMAgent, GMTurn
from table.dice import RollRequest
from table.transcript import TurnRecord


def _make_mock_client(narration, next_actor, roll_request=None, scene_update=None):
    response_json = json.dumps({
        "narration": narration,
        "next_actor": next_actor,
        "roll_request": roll_request,
        "scene_update": scene_update or {"hp_delta": {}, "conditions": {}},
    })
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=response_json)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


def test_narrate_returns_gm_turn():
    client = _make_mock_client("The goblin lunges!", "Brakka Stonefist")
    agent = GMAgent(client=client)
    result = agent.narrate(scene_state={}, transcript_tail=[])
    assert isinstance(result, GMTurn)
    assert result.narration == "The goblin lunges!"
    assert result.next_actor == "Brakka Stonefist"
    assert result.roll_request is None


def test_narrate_parses_roll_request():
    client = _make_mock_client(
        "Roll to attack!",
        "Brakka Stonefist",
        roll_request={"actor": "Brakka Stonefist", "formula": "1d20+3", "purpose": "attack roll"},
    )
    agent = GMAgent(client=client)
    result = agent.narrate(scene_state={}, transcript_tail=[])
    assert isinstance(result.roll_request, RollRequest)
    assert result.roll_request.formula == "1d20+3"
    assert result.roll_request.actor == "Brakka Stonefist"


def test_narrate_parses_scene_update():
    client = _make_mock_client(
        "The goblin is hit!",
        "ALL",
        scene_update={"hp_delta": {"Goblin A": -5}, "conditions": {}},
    )
    agent = GMAgent(client=client)
    result = agent.narrate(scene_state={}, transcript_tail=[])
    assert result.scene_update["hp_delta"]["Goblin A"] == -5


def test_narrate_falls_back_on_malformed_json():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(
        text='Here is the GM narration: {"narration": "The fight begins.", "next_actor": "Elara", "roll_request": null, "scene_update": {"hp_delta": {}, "conditions": {}}}'
    )]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    agent = GMAgent(client=mock_client)
    result = agent.narrate({}, [])
    assert result.narration == "The fight begins."


def test_narrate_passes_scene_state_and_tail_to_api():
    client = _make_mock_client("ok", "ALL")
    agent = GMAgent(client=client)
    tail = [TurnRecord(round=1, actor="Brakka", kind="player_action", text="I charge!")]
    agent.narrate(scene_state={"round": 1}, transcript_tail=tail)

    call_kwargs = client.messages.create.call_args
    user_content = call_kwargs[1]["messages"][0]["content"]
    assert "round" in user_content
    assert "I charge!" in user_content


def test_narrate_cue_actor_included_in_prompt():
    client = _make_mock_client("ok", "Elara")
    agent = GMAgent(client=client)
    agent.narrate({}, [], cue_actor="Elara")

    call_kwargs = client.messages.create.call_args
    user_content = call_kwargs[1]["messages"][0]["content"]
    assert "Elara" in user_content


def test_narrate_last_action_included_in_prompt():
    client = _make_mock_client("ok", "ALL")
    agent = GMAgent(client=client)
    agent.narrate({}, [], last_action="Brakka rolled 17 for attack")

    call_kwargs = client.messages.create.call_args
    user_content = call_kwargs[1]["messages"][0]["content"]
    assert "17" in user_content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_gm_agent.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'table.gm_agent'`

- [ ] **Step 3: Implement gm_agent.py**

```python
# table/gm_agent.py
import json
import os
import re
from dataclasses import dataclass

import anthropic

from table.dice import RollRequest
from table.transcript import TurnRecord

GM_MODEL = "claude-sonnet-4-6"
WORLD_STATE_PATH = "docs/world_state.md"
WORLD_STATE_CHAR_LIMIT = 2000


@dataclass
class GMTurn:
    narration: str
    next_actor: str   # player name or "ALL"
    roll_request: RollRequest | None
    scene_update: dict  # {"hp_delta": {name: int}, "conditions": {name: [str]}}


class GMAgent:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._world_state = self._load_world_state()

    def narrate(
        self,
        scene_state: dict,
        transcript_tail: list[TurnRecord],
        *,
        cue_actor: str | None = None,
        last_action: str | None = None,
    ) -> GMTurn:
        system = self._build_system()
        user = self._build_user(scene_state, transcript_tail, cue_actor, last_action)
        message = self._client.messages.create(
            model=GM_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return self._parse_response(message.content[0].text)

    def adjudicate(self, rule_question: str) -> str:
        from rag import answer
        return answer(rule_question)

    def _load_world_state(self) -> str:
        try:
            with open(WORLD_STATE_PATH) as f:
                return f.read()[:WORLD_STATE_CHAR_LIMIT]
        except FileNotFoundError:
            return ""

    def _build_system(self) -> str:
        world_snippet = self._world_state or "(no world state loaded)"
        return (
            "You are the Game Master for a D&D 5e encounter set in The Shattered Realm.\n"
            "Adjudicate rules strictly per SRD 5.2.1. Never invent dice results — "
            "always emit a roll_request when a roll is needed.\n"
            "Always name who acts next in next_actor.\n\n"
            f"World context:\n{world_snippet}\n\n"
            "Respond ONLY as JSON:\n"
            '{"narration": str, "next_actor": str, '
            '"roll_request": {"actor": str, "formula": str, "purpose": str} | null, '
            '"scene_update": {"hp_delta": {name: int}, "conditions": {name: [str]}}}'
        )

    def _build_user(
        self,
        scene_state: dict,
        tail: list[TurnRecord],
        cue_actor: str | None,
        last_action: str | None,
    ) -> str:
        tail_text = "\n".join(f"[{r.actor}]: {r.text}" for r in tail)
        parts = [
            f"Scene state:\n{json.dumps(scene_state, indent=2)}",
            f"Recent transcript:\n{tail_text}",
        ]
        if last_action:
            parts.append(f"Last action result: {last_action}")
        if cue_actor:
            parts.append(f"Address your narration to: {cue_actor}")
        return "\n\n".join(parts)

    def _parse_response(self, raw: str) -> GMTurn:
        obj: dict = {}
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        rr = obj.get("roll_request")
        roll_req = (
            RollRequest(actor=rr["actor"], formula=rr["formula"], purpose=rr["purpose"])
            if rr else None
        )
        return GMTurn(
            narration=obj.get("narration", ""),
            next_actor=obj.get("next_actor", "ALL"),
            roll_request=roll_req,
            scene_update=obj.get("scene_update", {"hp_delta": {}, "conditions": {}}),
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_gm_agent.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add table/gm_agent.py tests/table/test_gm_agent.py
git commit -m "feat(table): gm_agent.py — GMAgent via Claude Sonnet with world state grounding"
```

---

## Task 7: orchestrator.py

**Files:**
- Create: `table/orchestrator.py`
- Create: `tests/table/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/table/test_orchestrator.py
from unittest.mock import MagicMock
from table.orchestrator import TableOrchestrator, _build_goblin_ambush, _apply_scene_update
from table.gm_agent import GMTurn
from table.player_agent import PlayerTurn
from table.combat import CombatState, Combatant
from table.personas import PHASE_A_PERSONAS
from table.dice import RollRequest
from table.transcript import Transcript


def _mock_gm(narration="The goblin acts.", next_actor="Brakka Stonefist",
             roll_request=None, scene_update=None):
    gm = MagicMock()
    gm.narrate.return_value = GMTurn(
        narration=narration,
        next_actor=next_actor,
        roll_request=roll_request,
        scene_update=scene_update or {"hp_delta": {}, "conditions": {}},
    )
    return gm


def _mock_player(persona, speech="I charge!", action_type="attack",
                 target="Goblin A", roll_needed=False):
    player = MagicMock()
    player.persona = persona
    player.take_turn.return_value = PlayerTurn(
        actor=persona.name,
        speech=speech,
        action_type=action_type,
        target=target,
        roll_needed=roll_needed,
    )
    return player


def _one_sided_combat():
    """Goblins start at 0HP so party_wins immediately after first check."""
    return CombatState([
        Combatant("Brakka Stonefist", 13, 13, 14, is_player=True),
        Combatant("Goblin A", 7, 0, 10, is_player=False),  # already dead
    ], max_rounds=20)


def test_run_encounter_returns_transcript():
    gm = _mock_gm()
    players = [_mock_player(p) for p in PHASE_A_PERSONAS]
    orch = TableOrchestrator(gm, players, use_foundry=False)
    result = orch.run_encounter(_one_sided_combat())
    assert isinstance(result, Transcript)


def test_run_encounter_ends_on_party_wins():
    gm = _mock_gm()
    players = [_mock_player(p) for p in PHASE_A_PERSONAS]
    orch = TableOrchestrator(gm, players, use_foundry=False)
    transcript = orch.run_encounter(_one_sided_combat())
    # Final record metadata should contain end_condition
    last = transcript.tail(1)[0]
    assert last.metadata.get("end_condition") == "party_wins"


def test_run_encounter_records_player_action():
    combat = CombatState([
        Combatant("Brakka Stonefist", 13, 13, 14, is_player=True),
        Combatant("Goblin A", 7, 1, 10, is_player=False),
    ], max_rounds=1)
    gm = _mock_gm(scene_update={"hp_delta": {"Goblin A": -1}, "conditions": {}})
    players = [_mock_player(PHASE_A_PERSONAS[0])]
    orch = TableOrchestrator(gm, players, use_foundry=False)
    transcript = orch.run_encounter(combat)
    kinds = {r.kind for r in transcript.tail(20)}
    assert "player_action" in kinds


def test_run_encounter_calls_dice_for_roll_needed():
    combat = CombatState([
        Combatant("Brakka Stonefist", 13, 13, 14, is_player=True),
        Combatant("Goblin A", 7, 1, 10, is_player=False),
    ], max_rounds=1)
    gm = _mock_gm()
    player = _mock_player(PHASE_A_PERSONAS[0], roll_needed=True)
    orch = TableOrchestrator(gm, [player], use_foundry=False)
    transcript = orch.run_encounter(combat)
    kinds = [r.kind for r in transcript.tail(20)]
    assert "roll_result" in kinds


def test_apply_scene_update_applies_hp_delta():
    combat = CombatState([
        Combatant("Goblin A", 7, 7, 10, is_player=False),
    ])
    _apply_scene_update(combat, {"hp_delta": {"Goblin A": -5}, "conditions": {}})
    goblin = next(c for c in combat.combatants if c.name == "Goblin A")
    assert goblin.current_hp == 2


def test_apply_scene_update_applies_conditions():
    combat = CombatState([
        Combatant("Brakka Stonefist", 13, 13, 14, is_player=True),
    ])
    _apply_scene_update(combat, {"hp_delta": {}, "conditions": {"Brakka Stonefist": ["prone"]}})
    brakka = next(c for c in combat.combatants if c.name == "Brakka Stonefist")
    assert "prone" in brakka.conditions


def test_build_goblin_ambush_returns_combat_state():
    state = _build_goblin_ambush()
    names = {c.name for c in state.combatants}
    assert "Goblin A" in names
    assert "Goblin B" in names
    assert "Goblin C" in names
    assert "Brakka Stonefist" in names
    assert "Elara Moonwhisper" in names


def test_round_limit_combat_terminates():
    combat = CombatState([
        Combatant("Brakka Stonefist", 13, 13, 14, is_player=True),
        Combatant("Goblin A", 7, 7, 10, is_player=False),
    ], max_rounds=1)
    gm = _mock_gm()
    players = [_mock_player(PHASE_A_PERSONAS[0])]
    orch = TableOrchestrator(gm, players, use_foundry=False)
    transcript = orch.run_encounter(combat)
    last = transcript.tail(1)[0]
    assert last.metadata.get("end_condition") in {"round_limit", "party_wins", "tpk"}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_orchestrator.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'table.orchestrator'`

- [ ] **Step 3: Implement orchestrator.py**

```python
# table/orchestrator.py
import argparse

from table.combat import CombatState, Combatant
from table.dice import RollRequest, request_roll
from table.gm_agent import GMAgent
from table.personas import PHASE_A_PERSONAS, PHASE_B_PERSONAS
from table.player_agent import PlayerAgent
from table.transcript import Transcript, TurnRecord

MAX_ROUNDS = 20


def _apply_scene_update(state: CombatState, scene_update: dict) -> None:
    for name, delta in scene_update.get("hp_delta", {}).items():
        state.apply_hp_delta(name, delta)
    for name, conds in scene_update.get("conditions", {}).items():
        for cond in conds:
            state.add_condition(name, cond)


class TableOrchestrator:
    def __init__(
        self,
        gm: GMAgent,
        players: list[PlayerAgent],
        use_foundry: bool = True,
    ) -> None:
        self.gm = gm
        self.players = {p.persona.name: p for p in players}
        self.use_foundry = use_foundry

    def run_encounter(self, combat: CombatState) -> Transcript:
        transcript = Transcript()

        while combat.end_condition() is None:
            actor = combat.current_actor()
            tail = transcript.tail(6)

            if not actor.is_player:
                gm_turn = self.gm.narrate(
                    combat.to_dict(), tail,
                    last_action=f"Monster {actor.name} acts",
                )
                _apply_scene_update(combat, gm_turn.scene_update)
                transcript.append(TurnRecord(
                    round=combat.round, actor="GM",
                    kind="gm_narration", text=gm_turn.narration,
                    metadata={"next_actor": gm_turn.next_actor,
                               "scene_update": gm_turn.scene_update},
                ))
                if gm_turn.roll_request:
                    roll = request_roll(gm_turn.roll_request, use_foundry=self.use_foundry)
                    transcript.append(TurnRecord(
                        round=combat.round, actor=gm_turn.roll_request.actor,
                        kind="roll_result",
                        text=f"{gm_turn.roll_request.purpose}: {roll}",
                        metadata={"formula": gm_turn.roll_request.formula, "result": roll},
                    ))
            else:
                player = self.players.get(actor.name)
                if player is None:
                    combat.advance_turn()
                    continue

                gm_cue = self.gm.narrate(combat.to_dict(), tail, cue_actor=actor.name)
                transcript.append(TurnRecord(
                    round=combat.round, actor="GM",
                    kind="gm_narration", text=gm_cue.narration,
                    metadata={"next_actor": actor.name},
                ))

                player_turn = player.take_turn(combat.to_dict(), gm_cue.narration, tail)
                transcript.append(TurnRecord(
                    round=combat.round, actor=actor.name,
                    kind="player_action", text=player_turn.speech,
                    metadata={"action_type": player_turn.action_type,
                               "target": player_turn.target},
                ))

                if player_turn.roll_needed:
                    roll_req = RollRequest(
                        actor=actor.name,
                        formula="1d20",
                        purpose=player_turn.action_type,
                    )
                    roll = request_roll(roll_req, use_foundry=self.use_foundry)
                    transcript.append(TurnRecord(
                        round=combat.round, actor=actor.name,
                        kind="roll_result",
                        text=f"{player_turn.action_type}: {roll}",
                        metadata={"formula": "1d20", "result": roll},
                    ))
                    last_action = (
                        f"{actor.name} rolled {roll} for {player_turn.action_type} "
                        f"targeting {player_turn.target}"
                    )
                else:
                    last_action = f"{actor.name}: {player_turn.speech}"

                gm_followup = self.gm.narrate(
                    combat.to_dict(), transcript.tail(6), last_action=last_action
                )
                _apply_scene_update(combat, gm_followup.scene_update)
                transcript.append(TurnRecord(
                    round=combat.round, actor="GM",
                    kind="gm_narration", text=gm_followup.narration,
                    metadata={"scene_update": gm_followup.scene_update},
                ))

            combat.advance_turn()

        end = combat.end_condition()
        final = self.gm.narrate(
            combat.to_dict(), transcript.tail(6),
            last_action=f"Encounter ended: {end}",
        )
        transcript.append(TurnRecord(
            round=combat.round, actor="GM",
            kind="gm_narration", text=final.narration,
            metadata={"end_condition": end},
        ))
        return transcript


def _build_goblin_ambush() -> CombatState:
    return CombatState([
        Combatant("Brakka Stonefist", max_hp=13, current_hp=13, initiative=14, is_player=True),
        Combatant("Elara Moonwhisper", max_hp=7, current_hp=7, initiative=11, is_player=True),
        Combatant("Goblin A", max_hp=7, current_hp=7, initiative=13, is_player=False),
        Combatant("Goblin B", max_hp=7, current_hp=7, initiative=9, is_player=False),
        Combatant("Goblin C", max_hp=7, current_hp=7, initiative=6, is_player=False),
    ], max_rounds=MAX_ROUNDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an autonomous AI D&D table")
    parser.add_argument("--phase", choices=["A", "B"], default="A",
                        help="Phase A: 2 players / Phase B: 5 players")
    parser.add_argument("--out", default="transcript.md",
                        help="Output markdown file")
    parser.add_argument("--no-foundry", action="store_true",
                        help="Use local dice only (no Foundry MCP)")
    args = parser.parse_args()

    personas = PHASE_A_PERSONAS if args.phase == "A" else PHASE_B_PERSONAS
    gm = GMAgent()
    players = [PlayerAgent(p) for p in personas]
    orch = TableOrchestrator(gm, players, use_foundry=not args.no_foundry)
    combat = _build_goblin_ambush()

    print(f"Starting Phase {args.phase}: {len(personas)} players vs Goblin Ambush")
    transcript = orch.run_encounter(combat)

    md = transcript.to_markdown()
    with open(args.out, "w") as f:
        f.write(md)
    print(f"Done — {len(transcript)} turns. Transcript: {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/test_orchestrator.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Run the full test suite**

```bash
cd /opt/proj/campaign-forge
python -m pytest tests/table/ -v
```

Expected: All tests pass (transcript + personas + dice + combat + player_agent + gm_agent + orchestrator).

- [ ] **Step 6: Commit**

```bash
git add table/orchestrator.py tests/table/test_orchestrator.py
git commit -m "feat(table): orchestrator.py — TableOrchestrator event loop + CLI entrypoint"
```

---

## Task 8: smoke_test.py

**Files:**
- Create: `table/smoke_test.py`

- [ ] **Step 1: Implement smoke_test.py**

No failing test first — the smoke test IS the test. It's a self-validating script.

```python
# table/smoke_test.py
"""
Zero-dependency smoke test for the table module.
No Foundry, no Ollama, no Claude API required.
Run: python -m table.smoke_test
Exits 0 on pass, 1 on failure.
"""
import sys
from unittest.mock import MagicMock

from table.transcript import Transcript, TurnRecord
from table.personas import PHASE_A_PERSONAS, PHASE_B_PERSONAS
from table.dice import local_roll, RollRequest, request_roll
from table.combat import CombatState, Combatant
from table.gm_agent import GMTurn
from table.player_agent import PlayerTurn
from table.orchestrator import TableOrchestrator, _apply_scene_update, _build_goblin_ambush


def _mock_gm():
    gm = MagicMock()
    gm.narrate.return_value = GMTurn(
        narration="The goblin swings its scimitar!",
        next_actor="Brakka Stonefist",
        roll_request=None,
        scene_update={"hp_delta": {}, "conditions": {}},
    )
    return gm


def _mock_player(persona):
    player = MagicMock()
    player.persona = persona
    player.take_turn.return_value = PlayerTurn(
        actor=persona.name,
        speech="I slash at the goblin!",
        action_type="attack",
        target="Goblin A",
        roll_needed=False,
    )
    return player


def run() -> None:
    errors: list[str] = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            errors.append(f"FAIL: {label}")

    # 1. Transcript
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="Begin!"))
    check(len(t) == 1, "transcript append and len")
    check(t.tail(5)[0].actor == "GM", "transcript tail")
    md = t.to_markdown()
    check("GM" in md and "Begin!" in md, "transcript to_markdown")

    # 2. Personas
    check(len(PHASE_A_PERSONAS) == 2, "phase A has 2 personas")
    check(len(PHASE_B_PERSONAS) == 5, "phase B has 5 personas")
    check(PHASE_A_PERSONAS[0].cls == "Barbarian", "first persona is Barbarian")

    # 3. Dice
    for _ in range(20):
        r = local_roll("1d20")
        check(1 <= r <= 20, f"local_roll 1d20 in range (got {r})")
    check(local_roll("1d1") == 1, "local_roll 1d1 == 1")
    r = local_roll("2d6+3")
    check(5 <= r <= 15, f"local_roll 2d6+3 in range (got {r})")
    req = RollRequest(actor="Brakka", formula="1d20+3", purpose="attack")
    r = request_roll(req, use_foundry=False)
    check(4 <= r <= 23, f"request_roll 1d20+3 in range (got {r})")

    # 4. CombatState
    state = CombatState([
        Combatant("Brakka", 13, 13, 14, is_player=True),
        Combatant("Goblin", 7, 7, 10, is_player=False),
    ], max_rounds=2)
    check(state.end_condition() is None, "no end condition at start")
    check(state.current_actor().name == "Brakka", "initiative order correct")
    state.apply_hp_delta("Goblin", -7)
    check(state.end_condition() == "party_wins", "party_wins when monster at 0HP")

    # 5. apply_scene_update
    state2 = CombatState([Combatant("Goblin", 7, 7, 10, is_player=False)])
    _apply_scene_update(state2, {"hp_delta": {"Goblin": -3}, "conditions": {}})
    goblin = state2.combatants[0]
    check(goblin.current_hp == 4, f"hp_delta applied correctly (got {goblin.current_hp})")

    # 6. Goblin ambush fixture
    ambush = _build_goblin_ambush()
    names = {c.name for c in ambush.combatants}
    check("Goblin A" in names, "goblin ambush has Goblin A")
    check("Brakka Stonefist" in names, "goblin ambush has Brakka")

    # 7. Orchestrator dry run (mocked — no external calls)
    combat = CombatState([
        Combatant("Brakka Stonefist", 13, 13, 14, is_player=True),
        Combatant("Goblin A", 7, 0, 10, is_player=False),  # already dead → party_wins
    ], max_rounds=20)
    gm = _mock_gm()
    players = [_mock_player(PHASE_A_PERSONAS[0])]
    orch = TableOrchestrator(gm, players, use_foundry=False)
    transcript = orch.run_encounter(combat)
    check(len(transcript) > 0, "orchestrator produced at least one turn")
    last = transcript.tail(1)[0]
    check(last.metadata.get("end_condition") == "party_wins",
          f"end condition is party_wins (got {last.metadata.get('end_condition')})")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    else:
        print(f"smoke_test: all checks passed ({7 + 20 + 3 + 4 + 1 + 2 + 2} assertions)")
        sys.exit(0)


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Run the smoke test**

```bash
cd /opt/proj/campaign-forge
python -m table.smoke_test
```

Expected output: `smoke_test: all checks passed (N assertions)` and exit code 0.

- [ ] **Step 3: Commit**

```bash
git add table/smoke_test.py
git commit -m "feat(table): smoke_test.py — zero-dep data flow validation"
```

---

## Task 9: requirements-table.txt + final wiring

**Files:**
- Create: `requirements-table.txt`

- [ ] **Step 1: Create requirements-table.txt**

```
# table/ module runtime deps (Phase A/B)
# Install: pip install -r requirements-table.txt
# Note: urllib.request, json, re, dataclasses are stdlib — no extra install needed
anthropic>=0.40.0

# Phase C (TTS — not needed for Phase A/B):
# kokoro>=0.9.0
# soundfile>=0.12.0
```

- [ ] **Step 2: Install and verify**

```bash
cd /opt/proj/campaign-forge
python -m venv .venv-table
.venv-table/bin/pip install -r requirements-table.txt
.venv-table/bin/python -m table.smoke_test
```

Expected: smoke test passes in the new venv.

- [ ] **Step 3: Run the full test suite one final time**

```bash
cd /opt/proj/campaign-forge
.venv-table/bin/pip install pytest
.venv-table/bin/python -m pytest tests/table/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add requirements-table.txt
git commit -m "feat(table): requirements-table.txt — anthropic runtime dep for Phase A/B"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by task |
|---|---|
| §2 Phased delivery (A/B/C) | Task 2 (personas) + Task 9 (requirements note Phase C) |
| §3 Module layout (8 files) | All tasks 1–8 |
| §4 Persona dataclass + registries | Task 2 |
| §5.1 GMAgent.narrate, adjudicate, GMTurn | Task 6 |
| §5.2 PlayerAgent.take_turn, PlayerTurn | Task 5 |
| §6 Orchestrator event loop | Task 7 |
| §7 Dice — never LLM self-rolls | Task 3 + Task 7 (roll_needed path) |
| §8 Transcript → markdown | Task 1 |
| §9 Rules grounding via rag.answer | Task 6 (adjudicate method) |
| §10 Gating: smoke_test → dry run → A → B | Task 8 |
| §11 Pre-session setup (kanka_sync, ollama check) | Documented in spec; no new code |
| §12 Out of scope: social scenes, TTS | Confirmed absent — Phase C deps commented in requirements |
| §13 Open question #1 (request-player-rolls actor vs UUID) | `dice._foundry_roll` raises NotImplementedError — investigate before wiring |
| §13 Open question #2 (context window budget) | 6-turn rolling tail used; monitor in Phase B |
| §13 Open question #3 (requirements-table.txt for Phase C) | Task 9 — commented out |

**Placeholder scan:** None found — all steps contain actual code.

**Type consistency check:**
- `RollRequest` defined in `dice.py`, used in `gm_agent.py` and `orchestrator.py` ✓
- `GMTurn.scene_update` is `dict` with `hp_delta`/`conditions` keys — `_apply_scene_update` uses same keys ✓
- `apply_hp_delta` in `combat.py` (not `apply_damage`) — all callers use `apply_hp_delta` ✓
- `PlayerTurn.roll_needed` is `bool` — orchestrator checks `if player_turn.roll_needed:` ✓
- `Transcript.tail(n)` returns `list[TurnRecord]` — all callers use it as such ✓
