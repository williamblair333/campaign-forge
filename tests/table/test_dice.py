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
