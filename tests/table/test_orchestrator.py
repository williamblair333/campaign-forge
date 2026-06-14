# tests/table/test_orchestrator.py
from unittest.mock import MagicMock
from table.orchestrator import TableOrchestrator, _build_goblin_ambush, _apply_scene_update
from table.gm_agent import GMTurn
from table.player_agent import PlayerTurn
from table.combat import CombatState, Combatant
from table.personas import PHASE_A_PERSONAS
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


def _mock_player(persona, speech="I slash at the goblin!", action_type="attack",
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
