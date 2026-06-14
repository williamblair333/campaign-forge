# AI Table — Design Spec

**Date:** 2026-06-14  
**Status:** Spec — ready for implementation plan  
**Module path:** `table/`

---

## 1. What we're building

A self-contained Python module (`table/`) that runs an autonomous D&D table: one
AI Game Master (Claude Sonnet) plus up to five AI players (Ollama `llama3.1:8b`)
playing a combat encounter end-to-end. The GM narrates, adjudicates rules, and
tracks state. Players take turns, react to each other, and roll dice via Foundry.
Output is a structured transcript.

This is **not** a replacement for the human-facing campaign tools. It is a
standalone harness that stress-tests the full stack (rag + Foundry MCP + Kanka +
personas) in one loop and produces a narrative artifact as output.

---

## 2. Phased delivery

| Phase | Players | Combats | Voice | Gate to enter |
|---|---|---|---|---|
| **A** | 1 GM + 2 players | 1 | No | smoke_test passes + AI GM dry run passes |
| **B** | 1 GM + 5 players | 3 | No | Phase A transcript passes human eyeball |
| **C** | same as B | 3 | Kokoro-82M | Phase B transcripts pass |

**Phase B combats** are standalone tests — HP/resources reset between each.
They are not a connected narrative. This makes them independently runnable
and removes state-leakage as a variable.

**World:** The Shattered Realm (Kanka CE, campaign id=1). `kanka_sync.py` runs
before play to populate `world_state.md`; `kanka_push.py --apply` runs after to
write back any new NPCs/locations the GM created.

---

## 3. Module layout

```
table/
├── __init__.py
├── orchestrator.py      # event loop, scene state, turn routing
├── gm_agent.py          # GM agent — Claude Sonnet
├── player_agent.py      # player agent — Ollama llama3.1:8b
├── personas.py          # YAML-defined persona registry
├── combat.py            # initiative tracker, HP ledger, condition flags
├── dice.py              # Foundry request-player-rolls wrapper + local fallback
├── transcript.py        # append-only log → structured markdown output
└── smoke_test.py        # single-turn dry-run, no Foundry, no Ollama required
```

No new dependencies beyond what already exists (`anthropic`, `requests`,
`foundry-mcp` tools, `rag`). Ollama is accessed via its HTTP API (`localhost:11434`).

---

## 4. Personas

Defined in `personas.py` as a registry of `Persona` dataclasses:

```python
@dataclass
class Persona:
    name: str           # "Brakka Stonefist"
    cls: str            # "Barbarian"
    level: int          # 1
    personality: str    # system prompt suffix — trait + speech pattern + secret_goal
    foundry_actor_id: str | None = None  # set after create-actor-from-compendium
    voice: str | None = None             # Phase C: Kokoro voicepack name
```

Phase A uses two personas (barbarian + wizard). Phase B adds three more
(cleric, rogue, bard). Personas are hand-authored — no generation at runtime.

The `personality` string is injected into each player agent's system prompt.
The `secret_goal` field is embedded in the personality string but not visible
in the shared transcript — only in the agent's own context.

---

## 5. Agent interfaces

### 5.1 GM agent (`gm_agent.py`)

```
GMAgent.narrate(scene_state, last_action) -> GMTurn
GMAgent.adjudicate(rule_question) -> str        # wraps rag.answer()
GMAgent.generate_module(seed) -> Module         # Phase A only uses pre-built encounter
```

`GMTurn` fields:
- `narration: str` — what the GM says aloud
- `next_actor: str` — name of the player the GM is addressing (or "ALL")
- `roll_request: RollRequest | None` — if the GM calls for a roll
- `scene_update: dict` — HP deltas, conditions, fog changes to apply

GM system prompt includes:
- Role: DM adjudicating 5e RAW
- Current scene state (initiative order, HP, fog)
- `world_state.md` summary (first 500 tokens)
- Instruction: always name who acts next; never invent dice results

### 5.2 Player agent (`player_agent.py`)

```
PlayerAgent.take_turn(persona, scene_state, gm_narration, transcript_tail) -> PlayerTurn
```

`PlayerTurn` fields:
- `speech: str` — what the character says/does (in-character)
- `action_type: str` — "attack" | "spell" | "skill" | "move" | "pass"
- `target: str | None`
- `roll_needed: bool`

Player system prompt:
- Persona personality string (class, traits, secret_goal)
- Current HP, spell slots, conditions for this character
- Last 6 turns of transcript (rolling window — keeps context bounded)
- Instruction: stay in character; declare intent only, never roll your own dice

Players are called via Ollama HTTP API (`/api/chat`, model=`llama3.1:8b`).
In Phase B, up to 5 player calls per GM turn — these run **sequentially** in
initiative order during combat (Foundry tracks the order; only the active
player responds per tick).

---

## 6. Orchestrator (`orchestrator.py`)

```python
class TableOrchestrator:
    def run_encounter(encounter: Encounter) -> Transcript
```

**State the orchestrator owns** (not delegated to any LLM):
- Initiative order (from Foundry `get-current-scene` or local roll)
- HP ledger (dict of actor → current HP)
- Condition flags (poisoned, prone, etc.)
- Round counter
- Turn pointer

**Event loop (one combat round):**

```
for each actor in initiative_order:
    if actor is monster:
        gm_turn = gm_agent.narrate(scene_state, last_action=None)
        apply gm_turn.scene_update to state ledger
        transcript.append(gm_turn)
    else:  # player character
        gm_cue = gm_agent.narrate(scene_state, cue_actor=actor)
        player_turn = player_agent.take_turn(persona, scene_state, gm_cue)
        if player_turn.roll_needed:
            roll = dice.request_roll(actor, player_turn.action_type)
            outcome = resolve(roll, player_turn, scene_state)
        else:
            outcome = resolve_no_roll(player_turn, scene_state)
        gm_followup = gm_agent.narrate(scene_state, last_action=outcome)
        apply gm_followup.scene_update to state ledger
        transcript.append(player_turn, roll, gm_followup)

check end_condition() → break if all monsters dead or TPK or round_limit hit
```

**End conditions:** all monster HP ≤ 0 (party wins), all PC HP ≤ 0 (TPK),
or `MAX_ROUNDS` (default 20) reached (GM narrates a tactical retreat).

---

## 7. Dice (`dice.py`)

Primary: Foundry `request-player-rolls` MCP tool. Accepts actor name + roll
formula (`1d20+STR`), returns integer result.

Fallback (used in smoke_test and when Foundry is offline):
```python
import random
def local_roll(formula: str) -> int  # parses "NdX+Y", returns sum
```

**Hard rule:** no LLM ever reports its own roll. The orchestrator always calls
`dice.request_roll()` and feeds the integer back to both player and GM. Player
and GM agents receive the result as a fact, not a prompt to generate one.

---

## 8. Transcript (`transcript.py`)

Append-only log. Each entry is a `TurnRecord`:

```python
@dataclass
class TurnRecord:
    round: int
    actor: str
    kind: Literal["gm_narration", "player_action", "roll_result", "scene_update"]
    text: str
    metadata: dict   # HP deltas, roll values, conditions — structured, not prose
```

`Transcript.to_markdown()` renders a readable session log with round headers,
speaker labels, and roll callouts. This is the file handed to
`CampaignGenerator distill.py` for narrative post-processing.

---

## 9. Rules grounding

Every rules question routes through `rag.answer()`:

```python
from rag import answer
ruling = answer("Does Nimble Escape let a goblin disengage as a bonus action?")
```

The GM agent calls this before adjudicating contested rulings. Result is
injected into the GM's next narration turn as a grounding fact. Players never
call rag directly — they declare intent; the GM adjudicates.

---

## 10. Gating and test strategy

```
smoke_test.py
  └─ Single-turn dry run: mock GM turn + mock player turn + local dice roll
     No Foundry, no Ollama, no rag. Validates data flow and transcript output.
     Passes in < 2s. Required before any other run.

AI GM dry run
  └─ GM agent only. Give it a scene state, ask for one narration turn.
     Foundry + rag connected. No players. Confirms Claude connectivity
     and rag grounding work together. ~30s.

Phase A: 1 GM + 2 players, 1 combat (Goblin Ambush, 3 goblins)
  └─ Full loop. Human reads transcript: can you tell the barbarian from the wizard?
     Did HP track correctly to a clean end? Did the GM name an actor each turn?

Phase B: 1 GM + 5 players, 3 independent combats
  └─ HP/resources reset between combats. Each combat runs the same check.
     Additional check: does adding players 3/4/5 cause persona collapse
     (everyone sounding the same)?

Phase C: voice
  └─ Kokoro-82M added behind transcript output. One voice per persona.
     Check: are 5+ voices distinct enough to follow without labels?
```

No automated pass/fail on Phase A–C — human eyeball is the gate. `smoke_test.py`
is the only automated gate (exits nonzero on any assertion failure).

---

## 11. Pre-session setup (per run)

```bash
# 1. Sync world state
python kanka_sync.py --campaign 1 --output docs/world_state.md

# 2. Confirm Ollama is up
curl -s http://localhost:11434/api/tags | python3 -m json.tool | grep llama3

# 3. Confirm Foundry bridge is connected
# (check /mcp in Claude Code — foundry-mcp should show tools)

# 4. Run smoke test
python -m table.smoke_test

# 5. Run the table (Phase A)
python -m table.orchestrator --phase A --seed "goblin ambush"
```

Post-session:
```bash
python kanka_push.py --campaign 1 --input docs/world_state.md --apply
```

---

## 12. What is explicitly out of scope

- Narrative one-shot with continuous HP/resources across encounters (Phase B
  uses resets — simplifies state debugging)
- Social encounters / bid-to-speak turn-taking (§5 of brainstorm — deferred to
  a later iteration)
- Player-to-player direct conversation outside of the shared transcript feed
- The `run_session_pipeline` CampaignGenerator tool (deliberately not built —
  see `project_campaigngenerator_pipeline_gates` memory)
- Any TTS in Phase A or B

---

## 13. Open questions (parking lot)

1. Does `request-player-rolls` in the Foundry MCP tool accept an actor name as
   the roller, or does it need the Foundry actor UUID? Need to verify against
   the bridge source before wiring `dice.py`.
2. Ollama `llama3.1:8b` context window is 8k. With a 6-turn rolling transcript
   + persona prompt, peak context is ~2k tokens — well within budget. Verify
   if personality + scene_state + transcript ever exceeds 4k in Phase B (5 players).
3. Phase C: Kokoro requires a Python package (`kokoro`) not yet in any
   `requirements*.txt`. Add `requirements-table.txt` with `kokoro`, `soundfile`.

---

## Sources

Brainstorming doc: `reviews/ai-table-gm-and-players-exploration.md` (gitignored)
- UC San Diego D&D benchmark (NeurIPS 2025)
- LangChain multi-agent D&D demo
- Who Speaks Next? multi-party turn-taking (arXiv 2412.04937)
- Local TTS landscape 2026 comparison
