# =========================================================
# Local web front end: play against the agent in the browser.
#
#   python3 server.py            # then open http://localhost:8000
#   python3 server.py --port 8080
#
# Standard library only. One game at a time, kept in memory.
#
# API (JSON):
#   GET  /api/state                         -> game state
#   POST /api/new   {"color": "B", "strategy": "aggressive"}
#   POST /api/move  {"row": 4, "col": 4}  or  {"pass": true}
#   GET  /api/hint                          -> agent's top 3 moves for you
# =========================================================

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from session import GameSession
from strategies import STRATEGIES

INDEX = Path(__file__).parent / "web" / "index.html"

session = GameSession()
lock = threading.Lock()


def state_payload():
    state = session.state()
    state["strategies"] = sorted(STRATEGIES)
    return state


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_body(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            with lock:
                self.send_json(200, state_payload())
        elif self.path == "/api/hint":
            with lock:
                hints = [{"move": move, "total": reward.total, "breakdown": reward.breakdown}
                         for move, reward in session.hints()]
            self.send_json(200, {"hints": hints})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        global session
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "body must be JSON"})

        with lock:
            if self.path == "/api/new":
                try:
                    session = GameSession(data.get("color", "B"), data.get("strategy", "aggressive"))
                except ValueError as err:
                    return self.send_json(400, {"error": str(err)})
            elif self.path == "/api/move":
                if data.get("pass"):
                    session.human_move("pass")
                else:
                    try:
                        move = (int(data["row"]), int(data["col"]))
                    except (KeyError, TypeError, ValueError):
                        return self.send_json(400, {"error": "send row and col, or pass"})
                    session.human_move(move)
            else:
                return self.send_json(404, {"error": "not found"})
            self.send_json(200, state_payload())

    def send_json(self, status, payload):
        self.send_body(status, json.dumps(payload).encode(), "application/json")

    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass    # keep the terminal quiet


def main():
    parser = argparse.ArgumentParser(description="Play Go against the agent in your browser.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Go server running: open http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
