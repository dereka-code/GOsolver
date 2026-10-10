import math

import pytest

from go_engine import BLACK, WHITE, GoGame
from reward import compute_reward
from strategies import STRATEGIES


def raw(game, move, rule, color=BLACK, **params):
    """Raw value of a single rule: run a strategy with only that rule, weight 1."""
    only = {"rules": {rule: {"enabled": True, "weight": 1, **params}}}
    return compute_reward(game, move, color, only).breakdown[rule]


# ---------- center ----------

def test_center_is_highest_in_middle_and_zero_in_corner():
    g = GoGame()
    assert raw(g, (4, 4), "center") == 1.0
    assert raw(g, (4, 0), "center") == 0.5
    assert raw(g, (0, 0), "center") == 0.0
    assert raw(g, (8, 8), "center") == 0.0


# ---------- capture ----------

def test_capture_counts_stones(board):
    one = board(["W", "B"])
    assert raw(one, (0, 1), "capture") == 1.0

    two = board(["WW", "BB"])
    assert raw(two, (0, 2), "capture") == 2.0


def test_no_capture_scores_zero(board):
    g = board(["W", "B"])
    assert raw(g, (4, 4), "capture") == 0.0


# ---------- liberty + connection ----------

LIB_POS = ["", "..B", "...W"]   # B at (1,2), W at (2,3)


def test_liberty_and_connection(board):
    g = board(LIB_POS)
    assert raw(g, (1, 3), "liberty_connection") == 1.0   # touches W and B
    assert raw(g, (2, 2), "liberty_connection") == 1.0


def test_liberty_without_connection_scores_zero(board):
    g = board(LIB_POS)
    assert raw(g, (3, 3), "liberty_connection") == 0.0   # touches only W


def test_connection_without_liberty_scores_zero(board):
    g = board(LIB_POS)
    assert raw(g, (0, 2), "liberty_connection") == 0.0   # touches only B


# ---------- two eyes ----------

def test_move_that_makes_second_eye(board):
    g = board([".B..", "BBBB"])         # (0,0) is an eye, (0,2) is not yet
    assert raw(g, (0, 3), "two_eyes") == 1.0


def test_extending_group_that_already_has_two_eyes_scores_zero(board):
    g = board([".B.B", "BBBB"])
    assert raw(g, (2, 0), "two_eyes") == 0.0


def test_no_eyes_scores_zero():
    assert raw(GoGame(), (4, 4), "two_eyes") == 0.0


# ---------- corner / edge ----------

def test_corner_penalty_only_on_corners():
    g = GoGame()
    assert raw(g, (0, 0), "corner") == 1.0
    assert raw(g, (8, 0), "corner") == 1.0
    assert raw(g, (0, 4), "corner") == 0.0


def test_edge_excludes_corners_by_default():
    g = GoGame()
    assert raw(g, (0, 4), "edge") == 1.0
    assert raw(g, (4, 8), "edge") == 1.0
    assert raw(g, (0, 0), "edge") == 0.0
    assert raw(g, (4, 4), "edge") == 0.0


def test_edge_can_include_corners():
    assert raw(GoGame(), (0, 0), "edge", include_corners=True) == 1.0


# ---------- terminal (win/loss hook) ----------

def test_terminal_reward_on_game_ending_pass():
    g = GoGame()
    g.pass_turn()                       # Black passed; White to move
    assert raw(g, "pass", "terminal", color=WHITE) == 1.0    # White wins on komi
    g2 = GoGame()
    g2.current_player = WHITE
    g2.pass_turn()                      # White passed; Black to move
    assert raw(g2, "pass", "terminal", color=BLACK) == -1.0


def test_terminal_is_zero_while_game_continues():
    assert raw(GoGame(), (4, 4), "terminal") == 0.0
    assert raw(GoGame(), "pass", "terminal") == 0.0


# ---------- illegal moves ----------

@pytest.mark.parametrize("rows, move, reason", [
    (["B"], (0, 0), "point already occupied"),
    ([".W", "W"], (0, 0), "suicide"),
    ([], (9, 9), "outside the board"),
])
def test_illegal_moves(board, rows, move, reason):
    reward = compute_reward(board(rows), move, BLACK, "aggressive")
    assert not reward.legal and reward.illegal_reason == reason
    assert reward.total == -math.inf and reward.breakdown == {}


def test_ko_is_illegal():
    g = GoGame()
    moves = [(4,4),(3,4),(2,4),(4,3),(3,3),(5,3),(3,5),(3,2),(3,6),(2,3),(5,5),(3,4)]
    for m in moves:
        g.play_move(*m)
    reward = compute_reward(g, (3, 3), BLACK, "aggressive")
    assert reward.illegal_reason == "ko"


def test_illegal_reward_is_configurable(board):
    config = {"illegal_move": -999, "rules": {"center": {"weight": 1}}}
    assert compute_reward(board(["B"]), (0, 0), BLACK, config).total == -999


# ---------- compute_reward behavior ----------

def test_aggressive_ranks_one_capture_above_liberty_connection():
    rules = STRATEGIES["aggressive"]["rules"]
    assert rules["capture"]["weight"] > rules["liberty_connection"]["weight"]


def test_total_is_sum_of_breakdown_and_unpacks(board):
    # (0,1) captures W and touches B at (1,1), so both rules fire
    total, breakdown = compute_reward(board(["W", "BB"]), (0, 1), BLACK, "aggressive")
    assert total == sum(breakdown.values())
    assert breakdown["capture"] == 100 and breakdown["liberty_connection"] == 60


def test_corner_gets_only_corner_penalty():
    _, breakdown = compute_reward(GoGame(), (0, 0), BLACK, "aggressive")
    assert breakdown["corner"] == -50 and breakdown["edge"] == 0


def test_disabled_rules_are_left_out():
    config = {"rules": {"center": {"enabled": False, "weight": 10},
                        "corner": {"weight": -50}}}
    reward = compute_reward(GoGame(), (0, 0), BLACK, config)
    assert reward.breakdown == {"corner": -50}


def test_pass_skips_position_rules():
    reward = compute_reward(GoGame(), "pass", BLACK, "aggressive")
    assert reward.legal and reward.breakdown == {} and reward.total == 0


def test_board_is_not_changed(board):
    g = board(["W", "B"])
    key, player, history = g.board_key(), g.current_player, list(g.move_history)
    compute_reward(g, (0, 1), BLACK, "aggressive")
    compute_reward(g, "pass", BLACK, "aggressive")
    assert (g.board_key(), g.current_player, g.move_history) == (key, player, history)


def test_scores_moves_for_either_color(board):
    g = board(["B", "W"])               # Black to move, but score White's capture
    assert compute_reward(g, (0, 1), WHITE, "aggressive").breakdown["capture"] == 100


def test_unknown_strategy_or_rule_raises():
    with pytest.raises(ValueError, match="unknown strategy"):
        compute_reward(GoGame(), (4, 4), BLACK, "nope")
    with pytest.raises(ValueError, match="unknown rules"):
        compute_reward(GoGame(), (4, 4), BLACK, {"rules": {"nope": {"weight": 1}}})
