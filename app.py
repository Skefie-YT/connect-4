from __future__ import annotations

import threading
from flask import Flask, jsonify, render_template, request

from engine import Bitboard, Connect4AI, HEIGHT, WIDTH
from engine.bitboard import has_won

app = Flask(__name__)
_thread_local = threading.local()


def get_ai() -> Connect4AI:
    if not hasattr(_thread_local, "ai"):
        _thread_local.ai = Connect4AI()
    return _thread_local.ai


def _validate_grid(grid: object) -> list[list[int]] | None:
    if not isinstance(grid, list) or len(grid) != HEIGHT:
        return None
    cleaned: list[list[int]] = []
    for row in grid:
        if not isinstance(row, list) or len(row) != WIDTH:
            return None
        cleaned_row: list[int] = []
        for cell in row:
            if cell not in (0, 1, 2):
                return None
            cleaned_row.append(int(cell))
        cleaned.append(cleaned_row)
    return cleaned


def _drop_row(grid: list[list[int]], col: int) -> int:
    for r in range(HEIGHT - 1, -1, -1):
        if grid[r][col] == 0:
            return r
    return -1


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/move", methods=["POST"])
def api_move():
    data = request.get_json(silent=True) or {}
    grid = _validate_grid(data.get("board"))
    if grid is None:
        return jsonify({"error": "Invalid board format"}), 400

    ai_player = data.get("ai_player", 2)
    if ai_player not in (1, 2):
        return jsonify({"error": "Invalid ai_player"}), 400

    difficulty = str(data.get("difficulty", "unbeatable")).lower()
    if difficulty not in Connect4AI.DIFFICULTY_SETTINGS:
        difficulty = "unbeatable"

    human_player = 2 if ai_player == 1 else 1
    board = Bitboard.from_grid(grid, current_player=ai_player)

    # Check if human already won before AI moves
    human_pos = board.position ^ board.mask
    if has_won(human_pos):
        win_line = board.winning_line(human_pos)
        return jsonify({
            "col": None,
            "row": None,
            "winner": human_player,
            "winning_line": win_line,
            "is_draw": False,
        })

    if board.moves >= WIDTH * HEIGHT:
        return jsonify({
            "col": None,
            "row": None,
            "winner": None,
            "winning_line": None,
            "is_draw": True,
        })

    ai = get_ai()
    result = ai.choose_move(board, difficulty=difficulty)
    col = result.col
    row = _drop_row(grid, col)
    if row == -1:
        return jsonify({"error": "Selected column is full"}), 500

    grid[row][col] = ai_player
    after_board = Bitboard.from_grid(grid, current_player=human_player)
    ai_pos = after_board.position ^ after_board.mask

    winner = None
    winning_line = None
    is_draw = False

    if has_won(ai_pos):
        winner = ai_player
        winning_line = after_board.winning_line(ai_pos)
    elif after_board.moves >= WIDTH * HEIGHT:
        is_draw = True

    return jsonify({
        "col": col,
        "row": row,
        "winner": winner,
        "winning_line": winning_line,
        "is_draw": is_draw,
        "stats": {
            "depth": result.depth,
            "nodes": result.nodes,
            "elapsed_ms": round(result.elapsed_ms, 1),
            "score": result.score,
        },
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
