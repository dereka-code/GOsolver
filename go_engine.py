# =========================================================
# 9x9 Go engine
#
# Rules implemented:
#   - stones on intersections, groups = orthogonally connected
#   - liberties, capture, atari
#   - suicide is illegal unless the move captures
#   - ko: a move may not recreate the previous whole-board state
#     (optional positional superko: never repeat ANY earlier state)
#   - passing; two passes in a row end the game
#   - eye detection + "two eyes" check (for the reward function)
#   - area scoring (stones + surrounded territory + komi)
# =========================================================

import copy
from dataclasses import dataclass, field

BOARD_SIZE = 9
KOMI = 7.5          # common 9x9 komi; the .5 means no ties

EMPTY = "."
BLACK = "B"
WHITE = "W"


def other_color(color):
    return WHITE if color == BLACK else BLACK


def build_neighbor_table(size):
    """Precompute the orthogonal neighbors of every point once,
    so we never re-check board edges during play (big speed-up)."""
    table = {}
    for r in range(size):
        for c in range(size):
            table[(r, c)] = tuple(
                (r + dr, c + dc)
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if 0 <= r + dr < size and 0 <= c + dc < size
            )
    return table


def build_diagonal_table(size):
    """Diagonal neighbors, used only for eye detection."""
    table = {}
    for r in range(size):
        for c in range(size):
            table[(r, c)] = tuple(
                (r + dr, c + dc)
                for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1))
                if 0 <= r + dr < size and 0 <= c + dc < size
            )
    return table


@dataclass
class MoveResult:
    """What happened when a move was tried.
    Works like True/False in an `if`, but also says WHY a move failed
    and WHICH stones were captured (useful for the reward function)."""
    legal: bool
    reason: str = ""
    captured: list = field(default_factory=list)

    def __bool__(self):
        return self.legal


class GoGame:
    def __init__(self, size=BOARD_SIZE, komi=KOMI, superko=False):
        self.size = size
        self.komi = komi
        self.superko = superko

        self.board = [[EMPTY] * size for _ in range(size)]
        self.neighbors = build_neighbor_table(size)
        self.diagonals = build_diagonal_table(size)

        self.current_player = BLACK          # Black always starts
        self.consecutive_passes = 0
        self.captures = {BLACK: 0, WHITE: 0} # stones each player has captured

        # Ko bookkeeping: the board as it was BEFORE the last move.
        # A new move may not recreate it.
        self.previous_state = None
        # Every position seen so far (only used if superko=True)
        self.history = {self.board_key()}
        self.move_history = []               # list of (color, (row, col) or "pass")

    # -----------------------------------------
    # Basic helpers
    # -----------------------------------------

    def board_key(self):
        """The whole board as one string, e.g. '....B....' -> fast to compare."""
        return "".join("".join(row) for row in self.board)

    def is_on_board(self, row, col):
        return 0 <= row < self.size and 0 <= col < self.size

    def get_neighbors(self, row, col):
        return self.neighbors[(row, col)]

    def other_player(self, player):
        return other_color(player)

    def copy(self):
        """Independent copy of the game -> lets a solver try moves
        without touching the real game."""
        new = copy.copy(self)
        new.board = [row[:] for row in self.board]
        new.captures = dict(self.captures)
        new.history = set(self.history) if self.superko else self.history
        new.move_history = list(self.move_history)
        return new

    # -----------------------------------------
    # Groups and liberties
    # -----------------------------------------

    def get_group_and_liberties(self, row, col):
        """One flood fill that returns (stones, liberties) of the group at (row, col)."""
        color = self.board[row][col]
        if color == EMPTY:
            return set(), set()

        stones = {(row, col)}
        liberties = set()
        stack = [(row, col)]
        board = self.board

        while stack:
            point = stack.pop()
            for nr, nc in self.neighbors[point]:
                value = board[nr][nc]
                if value == EMPTY:
                    liberties.add((nr, nc))
                elif value == color and (nr, nc) not in stones:
                    stones.add((nr, nc))
                    stack.append((nr, nc))

        return stones, liberties

    def get_group(self, row, col):
        return self.get_group_and_liberties(row, col)[0]

    def get_liberties(self, group):
        liberties = set()
        for point in group:
            for nr, nc in self.neighbors[point]:
                if self.board[nr][nc] == EMPTY:
                    liberties.add((nr, nc))
        return liberties

    def all_groups(self, color=None):
        """Every group on the board as a list of (color, stones, liberties)."""
        seen = set()
        groups = []
        for r in range(self.size):
            for c in range(self.size):
                stone = self.board[r][c]
                if stone == EMPTY or (r, c) in seen:
                    continue
                if color is not None and stone != color:
                    continue
                stones, libs = self.get_group_and_liberties(r, c)
                seen |= stones
                groups.append((stone, stones, libs))
        return groups

    # -----------------------------------------
    # Atari
    # -----------------------------------------

    def is_in_atari(self, row, col):
        """True if the stone at (row, col) belongs to a group with exactly 1 liberty."""
        if self.board[row][col] == EMPTY:
            return False
        return len(self.get_group_and_liberties(row, col)[1]) == 1

    def groups_in_atari(self, color):
        """All groups of `color` that have exactly one liberty left."""
        return [(stones, libs) for _, stones, libs in self.all_groups(color) if len(libs) == 1]

    # -----------------------------------------
    # Eyes
    # -----------------------------------------

    def is_eye(self, row, col, color):
        """Is this empty point a (single-point) real eye for `color`?

        1. Every orthogonal neighbor must be a `color` stone.
        2. Diagonal check to rule out FALSE eyes:
           - on the edge or in a corner: NO diagonal may be an enemy stone
           - in the middle: at most ONE diagonal may be an enemy stone
        This is the standard heuristic used by most simple Go programs.
        It does not detect bigger multi-point eyes (e.g. a 3-space eye).
        """
        if self.board[row][col] != EMPTY:
            return False

        for nr, nc in self.neighbors[(row, col)]:
            if self.board[nr][nc] != color:
                return False

        enemy = other_color(color)
        diagonals = self.diagonals[(row, col)]
        enemy_diagonals = sum(1 for dr, dc in diagonals if self.board[dr][dc] == enemy)

        if len(diagonals) < 4:          # edge or corner
            return enemy_diagonals == 0
        return enemy_diagonals <= 1

    def count_eyes(self, group):
        """Number of distinct real eyes touching this group."""
        if not group:
            return 0
        r, c = next(iter(group))
        color = self.board[r][c]
        return sum(1 for lr, lc in self.get_liberties(group) if self.is_eye(lr, lc, color))

    def has_two_eyes(self, group):
        """A group with two or more real eyes can never be captured."""
        return self.count_eyes(group) >= 2

    # -----------------------------------------
    # Playing moves
    # -----------------------------------------

    def _apply_move(self, row, col, player):
        """Place a stone and resolve captures / legality.
        Returns (MoveResult, undo_info). If the move is illegal,
        the board is already restored when this returns."""
        if not self.is_on_board(row, col):
            return MoveResult(False, "outside the board"), None
        if self.board[row][col] != EMPTY:
            return MoveResult(False, "point already occupied"), None

        key_before = self.board_key()
        enemy = other_color(player)
        board = self.board
        board[row][col] = player

        # 1) Capture enemy groups that just lost their last liberty
        captured = []
        for nr, nc in self.neighbors[(row, col)]:
            if board[nr][nc] == enemy:
                stones, libs = self.get_group_and_liberties(nr, nc)
                if not libs:
                    for sr, sc in stones:
                        board[sr][sc] = EMPTY
                    captured.extend(stones)

        # 2) Suicide check (only possible if nothing was captured)
        if not captured:
            _, own_libs = self.get_group_and_liberties(row, col)
            if not own_libs:
                board[row][col] = EMPTY
                return MoveResult(False, "suicide"), None

        # 3) Ko check: the new board may not equal the board before the last move
        key_after = self.board_key()
        if key_after == self.previous_state or (self.superko and key_after in self.history):
            board[row][col] = EMPTY
            for sr, sc in captured:
                board[sr][sc] = enemy
            return MoveResult(False, "ko"), None

        return MoveResult(True, "", captured), (key_before, key_after)

    def play_move(self, row, col):
        """Play a stone for the current player. Returns a MoveResult
        (truthy if legal). Illegal moves leave the game unchanged."""
        player = self.current_player
        result, undo_info = self._apply_move(row, col, player)
        if not result:
            return result

        key_before, key_after = undo_info
        self.previous_state = key_before
        if self.superko:
            self.history.add(key_after)
        self.captures[player] += len(result.captured)
        self.move_history.append((player, (row, col)))
        self.consecutive_passes = 0
        self.current_player = other_color(player)
        return result

    def is_legal(self, row, col, player=None):
        """Check a move without changing the game."""
        player = player or self.current_player
        result, undo_info = self._apply_move(row, col, player)
        if result:
            # undo the trial move
            self.board[row][col] = EMPTY
            enemy = other_color(player)
            for sr, sc in result.captured:
                self.board[sr][sc] = enemy
        return result.legal

    def legal_moves(self, player=None):
        """Every legal (row, col) for `player` (passing is always legal too)."""
        player = player or self.current_player
        return [
            (r, c)
            for r in range(self.size)
            for c in range(self.size)
            if self.board[r][c] == EMPTY and self.is_legal(r, c, player)
        ]

    def pass_turn(self):
        self.consecutive_passes += 1
        self.previous_state = None           # a pass lifts the ko restriction
        self.move_history.append((self.current_player, "pass"))
        self.current_player = other_color(self.current_player)

    def game_over(self):
        return self.consecutive_passes >= 2

    # -----------------------------------------
    # Scoring (area scoring, like Chinese rules)
    #   score = your stones on the board
    #         + empty regions touched only by your stones
    #   White also gets komi.
    # NOTE: dead stones are NOT removed automatically, so play the
    # game out until dead stones are actually captured.
    # -----------------------------------------

    def score(self):
        points = {BLACK: 0, WHITE: 0}
        seen = set()

        for r in range(self.size):
            for c in range(self.size):
                value = self.board[r][c]
                if value != EMPTY:
                    points[value] += 1
                    continue
                if (r, c) in seen:
                    continue

                # flood fill this empty region and record who borders it
                region = {(r, c)}
                borders = set()
                stack = [(r, c)]
                while stack:
                    point = stack.pop()
                    for nr, nc in self.neighbors[point]:
                        v = self.board[nr][nc]
                        if v == EMPTY and (nr, nc) not in region:
                            region.add((nr, nc))
                            stack.append((nr, nc))
                        elif v != EMPTY:
                            borders.add(v)
                seen |= region
                if len(borders) == 1:
                    points[borders.pop()] += len(region)

        return {BLACK: points[BLACK], WHITE: points[WHITE] + self.komi}

    def winner(self):
        s = self.score()
        return BLACK if s[BLACK] > s[WHITE] else WHITE

    # -----------------------------------------
    # Display
    # -----------------------------------------

    def print_board(self):
        print("  " + " ".join(str(c) for c in range(self.size)))
        for r in range(self.size):
            print(r, " ".join(self.board[r]))
        print()

    # ----------------------------------------
    # Influence Calculation (your Phase 2 idea)
    # ----------------------------------------
    # def calc_influence(self, group, liberties):
    #     ...
