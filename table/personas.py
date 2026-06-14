from dataclasses import dataclass


@dataclass
class Persona:
    name: str
    cls: str
    level: int
    personality: str
    foundry_actor_id: str | None = None
    voice: str | None = None


PHASE_A_PERSONAS: list[Persona] = [
    Persona(
        name="Brakka Stonefist",
        cls="Barbarian",
        level=1,
        personality=(
            "Reckless, loyal, allergic to plans. Solves problems by hitting them. "
            "Distrusts magic. Speaks in short, blunt sentences. Always charges first. "
            "Secret goal: prove herself to the clan she was exiled from."
        ),
    ),
    Persona(
        name="Elara Moonwhisper",
        cls="Wizard",
        level=1,
        personality=(
            "Cautious, analytical, hoards spell slots for emergencies. Speaks in "
            "precise, measured sentences. Suspicious of the barbarian's recklessness. "
            "Secret goal: find evidence of an ancient spell catastrophe in the area."
        ),
    ),
]

PHASE_B_PERSONAS: list[Persona] = PHASE_A_PERSONAS + [
    Persona(
        name="Brother Aldric",
        cls="Cleric",
        level=1,
        personality=(
            "Devout, protective, slow to anger. Heals first, asks questions after. "
            "Speaks in formal, slightly archaic prose. "
            "Secret goal: atone for a failure that cost a companion their life."
        ),
    ),
    Persona(
        name="Silk",
        cls="Rogue",
        level=1,
        personality=(
            "Cynical, self-interested, charming when convenient. Never trusts the "
            "GM's read of a situation. Speaks in clipped sentences with dry humor. "
            "Secret goal: pocket the best loot before anyone notices."
        ),
    ),
    Persona(
        name="Finn the Fortunate",
        cls="Bard",
        level=1,
        personality=(
            "Optimistic, verbose, narrates everything in the third person. Treats "
            "danger as dramatic opportunity. Speaks in flowing, theatrical sentences. "
            "Secret goal: compose a ballad about this adventure and make it famous."
        ),
    ),
]
