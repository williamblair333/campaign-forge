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
        print(f"smoke_test: all checks passed")
        sys.exit(0)


if __name__ == "__main__":
    run()
