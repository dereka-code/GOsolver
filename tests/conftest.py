import pytest

from go_engine import BLACK, EMPTY, GoGame


@pytest.fixture
def board():
    """Build a game from a picture of the board.

        g = board([".B.", "BW."], to_move=WHITE)

    Spaces are ignored, and missing rows/columns are filled with empty points,
    so small positions only need the top-left corner.
    """
    def build(rows, to_move=BLACK):
        g = GoGame()
        for r, line in enumerate(rows):
            for c, ch in enumerate(line.replace(" ", "")):
                g.board[r][c] = ch
        assert all(v in (EMPTY, "B", "W") for row in g.board for v in row)
        g.current_player = to_move
        return g
    return build
