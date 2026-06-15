import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass

import anthropic

from table.dice import RollRequest
from table.transcript import TurnRecord

GM_MODEL = "claude-sonnet-4-6"
OLLAMA_GM_MODEL = "llama3.1:8b"
OLLAMA_URL = "http://localhost:11434/api/chat"
WORLD_STATE_PATH = "docs/world_state.md"
WORLD_STATE_CHAR_LIMIT = 2000


@dataclass
class GMTurn:
    narration: str
    next_actor: str   # player name or "ALL"
    roll_request: RollRequest | None
    scene_update: dict  # {"hp_delta": {name: int}, "conditions": {name: [str]}}


# --- Shared helpers used by all three backends ---

def _load_world_state() -> str:
    try:
        with open(WORLD_STATE_PATH) as f:
            return f.read()[:WORLD_STATE_CHAR_LIMIT]
    except FileNotFoundError:
        return ""


def _build_system(world_state: str) -> str:
    world_snippet = world_state or "(no world state loaded)"
    return (
        "You are the Game Master for a D&D 5e encounter set in The Shattered Realm.\n"
        "Adjudicate rules strictly per SRD 5.2.1. Never invent dice results — "
        "always emit a roll_request when a roll is needed.\n"
        "Always name who acts next in next_actor.\n"
        "For damage rolls, set roll_request.target to the name of the combatant taking the damage.\n"
        "To remove conditions (e.g. Concentration when unconscious), list them in scene_update.conditions_remove.\n\n"
        f"World context:\n{world_snippet}\n\n"
        "Respond ONLY as JSON:\n"
        '{"narration": str, "next_actor": str, '
        '"roll_request": {"actor": str, "formula": str, "purpose": str, "target": str | null} | null, '
        '"scene_update": {"hp_delta": {name: int}, "conditions": {name: [str]}, "conditions_remove": {name: [str]}}}'
    )


def _build_user(
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


def _parse_gm_response(raw: str) -> GMTurn:
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
        RollRequest(
            actor=rr["actor"],
            formula=rr["formula"],
            purpose=rr["purpose"],
            target=rr.get("target"),
        )
        if rr else None
    )
    return GMTurn(
        narration=obj.get("narration", ""),
        next_actor=obj.get("next_actor", "ALL"),
        roll_request=roll_req,
        scene_update=obj.get("scene_update", {"hp_delta": {}, "conditions": {}}),
    )


# --- Backend A: Anthropic SDK (requires ANTHROPIC_API_KEY) ---

class GMAgent:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic()
        self._world_state = _load_world_state()

    def narrate(
        self,
        scene_state: dict,
        transcript_tail: list[TurnRecord],
        *,
        cue_actor: str | None = None,
        last_action: str | None = None,
    ) -> GMTurn:
        system = _build_system(self._world_state)
        user = _build_user(scene_state, transcript_tail, cue_actor, last_action)
        message = self._client.messages.create(
            model=GM_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _parse_gm_response(message.content[0].text)

    def adjudicate(self, rule_question: str) -> str:
        from rag import answer
        return answer(rule_question)


# --- Backend B: claude CLI subprocess (uses Max subscription / OAuth) ---

class CLIGMAgent:
    def __init__(self, model: str = GM_MODEL) -> None:
        self._model = model
        self._world_state = _load_world_state()

    def narrate(
        self,
        scene_state: dict,
        transcript_tail: list[TurnRecord],
        *,
        cue_actor: str | None = None,
        last_action: str | None = None,
    ) -> GMTurn:
        system = _build_system(self._world_state)
        user = _build_user(scene_state, transcript_tail, cue_actor, last_action)
        result = subprocess.run(
            ["claude", "-p", user,
             "--system-prompt", system,
             "--tools", "",
             "--safe-mode"],   # skips MCP servers / plugins / hooks — avoids 120s startup
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI failed (exit {result.returncode}): {result.stderr[:200]}"
            )
        return _parse_gm_response(result.stdout.strip())

    def adjudicate(self, rule_question: str) -> str:
        from rag import answer
        return answer(rule_question)


# --- Backend C: Ollama local (zero cost, no API key needed) ---

class OllamaGMAgent:
    def __init__(
        self,
        ollama_url: str = OLLAMA_URL,
        model: str = OLLAMA_GM_MODEL,
    ) -> None:
        self._url = ollama_url
        self._model = model
        self._world_state = _load_world_state()

    def narrate(
        self,
        scene_state: dict,
        transcript_tail: list[TurnRecord],
        *,
        cue_actor: str | None = None,
        last_action: str | None = None,
    ) -> GMTurn:
        system = _build_system(self._world_state)
        user = _build_user(scene_state, transcript_tail, cue_actor, last_action)
        payload = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": user}],
            "system": system,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            self._url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return _parse_gm_response(data["message"]["content"])

    def adjudicate(self, rule_question: str) -> str:
        from rag import answer
        return answer(rule_question)


# --- Factory ---

def make_gm_agent(backend: str = "auto", **kwargs):
    """Return a GM agent for the given backend.

    backend choices:
      auto   — use sdk if ANTHROPIC_API_KEY is set, else cli
      sdk    — Anthropic Python SDK (requires ANTHROPIC_API_KEY)
      cli    — claude CLI subprocess (Max subscription / OAuth)
      ollama — local Ollama HTTP API (zero cost)
    """
    if backend == "auto":
        backend = "sdk" if os.environ.get("ANTHROPIC_API_KEY") else "cli"
    if backend == "sdk":
        return GMAgent(**kwargs)
    if backend == "cli":
        return CLIGMAgent(**kwargs)
    if backend == "ollama":
        return OllamaGMAgent(**kwargs)
    raise ValueError(f"Unknown GM backend: {backend!r}. Choose sdk, cli, or ollama.")
