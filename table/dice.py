import logging
import re
import random
from dataclasses import dataclass


@dataclass
class RollRequest:
    actor: str
    formula: str        # e.g. "1d20+3"
    purpose: str        # e.g. "attack roll"
    target: str | None = None  # combatant receiving damage; orchestrator auto-applies HP delta


def local_roll(formula: str) -> int:
    """Parse common D&D dice notation and return result. No external dependencies.

    Handles:
      NdX, dX              — standard (leading 1 implicit)
      NdX+Y, NdX-Y        — with modifier
      NdXkh/klK[+-]Y      — keep highest / keep lowest K dice (advantage/disadvantage)
      NdXdh/dlK[+-]Y      — drop highest / drop lowest K (converted to keep)
    Case-insensitive; spaces stripped.
    """
    f = re.sub(r"\s+", "", formula).lower()

    # keep-highest / keep-lowest: NdXkh/klK[+-]Y
    m = re.fullmatch(r"(\d*)d(\d+)k([hl])(\d+)([+-]\d+)?", f)
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        x, keep, mod = int(m.group(2)), int(m.group(4)), int(m.group(5) or 0)
        rolls = sorted([random.randint(1, x) for _ in range(n)], reverse=(m.group(3) == "h"))
        return sum(rolls[:keep]) + mod

    # drop-highest / drop-lowest: NdXdh/dlK[+-]Y  (convert: drop K → keep n-K)
    m = re.fullmatch(r"(\d*)d(\d+)d([hl])(\d+)([+-]\d+)?", f)
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        x, drop, mod = int(m.group(2)), int(m.group(4)), int(m.group(5) or 0)
        rolls = sorted([random.randint(1, x) for _ in range(n)], reverse=(m.group(3) == "l"))
        return sum(rolls[:max(n - drop, 1)]) + mod

    # standard: NdX[+-]Y
    m = re.fullmatch(r"(\d*)d(\d+)([+-]\d+)?", f)
    if not m:
        raise ValueError(f"Invalid roll formula: {formula!r}")
    n = int(m.group(1)) if m.group(1) else 1
    if n == 0:
        raise ValueError(f"Invalid roll formula: {formula!r} (0 dice)")
    x, mod = int(m.group(2)), int(m.group(3) or 0)
    return sum(random.randint(1, x) for _ in range(n)) + mod


def request_roll(req: RollRequest, *, use_foundry: bool = True) -> int:
    """Roll dice via Foundry MCP, falling back to local_roll."""
    if use_foundry:
        try:
            return _foundry_roll(req)
        except NotImplementedError:
            pass  # stub — live Foundry MCP not wired yet
        except Exception as e:
            logging.warning(
                "Foundry roll failed for %s (%s: %s) — falling back to local",
                req.actor, type(e).__name__, e,
            )
    try:
        return local_roll(req.formula)
    except ValueError:
        logging.warning(
            "Unrecognized formula %r for %s — falling back to 1d20",
            req.formula, req.actor,
        )
        return local_roll("1d20")


def _foundry_roll(req: RollRequest) -> int:
    """Invoke Foundry MCP request-player-rolls. Raises on any failure."""
    # Foundry MCP is accessed through the Claude Code MCP client at runtime.
    # In tests, mock this function. In production, the MCP bridge handles the call.
    raise NotImplementedError("Foundry roll requires a live MCP connection")
