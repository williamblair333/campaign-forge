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


def test_remove_condition():
    state = _make_state()
    state.add_condition("Brakka", "prone")
    state.remove_condition("Brakka", "prone")
    brakka = next(c for c in state.combatants if c.name == "Brakka")
    assert "prone" not in brakka.conditions


def test_remove_condition_noop_when_absent():
    state = _make_state()
    state.remove_condition("Brakka", "prone")  # should not raise
    brakka = next(c for c in state.combatants if c.name == "Brakka")
    assert brakka.conditions == []


def test_remove_condition_unknown_name_raises():
    state = _make_state()
    with pytest.raises(ValueError, match="Unknown combatant"):
        state.remove_condition("Nobody", "prone")


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
