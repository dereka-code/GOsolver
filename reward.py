# =========================================================
# Reward function for scoring candidate moves
#
#   compute_reward(board, move, color, strategy) -> RewardResult
#
# Each rule is a small function that returns a RAW value
# (a count, or 1.0 / 0.0). compute_reward multiplies it by the
# weight from strategies.py and records it in the breakdown.
# Rules never change the real game: they look at copies.
# =========================================================

from dataclasses import dataclass, field

from go_engine import GoGame, MoveResult, other_color
from strategies import STRATEGIES


@dataclass
class MoveContext:
    """Everything a rule may need about one candidate move."""
    before: GoGame          # board before the move (do not modify)
    after: GoGame           # board after the move
    point: tuple            # (row, col), or None for a pass
    color: str              # who is moving
    result: MoveResult      # captured stones etc. (None for a pass)


@dataclass
class RewardResult:
    """Total reward plus the weighted value of each rule.
    Unpacks like a pair:  total, breakdown = compute_reward(...)"""
    total: float
    breakdown: dict = field(default_factory=dict)
    illegal_reason: str = ""      # set when the move is illegal

    @property
    def legal(self):
        return not self.illegal_reason

    def __iter__(self):
        return iter((self.total, self.breakdown))


# ---------------------------------------------------------
# Rule registry
# ---------------------------------------------------------

RULES = {}        # name -> (function, applies_to_passes)


def rule(name, on_pass=False):
    """Register a rule under `name` (the key used in strategies.py).
    Rules about the stone's position skip passes unless on_pass=True."""
    def register(func):
        RULES[name] = (func, on_pass)
        return func
    return register


# ---------------------------------------------------------
# Rules for the "aggressive" strategy
# ---------------------------------------------------------

@rule("center")
def center_bonus(ctx, params):
    """1.0 at the center point, shrinking linearly to 0.0 in the corners
    (Manhattan distance)."""
    row, col = ctx.point
    mid = (ctx.before.size - 1) / 2
    max_distance = 2 * mid
    return 1.0 - (abs(row - mid) + abs(col - mid)) / max_distance


@rule("capture")
def stones_captured(ctx, params):
    return float(len(ctx.result.captured))


@rule("liberty_connection")
def liberty_and_connection(ctx, params):
    """1.0 if the move takes a liberty from an enemy group while
    touching one of my own stones. Looks at the board BEFORE the move."""
    enemy = other_color(ctx.color)
    neighbors = [ctx.before.board[r][c] for r, c in ctx.before.neighbors[ctx.point]]
    return 1.0 if enemy in neighbors and ctx.color in neighbors else 0.0


@rule("two_eyes")
def makes_two_eyes(ctx, params):
    """1.0 if the group containing the new stone now has two eyes and
    none of the groups it joined already did."""
    row, col = ctx.point
    if not ctx.after.has_two_eyes(ctx.after.get_group(row, col)):
        return 0.0
    for r, c in ctx.before.neighbors[ctx.point]:
        if ctx.before.board[r][c] == ctx.color and ctx.before.has_two_eyes(ctx.before.get_group(r, c)):
            return 0.0
    return 1.0


def _edge_count(point, size):
    """How many board edges this point touches (0 inside, 1 on an edge, 2 in a corner)."""
    row, col = point
    return (row in (0, size - 1)) + (col in (0, size - 1))


@rule("corner")
def corner_move(ctx, params):
    return 1.0 if _edge_count(ctx.point, ctx.before.size) == 2 else 0.0


@rule("edge")
def edge_move(ctx, params):
    edges = _edge_count(ctx.point, ctx.before.size)
    if edges == 2 and not params.get("include_corners", False):
        return 0.0
    return 1.0 if edges else 0.0


@rule("terminal", on_pass=True)
def final_result(ctx, params):
    """Win/loss hook: +1 if `color` wins, -1 if it loses, 0 while the
    game is still going. Replace the body to reward score margin etc."""
    if not ctx.after.game_over():
        return 0.0
    return 1.0 if ctx.after.winner() == ctx.color else -1.0


# ---------------------------------------------------------
# Main entry point
# ---------------------------------------------------------

def get_strategy(strategy):
    """Accept a strategy name from STRATEGIES or a config dict."""
    if isinstance(strategy, dict):
        config = strategy
    elif strategy in STRATEGIES:
        config = STRATEGIES[strategy]
    else:
        raise ValueError(f"unknown strategy {strategy!r}; known: {sorted(STRATEGIES)}")

    unknown = set(config["rules"]) - set(RULES)
    if unknown:
        raise ValueError(f"strategy uses unknown rules {sorted(unknown)}; known: {sorted(RULES)}")
    return config


def compute_reward(board, move, color, strategy="aggressive"):
    """Score `move` for `color` on `board` (a GoGame, left unchanged).

    move: (row, col), or "pass" / None.
    Returns a RewardResult; illegal moves get the strategy's
    "illegal_move" reward and illegal_reason says why.
    """
    config = get_strategy(strategy)

    after = board.copy()
    after.current_player = color
    if move is None or move == "pass":
        point, result = None, None
        after.pass_turn()
    else:
        point = tuple(move)
        result = after.play_move(*point)
        if not result:
            return RewardResult(config.get("illegal_move", float("-inf")), {}, result.reason)

    ctx = MoveContext(board, after, point, color, result)
    breakdown = {}
    for name, settings in config["rules"].items():
        if not settings.get("enabled", True):
            continue
        func, on_pass = RULES[name]
        if point is None and not on_pass:
            continue
        # "+ 0.0" turns -0.0 (negative weight x 0) into a plain 0.0
        breakdown[name] = settings["weight"] * func(ctx, settings) + 0.0

    return RewardResult(sum(breakdown.values()), breakdown)


def format_breakdown(move, reward):
    """Readable one-move summary for debugging weights."""
    if not reward.legal:
        return f"{move}: ILLEGAL ({reward.illegal_reason}) -> {reward.total}"
    lines = [f"{move}: total {reward.total:+.2f}"]
    for name, value in reward.breakdown.items():
        lines.append(f"    {name:<20} {value:+8.2f}")
    return "\n".join(lines)
