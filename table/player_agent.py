import json
import re
import urllib.request
from dataclasses import dataclass

from table.personas import Persona
from table.transcript import TurnRecord

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
TRANSCRIPT_TAIL = 6


@dataclass
class PlayerTurn:
    actor: str
    speech: str
    action_type: str   # "attack" | "spell" | "skill" | "move" | "pass"
    target: str | None
    roll_needed: bool


class PlayerAgent:
    def __init__(self, persona: Persona, ollama_url: str = OLLAMA_URL) -> None:
        self.persona = persona
        self._ollama_url = ollama_url

    def take_turn(
        self,
        scene_state: dict,
        gm_narration: str,
        transcript_tail: list[TurnRecord],
    ) -> PlayerTurn:
        system = self._build_system()
        user = self._build_user(scene_state, gm_narration, transcript_tail)
        raw = self._call_ollama(system, user)
        return self._parse_response(raw)

    def _build_system(self) -> str:
        return (
            f"You are {self.persona.name}, a level {self.persona.level} "
            f"{self.persona.cls}.\n{self.persona.personality}\n\n"
            "Stay in character at all times. Declare your intent and speech only — "
            "never roll your own dice or decide the outcome of rolls.\n"
            'Respond as JSON: {"speech": str, "action_type": str, '
            '"target": str|null, "roll_needed": bool}'
        )

    def _build_user(
        self,
        scene_state: dict,
        gm_narration: str,
        tail: list[TurnRecord],
    ) -> str:
        tail_text = "\n".join(f"[{r.actor}]: {r.text}" for r in tail)
        return (
            f"Scene state:\n{json.dumps(scene_state, indent=2)}\n\n"
            f"Recent transcript:\n{tail_text}\n\n"
            f"GM: {gm_narration}\n\nYour turn, {self.persona.name}:"
        )

    def _call_ollama(self, system: str, user: str) -> str:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            self._ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]

    def _parse_response(self, raw: str) -> PlayerTurn:
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
        return PlayerTurn(
            actor=self.persona.name,
            speech=obj.get("speech", ""),
            action_type=obj.get("action_type", "pass"),
            target=obj.get("target"),
            roll_needed=bool(obj.get("roll_needed", False)),
        )
