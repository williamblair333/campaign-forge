from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TurnRecord:
    round: int
    actor: str
    kind: Literal["gm_narration", "player_action", "roll_result", "scene_update"]
    text: str
    metadata: dict = field(default_factory=dict)


class Transcript:
    def __init__(self) -> None:
        self._records: list[TurnRecord] = []

    def append(self, record: TurnRecord) -> None:
        self._records.append(record)

    def tail(self, n: int) -> list[TurnRecord]:
        if n <= 0:
            return []
        return self._records[-n:]

    def __len__(self) -> int:
        return len(self._records)

    def to_markdown(self) -> str:
        lines: list[str] = []
        current_round = -1
        for r in self._records:
            if r.round != current_round:
                current_round = r.round
                lines.append(f"\n## Round {r.round}\n")
            if r.kind == "roll_result":
                lines.append(f"**[ROLL]** {r.actor}: {r.text}")
            else:
                lines.append(f"**{r.actor}:** {r.text}")
        return "\n".join(lines)
