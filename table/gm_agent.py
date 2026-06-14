import json
import re
from dataclasses import dataclass

import anthropic

from table.dice import RollRequest
from table.transcript import TurnRecord

GM_MODEL = "claude-sonnet-4-6"
WORLD_STATE_PATH = "docs/world_state.md"
WORLD_STATE_CHAR_LIMIT = 2000


@dataclass
class GMTurn:
    narration: str
    next_actor: str   # player name or "ALL"
    roll_request: RollRequest | None
    scene_update: dict  # {"hp_delta": {name: int}, "conditions": {name: [str]}}


class GMAgent:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic()
        self._world_state = self._load_world_state()

    def narrate(
        self,
        scene_state: dict,
        transcript_tail: list[TurnRecord],
        *,
        cue_actor: str | None = None,
        last_action: str | None = None,
    ) -> GMTurn:
        system = self._build_system()
        user = self._build_user(scene_state, transcript_tail, cue_actor, last_action)
        message = self._client.messages.create(
            model=GM_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return self._parse_response(message.content[0].text)

    def adjudicate(self, rule_question: str) -> str:
        from rag import answer
        return answer(rule_question)

    def _load_world_state(self) -> str:
        try:
            with open(WORLD_STATE_PATH) as f:
                return f.read()[:WORLD_STATE_CHAR_LIMIT]
        except FileNotFoundError:
            return ""

    def _build_system(self) -> str:
        world_snippet = self._world_state or "(no world state loaded)"
        return (
            "You are the Game Master for a D&D 5e encounter set in The Shattered Realm.\n"
            "Adjudicate rules strictly per SRD 5.2.1. Never invent dice results — "
            "always emit a roll_request when a roll is needed.\n"
            "Always name who acts next in next_actor.\n\n"
            f"World context:\n{world_snippet}\n\n"
            "Respond ONLY as JSON:\n"
            '{"narration": str, "next_actor": str, '
            '"roll_request": {"actor": str, "formula": str, "purpose": str} | null, '
            '"scene_update": {"hp_delta": {name: int}, "conditions": {name: [str]}}}'
        )

    def _build_user(
        self,
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

    def _parse_response(self, raw: str) -> GMTurn:
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
            RollRequest(actor=rr["actor"], formula=rr["formula"], purpose=rr["purpose"])
            if rr else None
        )
        return GMTurn(
            narration=obj.get("narration", ""),
            next_actor=obj.get("next_actor", "ALL"),
            roll_request=roll_req,
            scene_update=obj.get("scene_update", {"hp_delta": {}, "conditions": {}}),
        )
