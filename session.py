# =========================================================
# One human-vs-agent game. Shared by play.py (terminal) and
# server.py (web page) so both front ends behave the same.
# =========================================================

import random

from agent import decide, play, rank_moves
from go_engine import BLACK, WHITE, GoGame, other_color
from strategies import STRATEGIES


class GameSession:
    def __init__(self, human_color=BLACK, strategy="aggressive", seed=None):
        if human_color not in (BLACK, WHITE):
            raise ValueError(f"human_color must be {BLACK!r} or {WHITE!r}")
        if strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy {strategy!r}; known: {sorted(STRATEGIES)}")
        self.game = GoGame()
        self.human = human_color
        self.agent = other_color(human_color)
        self.strategy = strategy
        self.rng = random.Random(seed)
        self.last_decision = None     # the agent's most recent Decision
        self.message = ""
        self.agent_turn()             # agent opens if the human chose White

    def is_human_turn(self):
        return not self.game.game_over() and self.game.current_player == self.human

    def human_move(self, move):
        """Play the human's (row, col) or "pass", then the agent's reply.
        Returns True if the move was accepted; otherwise self.message says why."""
        if self.game.game_over():
            self.message = "The game is over."
            return False
        if not self.is_human_turn():
            self.message = "It's not your turn."
            return False

        result = play(self.game, move)
        if move != "pass" and not result:
            self.message = f"Illegal move: {result.reason}."
            return False

        captured = len(result.captured) if result else 0
        self.message = f"You captured {captured} stone(s)." if captured else ""
        self.agent_turn()
        return True

    def agent_turn(self):
        if self.game.game_over() or self.game.current_player != self.agent:
            return
        decision = decide(self.game, self.agent, self.strategy, self.rng)
        play(self.game, decision.move)
        self.last_decision = decision

    def hints(self, n=3):
        """The agent's top-n moves for the human's position, for a 'hint' button."""
        return rank_moves(self.game, self.human, self.strategy, self.rng)[:n]

    def state(self):
        """Everything a front end needs to draw the game, as plain JSON-ready data."""
        game = self.game
        last = game.move_history[-1] if game.move_history else None
        decision = self.last_decision
        state = {
            "size": game.size,
            "board": [row[:] for row in game.board],
            "human": self.human,
            "agent": self.agent,
            "strategy": self.strategy,
            "current_player": game.current_player,
            "your_turn": self.is_human_turn(),
            "captures": dict(game.captures),
            "last_move": {"color": last[0], "move": last[1]} if last else None,
            "agent_move": None,
            "message": self.message,
            "game_over": game.game_over(),
            "score": game.score(),
            "winner": game.winner() if game.game_over() else None,
            "move_number": len(game.move_history),
        }
        if decision:
            state["agent_move"] = {
                "move": decision.move,
                "why": decision.why,
                "total": decision.reward.total if decision.reward else None,
                "breakdown": decision.reward.breakdown if decision.reward else {},
            }
        return state
