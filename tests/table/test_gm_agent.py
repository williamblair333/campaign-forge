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
