from dataclasses import dataclass, field


@dataclass
class Combatant:
    name: str
    max_hp: int
    current_hp: int
    initiative: int
    is_player: bool
    conditions: list[str] = field(default_factory=list)


class CombatState:
    def __init__(self, combatants: list[Combatant], max_rounds: int = 20) -> None:
        self.combatants = sorted(combatants, key=lambda c: -c.initiative)
        self.max_rounds = max_rounds
        self.round = 0
        self._turn_index = 0

    @property
    def initiative_order(self) -> list[Combatant]:
        return self.combatants

    def current_actor(self) -> Combatant:
        return self.combatants[self._turn_index % len(self.combatants)]

    def advance_turn(self) -> None:
        self._turn_index += 1
        if self._turn_index % len(self.combatants) == 0:
            self.round += 1

    def apply_hp_delta(self, target_name: str, delta: int) -> None:
        """Apply HP change. Negative = damage, positive = healing. Clamps to [0, max_hp]."""
        for c in self.combatants:
            if c.name == target_name:
                c.current_hp = max(0, min(c.max_hp, c.current_hp + delta))
                return
        raise ValueError(f"Unknown combatant: {target_name!r}")

    def add_condition(self, target_name: str, condition: str) -> None:
        for c in self.combatants:
            if c.name == target_name:
                if condition not in c.conditions:
                    c.conditions.append(condition)
                return
        raise ValueError(f"Unknown combatant: {target_name!r}")

    def remove_condition(self, target_name: str, condition: str) -> None:
        for c in self.combatants:
            if c.name == target_name:
                if condition in c.conditions:
                    c.conditions.remove(condition)
                return
        raise ValueError(f"Unknown combatant: {target_name!r}")

    def end_condition(self) -> str | None:
        """Returns 'party_wins', 'tpk', 'round_limit', or None if combat continues."""
        monsters = [c for c in self.combatants if not c.is_player]
        players = [c for c in self.combatants if c.is_player]
        if monsters and all(m.current_hp <= 0 for m in monsters):
            return "party_wins"
        if players and all(p.current_hp <= 0 for p in players):
            return "tpk"
        if self.round >= self.max_rounds:
            return "round_limit"
        return None

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "combatants": [
                {
                    "name": c.name,
                    "hp": c.current_hp,
                    "max_hp": c.max_hp,
                    "initiative": c.initiative,
                    "is_player": c.is_player,
                    "conditions": c.conditions,
                }
                for c in self.combatants
            ],
        }
