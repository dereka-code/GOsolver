# =========================================================
# Play against the agent in the terminal.
#
#   python3 play.py                 # you are Black
#   python3 play.py --color W       # you are White (agent opens)
#   python3 play.py --strategy aggressive --seed 1
#
# Commands: "row col" (e.g. 4 4), pass, hint, quit
# =========================================================

import argparse

from go_engine import BLACK, EMPTY, WHITE
from session import GameSession
from strategies import STRATEGIES

NAMES = {BLACK: "Black (X)", WHITE: "White (O)"}
SYMBOLS = {EMPTY: ".", BLACK: "X", WHITE: "O"}


def show_board(state):
    size = state["size"]
    last = state["last_move"]
    last_point = tuple(last["move"]) if last and last["move"] != "pass" else None

    print("\n   " + " ".join(str(c) for c in range(size)))
    for r, row in enumerate(state["board"]):
        line = ""
        for c, value in enumerate(row):
            # parentheses around the most recent stone: (X)
            if (r, c) == last_point:
                line += "("
            elif (r, c - 1) == last_point:
                line += ")"
            else:
                line += " "
            line += SYMBOLS[value]
        line += ")" if (r, size - 1) == last_point else ""
        print(f"{r:>2}" + line)
    caps = state["captures"]
    print(f"\n Captures  X: {caps[BLACK]}   O: {caps[WHITE]}    move {state['move_number']}")


def show_agent_move(state):
    agent = state["agent_move"]
    if not agent or state["last_move"] is None or state["last_move"]["color"] != state["agent"]:
        return
    move = agent["move"]
    where = "passes" if move == "pass" else f"plays {move[0]} {move[1]}"
    print(f"\n Agent {where}  ({agent['why']})")
    if agent["breakdown"]:
        parts = [f"{name} {value:+g}" for name, value in agent["breakdown"].items() if value]
        print(f"   reward {agent['total']:+g}: " + (", ".join(parts) or "all zero"))


def show_result(state):
    score = state["score"]
    print(f"\n Game over.  Black {score[BLACK]}  White {score[WHITE]} (incl. komi)")
    you_won = state["winner"] == state["human"]
    print(f" {NAMES[state['winner']]} wins. " + ("You win!" if you_won else "The agent wins."))


def parse_move(text):
    """'4 4' or '4,4' -> (4, 4); anything else -> None."""
    parts = text.replace(",", " ").split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    return (int(parts[0]), int(parts[1]))


def main():
    parser = argparse.ArgumentParser(description="Play 9x9 Go against the reward-function agent.")
    parser.add_argument("--color", choices=["B", "W"], default="B", help="your color (default B)")
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="aggressive")
    parser.add_argument("--seed", type=int, default=None, help="make the agent's tie-breaks repeatable")
    args = parser.parse_args()

    session = GameSession(args.color, args.strategy, args.seed)
    print(f" You are {NAMES[session.human]}. Agent strategy: {session.strategy}.")
    print(" Enter 'row col' (e.g. 4 4), 'pass', 'hint', or 'quit'.")

    while True:
        state = session.state()
        show_board(state)
        show_agent_move(state)
        if state["message"]:
            print(f" {state['message']}")
        if state["game_over"]:
            show_result(state)
            return

        try:
            text = input(f"\n {NAMES[session.human]} > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if text in ("quit", "q", "exit"):
            return
        if text == "hint":
            tips = [f"{m[0]} {m[1]} ({reward.total:+g})" for m, reward in session.hints()]
            session.message = "Agent's top picks for you: " + ", ".join(tips)
            continue
        if text in ("pass", "p"):
            session.human_move("pass")
            continue

        move = parse_move(text)
        if move is None:
            session.message = "Enter 'row col' like 4 4, or pass / hint / quit."
            continue
        session.human_move(move)


if __name__ == "__main__":
    main()
