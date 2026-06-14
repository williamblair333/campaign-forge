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
