# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Goal

Build a 9x9 Go solver that **beats a random player** (computational economics class project), and let the user play against it through a front end. Strength comes from layering scoring on top of the rules engine. Done so far: the "aggressive" reward function and a greedy agent, which won 79/80 games against random. Still to come: influence/liberty evaluation and Monte Carlo search. The yardstick for every change is win rate against random play over many games.

## Setup

- Code lives in plain modules, layered bottom to top:
  - `go_engine.py`: the rules.
  - `reward.py` + `strategies.py`: move scoring and its weights config.
  - `agent.py`: the greedy `choose_move`.
  - `session.py`: one human-vs-agent game.
  - `play.py`: terminal front end.
  - `server.py` + `web/index.html`: browser front end.

  `GOsolver.ipynb` holds notes and driver cells and imports the modules. Everything uses the standard library only, plus pytest for tests.
- pytest is installed in a project venv: `.venv/` (created with `python3 -m venv .venv && .venv/bin/pip install pytest`). Jupyter is not installed locally.
- In Colab the notebook's first code cell `git clone`s `https://github.com/dereka-code/GOsolver.git`, so module changes must be pushed before Colab sees them.
- Edit notebook cells with the NotebookEdit tool. The cells have no ids, so check placement afterwards by listing cells with `json`.

## How to run things

```bash
.venv/bin/pytest                                  # all tests (pytest.ini sets pythonpath=. and testpaths=tests)
.venv/bin/pytest tests/test_reward.py -k capture  # a single test or group

python3 play.py [--color W] [--strategy aggressive] [--seed 1]   # play the agent in the terminal
python3 server.py [--port 8000]                                  # play in the browser at http://localhost:8000
```

`play.py` takes `row col`, `pass`, `hint` or `quit` and can be smoke-tested by piping input: `printf '4 4\nquit\n' | python3 play.py --seed 1`. To test the server, start it in the background on a spare port, `curl` the API, then `pkill -f "server.py --port <port>"`.

Run the notebook's code cells headlessly (no Jupyter needed):

```bash
.venv/bin/python -c "
import json
nb = json.load(open('GOsolver.ipynb'))
code = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
exec('\n'.join(code[0:3] + [code[4]]))
"
```

`code[i]` indexes **code cells only**: `0` import modules, `1` notebook rule tests, `2` random playouts (~190 games/sec), `3` interactive hand play (calls `input()`; never run it headlessly), `4` reward breakdown demo, `5`–`6` Phase 2/3 stubs. Update this list when adding code cells.

## What's in the notebook

| Cell(s) | Type | Contents |
|---|---|---|
| 0–5 | markdown | Strategy notes: heatmap/influence ideas, board symmetry, Connect 4 reward-function lecture, the "Aggressive" 9x9 strategy |
| 6 | markdown | The original reward-function spec |
| 7 | markdown | Changelog for the engine rewrite |
| 8 | code | Imports `go_engine` (cloning the repo first in Colab) |
| 9 | code | Rule tests (plain `assert`s; duplicated as pytest in `tests/test_engine.py`) |
| 10 | code | `random_playout` + 200 random games: the random baseline and a speed check |
| 11 | code | Interactive hand play |
| 12–13 | markdown + code | Reward function summary + breakdown for three example moves |
| 14–15 | code | "Phase 2: Solver" (notes only) and "Phase 3: Monte Carlo" stubs |

## How it works

### Engine (`go_engine.py`)
- Board is `self.board[row][col]` holding `"."`, `"B"`, `"W"` (`EMPTY`, `BLACK`, `WHITE`). Coordinates are 0-indexed `(row, col)` tuples. Default 9x9, komi 7.5, Black moves first.
- Neighbor and diagonal tables are precomputed once per game. `get_group_and_liberties` gets a group and its liberties in one flood fill. Use these in hot paths.
- `play_move(row, col)` returns a `MoveResult`: truthy if legal, `.reason` for illegal moves (`"suicide"`, `"ko"`, `"point already occupied"`, `"outside the board"`), and `.captured` listing captured stones. Illegal moves are undone in place.
- Ko: a move may not recreate `previous_state`. `GoGame(superko=True)` enables positional superko. `copy()` shares `history` unless superko is on.
- Helpers: `copy()`, `is_legal()`, `legal_moves()`, `is_in_atari`, `groups_in_atari`, `is_eye`, `count_eyes`, `has_two_eyes`, `all_groups()`, `get_group`, `get_liberties`.
- `pass_turn()`; two passes end the game. `score()` / `winner()` use area scoring plus komi.
- The engine never prints; keep output in `print_board()` and driver cells.

### Reward (`reward.py` + `strategies.py`)
- `compute_reward(board, move, color, strategy="aggressive")`:
  - `board` is a `GoGame` and is never mutated (the function works on a `copy()` with `current_player = color`, so either color can be scored).
  - `move` is `(row, col)` or `"pass"`/`None`.
  - `strategy` is a name in `STRATEGIES` or a config dict.
- It returns a `RewardResult` with `.total`, `.breakdown` (rule name → weighted value), `.illegal_reason`, and `.legal`. It also unpacks: `total, breakdown = compute_reward(...)`.
- Illegal moves return the strategy's `"illegal_move"` value (default `-inf`) with an empty breakdown and a reason.
- Rules are small functions registered with `@rule("name")`. Each takes `(ctx, params)`, where `ctx` is a `MoveContext` with `before`, `after`, `point`, `color`, and `result`, and returns a **raw** value (a count or 1.0/0.0). `compute_reward` multiplies by `weight`. `params` is that rule's config entry, so extra keys like `include_corners` act as per-rule settings.
- Rules skip passes unless registered with `on_pass=True` (only `terminal`). Disabled rules and rules missing from a strategy are left out of the breakdown. Unknown rule or strategy names raise `ValueError`.
- **To add a rule:** write a function in `reward.py` with `@rule("name")`, add `"name": {"enabled": True, "weight": ...}` to a strategy, and add a test. **To add a strategy:** copy a block in `strategies.py`. Weights only ever change in `strategies.py`.

### Agent (`agent.py`)
- `rank_moves(game, color, strategy, rng)` scores every **candidate** move (legal and not filling one of `color`'s own eyes), shuffling before a stable sort so ties break randomly. It returns `(move, RewardResult)` pairs, best first.
- `decide(...)` returns a `Decision(move, reward, why)`. It passes only if the opponent just passed and `color` is ahead on `score()` (which ends the game as a win), or if no candidates remain. Otherwise it plays the top-ranked move. `choose_move(...)` is just `decide(...).move`.
- `play(game, move)` applies `(row, col)` or `"pass"` for the current player.

### Front ends (`session.py`, `play.py`, `server.py`, `web/index.html`)
- `GameSession(human_color, strategy, seed)` owns one `GoGame`.
  - `human_move(move)` applies the human's move, then the agent's reply. It returns False and sets `.message` for an illegal move, a move out of turn, or a move after the game is over.
  - The agent opens if the human plays White.
  - `hints()` gives the agent's top 3 moves for the human.
  - `state()` is a JSON-ready dict: board, turn, captures, last move, the agent's move with its reward breakdown, score and winner.

  **Both front ends go through `GameSession`**, so put game-flow changes there, not in the UIs.
- `server.py` uses only `http.server`, listens on 127.0.0.1, and keeps one global session behind a lock. Endpoints:
  - `GET /` serves the page.
  - `GET /api/state` returns the game state.
  - `POST /api/new {color, strategy}` starts a new game.
  - `POST /api/move {row, col}` or `{pass: true}` plays a move.
  - `GET /api/hint` returns the hints.

  Every POST returns `state()` plus a `strategies` list.
- `web/index.html` is a single file with inline CSS and JS:
  - The SVG board is drawn from `state.board`, with hover ghost stones, a last-move ring and numbered hint markers.
  - A side panel shows the status, the score, the agent's breakdown and a new-game form.
  - Colors are CSS variables on `:root`, with a dark-mode override.
- Headless Chrome (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=new --screenshot=...`) works for visual checks. Its viewport can't go below 500px, so a narrower `--window-size` crops the screenshot instead of narrowing the layout.

### Tests
- `tests/conftest.py` provides a `board` fixture: `board(rows, to_move=BLACK)` builds a game from strings. Missing rows and columns are empty, so small corner positions need only a few short strings.
- `tests/test_agent.py` covers the agent and `GameSession`, including a seeded 6-game "beats random" check (needs at least 5 wins).
- `tests/test_reward.py` has a `raw(game, move, rule, color=BLACK, **params)` helper that runs a single rule at weight 1, to check raw values in isolation.

## "Aggressive" strategy (decisions settled with the user)

| Rule | Raw value | Weight |
|---|---|---|
| `center` | 1.0 at (4,4) → 0.0 at corners (Manhattan) | 10 |
| `capture` | stones captured | 100 |
| `liberty_connection` | 1 if the move touches an enemy stone **and** an own stone (checked on the board before the move) | 60 |
| `two_eyes` | 1 if the new stone's group now has two eyes and no group it joined already had them | 30 |
| `corner` | 1 on corner points | −50 |
| `edge` | 1 on edge points; corners excluded (`include_corners: False`) | −20 |
| `terminal` | +1 win / −1 loss on the game-ending pass (win/loss hook) | 1000, **disabled** |

- Captures rank above liberty+connection: one stone (100) beats 60. A capture next to an own stone earns both.
- Corners get only the corner penalty, not the edge penalty too.
- Eye detection is the engine's single-point heuristic, so `two_eyes` misses bigger multi-point eyes.

## Next steps

1. Use the reward or an influence measure inside Monte Carlo playouts (Phase 3), and compare the result against the greedy agent, not just against random.
2. Use board symmetry (cell 3 notes) to cut the search.
3. Add more strategies to `strategies.py`. They show up automatically in the web page's strategy dropdown and in `play.py --strategy`.
