import json
import os
import subprocess
from unittest.mock import MagicMock, patch
from table.gm_agent import (
    GMAgent, CLIGMAgent, OllamaGMAgent, GMTurn, make_gm_agent,
)
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
    assert result.roll_request.target is None


def test_narrate_parses_roll_request_with_target():
    client = _make_mock_client(
        "The goblin swings!",
        "Brakka Stonefist",
        roll_request={
            "actor": "Goblin A", "formula": "1d6+2",
            "purpose": "scimitar damage", "target": "Brakka Stonefist",
        },
    )
    agent = GMAgent(client=client)
    result = agent.narrate(scene_state={}, transcript_tail=[])
    assert result.roll_request.target == "Brakka Stonefist"


def test_narrate_parses_conditions_remove():
    client = _make_mock_client(
        "Elara falls unconscious.",
        "ALL",
        scene_update={
            "hp_delta": {"Elara Moonwhisper": -7},
            "conditions": {"Elara Moonwhisper": ["Unconscious"]},
            "conditions_remove": {"Elara Moonwhisper": ["Concentrating: Detect Magic"]},
        },
    )
    agent = GMAgent(client=client)
    result = agent.narrate(scene_state={}, transcript_tail=[])
    remove = result.scene_update.get("conditions_remove", {})
    assert "Concentrating: Detect Magic" in remove.get("Elara Moonwhisper", [])


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


# --- CLIGMAgent tests ---

def _cli_response_json(narration="The goblins attack!", next_actor="ALL"):
    return json.dumps({
        "narration": narration,
        "next_actor": next_actor,
        "roll_request": None,
        "scene_update": {"hp_delta": {}, "conditions": {}},
    })


def test_cli_gm_agent_calls_claude_subprocess():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = _cli_response_json()
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        agent = CLIGMAgent()
        turn = agent.narrate({}, [])
    args = mock_run.call_args[0][0]
    assert args[0] == "claude"
    assert "-p" in args
    assert "--system-prompt" in args
    assert "--tools" in args
    assert isinstance(turn, GMTurn)


def test_cli_gm_agent_parses_json_response():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = _cli_response_json("Swords clash!", "Brakka Stonefist")
    with patch("subprocess.run", return_value=mock_result):
        agent = CLIGMAgent()
        turn = agent.narrate({}, [])
    assert turn.narration == "Swords clash!"
    assert turn.next_actor == "Brakka Stonefist"


def test_cli_gm_agent_raises_on_nonzero_returncode():
    import pytest
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "auth error"
    with patch("subprocess.run", return_value=mock_result):
        agent = CLIGMAgent()
        with pytest.raises(RuntimeError, match="claude CLI failed"):
            agent.narrate({}, [])


# --- OllamaGMAgent tests ---

def _make_ollama_response(content: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"message": {"content": content}}
    ).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_ollama_gm_agent_calls_ollama_url():
    content = _cli_response_json("Darkness falls!", "Elara Moonwhisper")
    mock_resp = _make_ollama_response(content)
    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        agent = OllamaGMAgent()
        turn = agent.narrate({}, [])
    assert mock_open.called
    assert turn.narration == "Darkness falls!"
    assert turn.next_actor == "Elara Moonwhisper"


def test_ollama_gm_agent_sends_system_in_payload():
    content = _cli_response_json()
    mock_resp = _make_ollama_response(content)
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return mock_resp
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        OllamaGMAgent().narrate({}, [])
    assert "system" in captured["body"]
    assert "Game Master" in captured["body"]["system"]


# --- make_gm_agent factory tests ---

def test_make_gm_agent_sdk_backend():
    mock_client = MagicMock()
    agent = make_gm_agent("sdk", client=mock_client)
    assert isinstance(agent, GMAgent)


def test_make_gm_agent_cli_backend():
    agent = make_gm_agent("cli")
    assert isinstance(agent, CLIGMAgent)


def test_make_gm_agent_ollama_backend():
    agent = make_gm_agent("ollama")
    assert isinstance(agent, OllamaGMAgent)


def test_make_gm_agent_auto_picks_cli_without_api_key():
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        agent = make_gm_agent("auto")
    assert isinstance(agent, CLIGMAgent)


def test_make_gm_agent_auto_picks_sdk_with_api_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("anthropic.Anthropic", return_value=MagicMock()):
            agent = make_gm_agent("auto")
    assert isinstance(agent, GMAgent)


def test_make_gm_agent_unknown_backend_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown GM backend"):
        make_gm_agent("invalid")
