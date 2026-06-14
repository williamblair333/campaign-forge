import logging
import pytest
from unittest.mock import patch
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


def test_local_roll_d20_without_leading_digit():
    for _ in range(20):
        r = local_roll("d20")
        assert 1 <= r <= 20


def test_local_roll_d20_plus_modifier_without_leading_digit():
    for _ in range(20):
        r = local_roll("d20+4")
        assert 5 <= r <= 24


def test_local_roll_zero_dice_raises():
    with pytest.raises(ValueError, match="Invalid roll formula"):
        local_roll("0d20")


def test_local_roll_advantage_kh1():
    for _ in range(50):
        r = local_roll("2d20kh1+4")
        assert 5 <= r <= 24


def test_local_roll_disadvantage_kl1():
    for _ in range(50):
        r = local_roll("2d20kl1")
        assert 1 <= r <= 20


def test_local_roll_drop_lowest_dl1():
    for _ in range(50):
        r = local_roll("4d6dl1")
        assert 3 <= r <= 18


def test_local_roll_case_insensitive():
    for _ in range(20):
        r = local_roll("2D20KH1+3")
        assert 4 <= r <= 23


def test_request_roll_fallback_on_unknown_formula(caplog):
    import logging
    req = RollRequest(actor="Brakka", formula="1d20+STR", purpose="attack")
    with caplog.at_level(logging.WARNING):
        result = request_roll(req, use_foundry=False)
    assert 1 <= result <= 20
    assert "1d20+STR" in caplog.text


def test_request_roll_foundry_fallback_uses_local():
    req = RollRequest(actor="Brakka", formula="1d20", purpose="attack")
    # NotImplementedError (stub) should silently fall back
    result = request_roll(req, use_foundry=True)
    assert 1 <= result <= 20


def test_request_roll_logs_warning_on_foundry_error(caplog):
    req = RollRequest(actor="Brakka", formula="1d20", purpose="attack")
    with patch("table.dice._foundry_roll", side_effect=RuntimeError("conn refused")):
        with caplog.at_level(logging.WARNING):
            result = request_roll(req, use_foundry=True)
    assert isinstance(result, int)
    assert "conn refused" in caplog.text
