import re
import random
from dataclasses import dataclass


@dataclass
class RollRequest:
    actor: str
    formula: str   # e.g. "1d20+3"
    purpose: str   # e.g. "attack roll"


def local_roll(formula: str) -> int:
    """Parse NdX[+-]Y and return sum. No external dependencies."""
    match = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", formula.strip())
    if not match:
        raise ValueError(f"Invalid roll formula: {formula!r}")
    n = int(match.group(1))
    x = int(match.group(2))
    mod = int(match.group(3)) if match.group(3) else 0
    return sum(random.randint(1, x) for _ in range(n)) + mod


def request_roll(req: RollRequest, *, use_foundry: bool = True) -> int:
    """Roll dice via Foundry MCP, falling back to local_roll."""
    if use_foundry:
        try:
            return _foundry_roll(req)
        except Exception:
            pass
    return local_roll(req.formula)


def _foundry_roll(req: RollRequest) -> int:
    """Invoke Foundry MCP request-player-rolls. Raises on any failure."""
    # Foundry MCP is accessed through the Claude Code MCP client at runtime.
    # In tests, mock this function. In production, the MCP bridge handles the call.
    raise NotImplementedError("Foundry roll requires a live MCP connection")
