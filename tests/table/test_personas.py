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
