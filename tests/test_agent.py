import json
import random

import pytest

from agent import candidate_moves, choose_move, decide, play
from go_engine import BLACK, EMPTY, WHITE, GoGame
from session import GameSession


# ---------- choose_move / decide ----------

def test_takes_a_capture_when_available(board):
    g = board(["W", "BB"])
    assert choose_move(g, BLACK, rng=random.Random(0)) == (0, 1)


def test_opens_near_the_center():
    move = choose_move(GoGame(), BLACK, rng=random.Random(0))
    assert move == (4, 4)


def test_never_fills_own_eye(board):
    g = board([".B.B", "BBBB"])
    moves = candidate_moves(g, BLACK)
    assert (0, 0) not in moves and (0, 2) not in moves


def test_passes_when_opponent_passed_and_agent_is_ahead(board):
    g = board(["BBB", "BBB", "BBB"], to_move=WHITE)
    g.pass_turn()                       # White passes; Black (9 stones) beats komi 7.5
    decision = decide(g, BLACK)
    assert decision.move == "pass" and "ahead" in decision.why


def test_keeps_playing_when_opponent_passed_but_agent_is_behind():
    g = GoGame()
    g.current_player = WHITE
    g.pass_turn()                       # White passed; empty board, Black is behind on komi
    assert decide(g, BLACK).move != "pass"


def test_passes_when_no_candidate_moves(board):
    # Black owns the whole board except two eyes: nothing useful left to play
    rows = ["." + "B" * 8, "B" * 9, "B" * 9, "B" * 9, "B" * 9,
            "B" * 9, "B" * 9, "B" * 9, "B" * 8 + "."]
    decision = decide(board(rows), BLACK)
    assert decision.move == "pass" and decision.why == "no useful moves left"


def test_choose_move_does_not_change_the_game(board):
    g = board(["W", "BB"])
    key = g.board_key()
    choose_move(g, BLACK)
    assert g.board_key() == key and g.current_player == BLACK


def test_play_helper_handles_stones_and_passes():
    g = GoGame()
    assert play(g, (4, 4)) and g.board[4][4] == BLACK
    assert play(g, "pass") is None and g.consecutive_passes == 1


def test_beats_random_player():
    """The project goal: the greedy agent should beat random play."""
    rng = random.Random(0)

    def random_move(g, color):
        cands = [(r, c) for r in range(9) for c in range(9)
                 if g.board[r][c] == EMPTY and not g.is_eye(r, c, color)]
        rng.shuffle(cands)
        return next((m for m in cands if g.is_legal(*m, color)), "pass")

    wins = 0
    for i in range(6):
        agent = BLACK if i % 2 == 0 else WHITE
        g = GoGame()
        while not g.game_over() and len(g.move_history) < 250:
            c = g.current_player
            play(g, choose_move(g, c, rng=rng) if c == agent else random_move(g, c))
        wins += g.winner() == agent
    assert wins >= 5


# ---------- GameSession (shared by play.py and server.py) ----------

def test_agent_replies_after_human_move():
    s = GameSession(BLACK, seed=0)
    assert s.human_move((4, 4))
    assert s.state()["move_number"] == 2 and s.is_human_turn()
    assert s.state()["agent_move"]["why"] == "highest reward"


def test_agent_opens_when_human_is_white():
    s = GameSession(WHITE, seed=0)
    state = s.state()
    assert state["move_number"] == 1 and state["your_turn"] and state["agent_move"]["move"] == (4, 4)


def test_illegal_human_move_is_rejected_with_reason():
    s = GameSession(BLACK, seed=0)
    s.human_move((4, 4))
    assert not s.human_move((4, 4))
    assert s.message == "Illegal move: point already occupied."
    assert s.state()["move_number"] == 2


def test_moves_after_game_over_are_rejected():
    s = GameSession(BLACK, seed=0)
    s.game.pass_turn(); s.game.pass_turn()
    assert not s.human_move((4, 4)) and s.message == "The game is over."


def test_state_is_json_ready():
    s = GameSession(BLACK, seed=0)
    s.human_move((4, 4))
    json.dumps(s.state())


def test_hints_are_ranked_for_the_human():
    s = GameSession(BLACK, seed=0)
    hints = s.hints()
    assert len(hints) == 3 and hints[0][1].total >= hints[-1][1].total


def test_bad_session_settings_raise():
    with pytest.raises(ValueError):
        GameSession("X")
    with pytest.raises(ValueError):
        GameSession(BLACK, strategy="nope")
