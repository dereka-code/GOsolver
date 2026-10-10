# =========================================================
# Greedy agent: score every candidate move with compute_reward
# and play the best one.
#
#   choose_move(game, color, strategy) -> (row, col) or "pass"
#   decide(...)                        -> Decision (move + why)
#   rank_moves(...)                    -> every candidate, best first
# =========================================================

import random
from dataclasses import dataclass

from go_engine import other_color
from reward import RewardResult, compute_reward


@dataclass
class Decision:
    move: object                  # (row, col) or "pass"
    reward: RewardResult = None   # breakdown for the chosen stone move
    why: str = ""


def candidate_moves(game, color):
    """Legal moves that do not fill one of `color`'s own eyes
    (filling your own eye can only help the opponent capture you)."""
    return [
        (r, c)
        for r, c in game.legal_moves(color)
        if not game.is_eye(r, c, color)
    ]


def rank_moves(game, color, strategy="aggressive", rng=None):
    """Every candidate move with its RewardResult, best first.
    Ties are broken randomly so the agent does not always favor
    the top-left of the board."""
    rng = rng or random
    moves = candidate_moves(game, color)
    rng.shuffle(moves)
    scored = [(move, compute_reward(game, move, color, strategy)) for move in moves]
    scored.sort(key=lambda pair: pair[1].total, reverse=True)
    return scored


def leading(game, color):
    score = game.score()
    return score[color] > score[other_color(color)]


def decide(game, color, strategy="aggressive", rng=None):
    """Pick a move for `color` and say why.

    Pass rules:
      - opponent just passed and I'm ahead -> pass (ends the game, I win)
      - no candidate moves left            -> pass
    Otherwise play the highest-reward candidate.
    """
    last = game.move_history[-1] if game.move_history else None
    if last == (other_color(color), "pass") and leading(game, color):
        return Decision("pass", why="opponent passed and I'm ahead")

    ranked = rank_moves(game, color, strategy, rng)
    if not ranked:
        return Decision("pass", why="no useful moves left")

    move, reward = ranked[0]
    return Decision(move, reward, "highest reward")


def choose_move(game, color, strategy="aggressive", rng=None):
    return decide(game, color, strategy, rng).move


def play(game, move):
    """Apply a (row, col) or "pass" for the current player.
    Returns the MoveResult for stones, None for a pass."""
    if move == "pass":
        game.pass_turn()
        return None
    return game.play_move(*move)
