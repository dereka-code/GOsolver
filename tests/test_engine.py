# The notebook's rule tests, one pytest function each.

from go_engine import BLACK, EMPTY, WHITE, GoGame


def test_capture(board):
    g = board(["W", "B"])
    res = g.play_move(0, 1)
    assert res and res.captured == [(0, 0)] and g.board[0][0] == EMPTY


def test_suicide_is_illegal(board):
    g = board([".B", "B"], to_move=WHITE)
    res = g.play_move(0, 0)
    assert not res and res.reason == "suicide" and g.board[0][0] == EMPTY


def test_suicide_that_captures_is_legal(board):
    g = board([".BW", "BW", "W"], to_move=WHITE)
    res = g.play_move(0, 0)
    assert res and set(res.captured) == {(0, 1), (1, 0)}


def test_ko():
    g = GoGame()
    moves = [(4,4),(3,4),(2,4),(4,3),(3,3),(5,3),(3,5),(3,2),(3,6),(2,3),(5,5),(3,4)]
    for m in moves:
        assert g.play_move(*m), m
    res = g.play_move(3, 3)
    assert not res and res.reason == "ko"
    g.play_move(6, 6); g.play_move(6, 7)   # ko threat elsewhere, then retaking is fine
    assert g.play_move(3, 3)


def test_atari(board):
    g = board(["W", "B"])
    assert g.is_in_atari(0, 0) and len(g.groups_in_atari(WHITE)) == 1


def test_two_eyes(board):
    g = board([".B.B", "BBBB"], to_move=WHITE)
    assert g.is_eye(0, 0, BLACK) and g.is_eye(0, 2, BLACK)
    assert g.has_two_eyes(g.get_group(1, 0))
    assert not g.is_legal(0, 0) and not g.is_legal(0, 2)


def test_false_eye(board):
    g = board(["B.B", "WB"])
    assert not g.is_eye(0, 1, BLACK)


def test_two_passes_end_game_white_wins_on_komi():
    g = GoGame()
    g.pass_turn(); g.pass_turn()
    assert g.game_over() and g.score() == {BLACK: 0, WHITE: 7.5} and g.winner() == WHITE


def test_illegal_moves_change_nothing():
    g = GoGame(); g.play_move(4, 4)
    before = g.board_key()
    assert not g.play_move(4, 4) and not g.play_move(9, 9) and g.board_key() == before


def test_copy_is_independent():
    g = GoGame(); h = g.copy(); h.play_move(4, 4)
    assert g.board[4][4] == EMPTY and h.board[4][4] == BLACK
