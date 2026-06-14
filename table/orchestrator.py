# table/orchestrator.py
import argparse

from table.combat import CombatState, Combatant
from table.dice import RollRequest, request_roll
from table.gm_agent import GMAgent
from table.personas import PHASE_A_PERSONAS, PHASE_B_PERSONAS
from table.player_agent import PlayerAgent
from table.transcript import Transcript, TurnRecord

MAX_ROUNDS = 20


def _apply_scene_update(state: CombatState, scene_update: dict) -> None:
    for name, delta in scene_update.get("hp_delta", {}).items():
        state.apply_hp_delta(name, delta)
    for name, conds in scene_update.get("conditions", {}).items():
        for cond in conds:
            state.add_condition(name, cond)


class TableOrchestrator:
    def __init__(
        self,
        gm: GMAgent,
        players: list[PlayerAgent],
        use_foundry: bool = True,
    ) -> None:
        self.gm = gm
        self.players = {p.persona.name: p for p in players}
        self.use_foundry = use_foundry

    def run_encounter(self, combat: CombatState) -> Transcript:
        transcript = Transcript()

        while combat.end_condition() is None:
            actor = combat.current_actor()
            tail = transcript.tail(6)

            if not actor.is_player:
                gm_turn = self.gm.narrate(
                    combat.to_dict(), tail,
                    last_action=f"Monster {actor.name} acts",
                )
                _apply_scene_update(combat, gm_turn.scene_update)
                transcript.append(TurnRecord(
                    round=combat.round, actor="GM",
                    kind="gm_narration", text=gm_turn.narration,
                    metadata={"next_actor": gm_turn.next_actor,
                               "scene_update": gm_turn.scene_update},
                ))
                if gm_turn.roll_request:
                    roll = request_roll(gm_turn.roll_request, use_foundry=self.use_foundry)
                    transcript.append(TurnRecord(
                        round=combat.round, actor=gm_turn.roll_request.actor,
                        kind="roll_result",
                        text=f"{gm_turn.roll_request.purpose}: {roll}",
                        metadata={"formula": gm_turn.roll_request.formula, "result": roll},
                    ))
            else:
                player = self.players.get(actor.name)
                if player is None:
                    combat.advance_turn()
                    continue

                gm_cue = self.gm.narrate(combat.to_dict(), tail, cue_actor=actor.name)
                transcript.append(TurnRecord(
                    round=combat.round, actor="GM",
                    kind="gm_narration", text=gm_cue.narration,
                    metadata={"next_actor": actor.name},
                ))

                player_turn = player.take_turn(combat.to_dict(), gm_cue.narration, tail)
                transcript.append(TurnRecord(
                    round=combat.round, actor=actor.name,
                    kind="player_action", text=player_turn.speech,
                    metadata={"action_type": player_turn.action_type,
                               "target": player_turn.target},
                ))

                if player_turn.roll_needed:
                    formula = gm_cue.roll_request.formula if gm_cue.roll_request else "1d20"
                    roll_req = RollRequest(
                        actor=actor.name,
                        formula=formula,
                        purpose=player_turn.action_type,
                    )
                    roll = request_roll(roll_req, use_foundry=self.use_foundry)
                    transcript.append(TurnRecord(
                        round=combat.round, actor=actor.name,
                        kind="roll_result",
                        text=f"{player_turn.action_type}: {roll}",
                        metadata={"formula": formula, "result": roll},
                    ))
                    last_action = (
                        f"{actor.name} rolled {roll} for {player_turn.action_type} "
                        f"targeting {player_turn.target}"
                    )
                else:
                    last_action = f"{actor.name}: {player_turn.speech}"

                gm_followup = self.gm.narrate(
                    combat.to_dict(), transcript.tail(6), last_action=last_action
                )
                _apply_scene_update(combat, gm_followup.scene_update)
                transcript.append(TurnRecord(
                    round=combat.round, actor="GM",
                    kind="gm_narration", text=gm_followup.narration,
                    metadata={"scene_update": gm_followup.scene_update},
                ))

            combat.advance_turn()

        end = combat.end_condition()
        final = self.gm.narrate(
            combat.to_dict(), transcript.tail(6),
            last_action=f"Encounter ended: {end}",
        )
        transcript.append(TurnRecord(
            round=combat.round, actor="GM",
            kind="gm_narration", text=final.narration,
            metadata={"end_condition": end},
        ))
        return transcript


def _build_goblin_ambush() -> CombatState:
    return CombatState([
        Combatant("Brakka Stonefist", max_hp=13, current_hp=13, initiative=14, is_player=True),
        Combatant("Elara Moonwhisper", max_hp=7, current_hp=7, initiative=11, is_player=True),
        Combatant("Goblin A", max_hp=7, current_hp=7, initiative=13, is_player=False),
        Combatant("Goblin B", max_hp=7, current_hp=7, initiative=9, is_player=False),
        Combatant("Goblin C", max_hp=7, current_hp=7, initiative=6, is_player=False),
    ], max_rounds=MAX_ROUNDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an autonomous AI D&D table")
    parser.add_argument("--phase", choices=["A", "B"], default="A",
                        help="Phase A: 2 players / Phase B: 5 players")
    parser.add_argument("--out", default="transcript.md",
                        help="Output markdown file")
    parser.add_argument("--no-foundry", action="store_true",
                        help="Use local dice only (no Foundry MCP)")
    args = parser.parse_args()

    personas = PHASE_A_PERSONAS if args.phase == "A" else PHASE_B_PERSONAS
    gm = GMAgent()
    players = [PlayerAgent(p) for p in personas]
    orch = TableOrchestrator(gm, players, use_foundry=not args.no_foundry)
    combat = _build_goblin_ambush()

    print(f"Starting Phase {args.phase}: {len(personas)} players vs Goblin Ambush")
    transcript = orch.run_encounter(combat)

    md = transcript.to_markdown()
    with open(args.out, "w") as f:
        f.write(md)
    print(f"Done — {len(transcript)} turns. Transcript: {args.out}")


if __name__ == "__main__":
    main()
